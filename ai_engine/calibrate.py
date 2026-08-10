"""One-shot per-machine setup: probe, benchmark, write.

    uv run python ai_engine/calibrate.py

Answers "how many cameras can this machine carry at the required frame
rate?" — a number a person can act on — rather than picking a tick rate.

NOT the five-step probe/build/benchmark/verify/write of design doc section 6.1.
Two of those steps are deliberately absent, and the numbers here must be read
with that in mind:

- **No build.** The design doc calls for exporting epoch50.pt to the fastest
  format the machine supports (TensorRT where available). This benchmarks the
  plain PyTorch weights, so the capacity reported is a FLOOR — a TensorRT or
  ONNX build would raise it. TensorRT is deliberately outside the `ai` extra
  because its PyPI stub hangs indefinitely on install, so that path cannot be
  exercised here.
- **No verify.** `verification` is always written as unverified. Only the
  clip regression can promote it, and that needs clips this machine may not
  have.

`model_path` therefore always records the .pt, never a built artifact.
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
# It runs to 16 rather than 8 because 8 was not enough on the GTX 1650 this was
# developed against: batch 8 measured 63.6ms against the 66.7ms tick, so
# capacity hit the top of the grid at BOTH ends of the band and the field went
# dead again — truncated rather than quantised, but equally uninformative.
# A grid can always be saturated by a fast enough machine, so _grid_limited
# reports when that has happened instead of quietly returning the ceiling.
BATCH_SIZES = list(range(1, 17))
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


def load_sample_frame(path):
    """First frame of a real video (or a still image), resized to the
    benchmark resolution so content is the only variable against synthetic.
    """
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"[calibrate] --sample-frame not found: {path}")

    frame = cv2.imread(str(path))
    if frame is None:
        capture = cv2.VideoCapture(str(path))
        try:
            ok, frame = capture.read()
        finally:
            capture.release()
        if not ok or frame is None:
            raise SystemExit(f"[calibrate] could not read a frame from {path}")

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
    args = parser.parse_args()

    device = resolve_device()
    print(f"[calibrate] device: {device}")
    if device == "cpu":
        print(
            "[calibrate] WARNING: no GPU detected. This machine is useful for "
            "integration work but is not a detection platform — do not draw "
            "any performance claim from it."
        )

    if args.sample_frame:
        frame = load_sample_frame(args.sample_frame)
        print(f"[calibrate] benchmarking against {args.sample_frame}")
    else:
        frame = synthetic_frame()
        print("[calibrate] benchmarking against a blank frame (optimistic)")

    detector = AccidentDetector(config.WEIGHTS_PATH, device=device)

    latency = {}
    for batch in BATCH_SIZES:
        try:
            latency[batch] = _benchmark(detector, batch, frame)
        except Exception as exc:
            # Typically CUDA OOM on a smaller card. Stop here and keep what was
            # measured: a capacity derived from the batches that DID fit is
            # still correct, and crashing would leave the machine with no
            # profile at all.
            print(f"[calibrate] batch {batch} failed ({exc}); stopping the sweep")
            break
        print(f"[calibrate] batch {batch}: {latency[batch]:.1f} ms")

    if not latency:
        raise SystemExit(
            "[calibrate] could not benchmark even a single frame; no profile written"
        )

    capacity_max = capacity_from_latency(latency, config.FPS_BAND_MAX)
    capacity_min = capacity_from_latency(latency, config.FPS_BAND_MIN)

    print(
        f"\n[calibrate] CAPACITY: {capacity_max} camera(s) at "
        f"{config.FPS_BAND_MAX:.0f} FPS, or {capacity_min} at "
        f"{config.FPS_BAND_MIN:.0f} FPS."
    )
    if capacity_max == 0:
        print(
            "[calibrate] This machine cannot carry a single camera at the "
            "required frame rate. The engine will still run for integration "
            "work, but no performance claim may be drawn from it."
        )
    if _grid_limited(latency, capacity_max) or _grid_limited(latency, capacity_min):
        print(
            f"[calibrate] NOTE: capacity reached the largest batch benchmarked "
            f"({max(latency)}), so the real figure is AT LEAST this, not "
            f"exactly this. Extend BATCH_SIZES to resolve it."
        )

    chosen = args.cameras if args.cameras is not None else capacity_max

    profile = MachineProfile(
        device=device,
        model_path=str(config.WEIGHTS_PATH),
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
    print(f"[calibrate] wrote {config.PROFILE_PATH}")


if __name__ == "__main__":
    main()
