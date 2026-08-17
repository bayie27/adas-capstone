"""runtime_bench.py is the PURE half of the closed-loop benchmark, so this
module runs in CI on every push against fakes.

There is deliberately NO `pytest.importorskip` here, unlike test_capacity.py.
The whole reason the bench is split across two modules is that CI has no `ai`
extra, and a skip would hide the regression it exists to catch: if cv2 or
ultralytics ever leaks into runtime_bench, these tests must fail loudly rather
than quietly stop running.
test_the_pure_module_imports_with_cv2_and_ultralytics_blocked pins that
directly, in a subprocess so it holds on a machine that HAS them installed.

Fakes follow test_pipeline.py's, including its note on timestamps: `t` is
anchored to real time.monotonic() because the staleness check in _collect
compares against a real "now".
"""

import subprocess
import sys
import textwrap
import time
from pathlib import Path

import config
import runtime_bench
from pipeline import target_fps
from runtime_bench import (
    FAILURE_CONTAMINATED,
    FAILURE_INFERENCE_FAILED,
    FAILURE_STARVED,
    FAILURE_STREAM_DROPPED,
    InstrumentedPipeline,
    RecordsHandover,
    RunSample,
    climb,
    evaluate,
    summarise,
)

AI_ENGINE_DIR = Path(__file__).resolve().parents[1]
BOX = (100.0, 100.0, 200.0, 200.0)


class FakeFrameRead:
    def __init__(self, t, segment_id, frame="FRAME"):
        self.frame = frame
        self.t = t
        self.segment_id = segment_id


class _BaseCamera:
    def __init__(self, camera_id, reads=None, *, is_paused=False, measured_fps=None):
        self.camera_id = camera_id
        self.channel_id = camera_id
        self.reads = list(reads or [])
        self.is_paused = is_paused
        self.error_code = None
        self.error_message = None
        self.segment_id = 0
        self.measured_fps = measured_fps

    def read(self):
        return self.reads.pop(0) if self.reads else None

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False
        self.segment_id += 1


class FakeCamera(RecordsHandover, _BaseCamera):
    """The mixin sits ahead of the base exactly as bench_sources puts it ahead
    of the real CameraStream, so both paths exercise the same handover code."""


class FakeDetection:
    def __init__(self, boxes, confs):
        self.boxes = boxes
        self.confs = confs


class FakeDetector:
    def __init__(self, conf=0.1):
        self.conf = conf

    def predict_batch(self, frames):
        return [FakeDetection([BOX], [self.conf]) for _ in frames]


def _sample(**overrides):
    base = dict(
        cameras=2,
        target_fps=15.0,
        window_seconds=10.0,
        achieved_fps_by_camera={1: 15.0, 2: 15.0},
        achieved_fps_min=15.0,
        achieved_fps_mean=15.0,
    )
    base.update(overrides)
    return RunSample(**base)


# --- the pass criterion --------------------------------------------------


def test_a_healthy_run_passes():
    passed, reason = evaluate(_sample())
    assert passed is True
    assert reason is None


def test_one_starved_camera_fails_the_run_even_though_the_mean_looks_fine():
    """THE central assertion of the criterion, and the one worth mutating.

    Seven cameras at 15 FPS and one at 2 average out to 13.4, which clears a
    mean-based check at any sane tolerance. The eighth operator's camera is
    nonetheless being sampled at a seventh of the required rate, which is
    invisible in every aggregate number. Swapping min for mean here is a silent
    change that would let this ship."""
    achieved = {i: 15.0 for i in range(1, 8)}
    achieved[8] = 2.0
    sample = _sample(
        cameras=8,
        achieved_fps_by_camera=achieved,
        achieved_fps_min=min(achieved.values()),
        achieved_fps_mean=sum(achieved.values()) / len(achieved),
    )

    assert sample.achieved_fps_mean > 13.0  # a mean-based check would pass
    passed, reason = evaluate(sample)
    assert passed is False
    assert reason == FAILURE_STARVED


