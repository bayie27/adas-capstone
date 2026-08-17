"""One-shot per-machine setup: how many cameras can this machine carry?

The answer lands in machine_profile.json, which main.py reads at startup; that
file is gitignored because it describes THIS machine and no other.

TWO MODES, and the difference is what is inside the measurement.

`--mode closed-loop` (the DEFAULT) brings up N real CameraStreams against real
RTSP, runs the real InferencePipeline for a timed window, and reports the frame
rate each camera ACHIEVED. Decode, N reader threads competing for cores, the
accumulator and run()'s own scheduler are all in the number. Needs mediamtx and
ffmpeg on PATH, or `--source` pointed at a server already running.

`--mode inference` is the original sweep: batched predict_batch() over a grid of
batch sizes, on frames already decoded and sitting in memory, compared against
the tick budget. It measures one stage and calls it a system figure — which is
why it is no longer the default. It is retained because it needs no ffmpeg or
mediamtx, and because closed-loop mode uses it as the SEED that picks where to
start looking.

Closed-loop mode runs the seed sweep too, so it writes both sets of figures. The
sweep's number is expected to read high: it benchmarks a 1280x720 frame while
real streams are 2304x1296 and 2560x1440, and to_gray() runs two
full-resolution cvtColor passes before YOLO downscales to 640. The gap between
the two is printed, and it is the most useful line of output.

Needs the `ai` extra — this module imports cv2 and, via detector.py,
ultralytics. Install with `uv sync --extra ai`, or `--extra ai-cpu` on a
machine without an NVIDIA GPU. Run from the repo root, like everything else
here.

Usage:
    uv run python ai_engine/capacity.py

    # measure against a running MediaMTX, or the real VMS — the truest figure,
    # and it needs no mediamtx locally
    uv run python ai_engine/capacity.py --source rtsp://host:8554/channel{n}

    # the original inference-only sweep
    uv run python ai_engine/capacity.py --mode inference

    # benchmark a build that already exists, rather than the checkpoint
    uv run python ai_engine/capacity.py --model ai_engine/epoch50.engine

    # record fewer cameras than the machine can carry
    uv run python ai_engine/capacity.py --cameras 4

Flags:
    --mode          closed-loop (default) or inference. See above.
    --source        Where the streams come from: an RTSP URL template with {n},
                    or a clip to publish. Defaults to eval/clips/airbase.mp4,
                    the only crash-free clip — a crash fires an event, the
                    camera self-blindfolds, and the achieved rate drops for a
                    reason that is not capacity.
    --window        Seconds measured per camera count (default 30).
    --warmup        Seconds discarded first, covering model warm-up and streams
                    still connecting (default 10).
    --model         What to benchmark. Defaults to config.WEIGHTS_PATH
                    (epoch50.pt). Any format Ultralytics can load works — a
                    TensorRT engine, an ONNX export, another .pt — because
                    detector.py loads all of them through the same YOLO(path).
                    A path that does not exist is fatal, never a fallback to
                    the checkpoint: a profile claiming capacity for an
                    artifact that was never measured is worse than no profile.
    --sample-frame  Benchmark the SEED sweep against a video or image rather
                    than a blank frame. See synthetic_frame().
    --cameras       Override the recorded camera target. The measurement is
                    still written in full; only chosen_camera_target moves.

Nothing is written until the whole run finishes.

Still NOT the five-step probe/build/benchmark/verify/write of design doc
section 6.1. Two of those steps remain deliberately absent, and the numbers
here must be read with that in mind:

- **No build.** This script does not export epoch50.pt to a faster format —
  that stays out of band. By default it benchmarks the plain PyTorch weights,
  so the capacity reported is a FLOOR — a TensorRT or ONNX build would raise
  it. TensorRT is deliberately outside the `ai` extra because its PyPI stub
  hangs indefinitely on install. Pass `--model` to benchmark a build that
  already exists instead of the default checkpoint.
- **No verify.** `verification` is always written as unverified. Only the
  clip regression can promote it, and that needs clips this machine may not
  have.
- **No soak.** Every figure is a burst figure, recorded as
  `sustained_verified: false`. Thermal throttling — the one effect the
  10-15 FPS band exists for — is not measured.

`model_path` records whatever was actually benchmarked, and `source_kind`,
`clip_resolution` and `clip_native_fps` record what it watched, so a profile is
self-describing. Two capacities measured against different source resolutions
are not comparable.
"""

