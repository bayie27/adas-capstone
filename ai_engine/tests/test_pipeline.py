"""pipeline.py imports neither cv2 nor ultralytics, so this whole module
runs in CI on every push. Fakes stand in for cameras and the detector.

A note on FakeFrameRead timestamps: `t` must be anchored to real
time.monotonic() (not a literal small float like 0.0) because pipeline.py's
staleness check compares a real time.monotonic() "now" against `read.t`,
exactly as production does against camera.py's real decode timestamps. A
literal 0.0 would look tens of thousands of seconds old on any machine with
nonzero uptime and get filtered as stale before ever reaching the detector.
"""

import math
import time

import config
import pytest
from pipeline import AccumulatorRegistry, InferencePipeline

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
        self.inference_completions = 0
        self.processing_error_code = None
        self.processing_error_message = None
        self.segment_id = 0

    def read(self):
        return self.reads.pop(0) if self.reads else None

    def pause(self):
        self.is_paused = True
        self.paused_calls += 1

    def record_inference(self):
        self.inference_completions += 1

    def record_inference_failure(self, code, message):
        self.processing_error_code = code
        self.processing_error_message = message


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


class CameraTwoFailsDetector(FakeDetector):
    def __init__(self):
        super().__init__(fail_for_frame=2)


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


def test_a_long_gap_between_frames_resets_that_camera():
    """A stalled stream must not be credited with evidence nobody observed.

    accumulate.py creates a NEW region with `score = conf * dt` and checks it
    for firing on that same frame, so a frame arriving after a long stall is
    born above threshold and fires with age_s=0.0 — zero corroboration. Found
    live on 2026-08-11: "[ALERT] Channel 1: accident detected (peak 0.54, 0.0s
    of evidence)".

    Neither existing guard covers it. MAX_FRAME_AGE_SECONDS checks a frame's
    freshness, and a frame decoded just now after a five-second stall is fresh
    while still carrying dt=5s. segment_id covers reconnect and resume; a
    stream that stalls WITHOUT dropping keeps its segment.

    The gap is worst where it is most dangerous: the size needed shrinks as
    confidence rises (1.15s at conf 0.869), and this project's false positives
    score HIGHER than genuine crashes. Left unguarded it preferentially fires
    on false alarms, and hardest when the machine is already struggling.

    Fixed here rather than in accumulate.py: the frozen reference behaves
    identically, so changing it would break the parity gate.
    """
    registry = AccumulatorRegistry()
    cam = FakeCamera(1)
    first = registry.resolve(1, cam, 0, t=0.0)
    first.update(0.0, [BOX], [0.6])
    first.update(0.1, [BOX], [0.6])
    assert first.regions

    gapped = registry.resolve(1, cam, 0, t=0.1 + config.MAX_FRAME_GAP_SECONDS + 0.01)

    assert gapped.regions == []
    assert gapped._prev_t is None


def test_a_normal_frame_interval_keeps_accumulating():
    """The clamp must not fire on ordinary cadence, or it would throw away
    real evidence every tick and nothing could ever accumulate."""
    registry = AccumulatorRegistry()
    cam = FakeCamera(1)
    first = registry.resolve(1, cam, 0, t=0.0)
    first.update(0.0, [BOX], [0.6])
    first.update(0.1, [BOX], [0.6])

    same = registry.resolve(1, cam, 0, t=0.2)

    assert same is first
    assert same.regions


def test_a_gap_on_one_camera_does_not_reset_another():
    """Cameras stall independently; a stalled feed must not discard a
    healthy camera's accumulated evidence."""
    registry = AccumulatorRegistry()
    cam_a, cam_b = FakeCamera(1), FakeCamera(2)
    registry.resolve(1, cam_a, 0, t=0.0)
    acc_b = registry.resolve(2, cam_b, 0, t=0.0)
    acc_b.update(0.0, [BOX], [0.6])
    acc_b.update(0.1, [BOX], [0.6])

    registry.resolve(1, cam_a, 0, t=config.MAX_FRAME_GAP_SECONDS + 1.0)

    assert registry.resolve(2, cam_b, 0, t=0.2) is acc_b
    assert acc_b.regions


def test_the_gap_clamp_is_smaller_than_the_smallest_dangerous_gap():
    """The clamp only works if it trips before a single frame can fire.

    A new region is born with conf * dt, so the gap that fires instantly is
    threshold / conf. The worst measured false positive scores 0.869, needing
    only 1.0/0.869 = 1.15s. The clamp must sit below that, and above ordinary
    cadence (66.7ms at 15 FPS, 100ms at 10 FPS) or it would reset constantly.
    """
    worst_false_positive_conf = 0.869
    smallest_dangerous_gap = config.ACC_THRESHOLD / worst_false_positive_conf
    # Bound to a local: Ruff's SIM300 treats any UPPERCASE attribute as a
    # literal and flags the comparison whichever side it is written on.
    clamp = config.MAX_FRAME_GAP_SECONDS

    assert clamp < smallest_dangerous_gap
    assert clamp > 1.0 / config.FPS_BAND_MIN


