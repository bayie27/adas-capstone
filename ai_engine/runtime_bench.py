"""Closed-loop capacity measurement: how many cameras this machine actually
carries, observed rather than computed.

`capacity.py`'s sweep times `detector.predict_batch()` on frames already
decoded and sitting in memory. This drives the REAL `InferencePipeline` over
real camera objects for a timed window and reports the frame rate each camera
achieved. The difference is everything the sweep cannot see: decode, N reader
threads competing for cores, the accumulator, and `run()`'s own scheduler.

Pure module: no cv2, no ultralytics, no subprocess. `InferencePipeline`'s
import chain is cv2-free for exactly this reason (see pipeline.py's docstring),
and camera construction lives in bench_sources.py, which this module never
imports. That keeps the climb, the pass criterion and the instrumentation
testable in CI on a machine with no GPU, no ffmpeg and no `ai` extra — and
tests/test_runtime_bench.py deliberately carries no `importorskip`, so a
regression that drags cv2 in here turns the suite red instead of skipping it.

WHY THE METRIC IS PER-CAMERA ACHIEVED FRAME RATE. `CameraStream._latest` holds
exactly one frame and `read()` consumes it, so a camera contributes at most one
frame per tick and anything decoded in between is discarded. Therefore

    per-camera achieved rate = min(that camera's decode rate, the tick rate)

and the two ways a machine fails are distinguishable: when inference overruns,
`run()` slips and EVERY camera degrades together; when one decoder falls
behind, only that camera thins out while the rest stay healthy. Both are
invisible to a benchmark that only times the forward pass.
"""

import statistics
import threading
import time
from dataclasses import asdict, dataclass, field

import config
from pipeline import InferencePipeline

# A run passes when the SLOWEST camera held this fraction of the target rate.
# Slack exists because the window is finite and a camera can lose a frame to
# ordinary scheduling jitter without being over capacity.
TOLERANCE = 0.95

# How far below the seed prediction the climb starts. The seed comes from the
# inference sweep, which benchmarks a 1280x720 frame while real streams are
# 2304x1296 or 2560x1440 — up to 4x the pixels through to_gray()'s two
# full-resolution cvtColor passes, plus the decode the sweep never does. So the
# seed runs ahead of reality and the walk-down, not this constant, is what
# actually finds the answer.
SEED_BACKOFF = 2

# Absolute stop, so a machine that never fails cannot climb forever.
MAX_CAMERAS = 64

FAILURE_STARVED = "starved"
FAILURE_STREAM_DROPPED = "stream_dropped"
FAILURE_CONTAMINATED = "contaminated_by_events"
FAILURE_INFERENCE_FAILED = "inference_failed"
FAILURE_STREAMS_NOT_READY = "streams_not_ready"


class RecordsHandover:
    """Mixin: remembers the FrameRead this camera handed to the pipeline.

    Exists so stale-frame skips can be counted WITHOUT reimplementing
    `_collect()`. The pipeline drops a frame older than
    `config.MAX_FRAME_AGE_SECONDS` inside that method, and from outside there
    is otherwise no way to tell "this camera had nothing new" from "this
    camera's frame was too old to use" — the two mean opposite things, and
    duplicating the production logic to separate them would let the copy drift.

    Mixed in ahead of the real CameraStream by bench_sources; the CI fakes use
    it over a fake base, so both sides exercise the same code.
    """

    handed_over = None

    def read(self):
        self.handed_over = super().read()
        return self.handed_over


