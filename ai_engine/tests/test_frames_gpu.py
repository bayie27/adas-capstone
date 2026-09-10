"""frames.to_bgr()'s full-resolution NV12->BGR conversion, checked against
real decoded frames -- the synthetic-tensor tests in test_frames.py cover
the coefficient wiring, but only real footage proves the conversion matches
what an operator would see from the software path. Needs a GPU (to decode
via PyNvVideoCodec) and eval/clips populated, same as test_gpu_parity.py.
"""

from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
torch = pytest.importorskip("torch")

import gpu_preprocess  # noqa: E402
from frames import to_bgr  # noqa: E402
from gpu_camera import _load_nvc  # noqa: E402

pytestmark = pytest.mark.clips

AI_ENGINE = Path(__file__).resolve().parents[1]
CLIPS = [
    AI_ENGINE / "eval" / "clips" / name
    for name in ("airbase.mp4", "dekwatro.mp4", "car-motor-far.mp4")
]


@pytest.mark.parametrize("clip", CLIPS, ids=lambda p: p.stem)
def test_gpu_snapshot_bgr_matches_the_software_decode_exactly(clip):
    if not clip.exists():
        pytest.skip("clips not populated")
    nvc = _load_nvc()
    full_range = gpu_preprocess.source_full_range(str(clip))

    demux = nvc.CreateDemuxer(filename=str(clip))
    decoder = nvc.CreateDecoder(
        gpuid=0,
        codec=demux.GetNvCodecId(),
        usedevicememory=True,
        outputColorType=nvc.OutputColorType.NATIVE,
    )
    cap = cv2.VideoCapture(str(clip))
    try:
        checked = 0
        for packet in demux:
            for frame in decoder.Decode(packet):
                native = torch.from_dlpack(frame).clone()
                bgr_gpu = to_bgr(native, full_range=full_range)
                ok, bgr_cpu = cap.read()
                assert ok, f"{clip.name}: software decoder ran out of frames first"
                assert np.array_equal(bgr_gpu, bgr_cpu), (
                    f"{clip.name} frame {checked}: GPU-path snapshot BGR "
                    "differs from the software decode"
                )
                checked += 1
                if checked >= 5:
                    return
        pytest.fail(f"{clip.name}: fewer than 5 frames decoded")
    finally:
        cap.release()
