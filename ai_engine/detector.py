"""The per-frame half of the detector: grayscale, YOLO, class filtering.

The temporal half lives in accumulate.py. This module owns everything that
touches the model; pipeline.py owns scheduling and lifecycle and imports
neither cv2 nor ultralytics, which is what keeps it testable in CI.
"""

import logging
from typing import NamedTuple

import cv2
import numpy as np
from config import ACCIDENT_CLASS_ID, DETECTOR_CONF, DETECTOR_IMGSZ

logger = logging.getLogger("ai_engine")

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


def _gray_letterbox(predictor, images: list) -> list:
    """Ultralytics' own `pre_transform`, with the grayscale conversion folded
    in and the resize done on ONE channel instead of three.

    `to_gray()` replicates grayscale to three channels at full resolution, and
    Ultralytics then resizes all three — so two thirds of the resize is spent
    on duplicate data. Measured at batch 10 on 2304x1296 frames, `to_gray()`
    alone was 47 of the 79 ms whole-detector call; doing the grayscale here and
    expanding only after the image is down at 640x384 removes 21 ms of
    preprocessing and 14% of the whole call.

    The `auto=` expression is copied verbatim from the installed
    `BasePredictor.pre_transform` so the padding decision cannot drift from
    Ultralytics' own, which depends on model format and dynamic shapes. The
    output is byte-identical to the original path — asserted in
    tests/test_detector.py, and the reason a change to this hot path is safe at
    all given how close the accumulator runs to its firing threshold.
    """
    from ultralytics.data.augment import LetterBox

    same_shapes = len({im.shape for im in images}) == 1
    letterbox = LetterBox(
        predictor.imgsz,
        auto=same_shapes
        and predictor.args.rect
        and (
            predictor.model.format == "pt"
            or (
                getattr(predictor.model, "dynamic", False)
                and predictor.model.format != "imx"
            )
        ),
        stride=predictor.model.stride,
    )
    return [
        np.repeat(
            letterbox(image=cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)[..., None]),
            3,
            axis=2,
        )
        for im in images
    ]


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

    # Class attribute, not set in __init__, so an instance built with
    # __new__ (as the tests do) still has it.
    _gray_in_letterbox = False

    def predict_batch(self, frames: list) -> list[Detection]:
        """One batched forward pass. Returns one Detection per input frame,
        in input order — pipeline.py zips these against its camera list, so
        order and length are load-bearing.

        Grayscale is mandatory either way; only *where* it happens changes.
        Once `_gray_letterbox` is installed the frames are handed over in
        colour and converted inside the letterbox — Ultralytics must keep
        seeing the original full-resolution frame, because it rescales the
        returned boxes against that shape.
        """
        if not frames:
            return []

        results = self.model.predict(
            frames if self._gray_in_letterbox else [to_gray(f) for f in frames],
            conf=self.conf,
            imgsz=self.imgsz,
            device=self.device,
            verbose=False,
        )
        if not self._gray_in_letterbox:
            self._install_gray_letterbox()
        return [_to_detection(r) for r in results]

    def _install_gray_letterbox(self) -> None:
        """Swap in the cheap preprocessing path, once, after the first call.

        Ultralytics builds its predictor lazily on the first `predict()`, so
        there is nothing to patch before then. Anything unexpected about the
        internals leaves the original path in place: it is slower but produces
        the same tensors, so falling back is always safe.
        """
        predictor = getattr(self.model, "predictor", None)
        if predictor is None:
            return
        try:
            _gray_letterbox(predictor, [np.zeros((8, 8, 3), dtype="uint8")])
        except Exception:
            logger.warning(
                "Lower-copy preprocessing unavailable; keeping the full-resolution "
                "grayscale path",
                exc_info=True,
            )
            return
        predictor.pre_transform = lambda im: _gray_letterbox(predictor, im)
        self._gray_in_letterbox = True


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
