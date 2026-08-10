"""pipeline.py imports neither cv2 nor ultralytics, so this whole module
runs in CI on every push. Fakes stand in for cameras and the detector.

A note on FakeFrameRead timestamps: `t` must be anchored to real
time.monotonic() (not a literal small float like 0.0) because pipeline.py's
staleness check compares a real time.monotonic() "now" against `read.t`,
exactly as production does against camera.py's real decode timestamps. A
literal 0.0 would look tens of thousands of seconds old on any machine with
nonzero uptime and get filtered as stale before ever reaching the detector.
"""

import time

import config
from pipeline import AccumulatorRegistry, InferencePipeline, target_fps

BOX = (100.0, 100.0, 200.0, 200.0)


class FakeFrameRead:
    def __init__(self, t, segment_id, frame="FRAME"):
        self.frame = frame
        self.t = t
        self.segment_id = segment_id


class FakeCamera:
    """Stands in for CameraStream. `reads` is consumed one per tick."""

    def __init__(self, camera_id, reads=None, *, is_paused=False):
        self.camera_id = camera_id
        self.channel_id = camera_id
        self.reads = list(reads or [])
        self.is_paused = is_paused
        self.paused_calls = 0
        self.error_code = None
        self.error_message = None
        self.segment_id = 0

    def read(self):
        return self.reads.pop(0) if self.reads else None

    def pause(self):
        self.is_paused = True
        self.paused_calls += 1


class FakeDetection:
    def __init__(self, boxes, confs):
        self.boxes = boxes
        self.confs = confs


class FakeDetector:
    """Returns a steady detection for every frame. `fail_on` makes the
    batched call raise unless the batch is exactly one frame belonging to a
    different camera — used to test isolation."""

    def __init__(self, conf=0.6, fail_for_frame=None):
        self.conf = conf
        self.fail_for_frame = fail_for_frame
        self.batch_sizes = []

    def predict_batch(self, frames):
        self.batch_sizes.append(len(frames))
        if self.fail_for_frame is not None and self.fail_for_frame in frames:
            raise RuntimeError("CUDA error: injected")
        return [FakeDetection([BOX], [self.conf]) for _ in frames]


def _collect(events):
    return lambda camera, frame, event: events.append((camera.camera_id, event))


# --- AccumulatorRegistry -------------------------------------------------


def test_each_camera_gets_its_own_accumulator():
    """SPEC.md section 6 measured this directly: feed a steady detection to a shared
    instance until it fires, then feed an IDENTICAL sequence, and the second
    produces ZERO events. The fired region is retained forever and absorbs
    the new detections, so no new region can form."""
    registry = AccumulatorRegistry()
    cam_a, cam_b = FakeCamera(1), FakeCamera(2)
    acc_a = registry.resolve(1, cam_a, 0)
    acc_b = registry.resolve(2, cam_b, 0)
    assert acc_a is not acc_b


def test_the_same_camera_and_segment_reuses_its_accumulator():
    registry = AccumulatorRegistry()
    cam = FakeCamera(1)
    assert registry.resolve(1, cam, 0) is registry.resolve(1, cam, 0)


def test_a_segment_bump_resets_that_camera():
    """Covers all three reset seams at once — reconnect, resume, restart —
    because each one increments segment_id."""
    registry = AccumulatorRegistry()
    cam = FakeCamera(1)
    first = registry.resolve(1, cam, 0)
    first.update(0.0, [BOX], [0.6])
    # A single update always has dt=0 (no _prev_t yet), so its score is
    # conf*0=0 and accumulate.py's own end-of-update() pruning line drops
    # it immediately. A second call with dt>0 is needed for the region to
    # survive so this test can check what a segment bump does to it.
    first.update(1.0, [BOX], [0.6])
    assert first.regions

    second = registry.resolve(1, cam, 1)
    assert second.regions == []
    assert second._prev_t is None


