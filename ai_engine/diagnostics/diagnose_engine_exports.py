"""Compare explicit TensorRT exports on identical native-resolution frames."""

import sys
from pathlib import Path

# ai_engine is not a package (CLAUDE.md): its modules are imported flat, which
# works because ai_engine/ is normally the running script's own directory. This
# file lives one level down, so put ai_engine/ back on the path first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np
import psutil
import pynvml
import torch
from config import resolve_model_path
from detector import AccidentDetector

NAMES = [
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


def stats(values):
    return {
        "median_ms": float(np.median(values)),
        "p95_ms": float(np.percentile(values, 95)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    battery = psutil.sensors_battery()
    if battery and not battery.power_plugged:
        raise RuntimeError("AC power required")
    model = resolve_model_path(args.model)
    output = Path("var/log/engine-comparison")
    output.mkdir(parents=True, exist_ok=True)
    frames, hashes = [], []
    for name in NAMES:
        capture = cv2.VideoCapture(f"ai_engine/eval/clips/{name}.mp4")
        # Match the exact first decoded frame across runs, without modifying clips.
        ok, frame = capture.read()
        capture.release()
        if not ok:
            raise RuntimeError(name)
        frames.append(frame)
        hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
    pynvml.nvmlInit()
    gpu = pynvml.nvmlDeviceGetHandleByIndex(0)
    detector = AccidentDetector(model)
    detector.predict_batch(frames[:1])
    predictor = detector.model.predictor
    engine = predictor.model.backend.model
    start_event, end_event = (
        torch.cuda.Event(enable_timing=True),
        torch.cuda.Event(enable_timing=True),
    )
    gpu_times = []
    original = predictor.inference

    def forward(*a, **kw):
        start_event.record()
        result = original(*a, **kw)
        end_event.record()
        end_event.synchronize()
        gpu_times.append(start_event.elapsed_time(end_event))
        return result

    predictor.inference = forward
    profile = engine.get_tensor_profile_shape("images", 0)
    print(
        json.dumps(
            {
                "label": args.label,
                "model": str(model),
                "profile_min_opt_max": list(map(list, profile)),
                "gpu_used_mb_after_load": pynvml.nvmlDeviceGetMemoryInfo(gpu).used
                / 2**20,
            }
        ),
        flush=True,
    )
    report = {
        "label": args.label,
        "model": str(model),
        "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
        "frame_hashes": hashes,
        "profile_min_opt_max": list(map(list, profile)),
        "cases": [],
    }
    for kind in ["blank720", "mixed_native"]:
        source = (
            [np.zeros((720, 1280, 3), dtype=np.uint8)] * 10
            if kind == "blank720"
            else frames
        )
        for size in [1, 4, 6, 8, 10]:
            batch = source[:size]
            for _ in range(8):
                detector.predict_batch(batch)
            gpu_times.clear()
            total = []
            for _ in range(25):
                begin = time.perf_counter()
                detections = detector.predict_batch(batch)
                total.append((time.perf_counter() - begin) * 1000)
            row = {
                "kind": kind,
                "batch": size,
                "whole_detector": stats(total),
                "gpu_forward": stats(gpu_times),
                "gpu_used_mb": pynvml.nvmlDeviceGetMemoryInfo(gpu).used / 2**20,
                "gpu_sm_mhz": pynvml.nvmlDeviceGetClockInfo(gpu, 1),
                "gpu_temp": pynvml.nvmlDeviceGetTemperature(gpu, 0),
                "detections": [d._asdict() for d in detections],
            }
            report["cases"].append(row)
            print(
                json.dumps({k: v for k, v in row.items() if k != "detections"}),
                flush=True,
            )
    report["variable_batch_smoke"] = []
    for size in [10, 1, 7, 3, 10, 5, 2, 9, 4, 10]:
        detections = detector.predict_batch(frames[:size])
        report["variable_batch_smoke"].append(
            {"requested": size, "returned": len(detections)}
        )
    (output / f"{args.label}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "saved": str(output / f"{args.label}.json"),
                "variable_batches_passed": all(
                    r["requested"] == r["returned"]
                    for r in report["variable_batch_smoke"]
                ),
            }
        ),
        flush=True,
    )
    pynvml.nvmlShutdown()


if __name__ == "__main__":
    main()
