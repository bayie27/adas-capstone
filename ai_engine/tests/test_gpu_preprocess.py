"""Unit coverage for gpu_preprocess.py.

Format/shape validation and the ffprobe-based colour-range read need no GPU
and run in the default suite. Anything that actually launches the CUDA
kernel (`kernel()`, `prepare_nv12()`) needs a real device and is marked
`gpu` — see AI_ENGINE_GPU_INTEGRATION_PLAN.md section 6.4's "Unit, no GPU
required" list vs. its GPU-required parity gate.
"""

import json
import subprocess
from unittest.mock import Mock

import pytest

torch = pytest.importorskip("torch")

import gpu_preprocess  # noqa: E402
from gpu_preprocess import (  # noqa: E402
    UnsupportedFrameError,
    prepare_nv12,
    source_full_range,
)


def test_prepare_nv12_rejects_wrong_dtype():
    native = torch.zeros((12, 8), dtype=torch.float32)
    with pytest.raises(UnsupportedFrameError):
        prepare_nv12(native, square=False, dtype=torch.float32, full_range=False)


def test_prepare_nv12_rejects_wrong_ndim():
    native = torch.zeros((3, 12, 8), dtype=torch.uint8)
    with pytest.raises(UnsupportedFrameError):
        prepare_nv12(native, square=False, dtype=torch.float32, full_range=False)


def test_prepare_nv12_rejects_upscaling():
    # h = 12*2//3 = 8, w = 8; both well under the 640 target -> ratio > 1.
    native = torch.zeros((12, 8), dtype=torch.uint8)
    with pytest.raises(UnsupportedFrameError, match="Upscaling"):
        prepare_nv12(native, square=False, dtype=torch.float32, full_range=False)


def test_prepare_nv12_rejects_odd_plane_layout():
    # h % 2 != 0: shape[0] = 9 -> h = 9*2//3 = 6 (ok), but shape[0] % 3 != 0
    native = torch.zeros((10, 8), dtype=torch.uint8)  # 10 % 3 != 0
    with pytest.raises(UnsupportedFrameError):
        prepare_nv12(native, square=False, dtype=torch.float32, full_range=False)


def _fake_ffprobe(monkeypatch, pix_fmt, color_range):
    payload = json.dumps(
        {"streams": [{"pix_fmt": pix_fmt, "color_range": color_range}]}
    )

    def _run(command, **kwargs):
        assert command[0] == "ffprobe"
        return Mock(stdout=payload)

    monkeypatch.setattr(subprocess, "run", _run)


def test_source_full_range_true_for_yuvj420p(monkeypatch):
    _fake_ffprobe(monkeypatch, "yuvj420p", None)
    assert source_full_range("clip.mp4") is True


def test_source_full_range_true_for_explicit_pc_range(monkeypatch):
    _fake_ffprobe(monkeypatch, "yuv420p", "pc")
    assert source_full_range("clip.mp4") is True


def test_source_full_range_false_for_limited_range(monkeypatch):
    _fake_ffprobe(monkeypatch, "yuv420p", "tv")
    assert source_full_range("clip.mp4") is False


def test_source_full_range_rejects_unsupported_pixel_format(monkeypatch):
    _fake_ffprobe(monkeypatch, "yuv422p", "tv")
    with pytest.raises(UnsupportedFrameError):
        source_full_range("clip.mp4")


def test_source_full_range_rejects_no_video_stream(monkeypatch):
    def _run(command, **kwargs):
        return Mock(stdout=json.dumps({"streams": []}))

    monkeypatch.setattr(subprocess, "run", _run)
    with pytest.raises(UnsupportedFrameError):
        source_full_range("clip.mp4")


def test_source_full_range_forces_tcp_for_rtsp_urls(monkeypatch):
    captured = {}

    def _run(command, **kwargs):
        captured["command"] = command
        return Mock(
            stdout=json.dumps(
                {"streams": [{"pix_fmt": "yuv420p", "color_range": "tv"}]}
            )
        )

    monkeypatch.setattr(subprocess, "run", _run)
    source_full_range("rtsp://camera/1")

    command = captured["command"]
    assert "-rtsp_transport" in command
    assert command[command.index("-rtsp_transport") + 1] == "tcp"


def test_source_full_range_does_not_force_transport_for_a_file_path(monkeypatch):
    captured = {}

    def _run(command, **kwargs):
        captured["command"] = command
        return Mock(
            stdout=json.dumps(
                {"streams": [{"pix_fmt": "yuv420p", "color_range": "tv"}]}
            )
        )

    monkeypatch.setattr(subprocess, "run", _run)
    source_full_range("clip.mp4")

    assert "-rtsp_transport" not in captured["command"]


def test_kernel_raises_without_cuda(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    gpu_preprocess.kernel.cache_clear()
    try:
        with pytest.raises(UnsupportedFrameError):
            gpu_preprocess.kernel()
    finally:
        gpu_preprocess.kernel.cache_clear()


@pytest.mark.gpu
class TestKernelOnRealDevice:
    """Needs an actual CUDA device — excluded from the default run (pyproject
    `gpu` marker)."""

    def test_compute_capability_matches_torch(self):
        major, minor = torch.cuda.get_device_capability()
        assert (
            gpu_preprocess._compute_capability() == f"compute_{major}{minor}".encode()
        )

    def test_prepare_nv12_output_shape_square_vs_rect(self):
        native = torch.zeros((1296 * 3 // 2, 2304), dtype=torch.uint8, device="cuda")
        rect = prepare_nv12(native, square=False, dtype=torch.float32, full_range=False)
        square = prepare_nv12(
            native, square=True, dtype=torch.float32, full_range=False
        )
        assert rect.shape == (1, 3, 384, 640)
        assert square.shape == (1, 3, 640, 640)

    def test_prepare_nv12_output_is_normalised_to_unit_range(self):
        native = torch.full((768 * 3 // 2, 1024), 255, dtype=torch.uint8, device="cuda")
        out = prepare_nv12(native, square=True, dtype=torch.float32, full_range=True)
        assert out.max().item() <= 1.0
        assert out.min().item() >= 0.0

    def test_prepare_nv12_respects_requested_dtype(self):
        native = torch.zeros((768 * 3 // 2, 1024), dtype=torch.uint8, device="cuda")
        out = prepare_nv12(native, square=True, dtype=torch.float16, full_range=False)
        assert out.dtype == torch.float16