def test_a_reconnect_fails_the_run_even_when_the_rate_looks_healthy():
    """A dropped stream lost coverage outright. A reconnect early in the window
    still leaves the remaining seconds averaging out fine, so the rate check
    alone would call this machine healthy at a camera count where it cannot
    actually hold the streams open."""
    passed, reason = evaluate(_sample(reconnects=1))
    assert passed is False
    assert reason == FAILURE_STREAM_DROPPED


def test_a_starved_run_with_events_is_reported_as_contaminated_not_as_capacity():
    """An event pauses the camera mid-window (the self-blindfold), depressing
    its achieved rate for a reason that has nothing to do with capacity.
    Recording that as a capacity limit would understate the machine and send
    the reader to the wrong fix; the right response is to re-run against the
    negative clip."""
    passed, reason = evaluate(
        _sample(
            achieved_fps_by_camera={1: 15.0, 2: 4.0}, achieved_fps_min=4.0, events=3
        )
    )
    assert passed is False
    assert reason == FAILURE_CONTAMINATED


def test_events_that_did_not_cost_the_rate_do_not_fail_the_run():
    """Firing an event is not itself a failure — only losing the frame rate is.
    A clip with a crash in it still measures fine if the pause was short."""
    passed, reason = evaluate(_sample(events=2))
    assert passed is True
    assert reason is None


def test_isolated_cameras_are_reported_as_inference_failure_not_as_capacity():
    """The loudest lie the bench could tell.

    When predict_batch raises, pipeline._infer isolates that camera and carries
    on, so it contributes nothing and its achieved rate is 0 — which every other
    check reads as the machine running out of capacity. It is not: the model
    refused the batch it was handed, and no amount of slower hardware explains
    it. Almost always a TensorRT engine built for a fixed batch, or a dynamic
    one whose maximum the climb has passed.
    """
    passed, reason = evaluate(
        _sample(
            achieved_fps_by_camera={1: 15.0, 2: 0.0}, achieved_fps_min=0.0, isolated=1
        )
    )
    assert passed is False
    assert reason == FAILURE_INFERENCE_FAILED


def test_an_inference_failure_stops_the_search_instead_of_walking_down():
    """Trying fewer cameras cannot fix a model that will not accept the batch,
    so every remaining count would fail identically at the cost of a full
    warm-up and window each. Stop, and mark the result as measuring nothing."""

    def measure(n):
        return _sample(
            cameras=n, passed=False, failure_reason=FAILURE_INFERENCE_FAILED, isolated=1
        )

    result = climb(measure, seed_prediction=20)

    assert result.aborted is True
    assert len(result.samples) == 1  # did not walk down
    assert result.capacity == 0


def test_an_ordinary_failure_does_not_abort_the_search():
    """Only the fatal reason short-circuits. A starved run at N is exactly the
    boundary the climb exists to find, so it must keep looking."""
    measure = FakeMeasure(true_capacity=2)
    result = climb(measure, seed_prediction=6)

    assert result.aborted is False
    assert result.capacity == 2


def test_a_run_that_collected_nothing_is_starved_not_passed():
    """Guards the empty case: no cameras reporting must never fall through to
    a vacuous min() and read as success."""
    passed, reason = evaluate(_sample(achieved_fps_by_camera={}, achieved_fps_min=0.0))
    assert passed is False
    assert reason == FAILURE_STARVED


def test_the_tolerance_allows_jitter_but_not_a_real_shortfall():
    at_tolerance = _sample(achieved_fps_by_camera={1: 14.25}, achieved_fps_min=14.25)
    below = _sample(achieved_fps_by_camera={1: 14.0}, achieved_fps_min=14.0)
    assert evaluate(at_tolerance)[0] is True
    assert evaluate(below)[0] is False


