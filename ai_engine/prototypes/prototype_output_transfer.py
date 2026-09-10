"""THROWAWAY end-to-end-head output transfer/coordinate parity probe."""

import sys
from pathlib import Path

# ai_engine is not a package (CLAUDE.md): its modules are imported flat, which
# works because ai_engine/ is normally the running script's own directory. This
# file lives one level down, so put ai_engine/ back on the path first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import json
import time
from pathlib import Path

import cv2
import numpy as np
import psutil
import torch
from detector import AccidentDetector, Detection, _to_detection


def cpu_outputs(predictions, predictor, tensor, originals, reciprocal=False):
    if isinstance(predictions, (tuple, list)):
        predictions = predictions[0]
    if predictions.ndim != 3 or predictions.shape[-1] != 6:
        raise RuntimeError("Only this end-to-end six-value output head is supported")
    if predictions.dtype != torch.float32:
        raise RuntimeError("Only float32 model output has been validated")
    host = predictions.detach().cpu()
    if not reciprocal:
        return [
            _to_detection(r) for r in predictor.postprocess(host, tensor, originals)
        ]
    if predictor.args.classes is not None:
        raise RuntimeError("Class filters outside this diagnostic envelope")
    outputs = []
    ih, iw = tensor.shape[2:]
    for rows, image in zip(host, originals, strict=True):
        rows = rows[rows[:, 4] > predictor.args.conf][: predictor.args.max_det].clone()
        h, w = image.shape[:2]
        gain = min(ih / h, iw / w)
        px = round((iw - w * gain) / 2 - 0.1)
        py = round((ih - h * gain) / 2 - 0.1)
        rows[:, 0] -= px
        rows[:, 2] -= px
        rows[:, 1] -= py
        rows[:, 3] -= py
        inverse = float(np.float32(1) / np.float32(gain))
        rows[:, :4] *= inverse
        rows[:, 0].clamp_(0, w)
        rows[:, 2].clamp_(0, w)
        rows[:, 1].clamp_(0, h)
        rows[:, 3].clamp_(0, h)
        selected = [row for row in rows.tolist() if int(row[5]) == 0]
        outputs.append(
            Detection(
                [tuple(row[:4]) for row in selected], [row[4] for row in selected]
            )
        )
    return outputs


@torch.inference_mode()
def main():
    if not psutil.sensors_battery().power_plugged:
        raise RuntimeError("AC required")
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
    captures = [
        cv2.VideoCapture(str(root / f"ai_engine/eval/clips/{name}.mp4"))
        for name in names
    ]
    detector = AccidentDetector(root / "ai_engine/epoch50.engine")
    rows = []
    try:
        for frame_index in range(0, 90, 3):
            images = []
            for cap in captures:
                frame = None
                for _ in range(3):
                    ok, frame = cap.read()
                    if not ok:
                        raise RuntimeError("Unexpected EOF")
                images.append(frame)
            detector.predict_batch(images)
            predictor = detector.model.predictor
            tensor = predictor.preprocess(images)
            predictions = predictor.inference(tensor)
            expected = [
                _to_detection(r)
                for r in predictor.postprocess(predictions, tensor, images)
            ]
            cpu = cpu_outputs(predictions, predictor, tensor, images)
            reciprocal = cpu_outputs(
                predictions, predictor, tensor, images, reciprocal=True
            )
            rows.append(
                {
                    "frame_index": frame_index + 2,
                    "cpu_exact": expected == cpu,
                    "reciprocal_exact": expected == reciprocal,
                    "accident_boxes": sum(len(d.boxes) for d in expected),
                }
            )
            print(json.dumps(rows[-1]), flush=True)
    finally:
        for cap in captures:
            cap.release()
    output = (
        root
        / "var/log/gpu-resident"
        / f"output-check-{time.strftime('%Y%m%d-%H%M%S')}.json"
    )
    output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(output),
                "cpu_exact": sum(r["cpu_exact"] for r in rows),
                "reciprocal_exact": sum(r["reciprocal_exact"] for r in rows),
                "batches": len(rows),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
