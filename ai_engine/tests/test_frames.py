import pytest

np = pytest.importorskip("numpy")
torch = pytest.importorskip("torch")

import frames  # noqa: E402


def test_to_bgr_is_identity_for_an_ndarray():
    """The software reader already produces a BGR ndarray."""
    frame = np.zeros((4, 4, 3), dtype="uint8")
    assert frames.to_bgr(frame) is frame


def _synthetic_nv12(h, w, y_value, u_value, v_value):
    native = np.empty((h * 3 // 2, w), dtype=np.uint8)
    native[:h, :] = y_value
    native[h:, 0::2] = u_value
    native[h:, 1::2] = v_value
    return torch.from_numpy(native)


def test_to_bgr_accepts_a_gpu_resident_nv12_tensor():
    """CPU-only: torch tensors work without CUDA, and the conversion itself
    is pure numpy after .cpu() (ai_engine/docs/AI_ENGINE_GPU_INTEGRATION_PLAN.md section
    7.1) — no GPU needed to test the arithmetic."""
    native = _synthetic_nv12(4, 4, y_value=128, u_value=128, v_value=128)
    out = frames.to_bgr(native, full_range=False)
    assert out.shape == (4, 4, 3)
    assert out.dtype == np.uint8


def test_to_bgr_neutral_chroma_is_near_grey():
    """Y=U=V=128 (mid-grey, limited range) should decode close to a neutral
    grey in every channel — a sanity check on the coefficient wiring, not a
    substitute for the exact-match check against real decoded frames."""
    native = _synthetic_nv12(4, 4, y_value=128, u_value=128, v_value=128)
    out = frames.to_bgr(native, full_range=False)
    assert np.all(np.abs(out.astype(int) - 128) < 20)


def test_to_bgr_full_range_and_limited_range_disagree():
    """The full/limited branch must actually change the result — otherwise
    gpu_camera.GpuCameraStream.full_range (read from the live stream) would
    be silently ignored."""
    native = _synthetic_nv12(4, 4, y_value=200, u_value=90, v_value=180)
    limited = frames.to_bgr(native, full_range=False)
    full = frames.to_bgr(native, full_range=True)
    assert not np.array_equal(limited, full)


def test_to_bgr_upsamples_chroma_nearest_neighbour_like_the_kernel():
    """Matches the CUDA kernel's integer (x/2, y/2) chroma indexing exactly
    (ai_engine/docs/AI_ENGINE_GPU_INTEGRATION_PLAN.md section 6.2) -- a 2x2 luma block
    sharing one chroma sample must decode to a UNIFORM colour, not a
    bilinear blend across the block boundary."""
    h, w = 4, 4
    native = np.zeros((h * 3 // 2, w), dtype=np.uint8)
    native[:h, :] = 160
    # Two different chroma pairs for the top and bottom halves.
    native[h, 0::2] = 90
    native[h, 1::2] = 200
    native[h + 1, 0::2] = 60
    native[h + 1, 1::2] = 220
    out = frames.to_bgr(torch.from_numpy(native), full_range=False)
    top_left_block = out[0:2, 0:2]
    assert np.all(top_left_block == top_left_block[0, 0])


def test_to_bgr_rejects_an_unknown_frame_type():
    with pytest.raises(TypeError):
        frames.to_bgr(object())