import argparse
import time
from pathlib import Path

import config
import cv2
import numpy as np
from detector import AccidentDetector, resolve_device
from machine_profile import (
    METHOD_CLOSED_LOOP,
    SOURCE_EXISTING_SERVER,
    SOURCE_SYNTHETIC,
    VERIFICATION_UNVERIFIED,
    MachineProfile,
    capacity_from_latency,
    save_profile,
)
from runtime_bench import (
    FAILURE_STREAMS_NOT_READY,
    MAX_CAMERAS,
    SEED_BACKOFF,
    InstrumentedPipeline,
    RunSample,
    band_target_fps,
    climb,
    run_window,
    summarise,
    target_period_capacity,
)

# CONTIGUOUS, not powers of two. capacity_from_latency can only return a batch
# size it was actually handed, so a [1, 2, 4, 8] grid cannot express a capacity
# of 3, 5, 6 or 7 — it would understate a 7-camera machine as 4, and would
# report the SAME capacity at both ends of the FPS band, making
# capacity_at_min_fps a dead field and pipeline.target_fps's band-drop lever
# look pointless. Pinned by test_a_sparse_grid_understates_capacity.
#
# It has been raised twice, both times because the machine outgrew the grid,
# and the reason is always the same: a capacity equal to the largest batch
# measured is not a measurement, it is "we stopped looking here".
#
#   8  -> 16   batch 8 measured 63.6ms against the 66.7ms tick on a GTX 1650,
#              so capacity saturated at BOTH ends of the band and
#              capacity_at_min_fps went dead.
#   16 -> 32   a TensorRT build of the same model on the same card reached 14
#              cameras at 15 FPS and hit the grid ceiling at 10 FPS, reporting
#              15 when a linear fit of its own latencies (R^2 = 0.98) puts the
#              real figure near 22. Compiled builds roughly halved per-batch
#              latency, so the headroom 16 used to provide is gone.
#
# 32 is chosen to clear that extrapolated 22 with margin, not as a round
# number. VRAM does not constrain it on the development card: measured
# 2026-08-16, inference costs ~14 MiB per camera, so batch 32 peaks at 0.48 GiB
# of a 4 GiB card. Compute is the binding constraint, which is what makes this
# grid worth extending rather than a memory ceiling to respect.
#
# The cost is time: work scales with the SUM of the batch sizes, so 1..32 is
# roughly 4x the sweep of 1..16. A machine that OOMs partway up stops there and
# keeps what it measured, and _grid_limited still reports a capacity that
# reached the top rather than quietly returning the ceiling as an answer.
BATCH_SIZES = list(range(1, 33))
WARMUP_ITERATIONS = 10
TIMED_ITERATIONS = 30

BENCHMARK_WIDTH = 1280
BENCHMARK_HEIGHT = 720


def synthetic_frame():
    """The portable default: a blank frame at a typical camera resolution.

    Blank is a DELIBERATE choice over random noise. Noise makes the model's
    output arbitrary — it can emit anything from zero boxes to hundreds at
    conf 0.15 — so the NMS cost, and therefore the reported capacity, would
    swing on nothing meaningful. Blank is at least stable and reproducible
    across machines, which is what a portability profile needs.

    Its cost is that it UNDERSTATES latency: with almost no candidate boxes,
    NMS does near-zero work, so capacity measured this way is an upper bound.
    Pass --sample-frame to measure against real footage instead; the two are
    compared in eval/README.md.
    """
    return np.zeros((BENCHMARK_HEIGHT, BENCHMARK_WIDTH, 3), dtype="uint8")


# Resolution lives in config so main.py and capacity.py cannot disagree about
# which model a given AI_MODEL_PATH means, or about a missing one being fatal.
resolve_model_path = config.resolve_model_path