@dataclass
class RunSample:
    """One timed run at a fixed camera count. The evidence behind one row of
    the climb, recorded into the profile whether it passed or failed."""

    cameras: int
    target_fps: float
    window_seconds: float
    achieved_fps_by_camera: dict[int, float] = field(default_factory=dict)
    achieved_fps_min: float = 0.0
    achieved_fps_mean: float = 0.0
    decode_fps_min: float | None = None
    tick_rate_hz: float = 0.0
    tick_p50_ms: float = 0.0
    tick_p95_ms: float = 0.0
    overrun_fraction: float = 0.0
    stale_skips: int = 0
    reconnects: int = 0
    events: int = 0
    # Cameras the pipeline dropped because inference raised on their frames.
    # Almost always a model that will not accept the batch size it was handed —
    # a TensorRT engine built for a fixed batch, or a dynamic one whose maximum
    # the climb has now exceeded.
    isolated: int = 0
    # Percent of one core burned by publishers the bench spawned itself. The
    # disclosed confound — real cameras encode off-box and these do not — so it
    # is reported per run rather than folded away. None when measuring against
    # a server the bench does not own, where the confound does not exist.
    publisher_cpu_pct: float | None = None
    passed: bool = False
    failure_reason: str | None = None

    def as_dict(self) -> dict:
        data = asdict(self)
        data["achieved_fps_by_camera"] = {
            str(k): round(v, 2) for k, v in self.achieved_fps_by_camera.items()
        }
        for key in (
            "achieved_fps_min",
            "achieved_fps_mean",
            "tick_rate_hz",
            "tick_p50_ms",
            "tick_p95_ms",
            "overrun_fraction",
        ):
            data[key] = round(data[key], 2)
        if self.decode_fps_min is not None:
            data["decode_fps_min"] = round(self.decode_fps_min, 2)
        return data


def evaluate(sample: RunSample, *, tolerance: float = TOLERANCE):
    """Did this machine carry `sample.cameras` cameras? Returns (passed, reason).

    Three checks, and the ORDER matters because the reasons prescribe opposite
    responses: a contaminated run says "re-run against the negative clip", a
    dropped stream says "this machine cannot hold that many streams open", and
    starvation says "this machine cannot process that many". Reporting the
    wrong one sends the reader to the wrong fix.
    """
    if not sample.achieved_fps_by_camera:
        return False, FAILURE_STARVED

    # Checked FIRST because it is the loudest lie. An isolated camera stops
    # contributing entirely, so its achieved rate is 0 and every other check
    # would read this as the machine running out of capacity. It is not — the
    # model refused the batch it was handed, and no amount of slower hardware
    # or fewer cameras is the explanation.
    if sample.isolated:
        return False, FAILURE_INFERENCE_FAILED

    # Events pause the camera mid-window (the self-blindfold), so its achieved
    # rate drops for a reason that is nothing to do with capacity. Refuse to
    # call that a capacity limit.
    if sample.events and not _meets_rate(sample, tolerance):
        return False, FAILURE_CONTAMINATED

    # Checked before the rate: a stream that dropped and reconnected lost
    # coverage outright, and a reconnect early in the window can still leave
    # the average looking healthy.
    if sample.reconnects:
        return False, FAILURE_STREAM_DROPPED

    if not _meets_rate(sample, tolerance):
        return False, FAILURE_STARVED

    return True, None


def _meets_rate(sample: RunSample, tolerance: float) -> bool:
    """The SLOWEST camera, never the mean.

    A mean hides one starved camera behind N-1 healthy ones. That is a sharper
    version of the failure `pipeline.target_fps` already warns about — quality
    degrading invisibly — because here it degrades for one operator's camera
    while every aggregate number still looks fine.
    """
    return sample.achieved_fps_min >= sample.target_fps * tolerance


