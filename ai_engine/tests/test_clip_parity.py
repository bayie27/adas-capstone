"""SPEC.md section 8 step 3: prove the port did not change behaviour.

Runs the PORTED detector and accumulator over a clip and compares the
emitted events against adas_transfer/code/run.py's reference output. The
reference must come from the research repo's run.py, never from a
re-implementation.

Marked `clips` — needs a GPU and ai_engine/eval/clips populated.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
pytest.importorskip("ultralytics")

import config  # noqa: E402
from accumulate import Accumulator  # noqa: E402
from detector import AccidentDetector  # noqa: E402

pytestmark = pytest.mark.clips

AI_ENGINE = Path(__file__).resolve().parents[1]
CLIP = AI_ENGINE / "eval" / "clips" / "dekwatro.mp4"

# DELIBERATELY the checkpoint, and deliberately NOT config.WEIGHTS_PATH — this
# is the one clip test that must not follow AI_MODEL_PATH.
#
# What it proves is that PORTING the code changed no behaviour: ported
# detector/accumulator against the frozen adas_transfer reference, asserted as
# exact equality of t, peak_conf and score. Swapping in a different build adds
# a variable that has nothing to do with the port, and a failure would no
# longer distinguish "the port is broken" from "this build's numerics moved" —
# which is the entire question the test exists to answer. The non-vacuity
# guard below is likewise written against this checkpoint's known result on
# dekwatro (fires once, t=14.20s).
#
# test_clip_regression.py is the one that follows the configured model.
WEIGHTS = config.DEFAULT_WEIGHTS_PATH
REFERENCE_RUNNER = AI_ENGINE / "adas_transfer" / "code" / "run.py"


def _reference_events(tmp_path):
    out = tmp_path / "reference.json"
    subprocess.run(
        [
            sys.executable,
            str(REFERENCE_RUNNER),
            "--video",
            str(CLIP),
            "--weights",
            str(WEIGHTS),
            "--events",
            str(out),
            "--quiet",
        ],
        check=True,
    )
    return json.loads(out.read_text())["events"]


def _ported_events():
    """Mirrors the ported per-frame path exactly: file source, so
    t = frame_index / fps, which is what every recorded result depends on."""
    detector = AccidentDetector(WEIGHTS)
    accumulator = Accumulator()

    cap = cv2.VideoCapture(str(CLIP))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    events = []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        detection = detector.predict_batch([frame])[0]
        for ev in accumulator.update(idx / fps, detection.boxes, detection.confs):
            events.append(ev)
        idx += 1
    cap.release()
    return events


@pytest.mark.skipif(not CLIP.exists(), reason="clips not populated")
def test_ported_pipeline_emits_the_same_events_as_the_reference(tmp_path):
    reference = _reference_events(tmp_path)
    ported = _ported_events()

    # Non-vacuity guard, first. Without it this test passes when BOTH sides
    # emit nothing — which is exactly what a broken port looks like (no
    # grayscale, wrong `t` unit, over-tight confidence gate all produce
    # silence). `dekwatro` is a standard-difficulty HIT with a labelled onset
    # at 12.0s and the reference fires once, at t=14.20s.
    assert reference, (
        "the REFERENCE produced no events on a clip labelled as a hit — the "
        "comparison below would be vacuous. Check the weights and the clip, "
        "not the port."
    )

    assert len(ported) == len(reference), (
        f"event count differs: ported {len(ported)}, reference {len(reference)}"
    )
    for got, expected in zip(ported, reference, strict=True):
        assert round(got.t, 2) == expected["t"]
        assert got.peak_conf == expected["peak_conf"]
        assert got.score == expected["score"]
