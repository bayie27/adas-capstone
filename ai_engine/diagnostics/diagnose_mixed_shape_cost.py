"""Does a MIXED-RESOLUTION batch cost more than a uniform one? (offline)

Motivation: the 10-camera LAN demo collapsed from ~10 FPS to 0.6 FPS the
moment all ten cameras were Active, and the two that make the difference
(channels 3 and 6) are 2560x1440 while the other eight are 2304x1296.

detector._letterbox_auto_for_shapes() returns False as soon as the batch
holds more than one shape, and predict_batch_gpu() turns that into
`square=True` -- letterboxing to 640x640 instead of 640x384. Against a
TensorRT engine, an input-shape change is not free: the context has to
re-plan for the new shape. The batch composition changes tick to tick
(destructive read()), so `same_shapes` can flip constantly, which would mean
paying that cost over and over.

No RTSP, no backend, no cameras: synthetic NV12 device tensors of the two
real resolutions, pushed straight through the real detector.

Run from the repo root:
    uv run python ai_engine/diagnose_mixed_shape_cost.py
"""

import sys
from pathlib import Path

# ai_engine is not a package (CLAUDE.md): its modules are imported flat, which
# works because ai_engine/ is normally the running script's own directory. This
# file lives one level down, so put ai_engine/ back on the path first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import statistics
import time

import config
import torch
from detector import AccidentDetector

SMALL = (2304, 1296)  # channels 1,2,4,5,7,8,9,10
LARGE = (2560, 1440)  # channels 3 and 6
REPS = 30


def nv12(width: int, height: int):
    """One synthetic NV12 device tensor shaped exactly like NVDEC's output:
    (height * 3 // 2, width) uint8, which detector.predict_batch_gpu maps
    back to (height, width, 3)."""
    return torch.randint(
        0, 255, (height * 3 // 2, width), dtype=torch.uint8, device="cuda"
    )


def bench(detector, batch, label):
    full = [False] * len(batch)
    # Warm the shape in, so the first-call re-plan is not counted as steady state.
    detector.predict_batch_gpu(batch, full)
    torch.cuda.synchronize()
    times = []
    for _ in range(REPS):
        t0 = time.perf_counter()
        detector.predict_batch_gpu(batch, full)
        torch.cuda.synchronize()
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    print(
        f"{label:34} n={len(batch):2}  "
        f"p50={statistics.median(times):7.1f} ms  "
        f"min={times[0]:7.1f}  max={times[-1]:7.1f}"
    )
    return statistics.median(times)


def main():
    detector = AccidentDetector(config.resolve_model_path())
    detector.warm_up_gpu()
    print(f"model: {config.resolve_model_path().name}  device: {detector.device}\n")

    small10 = [nv12(*SMALL) for _ in range(10)]
    small8 = small10[:8]
    large2 = [nv12(*LARGE) for _ in range(2)]
    mixed10 = small8 + large2

    uniform = bench(detector, small10, "uniform 10x 2304x1296")
    bench(detector, small8, "uniform  8x 2304x1296")
    mixed = bench(detector, mixed10, "MIXED 8x2304x1296 + 2x2560x1440")

    # The live case: batch composition changes every tick, so the shape set
    # flips between uniform and mixed over and over.
    print("\nalternating uniform <-> mixed, as the live tick loop does:")
    full_u, full_m = [False] * 10, [False] * 10
    detector.predict_batch_gpu(small10, full_u)
    torch.cuda.synchronize()
    times = []
    for i in range(REPS):
        batch = small10 if i % 2 == 0 else mixed10
        t0 = time.perf_counter()
        detector.predict_batch_gpu(batch, full_u if i % 2 == 0 else full_m)
        torch.cuda.synchronize()
        times.append((time.perf_counter() - t0) * 1000)
    times_sorted = sorted(times)
    print(
        f"{'alternating':34} n=10  "
        f"p50={statistics.median(times):7.1f} ms  "
        f"min={times_sorted[0]:7.1f}  max={times_sorted[-1]:7.1f}"
    )

    print(
        f"\nmixed / uniform = {mixed / uniform:.2f}x   "
        f"alternating / uniform = {statistics.median(times) / uniform:.2f}x"
    )
    print(
        f"tick budget at {config.FPS_BAND_MAX:g} FPS = {1000 / config.FPS_BAND_MAX:.1f} ms"
    )


if __name__ == "__main__":
    main()
