from datetime import UTC, datetime, timedelta, timezone

import events
import pytest


def test_snapshot_key_format_and_utc_date_segments():
    now = datetime(2026, 7, 12, 10, 30, 5, tzinfo=UTC)
    key = events.build_snapshot_key(5, "abc-123", now=now)
    assert key == "2026/07/12/camera_5/abc-123.jpg"


def test_snapshot_key_uses_utc_date_not_local_date():
    # 23:30 local in UTC-5 on the 11th is 04:30 UTC on the 12th — a naive
    # local-date bug would put this in the wrong day's folder.
    local_tz = timezone(timedelta(hours=-5))
    local_time = datetime(2026, 7, 11, 23, 30, 0, tzinfo=local_tz)
    key = events.build_snapshot_key(5, "abc-123", now=local_time)
    assert key == "2026/07/12/camera_5/abc-123.jpg"


def test_snapshot_key_forward_slashes_only():
    now = datetime(2026, 7, 12, 10, 30, 5, tzinfo=UTC)
    key = events.build_snapshot_key(5, "abc-123", now=now)
    assert "\\" not in key


@pytest.mark.parametrize(
    "builder", [events.build_snapshot_key, events.build_event_payload]
)
def test_naive_datetime_is_rejected(builder):
    naive = datetime(2026, 7, 12, 10, 30, 5)
    with pytest.raises(ValueError):
        if builder is events.build_snapshot_key:
            builder(5, "abc-123", now=naive)
        else:
            builder(5, "abc-123", "key.jpg", 0.9, now=naive)


def test_payload_detected_at_carries_utc_offset():
    now = datetime(2026, 7, 12, 10, 30, 5, 123000, tzinfo=UTC)
    payload = events.build_event_payload(5, "abc-123", "key.jpg", 0.87, now=now)
    assert payload["detected_at"].endswith("+00:00")


def test_payload_has_exactly_the_five_v2_keys():
    now = datetime.now(UTC)
    payload = events.build_event_payload(5, "abc-123", "key.jpg", 0.87, now=now)
    assert set(payload.keys()) == {
        "source_event_id",
        "camera_id",
        "detected_at",
        "snapshot_key",
        "confidence_score",
    }


def test_two_events_in_the_same_second_produce_different_keys():
    now = datetime(2026, 7, 12, 10, 30, 5, tzinfo=UTC)
    id1 = events.new_source_event_id()
    id2 = events.new_source_event_id()
    assert id1 != id2

    key1 = events.build_snapshot_key(5, id1, now=now)
    key2 = events.build_snapshot_key(5, id2, now=now)
    assert key1 != key2