def test_pruning_drops_accumulators_for_stopped_cameras():
    """Without this a STOP leaks an accumulator for every camera ever run."""
    registry = AccumulatorRegistry()
    registry.resolve(1, FakeCamera(1), 0)
    registry.resolve(2, FakeCamera(2), 0)
    registry.prune({1})
    assert set(registry.camera_ids()) == {1}


# --- fixed target --------------------------------------------------------


def test_pipeline_defaults_to_the_top_of_the_supported_band():
    pipeline = InferencePipeline({}, FakeDetector(), lambda *args: None)
    assert pipeline.target_fps == config.FPS_BAND_MAX


def test_scheduler_period_does_not_change_with_camera_count(monkeypatch):
    cameras = {index: FakeCamera(index) for index in range(1, 7)}
    pipeline = InferencePipeline(cameras, FakeDetector(), lambda *args: None)
    assert pipeline.period_seconds == pytest.approx(1.0 / 15.0)


@pytest.mark.parametrize("target_fps", [0.0, -1.0])
def test_pipeline_rejects_non_positive_target_fps(target_fps):
    with pytest.raises(ValueError, match="target_fps must be positive"):
        InferencePipeline({}, FakeDetector(), lambda *args: None, target_fps=target_fps)


def test_successful_batch_records_one_completion_per_inferred_camera():
    now = time.monotonic()
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(now, 0, frame=1)]),
        2: FakeCamera(2, [FakeFrameRead(now, 0, frame=2)]),
    }
    pipeline = InferencePipeline(cameras, FakeDetector(), lambda *args: None)

    pipeline.tick_once()

    assert cameras[1].inference_completions == 1
    assert cameras[2].inference_completions == 1


def test_isolated_failure_is_not_recorded_as_a_completion():
    now = time.monotonic()
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(now, 0, frame=1)]),
        2: FakeCamera(2, [FakeFrameRead(now, 0, frame=2)]),
    }
    pipeline = InferencePipeline(cameras, CameraTwoFailsDetector(), lambda *args: None)

    pipeline.tick_once()

    assert cameras[1].inference_completions == 1
    assert cameras[2].inference_completions == 0
    assert cameras[2].processing_error_code == "INFERENCE_FAILED"


# --- InferencePipeline ---------------------------------------------------


def test_paused_cameras_are_excluded_from_the_batch():
    """The self-blindfold must actually stop GPU work for that camera."""
    detector = FakeDetector()
    now = time.monotonic()
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(now, 0)]),
        2: FakeCamera(2, [FakeFrameRead(now, 0)], is_paused=True),
    }
    pipeline = InferencePipeline(cameras, detector, lambda *a: None)
    pipeline.tick_once()
    assert detector.batch_sizes == [1]


def test_a_camera_with_no_new_frame_is_skipped():
    detector = FakeDetector()
    cameras = {1: FakeCamera(1, [])}
    pipeline = InferencePipeline(cameras, detector, lambda *a: None)
    pipeline.tick_once()
    assert detector.batch_sizes == []


def test_a_stale_frame_is_skipped():
    """A stream can stay connected while delivering frames far too slowly.
    Treating an old frame as current would silently pollute the scorecard."""
    detector = FakeDetector()
    stale_t = time.monotonic() - config.MAX_FRAME_AGE_SECONDS * 10
    cameras = {1: FakeCamera(1, [FakeFrameRead(stale_t, 0)])}
    pipeline = InferencePipeline(cameras, detector, lambda *a: None)
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

    pipeline = InferencePipeline(cameras, FakeDetector(), on_event)
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

    pipeline = InferencePipeline(cameras, TwoRegionDetector(), _collect(events))
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
    pipeline = InferencePipeline(cameras, detector, _collect(events))

    pipeline.tick_once()

    assert cameras[1].processing_error_code == "INFERENCE_FAILED"
    assert cameras[2].processing_error_code is None


def test_an_isolated_camera_is_excluded_from_later_batches():
    bad_frame = "BAD"
    now = time.monotonic()
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(now, 0, frame=bad_frame)]),
        2: FakeCamera(2, [FakeFrameRead(now, 0, frame="GOOD")]),
    }
    detector = FakeDetector(fail_for_frame=bad_frame)
    pipeline = InferencePipeline(cameras, detector, lambda *a: None)
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
    pipeline = InferencePipeline(cameras, FlakyDetector(), lambda *a: None)
    pipeline.tick_once()

    assert cameras[1].processing_error_code is None
    assert cameras[2].processing_error_code is None


