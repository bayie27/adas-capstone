"""THROWAWAY paired event evaluation: current CPU pixels versus GPU pipeline.

Run one clip per process. No thresholds or production behavior are changed.
"""

import sys
from pathlib import Path

# ai_engine is not a package (CLAUDE.md): its modules are imported flat, which
# works because ai_engine/ is normally the running script's own directory. This
# file lives one level down, so put ai_engine/ back on the path first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import argparse
import json
from pathlib import Path

import cv2
import psutil
import torch
from accumulate import Accumulator
from detector import AccidentDetector, _to_detection
from prototype_exact_gpu import prepare_nv12, source_full_range
from prototype_gpu_decode import load_decoder
from prototype_gpu_pipeline import prepare


@torch.inference_mode()
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--sample-fps", type=float, default=10)
    parser.add_argument("--isolate", action="store_true")
    parser.add_argument("--exact", action="store_true")
    args = parser.parse_args()
    if args.exact and args.isolate:
        parser.error("Use --exact or --isolate, not both")
    battery = psutil.sensors_battery()
    if battery and not battery.power_plugged:
        raise RuntimeError("AC power is required for this GPU experiment")
    root = Path(__file__).resolve().parents[1]
    path = root / "ai_engine/eval/clips" / args.clip
    nvc, handles = load_decoder()
    detector = AccidentDetector(root / "ai_engine/epoch50.engine")
    full_range = source_full_range(path) if args.exact else False
    decoder = nvc.SimpleDecoder(
        str(path),
        use_device_memory=True,
        decoder_cache_size=1,
        output_color_type=nvc.OutputColorType.NATIVE
        if args.exact
        else nvc.OutputColorType.RGBP,
    )
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    stride = max(1, round(fps / args.sample_fps))
    accumulators = {
        name: Accumulator(iou_link=0.30, threshold=1.0, decay=0.3)
        for name in (
            ["baseline", "gpu", "color_only", "resize_only"]
            if args.isolate
            else ["baseline", "gpu"]
        )
    }
    events = {name: [] for name in accumulators}
    index = 0
    sampled = 0
    exact_detections = 0
    exact_inputs = 0
    captured = [None]
    capture_installed = False
    try:
        while True:
            ok, bgr = cap.read()
            decoded = decoder.get_batch_frames(1)
            if not ok:
                if decoded:
                    raise RuntimeError("CPU/GPU frame count mismatch")
                break
            if not decoded:
                raise RuntimeError("GPU ended before CPU")
            if index % stride == 0:
                baseline = detector.predict_batch([bgr])[0]
                predictor = detector.model.predictor
                dtype = torch.float16 if predictor.model.fp16 else torch.float32
                rgb = torch.from_dlpack(decoded[0])
                if args.exact:
                    tensor = prepare_nv12(rgb, dtype=dtype, full_range=full_range)
                    reference = (
                        captured[0]
                        if capture_installed
                        else predictor.preprocess([bgr])
                    )
                    exact_inputs += torch.equal(tensor, reference)
                    if not capture_installed:
                        original_preprocess = predictor.preprocess

                        def capture_input(images, fn=original_preprocess):
                            captured[0] = fn(images)
                            return captured[0]

                        predictor.preprocess = capture_input
                        capture_installed = True
                else:
                    tensor = prepare(rgb, dtype=dtype)
                predictions = predictor.inference(tensor)
                gpu = _to_detection(
                    predictor.postprocess(predictions, tensor, [bgr])[0]
                )
                sampled += 1
                exact_detections += baseline == gpu
                comparisons = [("baseline", baseline), ("gpu", gpu)]
                if args.isolate:
                    color_bgr = rgb.permute(1, 2, 0).cpu().numpy()[..., ::-1].copy()
                    comparisons.append(
                        ("color_only", detector.predict_batch([color_bgr])[0])
                    )
                    original_rgb = (
                        torch.from_numpy(bgr[..., ::-1].copy())
                        .permute(2, 0, 1)
                        .to("cuda")
                    )
                    resized = prepare(original_rgb, dtype=dtype)
                    predictions = predictor.inference(resized)
                    comparisons.append(
                        (
                            "resize_only",
                            _to_detection(
                                predictor.postprocess(predictions, resized, [bgr])[0]
                            ),
                        )
                    )
                    del original_rgb, resized
                for name, detection in comparisons:
                    for event in accumulators[name].update(
                        index / fps, detection.boxes, detection.confs
                    ):
                        events[name].append(
                            {
                                "t": round(event.t, 2),
                                "box": [round(v, 1) for v in event.box],
                                "score": event.score,
                                "peak_conf": event.peak_conf,
                                "age_s": event.age_s,
                            }
                        )
                torch.cuda.synchronize()
                del rgb, tensor
            del decoded
            index += 1
            if index % 300 == 0:
                battery = psutil.sensors_battery()
                if battery and not battery.power_plugged:
                    raise RuntimeError(
                        "AC power disconnected; stopping incomplete evaluation"
                    )
                print(json.dumps({"clip": args.clip, "frames": index}), flush=True)
    finally:
        cap.release()
        del decoder
    for name in events:
        output = Path(args.output) / name / f"{path.stem}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "video": path.name,
                    "fps": fps,
                    "frames": index,
                    "gray": True,
                    "conf": 0.15,
                    "imgsz": 640,
                    "sample_fps": args.sample_fps,
                    "sampled_frames": sampled,
                    "exact_input_frames": exact_inputs if args.exact else None,
                    "exact_detection_frames": exact_detections,
                    "events": events[name],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "clip": args.clip,
                "sampled": sampled,
                "exact_detection_frames": exact_detections,
                "exact_input_frames": exact_inputs if args.exact else None,
                "baseline_events": events["baseline"],
                "gpu_events": events["gpu"],
                "all_events": events,
            }
        ),
        flush=True,
    )
    for handle in handles:
        handle.close()


if __name__ == "__main__":
    main()