def test_a_replaced_stream_object_resets_even_if_the_counter_collides():
    """A REAPPLY_CONFIG restart builds a new CameraStream starting at
    segment 0. Without the identity check that would look unchanged."""
    registry = AccumulatorRegistry()
    old = FakeCamera(1)
    acc = registry.resolve(1, old, 0)
    acc.update(0.0, [BOX], [0.6])

    new = FakeCamera(1)
    assert registry.resolve(1, new, 0).regions == []


def test_pruning_drops_accumulators_for_stopped_cameras():
    """Without this a STOP leaks an accumulator for every camera ever run."""
    registry = AccumulatorRegistry()
    registry.resolve(1, FakeCamera(1), 0)
    registry.resolve(2, FakeCamera(2), 0)
    registry.prune({1})
    assert set(registry.camera_ids()) == {1}


# --- target_fps ----------------------------------------------------------


def test_within_capacity_runs_at_the_top_of_the_band():
    assert target_fps(capacity=8, active_count=4) == config.FPS_BAND_MAX


def test_at_exactly_capacity_still_runs_at_the_top_of_the_band():
    assert target_fps(capacity=4, active_count=4) == config.FPS_BAND_MAX


def test_over_capacity_drops_to_the_band_floor():
    assert target_fps(capacity=2, active_count=6) == config.FPS_BAND_MIN


def test_no_active_cameras_is_not_a_division_by_zero():
    assert target_fps(capacity=4, active_count=0) == config.FPS_BAND_MAX


# --- InferencePipeline ---------------------------------------------------


def test_paused_cameras_are_excluded_from_the_batch():
    """The self-blindfold must actually stop GPU work for that camera."""
    detector = FakeDetector()
    now = time.monotonic()
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(now, 0)]),
        2: FakeCamera(2, [FakeFrameRead(now, 0)], is_paused=True),
    }
    pipeline = InferencePipeline(cameras, detector, lambda *a: None, capacity=8)
    pipeline.tick_once()
    assert detector.batch_sizes == [1]


def test_a_camera_with_no_new_frame_is_skipped():
    detector = FakeDetector()
    cameras = {1: FakeCamera(1, [])}
    pipeline = InferencePipeline(cameras, detector, lambda *a: None, capacity=8)
    pipeline.tick_once()
    assert detector.batch_sizes == []


def test_a_stale_frame_is_skipped():
    """A stream can stay connected while delivering frames far too slowly.
    Treating an old frame as current would silently pollute the scorecard."""
    detector = FakeDetector()
    stale_t = time.monotonic() - config.MAX_FRAME_AGE_SECONDS * 10
    cameras = {1: FakeCamera(1, [FakeFrameRead(stale_t, 0)])}
    pipeline = InferencePipeline(cameras, detector, lambda *a: None, capacity=8)
    pipeline.tick_once()
    assert detector.batch_sizes == []


def test_an_event_pauses_the_camera_before_the_callback_runs():
    """The self-blindfold ordering: pause first, then any disk or network
    work. Alert-handling code must preserve this."""
    seen = []
    cameras = {1: FakeCamera(1)}
    cam = cameras[1]

    def on_event(camera, frame, event):
        seen.append(camera.is_paused)

    pipeline = InferencePipeline(cameras, FakeDetector(), on_event, capacity=8)
    t0 = time.monotonic()
    for i in range(120):
        cam.reads.append(FakeFrameRead(t0 + i * (1 / 30), 0))
        pipeline.tick_once()
        if seen:
            break

    assert seen == [True]
    assert cam.paused_calls == 1


