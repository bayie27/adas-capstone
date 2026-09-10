"""THROWAWAY tensor parity gate for the fixed-point NV12 CUDA prototype."""

import sys
from pathlib import Path

# ai_engine is not a package (CLAUDE.md): its modules are imported flat, which
# works because ai_engine/ is normally the running script's own directory. This
# file lives one level down, so put ai_engine/ back on the path first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import json
import time
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import psutil
import torch
from detector import _gray_letterbox
from prototype_exact_gpu import prepare_nv12, source_full_range
from prototype_gpu_decode import load_decoder


@torch.inference_mode()
def main():
    if not psutil.sensors_battery().power_plugged:
        raise RuntimeError("AC required")
    nvc, handles = load_decoder()
    root = Path(__file__).resolve().parents[1]
    predictor = SimpleNamespace(
        imgsz=(640, 640),
        args=SimpleNamespace(rect=True),
        model=SimpleNamespace(format="engine", dynamic=True, stride=32),
    )
    rows = []
    for path in sorted((root / "ai_engine/eval/clips").glob("*.mp4")):
        full_range = source_full_range(path)
        decoder = nvc.SimpleDecoder(
            str(path),
            use_device_memory=True,
            decoder_cache_size=1,
            output_color_type=nvc.OutputColorType.NATIVE,
        )
        capture = cv2.VideoCapture(str(path))
        try:
            for index in range(3):
                ok, bgr = capture.read()
                if not ok:
                    raise RuntimeError(path.name)
                decoded = decoder.get_batch_frames(1)
                native = torch.from_dlpack(decoded[0])
                for square in [False, True]:
                    predictor.args.rect = not square
                    expected = _gray_letterbox(predictor, [bgr])[0]
                    expected = (
                        torch.from_numpy(
                            np.ascontiguousarray(expected.transpose(2, 0, 1))
                        )[None]
                        .to("cuda")
                        .float()
                        .div_(255)
                    )
                    actual = prepare_nv12(native, square=square, full_range=full_range)
                    equal = torch.equal(actual, expected)
                    rows.append(
                        {
                            "clip": path.name,
                            "frame": index,
                            "square": square,
                            "exact": equal,
                            "different_values": int((actual != expected).sum()),
                            "max_delta": float((actual - expected).abs().max()),
                        }
                    )
                del native, decoded
            print(json.dumps(rows[-6:]), flush=True)
        finally:
            capture.release()
            del decoder
    output = (
        root
        / "var/log/gpu-resident"
        / f"exact-check-{time.strftime('%Y%m%d-%H%M%S')}.json"
    )
    output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "exact": sum(row["exact"] for row in rows),
                "total": len(rows),
                "report": str(output),
            }
        ),
        flush=True,
    )
    for handle in handles:
        handle.close()


if __name__ == "__main__":
    main()
