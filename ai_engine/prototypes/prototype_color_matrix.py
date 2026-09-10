"""THROWAWAY CPU arithmetic check of YUV matrix hypotheses against OpenCV."""

import json
import subprocess

import cv2
import numpy as np


def main():
    for name in ["airbase", "red-car-motor", "motor-motor-night"]:
        path = f"ai_engine/eval/clips/{name}.mp4"
        cap = cv2.VideoCapture(path)
        ok, reference = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError(name)
        height, width = reference.shape[:2]
        raw = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-threads",
                "1",
                "-i",
                path,
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
        native = np.frombuffer(raw, np.uint8).reshape(height * 3 // 2, width)
        candidates = {"opencv_nv12": cv2.cvtColor(native, cv2.COLOR_YUV2BGR_NV12)}
        y = native[:height].astype(np.float32) - 16
        uv = (
            native[height:].reshape(height // 2, width // 2, 2).astype(np.float32) - 128
        )
        uv_integer = (
            cv2.resize(uv, (width, height), interpolation=cv2.INTER_NEAREST).astype(
                np.int32
            )
            * 8
        )
        y_integer = ((native[:height].astype(np.int32) * 8 - 128) * 9539) >> 16
        u_integer, v_integer = uv_integer[..., 0], uv_integer[..., 1]
        fixed = np.stack(
            [
                y_integer + ((u_integer * 16525) >> 16),
                y_integer + ((u_integer * -3209) >> 16) + ((v_integer * -6660) >> 16),
                y_integer + ((v_integer * 13075) >> 16),
            ],
            axis=2,
        )
        candidates["ffmpeg_601_fixed_point"] = np.clip(fixed, 0, 255).astype(np.uint8)
        for method, interpolation in [
            ("nearest", cv2.INTER_NEAREST),
            ("bilinear", cv2.INTER_LINEAR),
        ]:
            up = cv2.resize(uv, (width, height), interpolation=interpolation)
            u, v = up[..., 0], up[..., 1]
            for label, rv, gu, gv, bu in [
                ("601", 1.596027, -0.391762, -0.812968, 2.017232),
                ("709", 1.792741, -0.213249, -0.532909, 2.112402),
            ]:
                bgr = np.stack(
                    [
                        y * 1.164384 + bu * u,
                        y * 1.164384 + gu * u + gv * v,
                        y * 1.164384 + rv * v,
                    ],
                    axis=2,
                )
                candidates[f"{label}_{method}"] = np.clip(np.rint(bgr), 0, 255).astype(
                    np.uint8
                )
        rows = {}
        for label, candidate in candidates.items():
            delta = np.abs(reference.astype(np.int16) - candidate.astype(np.int16))
            rows[label] = {
                "max_delta": int(delta.max()),
                "mean_delta": float(delta.mean()),
                "different_fraction": float(np.mean(delta != 0)),
            }
        print(json.dumps({"clip": name, "comparisons": rows}), flush=True)


if __name__ == "__main__":
    main()
