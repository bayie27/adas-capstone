"""The real safety net: the full 17-clip result, asserted CLIP BY CLIP.

Deliberately not the 8/16 aggregate. If a later run still scores 8/16 but a
DIFFERENT eight — one crash gained, one lost — the summary looks untouched
while the behaviour has moved.

Marked `clips`. Run with: uv run pytest -m clips
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import config
import pytest

pytest.importorskip("ultralytics")

pytestmark = pytest.mark.clips

AI_ENGINE = Path(__file__).resolve().parents[1]
EVAL = AI_ENGINE / "eval"
BASELINE = json.loads((EVAL / "baseline_epoch50.json").read_text())

# The model the SYSTEM is configured to run, not a hardcoded checkpoint. This
# test asks "is what I am running still correct", so it has to follow
# AI_MODEL_PATH — otherwise it passes for epoch50.pt while main.py loads a
# TensorRT engine, which is a green result about a build nobody is running.
#
# The baseline is still the checkpoint's (baseline_epoch50.json). A different
# build is therefore measured against the .pt's recorded truth, which is the
# right reference to start from but is NOT like-for-like: a build that drifts
# is kept and its drift recorded, so read a failure here as "this build differs
# from the checkpoint", not automatically as "this build is broken".
MODEL = config.WEIGHTS_PATH


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    """Each clip runs in its OWN process — Ultralytics state leaks between
    videos and `model.predictor = None` does not reset it. This silently
    produced wrong numbers once.

    A full run is ~30 minutes on a GTX 1650. Set ADAS_EVAL_EVENTS_DIR to the
    output of a previous run to re-score it without re-inferring. The scoring
    is unchanged either way — only the inference is skipped — so this is a
    speed affordance, not a weaker check. Without it the honest cost of
    running this test is half an hour, which is how safety nets quietly stop
    being used.
    """
    reuse = os.environ.get("ADAS_EVAL_EVENTS_DIR")
    if reuse:
        out = Path(reuse)
        if not sorted(out.glob("*.json")):
            raise AssertionError(
                f"ADAS_EVAL_EVENTS_DIR={out} contains no event JSON files. "
                "Unset it to run the clips, or point it at a completed run."
            )
    else:
        out = tmp_path_factory.mktemp("events")
        subprocess.run(
            [
                sys.executable,
                str(EVAL / "run_clips.py"),
                "--weights",
                str(MODEL),
                "--events-dir",
                str(out),
            ],
            check=True,
        )
    scored = subprocess.run(
        [sys.executable, str(EVAL / "score.py"), "--events-dir", str(out), "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(scored.stdout)


@pytest.mark.skipif(
    not (EVAL / "clips" / "airbase.mp4").exists(), reason="clips not populated"
)
@pytest.mark.parametrize("clip", sorted(BASELINE["clips"]))
def test_each_clip_matches_the_recorded_baseline(results, clip):
    expected = BASELINE["clips"][clip]["hit"]
    assert results["clips"][clip]["hit"] is expected, (
        f"{clip}: baseline ({BASELINE['model']}) says hit={expected}, "
        f"{MODEL.name} got {results['clips'][clip]['hit']}"
    )


@pytest.mark.skipif(
    not (EVAL / "clips" / "airbase.mp4").exists(), reason="clips not populated"
)
def test_false_positive_count_has_not_regressed(results):
    """0.27 FP/min is roughly 16 false alerts per hour per camera, which is
    already a design constraint on the review queue."""
    assert results["false_positives"] <= BASELINE["false_positives"], (
        f"{MODEL.name} produced {results['false_positives']} false positives "
        f"against the {BASELINE['model']} baseline's {BASELINE['false_positives']}"
    )
