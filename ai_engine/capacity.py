"""One-shot per-machine setup: probe, benchmark, write.

Answers "how many cameras can this machine carry at the required frame
rate?" — a number a person can act on — rather than picking a tick rate.
The answer lands in machine_profile.json, which main.py reads at startup;
that file is gitignored because it describes THIS machine and no other.

Needs the `ai` extra — this module imports cv2 and, via detector.py,
ultralytics. Install with `uv sync --extra ai`, or `--extra ai-cpu` on a
machine without an NVIDIA GPU. Run from the repo root, like everything else
here.

Usage:
    uv run python ai_engine/capacity.py

    # benchmark a build that already exists, rather than the checkpoint
    uv run python ai_engine/capacity.py --model ai_engine/epoch50.engine

    # measure against real footage instead of a blank frame
    uv run python ai_engine/capacity.py --sample-frame ai_engine/eval/clips/<clip>.mp4

    # record fewer cameras than the machine can carry
    uv run python ai_engine/capacity.py --cameras 4

Flags:
    --model         What to benchmark. Defaults to config.WEIGHTS_PATH
                    (epoch50.pt). Any format Ultralytics can load works — a
                    TensorRT engine, an ONNX export, another .pt — because
                    detector.py loads all of them through the same YOLO(path).
                    A path that does not exist is fatal, never a fallback to
                    the checkpoint: a profile claiming capacity for an
                    artifact that was never measured is worse than no profile.
    --sample-frame  Benchmark against a video or image rather than a blank
                    frame. See synthetic_frame() for why the default is
                    optimistic and this is the number safe to quote.
    --cameras       Override the recorded camera target. The measurement is
                    still written in full; only chosen_camera_target moves.

Takes a few minutes: sixteen batch sizes, each warmed up and then timed.
Nothing is written until the sweep finishes.

NOT the five-step probe/build/benchmark/verify/write of design doc section 6.1.
Two of those steps are deliberately absent, and the numbers here must be read
with that in mind:

- **No build.** This script does not export epoch50.pt to a faster format —
  that stays out of band. By default it benchmarks the plain PyTorch weights,
  so the capacity reported is a FLOOR — a TensorRT or ONNX build would raise
  it. TensorRT is deliberately outside the `ai` extra because its PyPI stub
  hangs indefinitely on install. Pass `--model` to benchmark a build that
  already exists (a TensorRT engine, an ONNX export, or another .pt) instead
  of the default checkpoint; the floor caveat applies to the default, not to
  the script.
- **No verify.** `verification` is always written as unverified. Only the
  clip regression can promote it, and that needs clips this machine may not
  have.

`model_path` records whatever was actually benchmarked, so a profile is
self-describing.
"""

import argparse
import time
from pathlib import Path

import config
import cv2
import numpy as np
from detector import AccidentDetector, resolve_device
from machine_profile import (
    VERIFICATION_UNVERIFIED,
    MachineProfile,
    capacity_from_latency,
    save_profile,
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


def main() -> None:
    parser = argparse.ArgumentParser()
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

    if not latency:
        raise SystemExit(
            "[capacity] could not benchmark even a single frame; no profile written"
        )

    capacity_max = capacity_from_latency(latency, config.FPS_BAND_MAX)
    capacity_min = capacity_from_latency(latency, config.FPS_BAND_MIN)

    print(
        f"\n[capacity] CAPACITY: {capacity_max} camera(s) at "
        f"{config.FPS_BAND_MAX:.0f} FPS, or {capacity_min} at "
        f"{config.FPS_BAND_MIN:.0f} FPS."
    )
    if capacity_max == 0:
        print(
            "[capacity] This machine cannot carry a single camera at the "
            "required frame rate. The engine will still run for integration "
            "work, but no performance claim may be drawn from it."
        )
    if _grid_limited(latency, capacity_max) or _grid_limited(latency, capacity_min):
        print(
            f"[capacity] NOTE: capacity reached the largest batch benchmarked "
            f"({max(latency)}), so the real figure is AT LEAST this, not "
            f"exactly this. Extend BATCH_SIZES to resolve it."
        )

    chosen = args.cameras if args.cameras is not None else capacity_max

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
    )
    save_profile(config.PROFILE_PATH, profile)
    print(f"[capacity] wrote {config.PROFILE_PATH}")


if __name__ == "__main__":
    main()
