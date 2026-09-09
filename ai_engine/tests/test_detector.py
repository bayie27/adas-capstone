"""detector.py imports cv2 and (lazily) ultralytics. These tests need cv2
but NOT a GPU or the real weights — a stub model stands in for YOLO.
"""

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

import detector  # noqa: E402
from detector import AccidentDetector, Detection, resolve_device, to_gray  # noqa: E402


class _StubBoxes:
    def __init__(self, xyxy, cls, conf):
        self.xyxy = _Tensor(xyxy)
        self.cls = _Tensor(cls)
        self.conf = _Tensor(conf)


class _Tensor:
    def __init__(self, values):
        self._values = values

    def tolist(self):
        return self._values

    def int(self):
        return self


class _StubResult:
    def __init__(self, boxes):
        self.boxes = boxes


class _StubModel:
    """Records what it was called with and replays canned results."""

    def __init__(self, results):
        self.results = results
        self.calls = []

    def predict(self, frames, **kwargs):
        self.calls.append((frames, kwargs))
        return self.results


def _detector_with(model):
    det = AccidentDetector.__new__(AccidentDetector)
    det.model = model
    det.conf = 0.15
    det.imgsz = 640
    det.device = "cpu"
    return det


def test_to_gray_returns_three_channels():
    """The COCO-pretrained stem expects 3 channels; a 1-channel input would
    silently reshape it."""
    frame = np.random.randint(0, 255, (32, 32, 3), dtype="uint8")
    out = to_gray(frame)
    assert out.shape == (32, 32, 3)


def test_to_gray_actually_removes_colour():
    """SPEC.md section 3: the model only ever sees grayscale. Feed it colour
    and it barely fires — the training set pairs a 100%-grayscale accident
    source against a ~98%-colour vehicle source."""
    frame = np.zeros((4, 4, 3), dtype="uint8")
    frame[:, :, 2] = 255  # pure red in BGR
    out = to_gray(frame)
    assert out[0, 0, 0] == out[0, 0, 1] == out[0, 0, 2]


def test_predict_batch_keeps_only_the_accident_class():
    """Class 1 `vehicle` is a discriminative foil that exists only to occupy
    training space. Emitting it makes the system a vehicle detector."""
    boxes = _StubBoxes(
        xyxy=[[0, 0, 10, 10], [20, 20, 30, 30]],
        cls=[0, 1],
        conf=[0.42, 0.99],
    )
    model = _StubModel([_StubResult(boxes)])
    det = _detector_with(model)

    result = det.predict_batch([np.zeros((8, 8, 3), dtype="uint8")])

    assert result[0].boxes == [(0.0, 0.0, 10.0, 10.0)]
    assert result[0].confs == [0.42]


def test_predict_batch_keeps_low_confidence_accident_boxes():
    """Recall comes from the low per-frame confidence; precision comes from
    the accumulator. Filtering here would delete real crashes."""
    boxes = _StubBoxes(xyxy=[[0, 0, 10, 10]], cls=[0], conf=[0.17])
    det = _detector_with(_StubModel([_StubResult(boxes)]))
    result = det.predict_batch([np.zeros((8, 8, 3), dtype="uint8")])
    assert result[0].confs == [0.17]


def test_predict_batch_returns_one_result_per_frame_in_input_order():
    """The pipeline zips these against its camera list. A length or order
    mismatch would attribute one camera's detections to another."""
    first = _StubResult(_StubBoxes([[0, 0, 1, 1]], [0], [0.3]))
    second = _StubResult(_StubBoxes([[5, 5, 6, 6]], [0], [0.4]))
    det = _detector_with(_StubModel([first, second]))

    frames = [np.zeros((8, 8, 3), dtype="uint8") for _ in range(2)]
    result = det.predict_batch(frames)

    assert len(result) == 2
    assert result[0].boxes == [(0.0, 0.0, 1.0, 1.0)]
    assert result[1].boxes == [(5.0, 5.0, 6.0, 6.0)]


