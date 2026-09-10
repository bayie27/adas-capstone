"""THROWAWAY GPU-resident decoding/pixel-equivalence investigation.

Run from root with:
uv run --with pynvvideocodec==2.2.2 --with nvidia-cuda-runtime-cu12 python ai_engine/prototype_gpu_decode.py
No production configuration, models or source clips are changed.
"""

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch


def load_decoder():
    package = Path(importlib.util.find_spec("PyNvVideoCodec").origin).parent
    paths = [package]
    for entry in sys.path:
        if Path(entry).is_dir():
            paths.extend(
                p.parent
                for p in Path(entry).glob("nvidia/cuda_runtime/**/cudart64_12.dll")
            )
    # Retain handles; closing them removes the per-process DLL search paths.
    handles = [os.add_dll_directory(str(path)) for path in paths]
    import PyNvVideoCodec as nvc

    return nvc, handles


def main():
    nvc, handles = load_decoder()
    torch.cuda.init()
    root = Path(__file__).resolve().parents[1]
    output = root / "var/log/gpu-resident" / time.strftime("%Y%m%d-%H%M%S")
    output.mkdir(parents=True)
    rows = []
    for name in [
        "airbase",
        "dekwatro",
        "motor-motor-night",
        "red-car-motor",
        "jeep-yellow-car",
    ]:
        path = root / f"ai_engine/eval/clips/{name}.mp4"
        decoder = nvc.SimpleDecoder(
            str(path),
            use_device_memory=True,
            decoder_cache_size=1,
            output_color_type=nvc.OutputColorType.RGBP,
        )
        capture = cv2.VideoCapture(str(path))
        try:
            for index in range(3):
                ok, bgr = capture.read()
                if not ok:
                    raise RuntimeError(name)
                decoded = decoder.get_batch_frames(1)
                if not decoded:
                    raise RuntimeError(f"GPU decoder ended on {name}")
                rgb = torch.from_dlpack(decoded[0])
                cpu_rgb = rgb.permute(1, 2, 0).cpu().numpy()
                difference = np.abs(
                    cpu_rgb.astype(np.int16) - bgr[..., ::-1].astype(np.int16)
                )
                # OpenCV's uint8 grayscale fixed-point coefficients.
                channels = rgb.to(torch.int32)
                gray = (
                    (
                        channels[0] * 9798
                        + channels[1] * 19235
                        + channels[2] * 3735
                        + 16384
                    )
                    >> 15
                ).to(torch.uint8)
                gpu_gray = gray.cpu().numpy()
                cpu_gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                gray_delta = np.abs(
                    gpu_gray.astype(np.int16) - cpu_gray.astype(np.int16)
                )
                same_color_gray = cv2.cvtColor(cpu_rgb, cv2.COLOR_RGB2GRAY)
                row = {
                    "clip": name,
                    "frame": index,
                    "gpu_shape": list(rgb.shape),
                    "gpu_device": str(rgb.device),
                    "rgb_max_delta": int(difference.max()),
                    "rgb_different_fraction": float(np.mean(difference != 0)),
                    "gray_max_delta": int(gray_delta.max()),
                    "gray_different_fraction": float(np.mean(gray_delta != 0)),
                    "gpu_gray_matches_opencv_on_same_rgb": bool(
                        np.array_equal(gpu_gray, same_color_gray)
                    ),
                }
                rows.append(row)
                print(json.dumps(row), flush=True)
                del rgb, decoded, channels, gray
        finally:
            capture.release()
            del decoder
    (output / "pixel-check.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8"
    )
    native_rows = []
    for name in ["airbase", "motor-motor-night", "red-car-motor"]:
        path = root / f"ai_engine/eval/clips/{name}.mp4"
        decoder = nvc.SimpleDecoder(
            str(path),
            use_device_memory=True,
            output_color_type=nvc.OutputColorType.NATIVE,
        )
        decoded = decoder.get_batch_frames(1)
        native = torch.from_dlpack(decoded[0]).cpu().numpy()
        software = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-threads",
                "1",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-pix_fmt",
                "nv12",
                "-f",
                "rawvideo",
                "pipe:1",
            ],
            capture_output=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout
        raw = np.frombuffer(software, dtype=np.uint8).reshape(native.shape)
        row = {
            "clip": name,
            "native_shape": list(native.shape),
            "native_yuv_exact": bool(np.array_equal(native, raw)),
            "native_yuv_max_delta": int(
                np.abs(native.astype(np.int16) - raw.astype(np.int16)).max()
            ),
        }
        native_rows.append(row)
        print(json.dumps(row), flush=True)
        del decoded, decoder
    (output / "native-check.json").write_text(
        json.dumps(native_rows, indent=2), encoding="utf-8"
    )
    print(f"Report: {output}", flush=True)
    for handle in handles:
        handle.close()


if __name__ == "__main__":
    main()
