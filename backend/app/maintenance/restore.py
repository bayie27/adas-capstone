"""D-011 Steps 5-6 — the restore-request flag file, the offline restore
sequence, and rollback.

`write_restore_request` is called by the FastAPI route (Step 5) and never
touches `adas.db`. `perform_offline_restore` and `perform_rollback` are
called by the external orchestrator (PowerShell/systemd) only, while
FastAPI and the AI engine are already stopped — never by FastAPI itself
(08_PKG_backup_ops.md Step 6).

01_CONTRACTS.md §3.10 — restore state is a **file**, not a table:
`BACKUP_DIR/restore_state.json`. A restore replaces `adas.db`, so anything
recorded about the restore *in* the database would be destroyed by the
restore itself.
"""

import json
import logging
import os
import shutil
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.maintenance.backup import (
    MaintenanceBusyError,
    _perform_backup_write,
    maintenance_lock,
)
from app.maintenance.manifest import (
    ORIGIN_PRE_RESTORE,
    db_path_for,
    read_manifest,
    validate_backup_id,
)
from app.maintenance.verify import (
    compute_sha256,
    run_foreign_key_check,
    run_integrity_check,
)

logger = logging.getLogger("adas.maintenance")

RESTORE_STATE_FILENAME = "restore_state.json"

STATUS_REQUESTED = "requested"
STATUS_IN_PROGRESS = "in_progress"
# DB file swapped, waiting for the orchestrator to confirm the restarted
# services are actually healthy before this counts as "completed".
STATUS_DB_RESTORED = "db_restored"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_ROLLED_BACK = "rolled_back"


class RestoreCandidateInvalidError(ValueError):
    pass


class RestoreError(RuntimeError):
    pass


__all__ = [
    "MaintenanceBusyError",
    "RestoreCandidateInvalidError",
    "RestoreError",
    "RestoreState",
    "STATUS_COMPLETED",
    "STATUS_DB_RESTORED",
    "STATUS_FAILED",
    "STATUS_IN_PROGRESS",
    "STATUS_REQUESTED",
    "STATUS_ROLLED_BACK",
    "finalize_restore",
    "perform_offline_restore",
    "perform_rollback",
    "read_restore_state",
    "record_restore_outcome_audit",
    "restore_state_path",
    "write_restore_request",
    "write_restore_state",
]


@dataclass
class RestoreStep:
    name: str
    started_at: str
    completed_at: str | None = None
    duration_ms: float | None = None
    ok: bool | None = None
    detail: str | None = None


@dataclass
class RestoreState:
    status: str
    backup_id: str
    requested_at: str
    requested_by: str | None = None
    emergency_backup_id: str | None = None
    steps: list[dict] = field(default_factory=list)
    error: str | None = None
    completed_at: str | None = None


def restore_state_path(backup_dir: Path) -> Path:
    return backup_dir / RESTORE_STATE_FILENAME


def write_restore_state(backup_dir: Path, state: RestoreState) -> None:
    """Atomic rename — a reader (the API's GET /restores/latest, or a
    resuming orchestrator) must never observe a half-written file."""
    path = restore_state_path(backup_dir)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(asdict(state), indent=2))
    os.replace(tmp, path)