def load_sample_frame(path):
    """First frame of a real video (or a still image), resized to the
    benchmark resolution so content is the only variable against synthetic.
    """
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"[capacity] --sample-frame not found: {path}")

    frame = cv2.imread(str(path))
    if frame is None:
        capture = cv2.VideoCapture(str(path))
        try:
            ok, frame = capture.read()
        finally:
            capture.release()
        if not ok or frame is None:
            raise SystemExit(f"[capacity] could not read a frame from {path}")

    return cv2.resize(frame, (BENCHMARK_WIDTH, BENCHMARK_HEIGHT))


def _grid_limited(latency_ms_by_batch: dict, capacity: int) -> bool:
    """True when capacity is the largest batch measured, so the answer is a
    floor rather than the real figure.

    Worth reporting rather than swallowing: a capacity that silently equals
    the grid ceiling looks like a measurement but is really "we stopped
    looking here", and it is what made capacity_at_min_fps uninformative on
    the development machine.
    """
    return bool(latency_ms_by_batch) and capacity == max(latency_ms_by_batch)


def _benchmark(detector, batch_size: int, frame) -> float:
    """Median milliseconds for one batch of `batch_size` frames."""
    frames = [frame] * batch_size

    # The first inferences after loading are substantially slower than
    # steady state; timing them would understate capacity. Warmup runs per
    # batch size because cuDNN re-tunes for each new input shape.
    for _ in range(WARMUP_ITERATIONS):
        detector.predict_batch(frames)

    timings = []
    for _ in range(TIMED_ITERATIONS):
        started = time.perf_counter()
        detector.predict_batch(frames)
        timings.append((time.perf_counter() - started) * 1000)
    return float(np.median(timings))


def sweep(detector, frame, *, stop_at_ms=None) -> dict:
    """Time each batch size in turn. Returns latency by batch.

    `stop_at_ms` stops the climb once a batch overruns that budget. Closed-loop
    mode passes the loosest window in the band, because past it no supported
    frame rate can fit and the remaining sizes are only there to be measured,
    not used — on a CPU-only machine that is the difference between a
    three-second seed and several minutes of pointless work. `--mode inference`
    passes None and grinds the full grid exactly as it always has.
    """
    latency = {}
    for batch in BATCH_SIZES:
        try:
            latency[batch] = _benchmark(detector, batch, frame)
        except Exception as exc:
            # Typically CUDA OOM on a smaller card. Stop here and keep what was
            # measured: a capacity derived from the batches that DID fit is
            # still correct, and crashing would leave the machine with no
            # profile at all.
            print(f"[capacity] batch {batch} failed ({exc}); stopping the sweep")
            print(
                "[capacity] Two causes look identical here: CUDA OOM on a "
                "smaller card, or a TensorRT engine built for a fixed batch "
                "size, which can only be benchmarked at that size. If this "
                "is an engine, rebuild it with dynamic shapes to sweep the "
                "grid."
            )
            break
        print(f"[capacity] batch {batch}: {latency[batch]:.1f} ms")

        if stop_at_ms is not None and latency[batch] > stop_at_ms:
            print(
                f"[capacity] past the {stop_at_ms:.0f} ms window at "
                f"{config.FPS_BAND_MIN:.0f} FPS; seed sweep stops here"
            )
            break
    return latency


