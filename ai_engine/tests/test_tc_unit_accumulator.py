"""Tracker-bound unit cases for the accumulator and detector front-end.

Each test here exists because a case in ADAS_Test_Execution_Tracker.xlsx states
acceptance conditions that no existing test asserted in full. The existing
suite covers the load-bearing BEHAVIOUR of accumulate.py (leakiness, positional
linking, firing time); these cover the specific CONSTANTS the tracker cases
name — the 0.30 IoU link threshold, the 0.30/second decay rate, the 0.50 EMA
box-smoothing factor, and the 0.15 detector confidence floor.

Binding:
    TC-UNIT-015  iou_link 0.30, both sides of the threshold
    TC-UNIT-016  decay 0.30 per second, and discard at zero
    TC-UNIT-017  DETECTOR_CONF 0.15 floor
    TC-UNIT-020  ema 0.50 box smoothing

These assert against accumulate.py's configured defaults. They do not change
its behaviour and do not touch adas_transfer/.
"""

from __future__ import annotations

import pytest
from accumulate import Accumulator
from config import DETECTOR_CONF

np = pytest.importorskip(
    "numpy", reason="The AI unit suite requires the optional AI dependency set"
)

BOX = (100.0, 100.0, 200.0, 200.0)


def _box_with_iou_above(threshold: float) -> tuple[float, float, float, float]:
    """A box overlapping BOX well above `threshold`."""
    return (110.0, 110.0, 210.0, 210.0)


def _box_with_iou_below(threshold: float) -> tuple[float, float, float, float]:
    """A box overlapping BOX well below `threshold` but still touching."""
    return (190.0, 190.0, 290.0, 290.0)


# --------------------------------------------------------------------------
# TC-UNIT-015 — the accumulator links detections at the configured IoU
# --------------------------------------------------------------------------


class TestIouLinkThreshold:
    def test_configured_threshold_is_the_documented_value(self):
        assert Accumulator().iou_link == 0.30

    def test_overlap_above_threshold_links_into_one_candidate(self):
        """Acceptance 1: the overlapping pair is linked into a single
        accumulating candidate."""
        from accumulate import iou

        second = _box_with_iou_above(0.30)
        assert iou(BOX, second) >= 0.30

        acc = Accumulator()
        acc.update(0.0, [BOX], [0.6])
        acc.update(1 / 30, [second], [0.6])

        assert len(acc.regions) == 1

    def test_overlap_below_threshold_produces_two_independent_candidates(self):
        """Acceptance 2: the non-overlapping pair produces two separate
        candidates and neither inherits the other's evidence."""
        from accumulate import iou

        second = _box_with_iou_below(0.30)
        assert iou(BOX, second) < 0.30

        acc = Accumulator()
        # The first frame has dt == 0, so a region created on it holds zero
        # evidence and is culled. Build real evidence over a full second before
        # introducing the distant box, so inherited evidence would be obvious.
        for i in range(31):
            acc.update(i / 30, [BOX], [0.6])
        established = next(r for r in acc.regions if r.box[0] < 150.0)
        established_score = established.score
        assert established_score == pytest.approx(0.6, rel=0.05)

        acc.update(31 / 30, [second], [0.6])

        assert len(acc.regions) == 2
        new_region = next(r for r in acc.regions if r.box[0] >= 150.0)
        assert new_region is not established
        # A fresh candidate starts from one frame's worth of evidence only.
        assert new_region.score == pytest.approx(0.6 * (1 / 30))
        assert new_region.score < established_score


# --------------------------------------------------------------------------
# TC-UNIT-016 — unmatched evidence decays at the configured rate
# --------------------------------------------------------------------------