def read_restore_state(backup_dir: Path) -> RestoreState | None:
    path = restore_state_path(backup_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    try:
        return RestoreState(**data)
    except TypeError:
        return None


def write_restore_request(
    backup_dir: Path, *, backup_id: str, requested_by: str | None
) -> RestoreState:
    """Step 5 — what the API route calls after its own auth/password/
    confirmation checks pass. Validates the id is a bare uuid4 hex (never a
    client filesystem path — edge case 4.10), re-confirms it still maps to
    a valid, uncorrupted manifest-listed file inside `backup_dir`, and
    publishes the request via atomic rename. Never touches `adas.db`."""
    from app.maintenance.backup import get_valid_backup

    validate_backup_id(backup_id)
    manifest = get_valid_backup(backup_dir, backup_id)
    if manifest is None:
        raise RestoreCandidateInvalidError(
            f"{backup_id} is not a valid, currently-listed restore point."
        )

    state = RestoreState(
        status=STATUS_REQUESTED,
        backup_id=backup_id,
        requested_at=datetime.now(UTC).isoformat(),
        requested_by=requested_by,
    )
    write_restore_state(backup_dir, state)
    return state


def _remove_sidecars(path: Path) -> None:
    """Removes `path`'s own `-wal`/`-shm` companions. Needed for the
    *temporary* restore/rollback copy too, not just the final `db_path` —
    `sqlite3.Connection.backup()` can carry WAL mode into the copy, and
    even a read-only `run_integrity_check` against a WAL-mode file can
    create a `-shm` sidecar next to it. Without this, a temp file's
    sidecars survive the `os.replace()` that renames only the main file,
    leaking `adas.db.restoring.tmp-wal`/`-shm` next to the real database
    on every restore."""
    for suffix in ("-wal", "-shm"):
        path.with_name(path.name + suffix).unlink(missing_ok=True)


@contextmanager
def _timed_step(state: RestoreState, name: str):
    step = RestoreStep(name=name, started_at=datetime.now(UTC).isoformat())
    t0 = time.perf_counter()
    try:
        yield step
        step.ok = True
    except Exception as exc:
        step.ok = False
        step.detail = str(exc)
        raise
    finally:
        step.completed_at = datetime.now(UTC).isoformat()
        step.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        state.steps.append(asdict(step))


def perform_offline_restore(
    *, backup_dir: Path, db_path: Path, backup_id: str
) -> RestoreState:
    """D-011 Steps 3-7 — the pure file/DB manipulation that must run only
    while FastAPI and the AI engine are already stopped by the caller.
    Steps 1-2 and 8-9 (actually stopping/starting those OS processes) are
    the external orchestrator's job: a Python process cannot cleanly stop
    or restart itself, which is the whole reason this architecture exists.
    Always leaves a `RestoreState` recording success or failure; never
    leaves the primary database half-replaced."""
    validate_backup_id(backup_id)
    state = read_restore_state(backup_dir)
    if state is None or state.backup_id != backup_id:
        state = RestoreState(
            status=STATUS_REQUESTED,
            backup_id=backup_id,
            requested_at=datetime.now(UTC).isoformat(),
        )
    state.status = STATUS_IN_PROGRESS
    write_restore_state(backup_dir, state)

    try:
        with maintenance_lock():
            # Step 3 — emergency backup of the CURRENT (pre-restore) database.
            with _timed_step(state, "emergency_backup"):
                emergency = _perform_backup_write(
                    db_path, backup_dir, ORIGIN_PRE_RESTORE
                )
            state.emergency_backup_id = emergency.backup_id
            write_restore_state(backup_dir, state)

            # Step 4 — re-verify the selected backup is still a valid restore
            # point: checksum, full integrity_check, foreign_key_check.
            with _timed_step(state, "verify_selected_backup"):
                manifest = read_manifest(backup_dir, backup_id)
                if manifest is None or not manifest.valid:
                    raise RestoreError(
                        f"Backup {backup_id} is not a valid restore point."
                    )
                selected_path = db_path_for(backup_dir, backup_id)
                if (
                    not selected_path.exists()
                    or compute_sha256(selected_path) != manifest.sha256
                ):
                    raise RestoreError(
                        f"Backup {backup_id} failed checksum re-verification."
                    )
                if not run_integrity_check(selected_path):
                    raise RestoreError(f"Backup {backup_id} failed integrity_check.")
                if not run_foreign_key_check(selected_path):
                    raise RestoreError(f"Backup {backup_id} failed foreign_key_check.")

            # Step 5 — restore to a temporary path and validate again.
            tmp_restore_path = db_path.with_name(db_path.name + ".restoring.tmp")
            with _timed_step(state, "restore_to_temp"):
                shutil.copyfile(selected_path, tmp_restore_path)
                if not run_integrity_check(tmp_restore_path):
                    tmp_restore_path.unlink(missing_ok=True)
                    _remove_sidecars(tmp_restore_path)
                    raise RestoreError("Restored temp database failed integrity_check.")

            # Step 6 — remove obsolete WAL/SHM sidecars, for both the
            # primary path and the temp copy itself (see _remove_sidecars).
            # Only reached once services are confirmed offline (the
            # caller's responsibility).
            with _timed_step(state, "remove_sidecars"):
                _remove_sidecars(db_path)
                _remove_sidecars(tmp_restore_path)

            # Step 7 — atomically replace the primary database.
            with _timed_step(state, "swap_primary_database"):
                os.replace(tmp_restore_path, db_path)

            state.status = STATUS_DB_RESTORED
            write_restore_state(backup_dir, state)
            return state
    except Exception as exc:
        state.status = STATUS_FAILED
        state.error = str(exc)
        write_restore_state(backup_dir, state)
        logger.error("Offline restore failed for backup_id=%s: %s", backup_id, exc)
        raise


def perform_rollback(*, backup_dir: Path, db_path: Path) -> RestoreState:
    """Invoked by the orchestrator when readiness or a required startup
    check fails after `perform_offline_restore`. Restores the emergency
    pre-restore backup recorded in `restore_state.json`. A failed restore
    may never leave the system silently half-restored (D-011)."""
    state = read_restore_state(backup_dir)
    if state is None or state.emergency_backup_id is None:
        raise RestoreError("No emergency backup recorded; cannot roll back.")

    emergency_id = state.emergency_backup_id
    try:
        with maintenance_lock():
            with _timed_step(state, "rollback_verify_emergency"):
                manifest = read_manifest(backup_dir, emergency_id)
                if manifest is None:
                    raise RestoreError(
                        f"Emergency backup {emergency_id} manifest missing."
                    )
                emergency_path = db_path_for(backup_dir, emergency_id)
                if (
                    not emergency_path.exists()
                    or compute_sha256(emergency_path) != manifest.sha256
                ):
                    raise RestoreError(
                        "Emergency backup failed checksum re-verification."
                    )

            tmp_restore_path = db_path.with_name(db_path.name + ".rollback.tmp")
            with _timed_step(state, "rollback_restore_to_temp"):
                shutil.copyfile(emergency_path, tmp_restore_path)
                if not run_integrity_check(tmp_restore_path):
                    tmp_restore_path.unlink(missing_ok=True)
                    _remove_sidecars(tmp_restore_path)
                    raise RestoreError("Emergency backup failed integrity_check.")

            with _timed_step(state, "rollback_remove_sidecars"):
                _remove_sidecars(db_path)
                _remove_sidecars(tmp_restore_path)

            with _timed_step(state, "rollback_swap_primary_database"):
                os.replace(tmp_restore_path, db_path)

            state.status = STATUS_ROLLED_BACK
            state.completed_at = datetime.now(UTC).isoformat()
            write_restore_state(backup_dir, state)
            return state
    except Exception as exc:
        state.status = STATUS_FAILED
        state.error = f"rollback failed: {exc}"
        write_restore_state(backup_dir, state)
        logger.critical(
            "Rollback FAILED for backup_id=%s emergency_backup_id=%s: %s — system "
            "may be left in an inconsistent state, manual intervention required.",
            state.backup_id,
            emergency_id,
            exc,
        )
        raise


def finalize_restore(backup_dir: Path, *, healthy: bool) -> RestoreState:
    """Called by the orchestrator once `/healthz/ready` and a fresh AI
    heartbeat are both confirmed. On failure, the orchestrator is expected
    to call `perform_rollback` instead/first — this only records the
    outcome that was reached."""
    state = read_restore_state(backup_dir)
    if state is None:
        raise RestoreError("No restore in progress.")
    state.status = STATUS_COMPLETED if healthy else STATUS_FAILED
    state.completed_at = datetime.now(UTC).isoformat()
    write_restore_state(backup_dir, state)
    return state


def record_restore_outcome_audit(db_path: Path, *, state: RestoreState) -> None:
    """08_PKG_backup_ops.md Step 5 — the `RESTORE_TRIGGER` audit row for the
    *request* lives in the pre-restore database (and therefore in the
    emergency backup, which captured it). Once the restored (or
    rolled-back) database is live again, the outcome is written as a fresh
    `system`-actor row directly via `sqlite3` — this package stays free of
    an app.models/SQLAlchemy dependency, and by the time this runs the
    audit_log table's shape is whatever the now-live database already has.
    Best-effort: a failure to write this row must not raise into the
    orchestrator, since the restore/rollback itself already succeeded or
    failed independently of this bookkeeping step."""
    detail = {
        "outcome": state.status,
        "emergency_backup_id": state.emergency_backup_id,
    }
    result = (
        "success"
        if state.status in (STATUS_COMPLETED, STATUS_ROLLED_BACK)
        else "failure"
    )
    created_at = str(datetime.now(UTC).replace(tzinfo=None))

    try:
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO audit_log "
                "(actor_type, action, target_type, target_ref, result, detail, created_at) "
                "VALUES ('system', 'RESTORE_TRIGGER', 'restore', ?, ?, ?, ?)",
                (state.backup_id, result, json.dumps(detail), created_at),
            )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.critical(
            "Failed to write the post-restore outcome audit row for backup_id=%s "
            "status=%s.",
            state.backup_id,
            state.status,
            exc_info=True,
        )