class InstrumentedPipeline(InferencePipeline):
    """The production pipeline, timed.

    Overrides only the two seams it needs and calls `super()` for the actual
    work, so what is measured is the real tick and not a replica of it.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._measuring = False
        self.tick_durations_ms: list[float] = []
        self.contributions: dict[int, int] = {}
        self.stale_skips = 0
        self.started_at: float | None = None
        self.stopped_at: float | None = None

    def begin_measurement(self) -> None:
        """Discard everything so far. Called after the warm-up prefix, which
        covers model warm-up, cuDNN retuning for a new batch shape, and streams
        still negotiating their connection."""
        self.tick_durations_ms.clear()
        self.contributions.clear()
        self.stale_skips = 0
        self.started_at = time.monotonic()
        self._measuring = True

    def end_measurement(self) -> None:
        self.stopped_at = time.monotonic()
        self._measuring = False

    @property
    def isolated_count(self) -> int:
        """Cameras `_infer` dropped after inference raised on their frames.

        Reads the parent's own set rather than counting separately, so the two
        can never disagree about which cameras are still in the batch.
        """
        return len(self._isolated)

    @property
    def measured_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.stopped_at if self.stopped_at is not None else time.monotonic()
        return max(0.0, end - self.started_at)

    def _collect(self):
        for camera in list(self.cameras.values()):
            # Cleared every tick: `handed_over` is a per-tick observation, and
            # a stale value would be miscounted as this tick's skip.
            if hasattr(camera, "handed_over"):
                camera.handed_over = None

        collected = super()._collect()

        if self._measuring:
            contributed = {camera.camera_id for camera, _ in collected}
            for camera in list(self.cameras.values()):
                if camera.camera_id in contributed:
                    self.contributions[camera.camera_id] = (
                        self.contributions.get(camera.camera_id, 0) + 1
                    )
                elif getattr(camera, "handed_over", None) is not None:
                    # It had a frame and the pipeline still declined it, which
                    # only happens past MAX_FRAME_AGE_SECONDS.
                    self.stale_skips += 1
        return collected

    def tick_once(self) -> None:
        started = time.perf_counter()
        super().tick_once()
        if self._measuring:
            self.tick_durations_ms.append((time.perf_counter() - started) * 1000)


def summarise(
    pipeline: InstrumentedPipeline,
    cameras: dict,
    *,
    target_fps: float,
    events: int,
    reconnects: int,
) -> RunSample:
    """Turn a finished run into the row that goes in the profile."""
    window = pipeline.measured_seconds
    sample = RunSample(
        cameras=len(cameras),
        target_fps=target_fps,
        window_seconds=round(window, 2),
        events=events,
        reconnects=reconnects,
        stale_skips=pipeline.stale_skips,
        isolated=pipeline.isolated_count,
    )
    if window <= 0:
        sample.failure_reason = FAILURE_STARVED
        return sample

    # A camera that contributed NOTHING must still appear, at 0.0 — dropping it
    # would remove the very camera that fails the min check.
    achieved = {
        camera_id: pipeline.contributions.get(camera_id, 0) / window
        for camera_id in cameras
    }
    sample.achieved_fps_by_camera = achieved
    sample.achieved_fps_min = min(achieved.values()) if achieved else 0.0
    sample.achieved_fps_mean = statistics.fmean(achieved.values()) if achieved else 0.0

    decode_rates = [
        camera.measured_fps
        for camera in cameras.values()
        if getattr(camera, "measured_fps", None) is not None
    ]
    sample.decode_fps_min = min(decode_rates) if decode_rates else None

    ticks = pipeline.tick_durations_ms
    if ticks:
        sample.tick_rate_hz = len(ticks) / window
        sample.tick_p50_ms = statistics.median(ticks)
        sample.tick_p95_ms = _percentile(ticks, 95)
        budget_ms = 1000.0 / target_fps
        sample.overrun_fraction = sum(1 for t in ticks if t > budget_ms) / len(ticks)

    sample.passed, sample.failure_reason = evaluate(sample)
    return sample


def _percentile(values: list[float], pct: float) -> float:
    """Nearest-rank. statistics.quantiles needs at least two points and
    interpolates; a run short enough to produce one tick is exactly the case
    worth reporting rather than crashing on."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(pct / 100 * len(ordered) + 0.5)) - 1)
    return ordered[max(0, index)]


def run_window(
    pipeline: InstrumentedPipeline,
    *,
    warmup_seconds: float,
    window_seconds: float,
    on_begin=None,
    on_end=None,
    sleep=time.sleep,
) -> None:
    """Drive the real `pipeline.run()` loop for warm-up plus window.

    `run()` is used rather than a hand-rolled tick loop on purpose: its slip
    behaviour on an overrun (reset the baseline, never catch up) is part of
    what decides whether the engine keeps up, so reimplementing it here would
    measure a scheduler that does not ship.

    `on_begin` and `on_end` bracket the MEASURED window, not the whole run.
    Counters that live outside the pipeline — reconnects, publisher CPU — have
    to be sampled there or they would attribute the warm-up to the result, and
    warm-up is exactly when streams are still connecting and reconnecting.
    """
    thread = threading.Thread(target=pipeline.run, daemon=True)
    thread.start()
    try:
        sleep(warmup_seconds)
        pipeline.begin_measurement()
        if on_begin is not None:
            on_begin()
        sleep(window_seconds)
        pipeline.end_measurement()
        if on_end is not None:
            on_end()
    finally:
        pipeline.stop()
        thread.join(timeout=10)


