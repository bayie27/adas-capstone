"""Investigation only: original-clip preprocessing and batch-stage measurements.

Run from the repository root with uv run python. Does not change production.
"""

import sys
from pathlib import Path

# ai_engine is not a package (CLAUDE.md): its modules are imported flat, which
# works because ai_engine/ is normally the running script's own directory. This
# file lives one level down, so put ai_engine/ back on the path first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import cv2
import detector as detector_module
import numpy as np
from config import resolve_model_path
from detector import AccidentDetector, to_gray


def summary(values):
    return {
        "median_ms": statistics.median(values),
        "p95_ms": float(np.percentile(values, 95)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--decode", action="store_true")
    args = parser.parse_args()
    from ultralytics.data.augment import LetterBox

    names = [
        "airbase",
        "dekwatro",
        "car-motor-motor",
        "motor-motor-night",
        "jeep-yellow-car",
        "truck-student-car",
    ]
    frames = []
    for name in names:
        cap = cv2.VideoCapture(f"ai_engine/eval/clips/{name}.mp4")
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError(name)
        frames.append(frame)
    print(
        json.dumps(
            {
                "clips": dict(zip(names, [f.shape for f in frames], strict=True)),
                "opencv_threads": cv2.getNumThreads(),
            }
        ),
        flush=True,
    )
    if args.decode:

        def decode_clip(name, threads):
            cap = cv2.VideoCapture(
                f"ai_engine/eval/clips/{name}.mp4",
                cv2.CAP_FFMPEG,
                [cv2.CAP_PROP_N_THREADS, threads],
            )
            count = 0
            start = time.perf_counter()
            try:
                while count < 90:
                    ok, _ = cap.read()
                    if not ok:
                        break
                    count += 1
                return {
                    "clip": name,
                    "frames": count,
                    "seconds": time.perf_counter() - start,
                    "actual_threads": cap.get(cv2.CAP_PROP_N_THREADS),
                }
            finally:
                cap.release()

        for threads in [0, 1, 2, 4, 0]:
            start = time.perf_counter()
            cpu = time.process_time()
            with ThreadPoolExecutor(max_workers=6) as pool:
                rows = list(
                    pool.map(lambda name, n=threads: decode_clip(name, n), names)
                )
            print(
                json.dumps(
                    {
                        "decode_thread_request": threads,
                        "wall_seconds": time.perf_counter() - start,
                        "process_cpu_seconds": time.process_time() - cpu,
                        "clips": rows,
                    }
                ),
                flush=True,
            )
    for auto in [False, True]:
        letterbox = LetterBox((640, 640), auto=auto, stride=32)
        baseline_times, candidate_times, differences = [], [], []
        for frame in frames:
            expected = letterbox(image=to_gray(frame))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = letterbox(image=gray[..., None])
            actual = np.repeat(small, 3, axis=2)
            differences.append(
                {
                    "max_pixel_delta": int(
                        np.abs(
                            expected.astype(np.int16) - actual.astype(np.int16)
                        ).max()
                    ),
                    "shape": expected.shape,
                }
            )
        for _ in range(30):
            start = time.perf_counter()
            for f in frames:
                letterbox(image=to_gray(f))
            baseline_times.append((time.perf_counter() - start) * 1000)
            start = time.perf_counter()
            for f in frames:
                g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
                np.repeat(letterbox(image=g[..., None]), 3, axis=2)
            candidate_times.append((time.perf_counter() - start) * 1000)
        print(
            json.dumps(
                {
                    "auto_padding": auto,
                    "baseline_preparation": summary(baseline_times),
                    "single_channel_until_letterboxed": summary(candidate_times),
                    "pixel_comparison": differences,
                }
            ),
            flush=True,
        )
    if not args.gpu:
        return
    import torch

    detector = AccidentDetector(resolve_model_path("ai_engine/epoch50.engine"))
    detector.predict_batch([frames[0]])
    predictor = detector.model.predictor
    metrics = {}
    for stage in ["preprocess", "inference", "postprocess"]:
        original = getattr(predictor, stage)

        def timed(*a, _fn=original, _stage=stage, **kw):
            torch.cuda.synchronize()
            start = time.perf_counter()
            result = _fn(*a, **kw)
            torch.cuda.synchronize()
            metrics.setdefault(_stage, []).append((time.perf_counter() - start) * 1000)
            if _stage == "preprocess":
                metrics["tensor_shape"] = list(result.shape)
            return result

        setattr(predictor, stage, timed)
    for name, batch in [
        ("homogeneous_original", [frames[0]] * 6),
        ("mixed_original", frames),
        ("homogeneous_original_repeat", [frames[0]] * 6),
    ]:
        for _ in range(8):
            detector.predict_batch(batch)
        metrics.clear()
        times = []
        for _ in range(25):
            start = time.perf_counter()
            detector.predict_batch(batch)
            times.append((time.perf_counter() - start) * 1000)
        print(
            json.dumps(
                {
                    "case": name,
                    "total_instrumented": summary(times),
                    "stages": {
                        k: v if k == "tensor_shape" else summary(v)
                        for k, v in metrics.items()
                    },
                }
            ),
            flush=True,
        )

    # Remove synchronized stage wrappers for a paired whole-call comparison.
    for stage in ["preprocess", "inference", "postprocess"]:
        setattr(predictor, stage, getattr(type(predictor), stage).__get__(predictor))
    original_transform = predictor.pre_transform
    original_gray = detector_module.to_gray

    def lower_copy(images):
        same = len({im.shape for im in images}) == 1
        box = LetterBox(
            predictor.imgsz,
            auto=same
            and predictor.args.rect
            and (
                predictor.model.format == "pt"
                or (
                    getattr(predictor.model, "dynamic", False)
                    and predictor.model.format != "imx"
                )
            ),
            stride=predictor.model.stride,
        )
        return [
            np.repeat(
                box(image=cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)[..., None]), 3, axis=2
            )
            for im in images
        ]

    reference_tensor = predictor.preprocess([original_gray(f) for f in frames])
    predictor.pre_transform = lower_copy
    candidate_tensor = predictor.preprocess(frames)
    print(
        json.dumps(
            {
                "identical_mixed_model_tensor": bool(
                    torch.equal(reference_tensor, candidate_tensor)
                )
            }
        ),
        flush=True,
    )
    paired = {"baseline": [], "lower_copy": []}
    outputs_equal = True
    try:
        for iteration in range(40):
            results = {}
            for candidate in [False, True] if iteration % 2 == 0 else [True, False]:
                detector_module.to_gray = (lambda f: f) if candidate else original_gray
                predictor.pre_transform = (
                    lower_copy if candidate else original_transform
                )
                torch.cuda.synchronize()
                start = time.perf_counter()
                results[candidate] = detector.predict_batch(frames)
                torch.cuda.synchronize()
                if iteration >= 5:
                    paired["lower_copy" if candidate else "baseline"].append(
                        (time.perf_counter() - start) * 1000
                    )
            outputs_equal = outputs_equal and results[False] == results[True]
        print(
            json.dumps(
                {
                    "paired_identical_mixed_frames": {
                        k: summary(v) for k, v in paired.items()
                    },
                    "exact_detection_outputs_equal": outputs_equal,
                }
            ),
            flush=True,
        )
    finally:
        detector_module.to_gray = original_gray
        predictor.pre_transform = original_transform


if __name__ == "__main__":
    main()
