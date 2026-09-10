"""THROWAWAY GPU decode/preprocess smoke test and offline throughput probe.

Requires the temporary dependencies documented in prototype_gpu_decode.py.
RGB conversion and interpolation are NOT established equivalent to production.
This is not a live capacity or accuracy claim.
"""

import sys
from pathlib import Path

# ai_engine is not a package (CLAUDE.md): its modules are imported flat, which
# works because ai_engine/ is normally the running script's own directory. This
# file lives one level down, so put ai_engine/ back on the path first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import psutil
import torch
import torch.nn.functional as functional
from detector import AccidentDetector, _to_detection
from prototype_gpu_decode import load_decoder


def prepare(rgb, square=False, dtype=torch.float32):
    height, width = rgb.shape[1:]
    ratio = min(640 / height, 640 / width)
    resized_h, resized_w = round(height * ratio), round(width * ratio)
    pad_h, pad_w = 640 - resized_h, 640 - resized_w
    if not square:
        pad_h, pad_w = pad_h % 32, pad_w % 32
    top, left = round(pad_h / 2 - 0.1), round(pad_w / 2 - 0.1)
    bottom, right = round(pad_h / 2 + 0.1), round(pad_w / 2 + 0.1)
    channels = rgb.to(torch.int32)
    gray = (
        (channels[0] * 9798 + channels[1] * 19235 + channels[2] * 3735 + 16384) >> 15
    ).to(torch.float32)
    gray = (
        functional.interpolate(
            gray[None, None],
            size=(resized_h, resized_w),
            mode="bilinear",
            align_corners=False,
        )
        .round()
        .clamp(0, 255)
    )
    gray = functional.pad(gray, (left, right, top, bottom), value=114)
    return gray.to(dtype).div_(255).expand(-1, 3, -1, -1).contiguous()


@torch.inference_mode()
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=1)
    parser.add_argument("--cameras", type=int, choices=[1, 10], default=1)
    args = parser.parse_args()
    battery = psutil.sensors_battery()
    if battery and not battery.power_plugged:
        raise RuntimeError("AC power is required for this GPU experiment")
    nvc, handles = load_decoder()
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
    ][: args.cameras]
    model = AccidentDetector(root / "ai_engine/epoch50.engine")
    decoders, originals = [], []
    for name in names:
        path = root / f"ai_engine/eval/clips/{name}.mp4"
        capture = cv2.VideoCapture(str(path))
        ok, original = capture.read()
        capture.release()
        if not ok:
            raise RuntimeError(name)
        originals.append(original)
        decoders.append(
            nvc.SimpleDecoder(
                str(path),
                use_device_memory=True,
                decoder_cache_size=1,
                output_color_type=nvc.OutputColorType.RGBP,
            )
        )
    model.predict_batch(originals)
    predictor = model.model.predictor
    reference = predictor.preprocess(originals)
    timings, first_comparison = [], None
    for index in range(args.frames):
        torch.cuda.synchronize()
        started = time.perf_counter()
        decoded = [decoder.get_batch_frames(1) for decoder in decoders]
        if not all(decoded):
            break
        tensors = [torch.from_dlpack(frames[0]) for frames in decoded]
        tensor = torch.cat(
            [
                prepare(rgb, square=len(names) != 1, dtype=reference.dtype)
                for rgb in tensors
            ]
        )
        assert tensor.dtype == reference.dtype
        if index == 0:
            first_comparison = {
                "exact_model_tensor": torch.equal(tensor, reference),
                "max_normalized_delta": float((tensor - reference).abs().max()),
                "shape": list(tensor.shape),
            }
        predictions = predictor.inference(tensor)
        results = predictor.postprocess(predictions, tensor, originals)
        detections = [_to_detection(result) for result in results]
        torch.cuda.synchronize()
        elapsed = (time.perf_counter() - started) * 1000
        timings.append(elapsed)
        print(
            json.dumps(
                {
                    "batch": index,
                    "decode_preprocess_inference_ms": elapsed,
                    "accident_boxes": [len(d.boxes) for d in detections],
                }
            ),
            flush=True,
        )
        del tensors, decoded
    result = {
        "note": "offline synchronous prototype; includes startup, NOT live camera capacity",
        "cameras": args.cameras,
        "first_frame_comparison": first_comparison,
        "median_ms": float(np.median(timings)),
        "timings_ms": timings,
    }
    output = (
        root
        / "var/log/gpu-resident"
        / f"pipeline-{time.strftime('%Y%m%d-%H%M%S')}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)
    del decoders
    for handle in handles:
        handle.close()


if __name__ == "__main__":
    main()
