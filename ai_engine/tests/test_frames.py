import pytest

np = pytest.importorskip("numpy")

import frames  # noqa: E402


def test_to_bgr_is_identity_for_an_ndarray():
    """The software reader already produces a BGR ndarray."""
    frame = np.zeros((4, 4, 3), dtype="uint8")
    assert frames.to_bgr(frame) is frame


def test_to_bgr_rejects_a_gpu_resident_frame_for_now():
    """Phase 2 work (AI_ENGINE_GPU_INTEGRATION_PLAN.md section 7.1) — must
    fail loudly rather than silently returning something wrong until it's
    implemented."""
    with pytest.raises(NotImplementedError):
        frames.to_bgr(object())