def test_only_one_incident_is_emitted_per_camera_per_tick():
    """On a clip, three events mean three distinct places. In a live system
    the camera pauses on the first, so one incident per pause cycle is the
    correct operator-facing semantics."""
    events = []
    cam = FakeCamera(1)
    cameras = {1: cam}

    class TwoRegionDetector:
        def predict_batch(self, frames):
            return [
                FakeDetection(
                    [(0.0, 0.0, 10.0, 10.0), (500.0, 500.0, 600.0, 600.0)],
                    [0.5, 0.9],
                )
                for _ in frames
            ]

    pipeline = InferencePipeline(
        cameras, TwoRegionDetector(), _collect(events), capacity=8
    )
    t0 = time.monotonic()
    for i in range(120):
        cam.reads.append(FakeFrameRead(t0 + i * (1 / 30), 0))
        pipeline.tick_once()
        if events:
            break

    assert len(events) == 1
    assert events[0][1].peak_conf == 0.9  # the highest-confidence region wins


def test_a_failing_batch_isolates_the_offending_camera():
    """TC-R-302's guarantee, delivered without per-camera threads: one
    camera's fatal error must not silence the others."""
    events = []
    bad_frame = "BAD"
    now = time.monotonic()
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(now, 0, frame=bad_frame)]),
        2: FakeCamera(2, [FakeFrameRead(now, 0, frame="GOOD")]),
    }
    detector = FakeDetector(fail_for_frame=bad_frame)
    pipeline = InferencePipeline(cameras, detector, _collect(events), capacity=8)

    pipeline.tick_once()

    assert cameras[1].error_code == "INFERENCE_FAILED"
    assert cameras[2].error_code is None


def test_an_isolated_camera_is_excluded_from_later_batches():
    bad_frame = "BAD"
    now = time.monotonic()
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(now, 0, frame=bad_frame)]),
        2: FakeCamera(2, [FakeFrameRead(now, 0, frame="GOOD")]),
    }
    detector = FakeDetector(fail_for_frame=bad_frame)
    pipeline = InferencePipeline(cameras, detector, lambda *a: None, capacity=8)
    pipeline.tick_once()

    now2 = time.monotonic()
    cameras[1].reads.append(FakeFrameRead(now2, 0, frame=bad_frame))
    cameras[2].reads.append(FakeFrameRead(now2, 0, frame="GOOD"))
    detector.batch_sizes.clear()
    pipeline.tick_once()

    assert detector.batch_sizes == [1]


def test_a_transient_batch_failure_errors_nobody():
    """If the individual re-runs all succeed, the failure was transient.
    Marking a camera errored for a one-off would be wrong."""
    calls = {"n": 0}

    class FlakyDetector:
        def predict_batch(self, frames):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient")
            return [FakeDetection([BOX], [0.6]) for _ in frames]

    now = time.monotonic()
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(now, 0)]),
        2: FakeCamera(2, [FakeFrameRead(now, 0)]),
    }
    pipeline = InferencePipeline(cameras, FlakyDetector(), lambda *a: None, capacity=8)
    pipeline.tick_once()

    assert cameras[1].error_code is None
    assert cameras[2].error_code is None


def test_over_capacity_marks_the_run_degraded_without_dropping_cameras():
    """The backend is authoritative over WHICH cameras run. An engine
    silently ignoring an assigned camera would be an invisible blind spot."""
    detector = FakeDetector()
    now = time.monotonic()
    cameras = {i: FakeCamera(i, [FakeFrameRead(now, 0)]) for i in range(1, 7)}
    pipeline = InferencePipeline(cameras, detector, lambda *a: None, capacity=2)
    pipeline.tick_once()

    assert pipeline.degraded is True
    assert detector.batch_sizes == [6]


def test_accumulators_are_pruned_when_a_camera_is_stopped():
    detector = FakeDetector()
    now = time.monotonic()
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(now, 0)]),
        2: FakeCamera(2, [FakeFrameRead(now, 0)]),
    }
    pipeline = InferencePipeline(cameras, detector, lambda *a: None, capacity=8)
    pipeline.tick_once()
    del cameras[2]
    cameras[1].reads.append(FakeFrameRead(time.monotonic(), 0))
    pipeline.tick_once()

    assert set(pipeline.registry.camera_ids()) == {1}
