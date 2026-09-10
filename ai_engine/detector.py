"""The per-frame half of the detector: grayscale, YOLO, class filtering.

The temporal half lives in accumulate.py. This module owns everything that
touches the model; pipeline.py owns scheduling and lifecycle and imports
neither cv2 nor ultralytics, which is what keeps it testable in CI.
"""

import logging
from functools import lru_cache
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


def _letterbox_auto_for_shapes(predictor, shapes: list) -> bool:
    """Ultralytics' `BasePredictor.pre_transform` `auto=` decision, copied
    verbatim so it cannot drift from the installed version's own — it
    depends on model format and dynamic shapes, not just on whether every
    frame in the batch is the same size.

    Shared by the software path (`_gray_letterbox`, from real frames) and the
    GPU path (`AccidentDetector.predict_batch_gpu`, from NV12 tensor shapes)
    so the two can never independently derive different padding decisions.
    Must be computed from the ACTUAL batch on every call, never cached: with
    mixed-resolution cameras the destructive `CameraStream.read()` makes the
    live batch a different subset each tick, so `same_shapes` can flip tick
    to tick under completely normal operation (see
    ai_engine/docs/AI_ENGINE_GPU_INTEGRATION_PLAN.md section 4.1(b)).
    """
    same_shapes = len(set(shapes)) == 1
    return (
        same_shapes
        and predictor.args.rect
        and (
            predictor.model.format == "pt"
            or (
                getattr(predictor.model, "dynamic", False)
                and predictor.model.format != "imx"
            )
        )
    )