def _run_closed_loop(args, detector, seed_prediction: int) -> dict:
    """Measure capacity by running the real engine, and return profile fields.

    `bench_sources` is imported lazily because it spawns processes and is only
    reachable from this mode; `runtime_bench` is pure and imported normally at
    the top of this file.
    """
    import bench_sources as sources

    using_existing = args.source is not None and "://" in args.source
    clip = None

    if using_existing:
        source_kind, source_detail = SOURCE_EXISTING_SERVER, args.source
        print(f"[capacity] source: {args.source} (existing server)")
    else:
        sources.preflight()
        clip_path, source_kind = sources.choose_clip(args.source)
        clip = sources.probe_clip(clip_path)
        source_detail = str(clip_path)
        print(
            f"[capacity] source: {clip_path.name} · {clip.resolution} · "
            f"{clip.fps:.2f} fps · {clip.duration_s:.0f}s"
        )
        if source_kind == SOURCE_SYNTHETIC:
            print(
                "[capacity] NOTE: no clips present, so this is synthetic 720p "
                "footage. Real streams are 2560x1440, which decodes harder — "
                "treat the result as approximate."
            )
        print(
            "[capacity] Publishers run on this machine, which a real "
            "deployment does not do. For the truest figure, point --source at "
            "the real VMS."
        )

    def measure_factory(server, at_max_fps):
        def measure(n):
            return _measure_at(
                n,
                detector=detector,
                server=server,
                clip=clip,
                sources=sources,
                at_max_fps=at_max_fps,
                warmup=args.warmup,
                window=args.window,
                url_template=args.source if using_existing else None,
            )

        return measure

    scratch = config.PROFILE_PATH.parent / "_bench"
    server_ctx = (
        _NullServer(args.source) if using_existing else sources.MediaMtxServer(scratch)
    )

    with server_ctx as server:
        print(
            f"\n[capacity] climbing at {config.FPS_BAND_MAX:.0f} FPS "
            f"(seed predicted {seed_prediction})"
        )
        at_max = climb(
            measure_factory(server, True),
            seed_prediction=seed_prediction,
            max_cameras=args.max_cameras,
        )
        _print_trail(at_max)

        if at_max.aborted:
            # Nothing was measured, so nothing closed-loop goes in the profile.
            # The seed sweep still ran and is still true, so the profile is
            # written as a plain inference-sweep one rather than discarded —
            # but it must not carry an e2e capacity of 0, which would read as
            # "measured, and the answer is none".
            print(
                "\n[capacity] No closed-loop figure was produced. Writing the "
                "inference-sweep profile only."
            )
            return {}

        print(f"\n[capacity] climbing at {config.FPS_BAND_MIN:.0f} FPS")
        # Seeded from the max-FPS answer, which must also pass at the lower
        # rate: a longer tick is strictly more headroom. Adding the backoff back
        # makes the climb START there rather than below it.
        at_min = climb(
            measure_factory(server, False),
            seed_prediction=max(1, at_max.capacity) + SEED_BACKOFF,
            max_cameras=args.max_cameras,
        )
        _print_trail(at_min)

    runs = [s.as_dict() for s in at_max.samples] + [s.as_dict() for s in at_min.samples]
    publisher_cpu = next(
        (
            s.get("publisher_cpu_pct")
            for s in reversed(runs)
            if s.get("publisher_cpu_pct")
        ),
        None,
    )
    if at_min.capacity < at_max.capacity:
        # Theory says a longer tick is strictly more headroom, so this cannot
        # happen — which is exactly why it is reported rather than clamped. It
        # means the runs disagreed with each other, so the machine is sitting on
        # the boundary and BOTH figures are noise. Forcing the invariant with a
        # max() would have written a number no run ever observed.
        print(
            f"\n[capacity] WARNING: the {config.FPS_BAND_MIN:.0f} FPS climb "
            f"({at_min.capacity}) came out BELOW the "
            f"{config.FPS_BAND_MAX:.0f} FPS climb ({at_max.capacity}), which is "
            "impossible if the machine were stable — a longer tick is strictly "
            "more headroom. The two runs disagreed, so this machine is marginal "
            "at that count and neither figure should be quoted. Re-run with a "
            "longer --window, on an otherwise-idle machine."
        )

    return {
        "method": METHOD_CLOSED_LOOP,
        "e2e_capacity_at_max_fps": at_max.capacity,
        "e2e_capacity_at_min_fps": at_min.capacity,
        "e2e_runs": runs,
        "source_kind": source_kind,
        "source_detail": source_detail,
        "clip_resolution": clip.resolution if clip else None,
        "clip_native_fps": clip.fps if clip else None,
        "publisher_cpu_pct": publisher_cpu,
        "window_seconds": args.window,
        "warmup_seconds": args.warmup,
        "sustained_verified": False,
    }