class TestEvidenceDecay:
    def test_configured_decay_rate_is_the_documented_value(self):
        assert Accumulator().decay == 0.3

    def test_unmatched_evidence_decays_by_rate_times_elapsed_time(self):
        """Acceptance: evidence is reduced by 0.30 multiplied by elapsed time."""
        acc = Accumulator()
        acc.update(0.0, [BOX], [0.9])
        acc.update(1.0, [BOX], [0.9])  # dt 1.0s at conf 0.9 -> score 0.9

        region = acc.regions[0]
        before = region.score
        assert before == pytest.approx(0.9)

        acc.update(2.0, [], [])  # one second with no matching detection

        assert acc.regions[0].score == pytest.approx(before - 0.3 * 1.0)

    def test_candidate_whose_evidence_reaches_zero_is_discarded(self):
        """Acceptance: a candidate whose evidence reaches zero is discarded
        rather than firing."""
        acc = Accumulator()
        acc.update(0.0, [BOX], [0.3])
        acc.update(1.0, [BOX], [0.3])  # score 0.3, far below threshold 1.0
        assert acc.regions

        events = acc.update(2.0, [], [])  # decays 0.3 -> exactly 0.0

        assert events == []
        assert acc.regions == []


# --------------------------------------------------------------------------
# TC-UNIT-020 — box smoothing applies the configured EMA factor
# --------------------------------------------------------------------------


class TestBoxSmoothing:
    def test_configured_ema_factor_is_the_documented_value(self):
        assert Accumulator().ema == 0.5

    def test_smoothed_box_is_the_midpoint_not_the_raw_latest_box(self):
        """Acceptance: the smoothed box is the midpoint implied by an EMA
        factor of 0.50, not the raw latest box."""
        acc = Accumulator()
        # Two frames at the seed location so the region carries evidence and
        # survives the end-of-frame cull; its box is still exactly BOX.
        acc.update(0.0, [BOX], [0.6])
        acc.update(1 / 30, [BOX], [0.6])
        assert acc.regions[0].box == BOX

        displaced = (120.0, 140.0, 220.0, 240.0)
        acc.update(2 / 30, [displaced], [0.6])

        smoothed = acc.regions[0].box
        expected = tuple(0.5 * n + 0.5 * o for n, o in zip(displaced, BOX, strict=True))

        assert smoothed == pytest.approx(expected)
        assert smoothed != pytest.approx(displaced)


# --------------------------------------------------------------------------
# TC-UNIT-017 — the detector confidence floor admits weak detections
# --------------------------------------------------------------------------


class TestDetectorConfidenceFloor:
    def test_configured_floor_is_the_documented_value(self):
        assert DETECTOR_CONF == 0.15

    def test_floor_is_what_the_model_is_asked_to_apply(self):
        """The 0.10 detection is discarded because 0.15 is the confidence the
        detector hands the model; nothing below it is ever emitted."""
        from detector import AccidentDetector

        class _Model:
            def __init__(self):
                self.calls = []

            def predict(self, frames, **kwargs):
                self.calls.append(kwargs)
                return []

        model = _Model()
        det = AccidentDetector.__new__(AccidentDetector)
        det.model = model
        det.conf = DETECTOR_CONF
        det.imgsz = 640
        det.device = "cpu"

        det.predict_batch([np.zeros((8, 8, 3), dtype="uint8")])

        assert model.calls, "the model was never asked for a prediction"
        assert model.calls[0]["conf"] == 0.15
        # 0.10 is below the floor the model is given, so it is never emitted.
        assert 0.10 < model.calls[0]["conf"] <= 0.15

    def test_detections_at_and_above_the_floor_reach_accumulation(self):
        """Acceptance 1: detections at 0.15 and 0.40 reach accumulation."""
        for conf in (0.15, 0.40):
            acc = Accumulator()
            acc.update(0.0, [BOX], [conf])
            acc.update(1.0, [BOX], [conf])
            assert acc.regions, f"conf {conf} did not reach accumulation"
            assert acc.regions[0].score == pytest.approx(conf)

    def test_a_single_detection_never_fires_on_its_own(self):
        """Acceptance 3: no detection alerts on its own without meeting the
        evidence threshold."""
        acc = Accumulator()
        events = acc.update(0.0, [BOX], [0.99])
        assert events == []

        # Even a full second of the strongest possible single detection is
        # below the 1.0 conf-second threshold on one frame.
        events = acc.update(1.0, [BOX], [0.99])
        assert events == []
        assert acc.regions[0].score < acc.threshold