def _gray_letterbox(predictor, images: list) -> list:
    """Ultralytics' own `pre_transform`, with the grayscale conversion folded
    in and the resize done on ONE channel instead of three.

    `to_gray()` replicates grayscale to three channels at full resolution, and
    Ultralytics then resizes all three — so two thirds of the resize is spent
    on duplicate data. Measured at batch 10 on 2304x1296 frames, `to_gray()`
    alone was 47 of the 79 ms whole-detector call; doing the grayscale here and
    expanding only after the image is down at 640x384 removes 21 ms of
    preprocessing and 14% of the whole call.

    The output is byte-identical to the original path — asserted in
    tests/test_detector.py, and the reason a change to this hot path is safe at
    all given how close the accumulator runs to its firing threshold.
    """
    from ultralytics.data.augment import LetterBox

    letterbox = LetterBox(
        predictor.imgsz,
        auto=_letterbox_auto_for_shapes(predictor, [im.shape for im in images]),
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


@lru_cache(maxsize=32)
def _orig_placeholder(shape: tuple) -> np.ndarray:
    """A correctly-shaped stand-in for Ultralytics' `orig_imgs` postprocess
    argument, for the GPU path — which has no BGR original to hand it (the
    frame never left the GPU as a NumPy array).

    Reading the installed `DetectionPredictor.postprocess` /
    `construct_result` (ultralytics==8.4.41): passing a `list` for
    `orig_imgs` skips its `convert_torch2numpy_batch` branch entirely, and
    each element is then used ONLY for `.shape` — once to rescale boxes back
    to original coordinates (`ops.scale_boxes(img.shape[2:], boxes,
    orig_img.shape)`, which reads index [0]/[1]) and once for `Results.
    orig_shape = orig_img.shape[:2]`. The array itself is stored as
    `Results.orig_img` but nothing on this code path reads it again —
    `_to_detection()` below touches only `.boxes`. A future Ultralytics
    upgrade could change that; the GPU parity test asserts exact box-
    coordinate equality against the software path's real array, not just
    that this function runs, so a regression here would fail loudly rather
    than silently shipping wrong coordinates.

    Cached per distinct camera resolution, never rebuilt per frame — the
    plan is explicit that this must not become a per-tick cost.
    """
    return np.zeros(shape, dtype=np.uint8)


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

    # Class attributes, not set in __init__, so an instance built with
    # __new__ (as the tests do) still has them.
    _gray_in_letterbox = False
    _gpu_ready = False
    _gpu_input_dtype = None

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

    def warm_up_gpu(self) -> None:
        """Builds the Ultralytics predictor and resolves its real input dtype
        before any GPU-resident frame arrives.

        The predictor is built lazily on the first `predict()` call (see
        `_install_gray_letterbox` above), and `predict_batch_gpu()` never
        calls `predict()` — it calls `predictor.inference()` /
        `.postprocess()` directly, the way
        ai_engine/docs/AI_ENGINE_GPU_INTEGRATION_PLAN.md section 6.3 requires, so nothing
        else would trigger that lazy build. Idempotent: safe to call once at
        startup, before any camera — and therefore any real resolution — is
        known.

        The warmup frame's size does not need to match any real camera: it
        only has to be a valid image so `predict()` can build the predictor
        and report a real `.dtype`. Eight calls, matching
        `prototypes/prototype_gpu_rtsp.py`'s warmup, so the installed `_gray_letterbox`
        optimisation and any CUDA/cuDNN autotuning are both settled before
        the first live tick.
        """
        if self._gpu_ready:
            return
        warmup_frames = [np.zeros((640, 640, 3), dtype=np.uint8)]
        for _ in range(8):
            self.predict_batch(warmup_frames)
        predictor = self.model.predictor
        # FP16 export weights do not imply FP16 input bindings (plan section
        # 6.3) — take the dtype the predictor's own preprocessing actually
        # produces, not a label read off the model file.
        self._gpu_input_dtype = predictor.preprocess(warmup_frames).dtype
        self._gpu_ready = True

    def predict_batch_gpu(
        self, native_frames: list, full_ranges: list[bool]
    ) -> list[Detection]:
        """GPU-resident counterpart to `predict_batch()`: frames already live
        on the GPU as NV12 device tensors (gpu_camera.GpuCameraStream's
        reader), so this skips Ultralytics' own preprocessing and any host
        round trip, calling `predictor.inference()` / `.postprocess()`
        directly — the same shape as `prototypes/prototype_gpu_rtsp.py`'s tick.

        `native_frames` and `full_ranges` must be the same length, one entry
        per camera in this tick's batch, in the same order `_to_detection`'s
        results should map back to. Geometry (`square`) is derived from the
        ACTUAL batch shapes on every call via `_letterbox_auto_for_shapes` —
        never cached — because the live batch composition varies tick to
        tick (section 4.1(b)).
        """
        if not native_frames:
            return []
        if not self._gpu_ready:
            raise RuntimeError(
                "predict_batch_gpu() called before warm_up_gpu(); the "
                "Ultralytics predictor and input dtype are not resolved yet"
            )

        import gpu_preprocess
        import torch

        shapes = [
            (native.shape[0] * 2 // 3, native.shape[1], 3) for native in native_frames
        ]
        predictor = self.model.predictor
        square = not _letterbox_auto_for_shapes(predictor, shapes)
        tensor = torch.cat(
            [
                gpu_preprocess.prepare_nv12(
                    native,
                    square=square,
                    dtype=self._gpu_input_dtype,
                    full_range=full_range,
                )
                for native, full_range in zip(native_frames, full_ranges, strict=True)
            ]
        )
        orig_imgs = [_orig_placeholder(shape) for shape in shapes]
        # DetectionPredictor.construct_results() zips preds/orig_imgs against
        # self.batch[0] (paths) to build one Results per image — a real
        # trap found while writing this: self.batch is a leftover 1-frame
        # tuple from warm_up_gpu()'s predict() calls, so without resetting
        # it here, `zip()` SILENTLY TRUNCATES a real N-camera batch down to
        # 1 result and every other camera's detections vanish with no error.
        # Confirmed by direct testing, not assumed.
        predictor.batch = (
            [f"gpu-camera-{i}" for i in range(len(native_frames))],
            None,
            "",
        )
        with torch.inference_mode():
            preds = predictor.inference(tensor)
            results = predictor.postprocess(preds, tensor, orig_imgs)
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