# --- the climb -----------------------------------------------------------


class FakeMeasure:
    """Passes for any count up to `true_capacity`. Records what it was asked."""

    def __init__(self, true_capacity, *, reconnect_above=None):
        self.true_capacity = true_capacity
        self.reconnect_above = reconnect_above
        self.asked = []

    def __call__(self, n):
        self.asked.append(n)
        passed = n <= self.true_capacity
        reason = None
        if not passed:
            reason = (
                FAILURE_STREAM_DROPPED
                if self.reconnect_above is not None and n > self.reconnect_above
                else FAILURE_STARVED
            )
        return _sample(cameras=n, passed=passed, failure_reason=reason)


def test_the_climb_starts_below_the_seed_prediction():
    """The safety property. The seed comes from the inference sweep, which
    measures 720p frames with no decode and no threads, so it runs ahead of
    reality. Starting under it is what stops an optimistic prediction from
    stepping over a camera count that would have failed."""
    measure = FakeMeasure(true_capacity=20)
    result = climb(measure, seed_prediction=10)

    assert result.started_at_cameras < 10
    assert measure.asked[0] < 10


def test_an_optimistic_seed_cannot_skip_past_a_failing_count():
    """The seed says 12; the machine actually carries 3. Every count from the
    starting point down to the answer must be measured, so the reported
    capacity is one that was OBSERVED to pass rather than inferred."""
    measure = FakeMeasure(true_capacity=3)
    result = climb(measure, seed_prediction=12)

    assert result.capacity == 3
    assert 3 in measure.asked
    assert max(measure.asked) <= 10  # never tried above the starting point


def test_a_wildly_optimistic_seed_walks_all_the_way_down():
    """On a CPU-only machine the seed can be several times the truth, so the
    walk-down has to reach 1 rather than give up after a step or two."""
    measure = FakeMeasure(true_capacity=1)
    result = climb(measure, seed_prediction=30)

    assert result.capacity == 1
    assert measure.asked[-1] == 1


def test_a_pessimistic_seed_still_climbs_up_to_the_real_answer():
    measure = FakeMeasure(true_capacity=9)
    result = climb(measure, seed_prediction=5)

    assert result.capacity == 9
    assert 10 in measure.asked  # stopped only after observing a failure


def test_a_machine_that_cannot_carry_one_camera_records_zero():
    """The honest answer for a machine that never keeps up, written as 0 rather
    than rounded up to 1 — matching how the inference sweep already reports it."""
    measure = FakeMeasure(true_capacity=0)
    result = climb(measure, seed_prediction=4)

    assert result.capacity == 0


def test_every_attempt_is_recorded_including_the_failure_that_stopped_it():
    """The trail is the evidence behind the number. Dropping the failing row
    would leave a capacity nobody can audit, and would hide WHY the climb
    stopped — which is the difference between 'too slow' and 'too many
    streams'."""
    measure = FakeMeasure(true_capacity=4, reconnect_above=4)
    result = climb(measure, seed_prediction=4)

    assert [s.cameras for s in result.samples] == measure.asked
    failures = [s for s in result.samples if not s.passed]
    assert failures and failures[-1].failure_reason == FAILURE_STREAM_DROPPED


def test_the_climb_respects_an_absolute_ceiling():
    """A machine that never fails must still terminate."""
    measure = FakeMeasure(true_capacity=10**6)
    result = climb(measure, seed_prediction=1, max_cameras=6)

    assert result.capacity == 6
    assert max(measure.asked) == 6


def test_running_out_of_ceiling_is_reported_as_a_floor_not_an_answer():
    """A capacity equal to the largest count attempted is "we stopped looking
    here". The sweep learned this twice — a grid ending at 8, then at 16, both
    saturated by real hardware and both reporting the ceiling as the result —
    which is why `_grid_limited` exists. The climb needs the same guard."""
    result = climb(FakeMeasure(true_capacity=10**6), seed_prediction=1, max_cameras=6)

    assert result.ceiling_bound is True
    assert result.aborted is False  # something WAS measured, it is just a floor