@dataclass
class ClimbResult:
    capacity: int
    samples: list[RunSample] = field(default_factory=list)
    seed_prediction: int = 0
    started_at_cameras: int = 0
    # True when NOTHING was measured: inference refused the very first count, so
    # `capacity` is meaningless rather than merely conservative.
    aborted: bool = False
    # True when counts passed and then inference refused the next one up. The
    # MODEL decided the answer, not the machine, so `capacity` is a floor — the
    # same distinction `capacity._grid_limited` draws for the sweep, where a
    # capacity equal to the largest batch measured is "we stopped looking here"
    # rather than a measurement.
    ceiling_bound: bool = False


def climb(
    measure,
    *,
    seed_prediction: int,
    max_cameras: int = MAX_CAMERAS,
    backoff: int = SEED_BACKOFF,
    floor: int = 1,
) -> ClimbResult:
    """Find the largest camera count this machine sustains.

    `measure` is a callable taking a camera count and returning a RunSample, so
    CI can exercise the search with no hardware.

    The search STARTS BELOW the seed and that is the whole safety property: the
    seed is a prediction from a different measurement (720p, no decode, no
    threads) and is expected to run ahead of reality, so beginning under it
    means an optimistic prediction cannot cause the search to step over a
    camera count that would have failed. When the starting point itself fails,
    the walk-down goes all the way to `floor` rather than giving up after a
    step or two — on a CPU-only machine the seed can be several times the truth.
    """
    start = max(floor, min(seed_prediction - backoff, max_cameras))
    result = ClimbResult(
        capacity=0, seed_prediction=seed_prediction, started_at_cameras=start
    )

    first = measure(start)
    result.samples.append(first)
    if _fatal(first):
        result.aborted = True
        return result

    if first.passed:
        result.capacity = start
        for n in range(start + 1, max_cameras + 1):
            sample = measure(n)
            result.samples.append(sample)
            if not sample.passed:
                # Counts BELOW this one passed, so something was measured. If
                # the model refused rather than the machine falling behind, the
                # answer is a floor: the engine's batch ceiling decided it.
                result.ceiling_bound = _fatal(sample)
                return result
            result.capacity = n

        # Ran out of ceiling with every count still passing — "we stopped
        # looking here", not an answer. Raise max_cameras to resolve it.
        result.ceiling_bound = True
        return result

    for n in range(start - 1, floor - 1, -1):
        sample = measure(n)
        result.samples.append(sample)
        if _fatal(sample):
            result.aborted = True
            return result
        if sample.passed:
            result.capacity = n
            return result

    # Nothing passed, not even one camera. Recorded as 0 rather than rounded up
    # to 1: it is the honest answer for a machine that cannot keep up at all,
    # and capacity.py already reports 0 the same way.
    return result


def _fatal(sample: RunSample) -> bool:
    """Whether this failure makes the rest of the search pointless.

    Inference refusing a batch is not a boundary the search can find by trying
    fewer cameras — every remaining count would fail identically, each costing a
    full warm-up and window. Stop and say why instead of walking down to 1 and
    reporting a capacity of 0 that describes nothing.
    """
    return sample.failure_reason == FAILURE_INFERENCE_FAILED


def target_period_capacity(n: int, at_max_fps: bool) -> int:
    """What to pass as `InferencePipeline(capacity=...)` to pin the tick rate.

    `pipeline.target_fps` returns FPS_BAND_MAX while `active <= capacity` and
    FPS_BAND_MIN otherwise, so handing it `n` pins the top of the band and -1
    pins the bottom (no non-negative active count is <= -1). The only other
    thing `capacity` reaches is `InferencePipeline.degraded`, which nothing
    reads — so this pins the rate without touching production code.
    """
    return n if at_max_fps else -1


def band_target_fps(at_max_fps: bool) -> float:
    return config.FPS_BAND_MAX if at_max_fps else config.FPS_BAND_MIN
