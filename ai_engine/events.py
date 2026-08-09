"""Detection-event construction: UUIDs, snapshot keys, and the v2 payload.

Pure module: no cv2, no ultralytics.
"""

import uuid
from datetime import UTC, datetime


def new_source_event_id() -> str:
    """One UUID per genuine detection event, reused on every retry — the
    whole idempotency mechanism (01_CONTRACTS.md §6.3)."""
    return str(uuid.uuid4())


def _to_utc(now: datetime) -> datetime:
    """Callers must pass a timezone-aware datetime. A naive value is
    ambiguous local time — accepting it here is exactly how the eight-hour
    Philippine-time shift bug happens, so fail loudly instead."""
    if now.tzinfo is None:
        raise ValueError(
            "events.py requires a timezone-aware datetime (use datetime.now(UTC)), "
            "got a naive one"
        )
    return now.astimezone(UTC)


def build_snapshot_key(camera_id: int, source_event_id: str, *, now: datetime) -> str:
    """2026/07/12/camera_5/<source_event_id>.jpg — UTC date segments,
    forward slashes only even on Windows (the backend's resolve() rejects
    backslash-leading keys and drive letters). The UUID filename fixes the
    legacy one-second-granularity collision bug (`cam{id}_{YYYYMMDD_HHMMSS}`)."""
    utc_now = _to_utc(now)
    return f"{utc_now:%Y/%m/%d}/camera_{camera_id}/{source_event_id}.jpg"


def build_event_payload(
    camera_id: int,
    source_event_id: str,
    snapshot_key: str,
    confidence: float,
    *,
    now: datetime,
) -> dict:
    """Matches DetectionLogCreateV2 exactly — that schema is
    extra="forbid", so these must be exactly these five keys, no more, no
    less. `detected_at` always carries a UTC offset."""
    utc_now = _to_utc(now)
    return {
        "source_event_id": source_event_id,
        "camera_id": camera_id,
        "detected_at": utc_now.isoformat(),
        "snapshot_key": snapshot_key,
        "confidence_score": round(confidence, 4),
    }
