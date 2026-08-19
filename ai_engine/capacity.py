"""Inference-only capacity sweep for a model on this machine.

This is deliberately a lightweight diagnostic. It times batched detector
inference on a blank frame (or a supplied representative frame) and prints a
rough camera estimate. It does not start RTSP streams, MediaMTX, or FFmpeg; it
does not write a report; and production never reads its result.

Run from the repository root:

    uv run python ai_engine/capacity.py
"""

import argparse
import time
from pathlib import Path

import config
import cv2
import numpy as np
from detector import AccidentDetector, resolve_device

BATCH_SIZES = list(range(1, 33))
WARMUP_ITERATIONS = 10
TIMED_ITERATIONS = 30
BENCHMARK_WIDTH = 1280
BENCHMARK_HEIGHT = 720


def synthetic_frame():
    """A stable 720p frame for the portable default diagnostic."""
    return np.zeros((BENCHMARK_HEIGHT, BENCHMARK_WIDTH, 3), dtype="uint8")


resolve_model_path = config.resolve_model_path


def load_sample_frame(path):
    """Read a video/image frame and normalize its resolution for the sweep."""
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


def _benchmark(detector, batch_size: int, frame) -> float:
    """Median milliseconds for one batch after shape-specific warm-up."""
    frames = [frame] * batch_size
    for _ in range(WARMUP_ITERATIONS):
        detector.predict_batch(frames)

    timings = []
    for _ in range(TIMED_ITERATIONS):
        started = time.perf_counter()
        detector.predict_batch(frames)
        timings.append((time.perf_counter() - started) * 1000)
    return float(np.median(timings))


def capacity_from_latency(latency_ms_by_batch: dict[int, float], fps: float) -> int:
    """Largest measured batch that fits one inference interval at ``fps``."""
    budget_ms = 1000.0 / fps
    return max(
        (
            batch
            for batch, latency in latency_ms_by_batch.items()
            if latency <= budget_ms
        ),
        default=0,
    )


def _grid_limited(latency_ms_by_batch: dict[int, float], capacity: int) -> bool:
    return bool(latency_ms_by_batch) and capacity == max(latency_ms_by_batch)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        allow_abbrev=False,
        description=(
            "Inference-only capacity diagnostic. It does not start simulated "
            "cameras and never changes the AI-engine pipeline."
        ),
    )
    parser.add_argument(
        "--sample-frame",
        help="benchmark a video or image frame instead of the optimistic blank default",
    )
    parser.add_argument(
        "--model",
        help="model artifact to benchmark; defaults to AI_MODEL_PATH or epoch50.pt",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    device = resolve_device()
    print(f"[capacity] device: {device}")
    if device == "cpu":
        print("[capacity] WARNING: CPU result is for diagnostic use only.")

    if args.sample_frame:
        frame = load_sample_frame(args.sample_frame)
        print(f"[capacity] benchmarking against {args.sample_frame}")
    else:
        frame = synthetic_frame()
        print("[capacity] benchmarking against a blank frame (optimistic)")

    model_path = resolve_model_path(args.model)
    print(f"[capacity] model: {model_path}")
    detector = AccidentDetector(model_path, device=device)

    latency: dict[int, float] = {}
    for batch in BATCH_SIZES:
        try:
            latency[batch] = _benchmark(detector, batch, frame)
        except Exception as exc:
            print(f"[capacity] batch {batch} failed ({exc}); stopping the sweep")
            break
        print(f"[capacity] batch {batch}: {latency[batch]:.1f} ms")

    if not latency:
        print("[capacity] could not benchmark even a single frame")
        return 1

    capacity_15 = capacity_from_latency(latency, 15.0)
    capacity_10 = capacity_from_latency(latency, 10.0)
    print(
        f"\n[capacity] inference-only estimate: {capacity_15} camera(s) at 15 FPS, "
        f"or {capacity_10} at 10 FPS."
    )
    if _grid_limited(latency, capacity_15) or _grid_limited(latency, capacity_10):
        print(
            f"[capacity] NOTE: the estimate reached the largest tested batch "
            f"({max(latency)}), so actual capacity may be higher."
        )
    print("[capacity] this is a diagnostic only; production is unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
