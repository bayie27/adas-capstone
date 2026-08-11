"""The per-frame half of the detector: grayscale, YOLO, class filtering.

The temporal half lives in accumulate.py. This module owns everything that
touches the model; pipeline.py owns scheduling and lifecycle and imports
neither cv2 nor ultralytics, which is what keeps it testable in CI.
"""

from typing import NamedTuple

import cv2
from config import ACCIDENT_CLASS_ID, DETECTOR_CONF, DETECTOR_IMGSZ

Box = tuple[float, float, float, float]


class Detection(NamedTuple):
    """One frame's accident boxes. Class 1 `vehicle` is already discarded."""

    boxes: list[Box]
    confs: list[float]


def to_gray(frame):
    """BGR -> grayscale, replicated back to 3 channels.

    MANDATORY, and not cosmetic. The accident training source is 100%
    grayscale and the vehicle source ~98% colour, so without forcing every
    image to grayscale the cheapest rule the model can learn is
    "colour => vehicle, grayscale => accident" — and on colour deployment
    footage it would then never fire. Three channels on purpose: the
    COCO-pretrained stem expects 3, and 1 would silently reshape it.
    """
    return cv2.cvtColor(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _mps_available() -> bool:
    try:
        import torch

        return bool(torch.backends.mps.is_available())
    except Exception:
        return False


def resolve_device(preferred: str | None = None) -> str:
    """Pick an inference device. Returns an Ultralytics device string.

    `main.py` previously hardcoded `device=0`, which is not a preference but
    an error on any machine without an NVIDIA GPU — including teammates'
    laptops and any Apple Silicon machine.
    """
    if preferred:
        return preferred
    if _cuda_available():
        return "0"
    if _mps_available():
        return "mps"
    return "cpu"


class AccidentDetector:
    """Owns one model. Construct once at process start — model construction
    takes seconds, while inference is milliseconds.
    """

    def __init__(
        self,
        weights_path,
        *,
        device: str | None = None,
        conf: float = DETECTOR_CONF,
        imgsz: int = DETECTOR_IMGSZ,
    ):
        from ultralytics import YOLO

        self.model = YOLO(str(weights_path))
        self.conf = conf
        self.imgsz = imgsz
        self.device = resolve_device(device)

    def predict_batch(self, frames: list) -> list[Detection]:
        """One batched forward pass. Returns one Detection per input frame,
        in input order — pipeline.py zips these against its camera list, so
        order and length are load-bearing.
        """
        if not frames:
            return []

        results = self.model.predict(
            [to_gray(f) for f in frames],
            conf=self.conf,
            imgsz=self.imgsz,
            device=self.device,
            verbose=False,
        )
        return [_to_detection(r) for r in results]


def _to_detection(result) -> Detection:
    boxes: list[Box] = []
    confs: list[float] = []
    if result.boxes is None:
        return Detection(boxes=boxes, confs=confs)

    for box, cls, conf in zip(
        result.boxes.xyxy.tolist(),
        result.boxes.cls.int().tolist(),
        result.boxes.conf.tolist(),
        strict=True,
    ):
        if int(cls) == ACCIDENT_CLASS_ID:
            boxes.append(tuple(float(v) for v in box))
            confs.append(float(conf))
    return Detection(boxes=boxes, confs=confs)
