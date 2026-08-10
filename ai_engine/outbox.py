"""Directory-backed durable outbox for AI detection events (D-012).

Pure module: no cv2, no ultralytics. One JSON file per pending event under
OUTBOX_DIR; a `quarantine/` subdirectory holds terminal-defect events kept
for diagnosis, never retried. No SQLite, no broker — the engine must stay
simple and inspectable, and D-003 forbids it touching the backend's
database directly.

`config` is imported as a module (not `from config import OUTBOX_DIR`) so
tests can monkeypatch `config.OUTBOX_DIR` to a temp directory.
"""

import json
import logging
import os
import random
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import config
from backend_client import DeliveryOutcome, post_event

logger = logging.getLogger("ai_engine")

_BASE_BACKOFF_SECONDS = 2.0
_MAX_BACKOFF_SECONDS = 300.0
_WORKER_POLL_SECONDS = 1.0


def _outbox_dir() -> Path:
    return config.OUTBOX_DIR


def _quarantine_dir() -> Path:
    return config.OUTBOX_DIR / "quarantine"


def _ensure_dirs() -> None:
    _outbox_dir().mkdir(parents=True, exist_ok=True)
    _quarantine_dir().mkdir(parents=True, exist_ok=True)


def _filename_for(source_event_id: str, created_at: datetime) -> str:
    # Timestamp prefix makes a plain filename sort equal oldest-first order.
    stamp = created_at.strftime("%Y%m%dT%H%M%S%f")
    return f"{stamp}_{source_event_id}.json"


def _atomic_write(path: Path, record: dict) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(record), encoding="utf-8")
    os.replace(tmp_path, path)


def enqueue(payload: dict) -> Path:
    """Persist an event before relying on network delivery (D-012). Atomic:
    write a .tmp file, then os.replace — a crash mid-write leaves a .tmp
    that pending() ignores, never a half-written entry that poisons the
    queue on restart."""
    _ensure_dirs()
    now = datetime.now(UTC)
    source_event_id = payload.get("source_event_id") or str(uuid.uuid4())
    final_path = _outbox_dir() / _filename_for(source_event_id, now)
    record = {
        "payload": payload,
        "attempts": 0,
        "next_attempt_at": None,
        "created_at": now.isoformat(),
    }
    _atomic_write(final_path, record)
    return final_path


def _load(path: Path) -> dict | None:
    """Reads and parses a pending event file. A corrupt file is quarantined
    rather than left to block the queue on every subsequent pass."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Corrupt outbox entry %s: %s", path.name, exc)
        quarantine(path, "corrupt_json")
        return None


def pending() -> list[Path]:
    """All pending event files, oldest-first. `.tmp` files (mid-write
    crashes) and the quarantine/ subdirectory are excluded."""
    _ensure_dirs()
    return sorted(
        p for p in _outbox_dir().iterdir() if p.is_file() and p.suffix == ".json"
    )


def pending_camera_ids() -> set[int]:
    """Camera IDs with at least one event still queued for delivery.

    Read by supervisor.py's reconciliation (F20, be_audit/00_FINDINGS.md) to
    withhold a resume the backend's heartbeat snapshot would otherwise
    grant: the backend has no way to know about an event that hasn't been
    delivered yet, since nothing is committed to its DB until then."""
    camera_ids: set[int] = set()
    for path in pending():
        record = _load(path)
        if record is None:
            continue
        camera_id = record.get("payload", {}).get("camera_id")
        if camera_id is not None:
            camera_ids.add(camera_id)
    return camera_ids


def acknowledge(path: Path) -> None:
    """Delivery confirmed (or genuinely redundant, e.g. CONFLICT) — remove
    the entry."""
    path.unlink(missing_ok=True)


def quarantine(path: Path, reason: str) -> None:
    """Move a non-retryable event aside for diagnosis. Never retried —
    pending() only scans the top-level outbox directory."""
    _ensure_dirs()
    if not path.exists():
        return
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        record = {"payload": None}
    record["quarantine_reason"] = reason
    record["quarantined_at"] = datetime.now(UTC).isoformat()
    dest = _quarantine_dir() / path.name
    dest.write_text(json.dumps(record), encoding="utf-8")
    path.unlink(missing_ok=True)


def _compute_backoff_seconds(attempts: int) -> float:
    backoff = min(_BASE_BACKOFF_SECONDS * (2**attempts), _MAX_BACKOFF_SECONDS)
    return backoff + random.uniform(0, backoff * 0.25)


def mark_attempt(path: Path, *, minimum_backoff_seconds: float | None = None) -> None:
    """Bump the attempt count and schedule the next attempt with bounded
    exponential backoff plus jitter. `minimum_backoff_seconds` forces a
    longer wait for non-transient-but-not-terminal failures (AUTH_FAILURE
    — a misconfigured INTERNAL_API_KEY, not a network blip)."""
    record = _load(path)
    if record is None:
        return
    attempts = record.get("attempts", 0) + 1
    backoff = _compute_backoff_seconds(attempts)
    if minimum_backoff_seconds is not None:
        backoff = max(backoff, minimum_backoff_seconds)
    record["attempts"] = attempts
    record["next_attempt_at"] = (
        datetime.now(UTC) + timedelta(seconds=backoff)
    ).isoformat()
    _atomic_write(path, record)


def _is_due(record: dict) -> bool:
    next_attempt_at = record.get("next_attempt_at")
    if not next_attempt_at:
        return True
    return datetime.now(UTC) >= datetime.fromisoformat(next_attempt_at)


def _deliver_one(path: Path, on_camera_gone) -> None:
    record = _load(path)
    if record is None or not _is_due(record):
        return

    outcome = post_event(record["payload"])

    if outcome is DeliveryOutcome.ACKNOWLEDGED:
        acknowledge(path)
    elif outcome is DeliveryOutcome.CONFLICT:
        # The backend already has an open incident for that camera — this
        # event is genuinely redundant, not a failure.
        logger.info("Event %s conflicted with an open incident; dropping", path.name)
        acknowledge(path)
    elif outcome is DeliveryOutcome.CAMERA_GONE:
        camera_id = record["payload"].get("camera_id")
        acknowledge(path)
        if on_camera_gone is not None and camera_id is not None:
            on_camera_gone(camera_id)
    elif outcome is DeliveryOutcome.AUTH_FAILURE:
        mark_attempt(path, minimum_backoff_seconds=_MAX_BACKOFF_SECONDS)
    elif outcome is DeliveryOutcome.QUARANTINE:
        quarantine(path, "validation_rejected")
    else:  # RETRY — transient (5xx, timeout, connection error)
        mark_attempt(path)


def run_delivery_cycle(on_camera_gone=None) -> None:
    """One oldest-first pass over the outbox. Safe to call directly for a
    startup drain, or repeatedly from the worker thread."""
    for path in pending():
        try:
            _deliver_one(path, on_camera_gone)
        except Exception:
            logger.exception("Unhandled error delivering outbox event %s", path.name)


def _worker_loop(on_camera_gone) -> None:
    while True:
        run_delivery_cycle(on_camera_gone)
        time.sleep(_WORKER_POLL_SECONDS)


def start_delivery_worker(*, on_camera_gone=None) -> threading.Thread:
    """A single bounded delivery worker thread — not a thread per event,
    and not the fire-and-forget ThreadPoolExecutor accident.py used to
    spawn. Draining pending events from a prior crash happens on this
    thread's first pass, before any new detection can be queued behind it."""
    thread = threading.Thread(target=_worker_loop, args=(on_camera_gone,), daemon=True)
    thread.start()
    return thread
