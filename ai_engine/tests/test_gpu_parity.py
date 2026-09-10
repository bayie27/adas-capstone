"""The Phase 1 acceptance gate: ai_engine/docs/AI_ENGINE_GPU_INTEGRATION_PLAN.md section 6.4.

For every clip in ai_engine/eval/clips, decodes it TWICE — once with
OpenCV (the software path's decoder) and once with PyNvVideoCodec (the GPU
path's decoder, direct from the file, mirroring prototypes/prototype_gpu_decode.py's
file-based comparison rather than gpu_camera.py's RTSP plumbing, which is
orthogonal to whether the preprocessing arithmetic matches) — and asserts,
per frame:

  1. the prepared model input TENSOR is bit-identical between paths
     (predictor.preprocess() for software, gpu_preprocess.prepare_nv12()
     for GPU);
  2. the resulting DETECTIONS (boxes, confidences) are bit-identical;

then feeds both paths' detections through independent accumulators and
asserts the full EVENT list matches.

"Almost identical" is a failure of this gate, not a partial success — see
the plan's reporting instructions. Every frame of every clip is compared
(not a subsampled rate), which is a strictly stronger bar than the 9,658-
sample nominal-10-FPS gate the investigation report describes.

Marked `clips`: needs a GPU and ai_engine/eval/clips populated, same as
test_clip_parity.py and test_clip_regression.py.
"""

from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
torch = pytest.importorskip("torch")
pytest.importorskip("ultralytics")

import config  # noqa: E402
import gpu_preprocess  # noqa: E402
from accumulate import Accumulator  # noqa: E402
from detector import AccidentDetector, _letterbox_auto_for_shapes  # noqa: E402
from gpu_camera import _load_nvc  # noqa: E402

pytestmark = pytest.mark.clips

AI_ENGINE = Path(__file__).resolve().parents[1]
CLIPS_DIR = AI_ENGINE / "eval" / "clips"
CLIPS = sorted(CLIPS_DIR.glob("*.mp4")) if CLIPS_DIR.is_dir() else []


def _gpu_frames(nvc, path: Path):
    """Direct file decode via PyNvVideoCodec, mirroring
    prototypes/prototype_gpu_decode.py — native NV12, cloned into owned memory."""
    demux = nvc.CreateDemuxer(filename=str(path))
    decoder = nvc.CreateDecoder(
        gpuid=0,
        codec=demux.GetNvCodecId(),
        usedevicememory=True,
        outputColorType=nvc.OutputColorType.NATIVE,
    )
    for packet in demux:
        for frame in decoder.Decode(packet):
            yield torch.from_dlpack(frame).clone()


def _software_frames(path: Path):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    try:
        idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                return
            yield idx / fps, frame
            idx += 1
    finally:
        cap.release()


@pytest.fixture(scope="module")
def nvc():
    return _load_nvc()


@pytest.fixture(scope="module")
def detector():
    det = AccidentDetector(config.DEFAULT_WEIGHTS_PATH)
    det.warm_up_gpu()  # also builds the predictor + installs _gray_letterbox
    return det


@pytest.mark.parametrize("clip", CLIPS, ids=lambda p: p.stem)
def test_gpu_path_matches_software_path_exactly(clip, nvc, detector):
    full_range = gpu_preprocess.source_full_range(str(clip))
    predictor = detector.model.predictor

    gpu_accumulator = Accumulator(
        iou_link=config.ACC_IOU_LINK,
        threshold=config.ACC_THRESHOLD,
        decay=config.ACC_DECAY,
        ema=config.ACC_EMA,
    )
    sw_accumulator = Accumulator(
        iou_link=config.ACC_IOU_LINK,
        threshold=config.ACC_THRESHOLD,
        decay=config.ACC_DECAY,
        ema=config.ACC_EMA,
    )
    gpu_events, sw_events = [], []

    gpu_gen = _gpu_frames(nvc, clip)
    sw_gen = _software_frames(clip)
    frame_count = 0
    mismatched_tensor_frames = []
    mismatched_detection_frames = []

    for native, (t, bgr) in zip(gpu_gen, sw_gen, strict=False):
        shape = (native.shape[0] * 2 // 3, native.shape[1], 3)
        assert shape == bgr.shape, (
            f"{clip.name} frame {frame_count}: GPU-decoded shape {shape} != "
            f"CPU-decoded shape {bgr.shape}"
        )

        sw_tensor = predictor.preprocess([bgr])
        square = not _letterbox_auto_for_shapes(predictor, [shape])
        gpu_tensor = gpu_preprocess.prepare_nv12(
            native, square=square, dtype=sw_tensor.dtype, full_range=full_range
        )
        if not torch.equal(sw_tensor, gpu_tensor):
            mismatched_tensor_frames.append(frame_count)

        sw_det = detector.predict_batch([bgr])[0]
        gpu_det = detector.predict_batch_gpu([native], [full_range])[0]
        if sw_det.boxes != gpu_det.boxes or sw_det.confs != gpu_det.confs:
            mismatched_detection_frames.append(frame_count)

        sw_events.extend(sw_accumulator.update(t, sw_det.boxes, sw_det.confs))
        gpu_events.extend(gpu_accumulator.update(t, gpu_det.boxes, gpu_det.confs))
        frame_count += 1

    # Frame-count agreement at EOF, same discipline as the investigation's
    # own gate (ai_engine/docs/AI_ENGINE_GPU_RESIDENT_PROTOTYPE_REPORT.md).
    leftover_gpu = sum(1 for _ in gpu_gen)
    leftover_sw = sum(1 for _ in sw_gen)
    assert leftover_gpu == 0 and leftover_sw == 0, (
        f"{clip.name}: GPU and software decoders produced different frame "
        f"counts (compared {frame_count}, {leftover_gpu} GPU frames and "
        f"{leftover_sw} software frames left over)"
    )
    assert frame_count > 0, f"{clip.name}: decoded zero frames"

    assert not mismatched_tensor_frames, (
        f"{clip.name}: model input tensor differs from the software path on "
        f"{len(mismatched_tensor_frames)}/{frame_count} frames, first at "
        f"{mismatched_tensor_frames[0]}"
    )
    assert not mismatched_detection_frames, (
        f"{clip.name}: detections differ from the software path on "
        f"{len(mismatched_detection_frames)}/{frame_count} frames, first at "
        f"{mismatched_detection_frames[0]}"
    )

    assert len(gpu_events) == len(sw_events), (
        f"{clip.name}: event count differs — GPU {len(gpu_events)}, "
        f"software {len(sw_events)}"
    )
    for gpu_ev, sw_ev in zip(gpu_events, sw_events, strict=True):
        assert gpu_ev.t == sw_ev.t
        assert gpu_ev.peak_conf == sw_ev.peak_conf
        assert gpu_ev.score == sw_ev.score