def test_a_climb_that_found_a_real_boundary_is_not_ceiling_bound():
    result = climb(FakeMeasure(true_capacity=3), seed_prediction=1, max_cameras=32)

    assert result.capacity == 3
    assert result.ceiling_bound is False


def test_an_engine_refusing_the_next_count_up_makes_the_answer_a_floor():
    """The realistic TensorRT case: an engine built dynamic to max batch N runs
    every count up to N and refuses N+1. Counts below it genuinely passed, so
    this is not an abort — but the MODEL decided where it stopped, not the
    machine, so the number is a floor and must say so."""

    def measure(n):
        if n <= 4:
            return _sample(cameras=n, passed=True)
        return _sample(
            cameras=n, passed=False, failure_reason=FAILURE_INFERENCE_FAILED, isolated=1
        )

    result = climb(measure, seed_prediction=4, max_cameras=32)

    assert result.capacity == 4
    assert result.ceiling_bound is True
    assert result.aborted is False


def test_inference_failing_at_the_very_first_count_measures_nothing():
    """Distinct from the case above: nothing passed, so `capacity` describes
    nothing and the profile must not carry an end-to-end figure at all."""

    def measure(n):
        return _sample(
            cameras=n, passed=False, failure_reason=FAILURE_INFERENCE_FAILED, isolated=1
        )

    result = climb(measure, seed_prediction=6, max_cameras=32)

    assert result.aborted is True
    assert result.ceiling_bound is False
    assert result.capacity == 0


# --- rate pinning --------------------------------------------------------


def test_the_capacity_argument_pins_each_end_of_the_fps_band():
    """The bench pins the tick rate purely through what it passes as
    `capacity`, which is what keeps pipeline.py unmodified. If target_fps ever
    stops returning the band floor for a negative capacity, the min-FPS climb
    would silently measure the wrong rate."""
    for n in (1, 8, 32):
        at_max = runtime_bench.target_period_capacity(n, at_max_fps=True)
        at_min = runtime_bench.target_period_capacity(n, at_max_fps=False)
        assert target_fps(at_max, n) == config.FPS_BAND_MAX
        assert target_fps(at_min, n) == config.FPS_BAND_MIN


def test_band_target_fps_matches_the_capacity_pin():
    assert runtime_bench.band_target_fps(True) == config.FPS_BAND_MAX
    assert runtime_bench.band_target_fps(False) == config.FPS_BAND_MIN


# --- instrumentation over the real pipeline ------------------------------


def _pipeline(cameras, capacity=8):
    return InstrumentedPipeline(
        cameras, FakeDetector(), lambda *a: None, capacity=capacity
    )


def test_contributions_are_counted_per_camera_over_the_real_tick():
    now = time.monotonic()
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(now, 0), FakeFrameRead(now, 0)]),
        2: FakeCamera(2, [FakeFrameRead(now, 0)]),
    }
    pipeline = _pipeline(cameras)
    pipeline.begin_measurement()

    pipeline.tick_once()
    pipeline.tick_once()

    assert pipeline.contributions == {1: 2, 2: 1}


def test_a_stale_frame_is_counted_separately_from_having_no_frame():
    """These mean opposite things. A camera with nothing new is simply decoding
    slower than the tick; a camera whose frame was REFUSED for age
    (MAX_FRAME_AGE_SECONDS) is connected but stalled, which is a fault rather
    than a rate. Collapsing them would hide the second behind the first."""
    now = time.monotonic()
    stale_t = now - config.MAX_FRAME_AGE_SECONDS - 1
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(stale_t, 0)]),  # has a frame, too old
        2: FakeCamera(2, []),  # simply has nothing
    }
    pipeline = _pipeline(cameras)
    pipeline.begin_measurement()

    pipeline.tick_once()

    assert pipeline.stale_skips == 1
    assert pipeline.contributions == {}


