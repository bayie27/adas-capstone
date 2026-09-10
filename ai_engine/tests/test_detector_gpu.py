"""GPU batch-path regression coverage that needs a real CUDA device and the
adopted checkpoint, but not ai_engine/eval/clips — marked `gpu`, not `clips`.

The full cross-path parity gate (17 clips, tensors + detections + events)
lives in test_gpu_parity.py, marked `clips`.
"""

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import config  # noqa: E402
from detector import AccidentDetector  # noqa: E402
from gpu_preprocess import UnsupportedFrameError  # noqa: E402

pytestmark = pytest.mark.gpu


def _native(h, w, seed=0):
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, (h * 3 // 2, w), dtype=np.uint8)
    return torch.from_numpy(arr).cuda()


@pytest.fixture(scope="module")
def warmed_detector():
    det = AccidentDetector(config.DEFAULT_WEIGHTS_PATH)
    det.warm_up_gpu()
    return det


def test_predict_batch_gpu_returns_one_result_per_camera_not_per_warmup_batch(
    warmed_detector,
):
    """Regression for a real bug found while building this path: Ultralytics'
    DetectionPredictor.construct_results() zips its outputs against
    predictor.batch[0] (image paths), and predictor.batch is a leftover
    1-frame tuple from warm_up_gpu()'s predict() calls. Without resetting it
    before postprocess(), a real N-camera batch silently truncates to ONE
    result and every other camera's detections vanish with no error —
    reproduced directly against the real predictor, not assumed from reading
    the source.
    """
    natives = [_native(1296, 2304, seed=i) for i in range(3)]
    result = warmed_detector.predict_batch_gpu(natives, [False, False, False])
    assert len(result) == 3


def test_predict_batch_gpu_of_one_camera(warmed_detector):
    result = warmed_detector.predict_batch_gpu([_native(1296, 2304)], [False])
    assert len(result) == 1


def test_predict_batch_gpu_of_ten_cameras(warmed_detector):
    natives = [_native(1296, 2304, seed=i) for i in range(10)]
    result = warmed_detector.predict_batch_gpu(natives, [False] * 10)
    assert len(result) == 10


def test_predict_batch_gpu_of_nothing_returns_nothing(warmed_detector):
    assert warmed_detector.predict_batch_gpu([], []) == []


def test_predict_batch_gpu_before_warm_up_raises():
    det = AccidentDetector(config.DEFAULT_WEIGHTS_PATH)
    with pytest.raises(RuntimeError, match="warm_up_gpu"):
        det.predict_batch_gpu([_native(1296, 2304)], [False])


def test_warm_up_gpu_is_idempotent(warmed_detector):
    dtype_before = warmed_detector._gpu_input_dtype
    warmed_detector.warm_up_gpu()
    assert warmed_detector._gpu_input_dtype == dtype_before


def test_predict_batch_gpu_raises_for_a_malformed_frame_in_a_mixed_batch(
    warmed_detector,
):
    """Lifecycle case: 'one failing camera while nine continue' (plan
    section 7.2). pipeline._infer()'s isolation re-run relies on a bad
    camera's frame raising, not silently producing garbage or hanging — this
    confirms predict_batch_gpu does that; the generic re-run mechanism
    itself is already covered by test_pipeline.py's fake-detector tests,
    which don't care which detector method underlies it.
    """
    good = _native(1296, 2304, seed=1)
    bad = torch.zeros((3, 8, 8), dtype=torch.uint8, device="cuda")  # wrong ndim
    with pytest.raises(UnsupportedFrameError):
        warmed_detector.predict_batch_gpu([good, bad], [False, False])


def test_predict_batch_gpu_handles_a_resolution_change_across_sequential_calls(
    warmed_detector,
):
    """A stream whose resolution changes mid-run (plan section 7.2) is not
    a special case: nothing caches the previous call's shape.
    _letterbox_auto_for_shapes and _orig_placeholder are both keyed off the
    ACTUAL batch/shape on every call."""
    first = warmed_detector.predict_batch_gpu([_native(1296, 2304)], [False])
    second = warmed_detector.predict_batch_gpu([_native(720, 1280)], [False])
    third = warmed_detector.predict_batch_gpu([_native(1296, 2304)], [False])
    assert len(first) == len(second) == len(third) == 1
