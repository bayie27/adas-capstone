"""accident.py imports cv2, so this module is guarded and only runs where
the `ai` extra is installed.
"""

from datetime import UTC, datetime
from unittest.mock import patch

import config
import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

import accident  # noqa: E402
from accident import AccidentManager, annotate  # noqa: E402
from accumulate import Event  # noqa: E402


class _DummyCamera:
    camera_id = 3
    channel_id = 3


def _event(age_s=3.0, peak_conf=0.62):
    return Event(
        t=12.0,
        box=(10.0, 10.0, 40.0, 40.0),
        score=1.02,
        peak_conf=peak_conf,
        age_s=age_s,
    )


def test_snapshot_is_a_loadable_jpeg(tmp_path, monkeypatch):
    """Regression: the temp path passed to cv2.imwrite must still end in
    .jpg — cv2 picks its encoder from the extension, so a plain `.tmp`
    suffix makes imwrite fail with "could not find a writer"."""
    monkeypatch.setattr(accident, "SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setattr(config, "OUTBOX_DIR", tmp_path / "outbox")

    frame = np.zeros((64, 64, 3), dtype="uint8")
    AccidentManager().handle_event(_DummyCamera(), frame, _event())

    written = list(tmp_path.rglob("*.jpg"))
    assert len(written) == 1
    assert cv2.imread(str(written[0])) is not None


def test_confidence_sent_is_the_events_peak(tmp_path, monkeypatch):
    """peak_conf is the accumulator's analogue of the old single-frame
    confidence. score and age_s stay engine-side."""
    monkeypatch.setattr(accident, "SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setattr(config, "OUTBOX_DIR", tmp_path / "outbox")

    with patch("accident.outbox.enqueue") as enqueue:
        AccidentManager().handle_event(
            _DummyCamera(), np.zeros((16, 16, 3), dtype="uint8"), _event(peak_conf=0.62)
        )

    assert enqueue.call_args[0][0]["confidence_score"] == 0.62


def test_detected_at_is_the_collision_not_the_alert(tmp_path, monkeypatch):
    """The event fires a median +3.02s AFTER impact. Stamping at send time
    logs every accident ~3 seconds late into the incident record and the
    peak-time analytics. age_s measures back to when the region appeared."""
    monkeypatch.setattr(accident, "SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setattr(config, "OUTBOX_DIR", tmp_path / "outbox")
    now = datetime(2026, 7, 12, 10, 30, 0, tzinfo=UTC)

    with (
        patch("accident.datetime") as mock_datetime,
        patch("accident.outbox.enqueue") as enqueue,
    ):
        mock_datetime.now.return_value = now
        AccidentManager().handle_event(
            _DummyCamera(), np.zeros((16, 16, 3), dtype="uint8"), _event(age_s=3.0)
        )

    detected_at = enqueue.call_args[0][0]["detected_at"]
    assert detected_at.startswith("2026-07-12T10:29:57")


def test_payload_has_exactly_the_five_contract_keys(tmp_path, monkeypatch):
    """DetectionLogCreateV2 is extra="forbid". An extra key is a 422."""
    monkeypatch.setattr(accident, "SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setattr(config, "OUTBOX_DIR", tmp_path / "outbox")

    with patch("accident.outbox.enqueue") as enqueue:
        AccidentManager().handle_event(
            _DummyCamera(), np.zeros((16, 16, 3), dtype="uint8"), _event()
        )

    assert set(enqueue.call_args[0][0]) == {
        "source_event_id",
        "camera_id",
        "detected_at",
        "snapshot_key",
        "confidence_score",
    }


def test_a_failed_snapshot_encode_drops_the_event(tmp_path, monkeypatch):
    """A committed incident pointing at a half-written JPEG is unrecoverable
    evidence loss. Dropping is safe: no incident means no Paused desired
    state, so the camera resumes at the next heartbeat."""
    monkeypatch.setattr(accident, "SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setattr(config, "OUTBOX_DIR", tmp_path / "outbox")
    monkeypatch.setattr(accident.cv2, "imwrite", lambda *a, **k: False)

    with patch("accident.outbox.enqueue") as enqueue:
        AccidentManager().handle_event(
            _DummyCamera(), np.zeros((16, 16, 3), dtype="uint8"), _event()
        )

    enqueue.assert_not_called()


def test_annotation_draws_on_the_colour_frame():
    """The old code passed r.plot(), which under grayscale input would
    annotate the tensor the model sees rather than something an operator
    can read."""
    frame = np.zeros((64, 64, 3), dtype="uint8")
    frame[:, :, 2] = 200  # red channel, so colour survival is detectable

    out = annotate(frame, (10.0, 10.0, 40.0, 40.0))

    assert out.shape == frame.shape
    assert not np.array_equal(out, frame)  # something was drawn
    assert out[:, :, 2].max() >= 200  # still colour, not greyed


def test_annotation_does_not_mutate_the_original_frame():
    frame = np.zeros((64, 64, 3), dtype="uint8")
    before = frame.copy()
    annotate(frame, (10.0, 10.0, 40.0, 40.0))
    assert np.array_equal(frame, before)