def test_a_stalled_camera_does_not_alert_from_a_single_frame():
    """The live failure, end to end.

    On 2026-08-11 a real run emitted "[ALERT] Channel 1: accident detected
    (peak 0.54, 0.0s of evidence)" — an alert from one frame, where the same
    clip's parity run records age_s=2.31. Two frames separated by more than the
    gap bound must produce no event at all, because nothing was observed in
    between to corroborate anything.
    """
    events = []
    cam = FakeCamera(1)
    pipeline = InferencePipeline({1: cam}, FakeDetector(conf=0.9), _collect(events))

    now = time.monotonic()
    cam.reads.append(FakeFrameRead(now, 0))
    pipeline.tick_once()
    # Long enough that conf*dt clears the threshold on its own: at conf 0.9 a
    # 1.12s gap alone scores 1.008 against a threshold of 1.0.
    cam.reads.append(FakeFrameRead(now + config.MAX_FRAME_GAP_SECONDS + 1.0, 0))
    pipeline.tick_once()

    assert events == []
    assert cam.paused_calls == 0


def test_accumulators_are_pruned_when_a_camera_is_stopped():
    detector = FakeDetector()
    now = time.monotonic()
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(now, 0)]),
        2: FakeCamera(2, [FakeFrameRead(now, 0)]),
    }
    pipeline = InferencePipeline(cameras, detector, lambda *a: None)
    pipeline.tick_once()
    del cameras[2]
    cameras[1].reads.append(FakeFrameRead(time.monotonic(), 0))
    pipeline.tick_once()

    assert set(pipeline.registry.camera_ids()) == {1}


def test_reported_latency_is_the_per_camera_share_of_the_batch():
    """Task 7's fix: TC-AI-401 budgets "strictly under 100 ms PER FRAME".
    Reporting whole-batch latency to every camera (the pre-Task-7 behaviour)
    overstates per-frame cost by exactly the camera count, and gets worse as
    cameras are added -- a criterion the system actually meets would then
    read as failing. Nothing else in this file reads inference_latency_ms
    or last_batch_latency_ms, so without this test that division is
    unprotected.
    """
    sleep_s = 0.05  # long enough to dominate scheduler/timer noise

    class SlowDetector:
        def predict_batch(self, frames):
            time.sleep(sleep_s)
            return [FakeDetection([BOX], [0.6]) for _ in frames]

    now = time.monotonic()
    camera_count = 4
    cameras = {
        i: FakeCamera(i, [FakeFrameRead(now, 0)]) for i in range(1, camera_count + 1)
    }
    pipeline = InferencePipeline(cameras, SlowDetector(), lambda *a: None)
    pipeline.tick_once()

    batch_ms = pipeline.last_batch_latency_ms
    assert batch_ms is not None
    # Sanity: the fake detector actually took measurable time, so a
    # regression that reports 0 or the raw sleep everywhere can't hide.
    assert batch_ms >= sleep_s * 1000 * 0.5

    for camera in cameras.values():
        # Both sides are derived from the SAME measured batch_ms, so this
        # is an exact relationship, not a wall-clock guess -- rel_tol=1e-9
        # only allows for float rounding, not for timing jitter. This is
        # what actually pins the division: under the reverted mutation
        # (per_camera = last_batch_latency_ms, no division) every camera
        # would report batch_ms instead of batch_ms / camera_count, and
        # this assertion fails outright.
        assert math.isclose(
            camera.inference_latency_ms, batch_ms / camera_count, rel_tol=1e-9
        )
        # Belt-and-suspenders, independent of the exact-ratio check above:
        # with 4 cameras sharing one batch, the per-camera figure must be
        # clearly below the whole-batch figure -- comfortably outside any
        # plausible timing noise.
        assert camera.inference_latency_ms < batch_ms * 0.5


def test_a_fully_failed_batch_leaves_no_stale_batch_latency():
    """_infer() clears last_batch_latency_ms as its first line, before the
    batched predict is even attempted, so a batch that raises can't leave a
    previous tick's timing sitting around to be misread as current."""

    class AlwaysFailingDetector:
        def predict_batch(self, frames):
            raise RuntimeError("CUDA error: injected")

    now = time.monotonic()
    cameras = {1: FakeCamera(1, [FakeFrameRead(now, 0)])}
    pipeline = InferencePipeline(cameras, AlwaysFailingDetector(), lambda *a: None)
    pipeline.tick_once()

    assert pipeline.last_batch_latency_ms is None