def test_handover_is_cleared_each_tick_so_a_stale_count_cannot_repeat():
    """`handed_over` is a per-tick observation. Left uncleared, one refused
    frame would be recounted on every subsequent tick and the stale figure
    would grow without any new fault."""
    now = time.monotonic()
    stale_t = now - config.MAX_FRAME_AGE_SECONDS - 1
    cameras = {1: FakeCamera(1, [FakeFrameRead(stale_t, 0)])}
    pipeline = _pipeline(cameras)
    pipeline.begin_measurement()

    pipeline.tick_once()
    pipeline.tick_once()
    pipeline.tick_once()

    assert pipeline.stale_skips == 1


def test_nothing_is_counted_before_the_measurement_window_opens():
    """The warm-up prefix covers model warm-up, cuDNN retuning for a new batch
    shape and streams still connecting. Counting it would drag the achieved
    rate down for reasons that are not capacity."""
    now = time.monotonic()
    cameras = {1: FakeCamera(1, [FakeFrameRead(now, 0), FakeFrameRead(now, 0)])}
    pipeline = _pipeline(cameras)

    pipeline.tick_once()  # warm-up: must not count
    pipeline.begin_measurement()
    pipeline.tick_once()

    assert pipeline.contributions == {1: 1}
    assert len(pipeline.tick_durations_ms) == 1


# --- summarising ---------------------------------------------------------


def test_a_camera_that_contributed_nothing_is_reported_at_zero_not_omitted():
    """Dropping it would remove the very camera that fails the min check, and
    the run would be scored on the survivors."""
    now = time.monotonic()
    cameras = {1: FakeCamera(1, [FakeFrameRead(now, 0)]), 2: FakeCamera(2, [])}
    pipeline = _pipeline(cameras)
    pipeline.begin_measurement()
    pipeline.tick_once()
    pipeline.end_measurement()

    sample = summarise(pipeline, cameras, target_fps=15.0, events=0, reconnects=0)

    assert set(sample.achieved_fps_by_camera) == {1, 2}
    assert sample.achieved_fps_by_camera[2] == 0.0
    assert sample.achieved_fps_min == 0.0
    assert sample.passed is False


def test_the_sample_serialises_for_the_profile():
    """e2e_runs goes to JSON, so keys must be strings and floats must not carry
    fifteen digits of noise into a file a human reads."""
    sample = _sample(decode_fps_min=29.916666)
    data = sample.as_dict()

    assert set(data["achieved_fps_by_camera"]) == {"1", "2"}
    assert data["decode_fps_min"] == 29.92


# --- the CI guard --------------------------------------------------------


def test_the_pure_module_imports_with_cv2_and_ultralytics_blocked():
    """The split exists so this half runs in CI, where the `ai` extra is not
    installed. If cv2, ultralytics or torch ever becomes reachable from
    runtime_bench — directly OR through something it imports — every test in
    this file would start skipping on CI and the coverage would vanish
    silently.

    Run in a subprocess with those modules poisoned at the import hook, so the
    check holds on a developer machine that HAS them installed. A source-text
    scan would miss a transitive import; this cannot.
    """
    probe = textwrap.dedent(
        """
        import sys
        BANNED = ("cv2", "ultralytics", "torch")

        class Blocker:
            def find_module(self, name, path=None):
                return self.find_spec(name, path)

            def find_spec(self, name, path=None, target=None):
                if name.split(".")[0] in BANNED:
                    raise ImportError(f"{name} is not available in CI")
                return None

        sys.meta_path.insert(0, Blocker())
        sys.path.insert(0, %r)
        import runtime_bench  # noqa: F401
        print("ok")
        """
    ) % str(AI_ENGINE_DIR)

    completed = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stderr
    assert "ok" in completed.stdout
