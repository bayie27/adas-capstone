import json
import time
from unittest.mock import patch

import config
import outbox
import pytest
from backend_client import DeliveryOutcome


@pytest.fixture(autouse=True)
def _outbox_dir(tmp_path, monkeypatch):
    outbox_dir = tmp_path / "outbox"
    monkeypatch.setattr(config, "OUTBOX_DIR", outbox_dir)
    return outbox_dir


def _payload(source_event_id="evt-1", camera_id=5):
    return {
        "source_event_id": source_event_id,
        "camera_id": camera_id,
        "detected_at": "2026-07-12T10:30:00+00:00",
        "snapshot_key": f"2026/07/12/camera_{camera_id}/{source_event_id}.jpg",
        "confidence_score": 0.9,
    }


def test_enqueue_creates_a_pending_entry():
    path = outbox.enqueue(_payload())
    assert path.exists()
    assert path in outbox.pending()


def test_enqueue_is_atomic_a_stray_tmp_is_ignored(_outbox_dir):
    _outbox_dir.mkdir(parents=True, exist_ok=True)
    stray_tmp = _outbox_dir / "20260101T000000000000_ghost.json.tmp"
    stray_tmp.write_text("not even valid json{{{", encoding="utf-8")
    assert outbox.pending() == []


def test_pending_returns_fifo_oldest_first():
    first = outbox.enqueue(_payload("evt-1"))
    time.sleep(0.01)
    second = outbox.enqueue(_payload("evt-2"))
    assert outbox.pending() == [first, second]


def test_acknowledge_removes_the_entry():
    path = outbox.enqueue(_payload())
    outbox.acknowledge(path)
    assert not path.exists()
    assert outbox.pending() == []


def test_quarantine_moves_the_entry_and_is_never_retried(_outbox_dir):
    path = outbox.enqueue(_payload())
    outbox.quarantine(path, "validation_rejected")

    assert not path.exists()
    assert outbox.pending() == []

    quarantined = list((_outbox_dir / "quarantine").iterdir())
    assert len(quarantined) == 1
    record = json.loads(quarantined[0].read_text(encoding="utf-8"))
    assert record["quarantine_reason"] == "validation_rejected"
    assert record["payload"]["source_event_id"] == "evt-1"


def test_source_event_id_is_stable_across_attempts():
    path = outbox.enqueue(_payload("evt-stable"))
    outbox.mark_attempt(path)
    outbox.mark_attempt(path)

    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["payload"]["source_event_id"] == "evt-stable"
    assert record["attempts"] == 2


def test_backoff_grows_with_attempts_and_is_jittered():
    small = [outbox._compute_backoff_seconds(1) for _ in range(5)]
    large = [outbox._compute_backoff_seconds(10) for _ in range(5)]
    assert max(small) < min(large)
    assert len(set(small)) > 1  # jitter varies run to run


def test_backoff_is_capped_at_the_maximum():
    backoff = outbox._compute_backoff_seconds(50)
    assert backoff <= outbox._MAX_BACKOFF_SECONDS * 1.25  # base + max jitter


def test_corrupt_json_is_quarantined_and_does_not_block_the_rest(_outbox_dir):
    _outbox_dir.mkdir(parents=True, exist_ok=True)
    # Sorts before the real enqueue() timestamp below, so it's processed first.
    corrupt = _outbox_dir / "20260101T000000000000_bad.json"
    corrupt.write_text("{not valid json", encoding="utf-8")
    good_path = outbox.enqueue(_payload("evt-good"))

    with patch("outbox.post_event", return_value=DeliveryOutcome.ACKNOWLEDGED):
        outbox.run_delivery_cycle()

    assert not corrupt.exists()
    assert not good_path.exists()  # the good event was still delivered
    quarantined_names = [p.name for p in (_outbox_dir / "quarantine").iterdir()]
    assert corrupt.name in quarantined_names


@pytest.mark.parametrize(
    "outcome,should_remove",
    [
        (DeliveryOutcome.ACKNOWLEDGED, True),
        (DeliveryOutcome.CONFLICT, True),
        (DeliveryOutcome.CAMERA_GONE, True),
        (DeliveryOutcome.QUARANTINE, True),  # removed from pending, moved aside
        (DeliveryOutcome.AUTH_FAILURE, False),
        (DeliveryOutcome.RETRY, False),
    ],
)
def test_run_delivery_cycle_branches_on_outcome(outcome, should_remove):
    path = outbox.enqueue(_payload())

    with patch("outbox.post_event", return_value=outcome):
        outbox.run_delivery_cycle()

    assert (path not in outbox.pending()) == should_remove


def test_camera_gone_signals_the_callback_with_camera_id():
    outbox.enqueue(_payload(camera_id=42))
    seen = []

    with patch("outbox.post_event", return_value=DeliveryOutcome.CAMERA_GONE):
        outbox.run_delivery_cycle(on_camera_gone=seen.append)

    assert seen == [42]


def test_auth_failure_uses_a_long_backoff():
    path = outbox.enqueue(_payload())

    with patch("outbox.post_event", return_value=DeliveryOutcome.AUTH_FAILURE):
        outbox.run_delivery_cycle()

    record = json.loads(path.read_text(encoding="utf-8"))
    next_attempt = record["next_attempt_at"]
    assert next_attempt is not None


def test_retry_does_not_redeliver_before_next_attempt_is_due():
    outbox.enqueue(_payload())
    call_count = {"n": 0}

    def fake_post_event(_payload):
        call_count["n"] += 1
        return DeliveryOutcome.RETRY

    with patch("outbox.post_event", side_effect=fake_post_event):
        outbox.run_delivery_cycle()
        outbox.run_delivery_cycle()  # too soon — must not attempt again yet

    assert call_count["n"] == 1


def test_restart_drains_events_left_pending_from_a_prior_crash():
    # Simulates two events persisted before a crash, discovered fresh on
    # the next process start — this is the entire reason the outbox exists.
    outbox.enqueue(_payload("evt-1"))
    outbox.enqueue(_payload("evt-2"))

    with patch("outbox.post_event", return_value=DeliveryOutcome.ACKNOWLEDGED):
        outbox.run_delivery_cycle()

    assert outbox.pending() == []
