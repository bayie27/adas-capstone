"""Process-local experiments in transfer and profiling overhead; no production edits."""

import sys
from pathlib import Path

# ai_engine is not a package (CLAUDE.md): its modules are imported flat, which
# works because ai_engine/ is normally the running script's own directory. This
# file lives one level down, so put ai_engine/ back on the path first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import json
import random
import time
from pathlib import Path

import cv2
import detector as module
import numpy as np
import torch
from ultralytics.utils import ops


def packed_detection(result):
    rows = [] if result.boxes is None else result.boxes.data.tolist()
    rows = [row for row in rows if int(row[-1]) == module.ACCIDENT_CLASS_ID]
    return module.Detection(
        boxes=[tuple(float(v) for v in row[:4]) for row in rows],
        confs=[float(row[-2]) for row in rows],
    )


def make_gray_upload(predictor):
    def gray_upload(images):
        gray = np.stack([im[..., 0] for im in predictor.pre_transform(images)])
        tensor = torch.from_numpy(gray).to(predictor.device)
        tensor = tensor.half() if predictor.model.fp16 else tensor.float()
        tensor /= 255
        return tensor[:, None].expand(-1, 3, -1, -1).contiguous()

    return gray_upload


def main():
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
    detector = module.AccidentDetector(root / "ai_engine/epoch50.engine")
    detector.predict_batch(frames)
    predictor = detector.model.predictor
    original_preprocess = predictor.preprocess
    original_convert = module._to_detection
    original_clock = ops.Profile.time

    gray_upload = make_gray_upload(predictor)

    arms = ["baseline", "packed_output", "no_profile_sync", "gray_upload", "combined"]
    report = []
    try:
        for case, batch in [
            ("mixed_native_10", frames),
            ("homogeneous_native_10", [frames[0].copy() for _ in frames]),
        ]:
            predictor.preprocess = original_preprocess
            module._to_detection = original_convert
            ops.Profile.time = original_clock
            expected_tensor = original_preprocess(batch)
            candidate_tensor = gray_upload(batch)
            tensor_equal = torch.equal(expected_tensor, candidate_tensor)
            if not tensor_equal:
                raise RuntimeError("Single-channel upload changed the model tensor")
            for _ in range(8):
                expected = detector.predict_batch(batch)
            values = {arm: [] for arm in arms}
            equal = {arm: True for arm in arms}
            rng = random.Random(20260909)
            for iteration in range(5):
                order = arms.copy()
                rng.shuffle(order)
                for arm in order:
                    predictor.preprocess = (
                        gray_upload
                        if arm in {"gray_upload", "combined"}
                        else original_preprocess
                    )
                    module._to_detection = (
                        packed_detection
                        if arm in {"packed_output", "combined"}
                        else original_convert
                    )
                    ops.Profile.time = (
                        (lambda self: time.perf_counter())
                        if arm in {"no_profile_sync", "combined"}
                        else original_clock
                    )
                    for _ in range(3):
                        detector.predict_batch(batch)
                    for _ in range(10):
                        torch.cuda.synchronize()
                        start = time.perf_counter()
                        actual = detector.predict_batch(batch)
                        torch.cuda.synchronize()
                        values[arm].append((time.perf_counter() - start) * 1000)
                        equal[arm] &= actual == expected
                print(json.dumps({"case": case, "round": iteration + 1}), flush=True)
            row = {
                "case": case,
                "opencv_threads": cv2.getNumThreads(),
                "exact_tensor_equal": tensor_equal,
                "arms": {
                    arm: {
                        "median_ms": float(np.median(v)),
                        "p95_ms": float(np.percentile(v, 95)),
                        "exact_detections_equal": bool(equal[arm]),
                    }
                    for arm, v in values.items()
                },
            }
            report.append(row)
            print(json.dumps(row), flush=True)
    finally:
        predictor.preprocess = original_preprocess
        module._to_detection = original_convert
        ops.Profile.time = original_clock
    output = (
        root / "var/log/detector-overhead" / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report: {output}", flush=True)


if __name__ == "__main__":
    main()