class _NullServer:
    """Stands in for MediaMtxServer when --source names a server already
    running. Same `url_for` contract, nothing to start or stop."""

    def __init__(self, template: str):
        if "{n}" not in template:
            # str.format leaves a template with no placeholder untouched, so
            # every camera would open the SAME url. N cameras on one stream
            # still produces a plausible-looking capacity figure — it just
            # measures the wrong thing, silently.
            raise SystemExit(
                f"[capacity] --source {template!r} has no {{n}} placeholder, so "
                "every camera would read the same stream and the measurement "
                "would be meaningless.\n"
                "Use something like rtsp://localhost:8554/channel{n} — the "
                "cameras are numbered from 1."
            )
        self.template = template

    def url_for(self, index: int) -> str:
        return self.template.format(n=index)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _measure_at(
    n,
    *,
    detector,
    server,
    clip,
    sources,
    at_max_fps,
    warmup,
    window,
    url_template,
):
    """One timed run at n cameras against real RTSP."""
    target_fps = band_target_fps(at_max_fps)
    events = {"count": 0}
    resumes: dict[int, int] = {}
    baseline: dict[int, int] = {}
    cpu = {"start": None, "end": None}

    def on_event(camera, frame, event):
        # The production response to an event. Without it the camera stays
        # blindfolded for the rest of the window and its achieved rate collapses
        # for a reason that is not capacity.
        events["count"] += 1
        resumes[camera.camera_id] = resumes.get(camera.camera_id, 0) + 1
        camera.resume()

    publishers = None
    cameras = {}
    try:
        if url_template is None:
            publishers = sources.Publishers(server, clip, n)
            publishers.__enter__()
        cameras = sources.start_cameras(server, n)
    except sources.StreamsNotReadyError as exc:
        # Not fatal, and not silently swallowed either. Bringing up N streams at
        # once is itself part of what is being measured, so this is recorded as
        # a failed run at this count and the climb walks down — rather than
        # aborting and discarding a seed sweep that took minutes.
        print(f"[capacity]   {n} cam  could not start streams: {exc}")
        if publishers is not None:
            publishers.__exit__(None, None, None)
        sources.stop_cameras(cameras)
        return RunSample(
            cameras=n,
            target_fps=target_fps,
            window_seconds=0.0,
            passed=False,
            failure_reason=FAILURE_STREAMS_NOT_READY,
        )

    try:
        pipeline = InstrumentedPipeline(
            cameras,
            detector,
            on_event,
            # Pins the tick rate; see runtime_bench.target_period_capacity.
            capacity=target_period_capacity(n, at_max_fps),
        )

        def on_begin():
            baseline.update({cid: c.segment_id for cid, c in cameras.items()})
            if publishers is not None:
                cpu["start"] = sources.cpu_seconds(publishers.pids)

        def on_end():
            if publishers is not None:
                cpu["end"] = sources.cpu_seconds(publishers.pids)

        run_window(
            pipeline,
            warmup_seconds=warmup,
            window_seconds=window,
            on_begin=on_begin,
            on_end=on_end,
        )

        if publishers is not None:
            # A dead publisher is the apparatus breaking, not the machine
            # running out of capacity. Recording it as a failed run would be a
            # wrong answer that looks exactly like a right one.
            publishers.assert_alive()

        sample = summarise(
            pipeline,
            cameras,
            target_fps=target_fps,
            events=events["count"],
            reconnects=sources.reconnect_count(cameras, baseline, resumes),
        )
    finally:
        sources.stop_cameras(cameras)
        if publishers is not None:
            publishers.__exit__(None, None, None)

    if cpu["start"] is not None and cpu["end"] is not None and sample.window_seconds:
        pct = (cpu["end"] - cpu["start"]) / sample.window_seconds * 100
        sample.publisher_cpu_pct = round(pct, 1)
    return sample


