"""Shared frame-materialisation helper.

Snapshot code must go through here so it never depends on which reader is
running (AI_ENGINE_GPU_INTEGRATION_PLAN.md section 7.1). The software reader
already produces a BGR ndarray, so `to_bgr()` is identity for it — byte-
identical to the pre-Phase-2 code path. The GPU reader produces a device-
resident NV12 tensor with no BGR form; this module does that conversion,
off the hot path: accidents are rare, and converting every frame would
reintroduce the full-resolution CPU cost the GPU path exists to remove.
"""

import numpy as np

# Fixed-point BT.601 YUV -> RGB coefficients, full-range vs limited-range.
# Identical to gpu_preprocess.SOURCE's `gray_at()` before its grayscale fold
# and resize — the same arithmetic already validated against the software
# path's decode by the Phase 1 parity gate (17/17 clips, exact), just run at
# full resolution instead of the small model-input tensor, and stopping
# short of the grayscale reduction: evidence must be colour (accident.py's
# docstring), not the grayscale tensor the model sees.
_LIMITED = {"b_u": 16525, "g_u": -3209, "g_v": -6660, "r_v": 13075}
_FULL = {"b_u": 14516, "g_u": -2819, "g_v": -5850, "r_v": 11485}


def _nv12_to_bgr(native: np.ndarray, *, full_range: bool) -> np.ndarray:
    """Full-resolution NV12 -> BGR, nearest-neighbour chroma upsample —
    matching the CUDA kernel's `(x/2, y/2)` integer indexing exactly, not a
    bilinear guess.
    """
    h = native.shape[0] * 2 // 3
    w = native.shape[1]
    y = native[:h, :].astype(np.int32)
    uv = native[h : h + h // 2, :w].reshape(h // 2, w // 2, 2).astype(np.int32)
    u = np.repeat(np.repeat(uv[..., 0], 2, axis=0), 2, axis=1)[:h, :w]
    v = np.repeat(np.repeat(uv[..., 1], 2, axis=0), 2, axis=1)[:h, :w]

    coef = _FULL if full_range else _LIMITED
    yy = y if full_range else ((y * 8 - 128) * 9539) >> 16
    uu = (u - 128) * 8
    vv = (v - 128) * 8

    b = np.clip(yy + ((uu * coef["b_u"]) >> 16), 0, 255)
    g = np.clip(yy + ((uu * coef["g_u"]) >> 16) + ((vv * coef["g_v"]) >> 16), 0, 255)
    r = np.clip(yy + ((vv * coef["r_v"]) >> 16), 0, 255)

    return np.stack([b, g, r], axis=-1).astype(np.uint8)


def to_bgr(frame, *, full_range: bool = False):
    """Materialise an operator-facing BGR image from whatever a reader
    produced.

    `full_range` is the triggering camera's own colour-range metadata
    (gpu_camera.GpuCameraStream.full_range, read from the live stream at
    connect time) — ignored for the software path, which has no such
    concept because OpenCV's FFmpeg backend already applied it.
    """
    if isinstance(frame, np.ndarray):
        return frame
    import torch

    if isinstance(frame, torch.Tensor):
        native = frame.detach().cpu().numpy()
        return _nv12_to_bgr(native, full_range=full_range)
    raise TypeError(f"to_bgr() cannot handle a frame of type {type(frame)!r}")
