"""Diagnostic only: exact-input OpenCV threading and CPU preprocessing sweep.

No live service, production configuration, model, or source clip is modified.
"""

import sys
from pathlib import Path

# ai_engine is not a package (CLAUDE.md): its modules are imported flat, which
# works because ai_engine/ is normally the running script's own directory. This
# file lives one level down, so put ai_engine/ back on the path first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import argparse
import json
import random
import time
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import psutil
from detector import AccidentDetector, _gray_letterbox


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    names = [
        "airbase",
        "dekwatro",
        "car-motor-motor",
        "motor-motor-night",
        "jeep-yellow-car",
        "truck-student-car",
        "car-motor",
        "armored-car-car",
        "red-car-motor",
        "jeep-car",
    ]
    frames = []
    for name in names:
        cap = cv2.VideoCapture(str(root / f"ai_engine/eval/clips/{name}.mp4"))
        try:
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(name)
            frames.append(frame)
        finally:
            cap.release()
    default_threads = cv2.getNumThreads()
    predictor = SimpleNamespace(
        imgsz=(640, 640),
        args=SimpleNamespace(rect=True),
        model=SimpleNamespace(format="engine", dynamic=True, stride=32),
    )
    detector = None
    if args.gpu:
        detector = AccidentDetector(root / "ai_engine/epoch50.engine")
    # Importing Ultralytics changes OpenCV's thread setting; initial is not runtime.
    from ultralytics.data.augment import LetterBox  # noqa: F401

    report = {
        "opencv_initial_threads": default_threads,
        "opencv_runtime_baseline_threads": cv2.getNumThreads(),
        "gpu": args.gpu,
        "cases": [],
    }
    try:
        for name, batch in [
            ("mixed_native_10", frames),
            ("homogeneous_native_10", [frames[0].copy() for _ in frames]),
        ]:
            reference = _gray_letterbox(predictor, batch)
            reference_detections = None
            if detector:
                for _ in range(8):
                    reference_detections = detector.predict_batch(batch)
            settings = list(dict.fromkeys([default_threads, 1, 2, 4, 8]))
            timings = {n: [] for n in settings}
            cpus = {n: [] for n in settings}
            equal = {n: True for n in settings}
            rng = random.Random(20260909)
            for round_number in range(6):
                order = settings.copy()
                rng.shuffle(order)
                for threads in order:
                    cv2.setNumThreads(threads)
                    actual = _gray_letterbox(predictor, batch)
                    equal[threads] &= all(
                        np.array_equal(a, b)
                        for a, b in zip(reference, actual, strict=True)
                    )
                    operation = (
                        (lambda batch=batch: detector.predict_batch(batch))
                        if detector
                        else (lambda batch=batch: _gray_letterbox(predictor, batch))
                    )
                    for _ in range(3):
                        operation()
                    for _ in range(10):
                        start, cpu = time.perf_counter(), time.process_time()
                        result = operation()
                        timings[threads].append((time.perf_counter() - start) * 1000)
                        cpus[threads].append((time.process_time() - cpu) * 1000)
                        if detector:
                            equal[threads] &= result == reference_detections
                print(
                    json.dumps({"case": name, "round_complete": round_number + 1}),
                    flush=True,
                )
            row = {
                "case": name,
                "available_ram_mb": psutil.virtual_memory().available / 2**20,
                "settings": {
                    str(n): {
                        "median_ms": float(np.median(timings[n])),
                        "p95_ms": float(np.percentile(timings[n], 95)),
                        "mean_process_cpu_ms": float(np.mean(cpus[n])),
                        "exact_outputs_equal": bool(equal[n]),
                    }
                    for n in settings
                },
            }
            report["cases"].append(row)
            print(json.dumps(row), flush=True)
    finally:
        cv2.setNumThreads(default_threads)
    output = (
        root
        / "var/log/preprocess-threads"
        / f"{time.strftime('%Y%m%d-%H%M%S')}-{'gpu' if args.gpu else 'cpu'}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report: {output}", flush=True)


if __name__ == "__main__":
    main()