def _print_trail(result) -> None:
    for sample in result.samples:
        verdict = "ok  " if sample.passed else f"FAIL ({sample.failure_reason})"
        print(
            f"[capacity]   {sample.cameras:>3} cam  "
            f"min {sample.achieved_fps_min:5.2f} fps  "
            f"tick p95 {sample.tick_p95_ms:6.1f} ms  "
            f"stale {sample.stale_skips:<3} reconn {sample.reconnects:<3} {verdict}"
        )

    if result.aborted:
        # Same two-causes-look-identical problem the sweep already warns about,
        # and worse here: the pipeline isolates a camera whose inference raised
        # and carries on, so without this the run reports a capacity of 0 and
        # blames the hardware for a model that simply refused the batch.
        print(
            "[capacity]   -> ABORTED: inference raised and cameras were "
            "isolated, so no capacity was measured.\n"
            "[capacity]      This is almost always the MODEL refusing the batch "
            "size, not the machine running out.\n"
            "[capacity]      Closed-loop mode hands the detector a batch that "
            "VARIES tick to tick — only cameras with a fresh frame are in it — "
            "so a\n"
            "[capacity]      TensorRT engine built for a fixed batch cannot run "
            "it at all, and a dynamic one fails once the climb passes its "
            "maximum.\n"
            "[capacity]      Rebuild with dynamic shapes and a maximum above "
            "the capacity you expect, or measure the checkpoint instead."
        )
        return

    if result.ceiling_bound:
        print(
            f"[capacity]   -> AT LEAST {result.capacity} camera(s) — the climb "
            "ran out of room, not out of machine.\n"
            "[capacity]      Either the engine's batch ceiling or --max-cameras "
            "stopped it, so this is a FLOOR. The same shape of mistake as a "
            "saturated\n"
            "[capacity]      batch grid: a capacity equal to the largest count "
            "attempted is 'we stopped looking here', not a measurement. "
            "Rebuild the\n"
            "[capacity]      engine with a higher max batch, or raise "
            "--max-cameras, to resolve it."
        )
        return

    print(f"[capacity]   -> {result.capacity} camera(s)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("closed-loop", "inference"),
        default="closed-loop",
        help="closed-loop (default) runs the real engine against real RTSP and "
        "reports the frame rate each camera ACHIEVED — it includes the seed "
        "sweep, so it writes both sets of figures. inference runs only the "
        "original batched-inference sweep, which needs no ffmpeg or mediamtx "
        "but measures one stage rather than the system.",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="closed-loop only. An RTSP URL template with {n} "
        "(e.g. rtsp://localhost:8554/channel{n}) measures against a server "
        "already running, or the real VMS — the truest figure, and it needs no "
        "mediamtx locally. A path to a clip publishes that clip instead. "
        f"Defaults to eval/clips/{'airbase.mp4'}, the only crash-free clip.",
    )
    parser.add_argument(
        "--window",
        type=float,
        default=30.0,
        help="seconds of measurement per camera count (default 30).",
    )
    parser.add_argument(
        "--warmup",
        type=float,
        default=10.0,
        help="seconds discarded before measuring, covering model warm-up and "
        "streams still connecting (default 10).",
    )
    parser.add_argument(
        "--max-cameras",
        type=int,
        default=MAX_CAMERAS,
        help="highest camera count the climb may try (default "
        f"{MAX_CAMERAS}). Set this to a TensorRT engine's maximum batch: the "
        "closed-loop batch varies tick to tick, so a climb that steps past the "
        "engine's ceiling fails with inference_failed and measures nothing. "
        "A capacity that reaches this limit is reported as a floor, never as "
        "the answer.",
    )
    parser.add_argument(
        "--cameras",
        type=int,
        default=None,
        help="target camera count; defaults to the measured maximum at "
        f"{config.FPS_BAND_MAX:.0f} FPS. Lower is a legitimate choice on a "
        "machine also running the dev server and a browser.",
    )
    parser.add_argument(
        "--sample-frame",
        default=None,
        help="benchmark against a real video or image instead of a blank "
        "frame. The blank default has near-zero NMS load, so it reports a "
        "slightly OPTIMISTIC capacity; pass a representative clip for a "
        "number safe to quote.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="benchmark this model instead of the configured checkpoint — a "
        "built TensorRT engine, an ONNX export, or another .pt. Defaults to "
        f"{config.WEIGHTS_PATH.name}, which reports a FLOOR: a built artifact "
        "raises capacity. Whatever is passed is recorded as the profile's "
        "model_path.",
    )
    args = parser.parse_args()

    # Validated before the model loads: the seed sweep takes minutes, and
    # finding out then that a flag was malformed wastes all of it.
    if args.mode == "closed-loop" and args.source and "://" in args.source:
        _NullServer(args.source)

    device = resolve_device()
    print(f"[capacity] device: {device}")
    if device == "cpu":
        print(
            "[capacity] WARNING: no GPU detected. This machine is useful for "
            "integration work but is not a detection platform — do not draw "
            "any performance claim from it."
        )

    if args.sample_frame:
        frame = load_sample_frame(args.sample_frame)
        print(f"[capacity] benchmarking against {args.sample_frame}")
    else:
        frame = synthetic_frame()
        print("[capacity] benchmarking against a blank frame (optimistic)")

    model_path = resolve_model_path(args.model)
    print(f"[capacity] model: {model_path}")
    detector = AccidentDetector(model_path, device=device)

    closed_loop = args.mode == "closed-loop"
    latency = sweep(
        detector,
        frame,
        stop_at_ms=(1000.0 / config.FPS_BAND_MIN) if closed_loop else None,
    )

    if not latency:
        raise SystemExit(
            "[capacity] could not benchmark even a single frame; no profile written"
        )

    capacity_max = capacity_from_latency(latency, config.FPS_BAND_MAX)
    capacity_min = capacity_from_latency(latency, config.FPS_BAND_MIN)

    label = "SEED (inference only)" if closed_loop else "CAPACITY"
    print(
        f"\n[capacity] {label}: {capacity_max} camera(s) at "
        f"{config.FPS_BAND_MAX:.0f} FPS, or {capacity_min} at "
        f"{config.FPS_BAND_MIN:.0f} FPS."
    )
    if capacity_max == 0 and not closed_loop:
        print(
            "[capacity] This machine cannot carry a single camera at the "
            "required frame rate. The engine will still run for integration "
            "work, but no performance claim may be drawn from it."
        )
    if not closed_loop and (
        _grid_limited(latency, capacity_max) or _grid_limited(latency, capacity_min)
    ):
        print(
            f"[capacity] NOTE: capacity reached the largest batch benchmarked "
            f"({max(latency)}), so the real figure is AT LEAST this, not "
            f"exactly this. Extend BATCH_SIZES to resolve it."
        )

    extra: dict = {}
    if closed_loop:
        extra = _run_closed_loop(args, detector, capacity_max)
    if extra:
        e2e_max = extra["e2e_capacity_at_max_fps"]
        e2e_min = extra["e2e_capacity_at_min_fps"]
        print(
            f"\n[capacity] MEASURED: {e2e_max} camera(s) at "
            f"{config.FPS_BAND_MAX:.0f} FPS, or {e2e_min} at "
            f"{config.FPS_BAND_MIN:.0f} FPS."
        )
        # The gap is the point of this whole mode: it is how much the
        # inference-only sweep overstates once decode, threads and the
        # scheduler are in the measurement.
        print(
            f"[capacity] The inference-only sweep predicted {capacity_max}; "
            f"running the engine gives {e2e_max}."
        )
        if e2e_max == 0:
            print(
                "[capacity] This machine cannot carry a single camera at the "
                "required frame rate. The engine will still run for integration "
                "work, but no performance claim may be drawn from it."
            )
        print(
            "[capacity] Burst figures on an otherwise-idle machine, with no "
            "thermal soak. Running the backend, the frontend dev server or a "
            "browser alongside will reduce them."
        )

    measured_max = extra.get("e2e_capacity_at_max_fps") if extra else None
    default_target = measured_max if measured_max is not None else capacity_max
    chosen = args.cameras if args.cameras is not None else default_target

    profile = MachineProfile(
        device=device,
        model_path=str(model_path),
        latency_ms_by_batch=latency,
        capacity_at_max_fps=capacity_max,
        capacity_at_min_fps=capacity_min,
        chosen_camera_target=chosen,
        # Verification runs only where the clips are present. Task 10's
        # regression is the full check; run it after calibrating on a
        # machine that has them.
        verification=VERIFICATION_UNVERIFIED,
        verification_detail=(
            "Run `uv run pytest -m clips` on this machine to verify the build "
            "against the recorded per-clip baseline. A build that drifts is "
            "KEPT — the drift is recorded, not used to reject it — but only a "
            "machine whose verification matched may be cited for reported "
            "numbers."
        ),
        **extra,
    )
    save_profile(config.PROFILE_PATH, profile)
    print(f"[capacity] wrote {config.PROFILE_PATH}")


if __name__ == "__main__":
    main()