def test_predict_batch_handles_a_frame_with_no_detections():
    det = _detector_with(_StubModel([_StubResult(None)]))
    result = det.predict_batch([np.zeros((8, 8, 3), dtype="uint8")])
    assert result == [Detection(boxes=[], confs=[])]


def test_predict_batch_feeds_grayscale_to_the_model():
    """Guards the single most consequential preprocessing decision.

    Covers the path taken before `_gray_letterbox` is installed — and the
    only path a stub model ever takes, since it has no Ultralytics predictor
    to patch. The installed path is guarded by the parity test below.
    """
    model = _StubModel([_StubResult(None)])
    det = _detector_with(model)
    frame = np.zeros((8, 8, 3), dtype="uint8")
    frame[:, :, 2] = 255

    det.predict_batch([frame])

    sent = model.calls[0][0][0]
    assert sent[0, 0, 0] == sent[0, 0, 1] == sent[0, 0, 2]


class _FakePredictorArgs:
    rect = True


class _FakePredictorModel:
    format = "engine"
    dynamic = True
    stride = 32


class _FakePredictor:
    imgsz = 640
    args = _FakePredictorArgs()
    model = _FakePredictorModel()


def test_gray_letterbox_is_byte_identical_to_the_full_resolution_path():
    """The whole justification for moving grayscale inside the letterbox is
    that it changes nothing. Detections on this clip set sit barely above the
    accumulator's firing threshold, so a preprocessing change that shifted a
    single pixel could silently cost a crash. Assert equality, not closeness.
    """
    pytest.importorskip("ultralytics")
    from ultralytics.data.augment import LetterBox

    rng = np.random.default_rng(0)
    frames = [
        rng.integers(0, 255, (1296, 2304, 3), dtype=np.uint8),
        rng.integers(0, 255, (1296, 2304, 3), dtype=np.uint8),
    ]
    predictor = _FakePredictor()

    letterbox = LetterBox(predictor.imgsz, auto=True, stride=32)
    baseline = [letterbox(image=to_gray(f)) for f in frames]
    candidate = detector._gray_letterbox(predictor, frames)

    assert len(candidate) == len(baseline)
    for got, want in zip(candidate, baseline, strict=True):
        assert got.shape == want.shape
        assert np.array_equal(got, want)


def test_gray_letterbox_output_is_still_three_channel_grayscale():
    """Same contract as to_gray(): the COCO-pretrained stem expects three
    channels, and they must carry no colour."""
    pytest.importorskip("ultralytics")
    frame = np.zeros((64, 64, 3), dtype="uint8")
    frame[:, :, 2] = 255  # pure red in BGR

    out = detector._gray_letterbox(_FakePredictor(), [frame])[0]

    assert out.shape[2] == 3
    assert np.array_equal(out[:, :, 0], out[:, :, 1])
    assert np.array_equal(out[:, :, 1], out[:, :, 2])


def test_predict_batch_of_nothing_does_not_call_the_model():
    model = _StubModel([])
    det = _detector_with(model)
    assert det.predict_batch([]) == []
    assert model.calls == []


def test_resolve_device_falls_back_to_cpu_without_cuda(monkeypatch):
    """main.py used to hardcode device=0, which is an error rather than a
    fallback on any machine without an NVIDIA GPU."""
    monkeypatch.setattr(detector, "_cuda_available", lambda: False)
    monkeypatch.setattr(detector, "_mps_available", lambda: False)
    assert resolve_device() == "cpu"


def test_resolve_device_prefers_cuda(monkeypatch):
    monkeypatch.setattr(detector, "_cuda_available", lambda: True)
    monkeypatch.setattr(detector, "_mps_available", lambda: False)
    assert resolve_device() == "0"


def test_resolve_device_honours_an_explicit_preference(monkeypatch):
    monkeypatch.setattr(detector, "_cuda_available", lambda: True)
    assert resolve_device("cpu") == "cpu"
