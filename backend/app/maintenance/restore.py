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
import uuid
from contextlib import contextmanager, nullcontext
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.maintenance.backup import (
    MaintenanceBusyError,
    _check_disk_space,
    _perform_backup_write,
    _prune_pre_restore_backups_unlocked,
    _remove_sidecars,
    maintenance_lock,
)
from app.maintenance.manifest import (
    ORIGIN_PRE_RESTORE,
    db_path_for,
    read_manifest,
    validate_backup_id,
)
from app.maintenance.storage import (
    STORAGE_TIER_DEGRADED,
    StorageTargetProvider,
    probe_protected_storage,
    validate_storage_tier,
)
from app.maintenance.verify import (
    compute_sha256,
    run_foreign_key_check,
    run_integrity_check,
)

logger = logging.getLogger("adas.maintenance")

RESTORE_STATE_FILENAME = "restore_state.json"
RESTORE_REQUEST_GRACE_SECONDS = 3
RESTORE_REQUEST_MAX_AGE_SECONDS = 60

STATUS_REQUESTED = "requested"
STATUS_IN_PROGRESS = "in_progress"
# DB file swapped, waiting for the orchestrator to confirm the restarted
# services are actually healthy before this counts as "completed".
STATUS_DB_RESTORED = "db_restored"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_ROLLED_BACK = "rolled_back"
STATUS_MANUAL_INTERVENTION = "manual_intervention"
VALID_RESTORE_STATUSES = frozenset(
    {
        STATUS_REQUESTED,
        STATUS_IN_PROGRESS,
        STATUS_DB_RESTORED,
        STATUS_COMPLETED,
        STATUS_FAILED,
        STATUS_ROLLED_BACK,
        STATUS_MANUAL_INTERVENTION,
    }
)


class RestoreCandidateInvalidError(ValueError):
    pass


class RestoreRequestBusyError(RuntimeError):
    """Raised when a new request would overwrite an active request."""


class RestoreError(RuntimeError):
    pass


class RestoreStateUnreadableError(RestoreError):
    """Raised instead of treating an indeterminate state file as empty."""


__all__ = [
    "MaintenanceBusyError",
    "RestoreCandidateInvalidError",
    "RestoreRequestBusyError",
    "RestoreError",
    "RestoreStateUnreadableError",
    "RestoreState",
    "RESTORE_REQUEST_GRACE_SECONDS",
    "RESTORE_REQUEST_MAX_AGE_SECONDS",
    "STATUS_COMPLETED",
    "STATUS_DB_RESTORED",
    "STATUS_FAILED",
    "STATUS_IN_PROGRESS",
    "STATUS_REQUESTED",
    "STATUS_ROLLED_BACK",
    "STATUS_MANUAL_INTERVENTION",
    "VALID_RESTORE_STATUSES",
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
    storage_tier: str = STORAGE_TIER_DEGRADED
    requested_by: str | None = None
    request_id: str | None = None
    execute_after: str | None = None
    claimed_at: str | None = None
    emergency_backup_id: str | None = None
    emergency_storage_tier: str = STORAGE_TIER_DEGRADED
    steps: list[dict] = field(default_factory=list)
    error: str | None = None
    completed_at: str | None = None


def restore_state_path(backup_dir: Path) -> Path:
    return backup_dir / RESTORE_STATE_FILENAME


def write_restore_state(backup_dir: Path, state: RestoreState) -> None:
    """Atomic rename — a reader (the API's GET /restores/latest, or a
    resuming orchestrator) must never observe a half-written file."""
    path = restore_state_path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def read_restore_state(backup_dir: Path) -> RestoreState | None:
    path = restore_state_path(backup_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    required = {"status", "backup_id", "requested_at"}
    if not required.issubset(data):
        return None
    if data.get("status") not in VALID_RESTORE_STATUSES:
        return None
    if not isinstance(data.get("backup_id"), str) or not isinstance(
        data.get("requested_at"), str
    ):
        return None
    try:
        validate_backup_id(data["backup_id"])
        if data.get("emergency_backup_id") is not None:
            validate_backup_id(data["emergency_backup_id"])
    except (TypeError, ValueError):
        return None
    try:
        storage_tier = validate_storage_tier(
            data.get("storage_tier", STORAGE_TIER_DEGRADED)
        )
        emergency_storage_tier = validate_storage_tier(
            data.get("emergency_storage_tier", STORAGE_TIER_DEGRADED)
        )
    except (TypeError, ValueError):
        return None
    try:
        requested_at = datetime.fromisoformat(data["requested_at"])
    except (TypeError, ValueError):
        return None
    if requested_at.tzinfo is None:
        return None
    for key in (
        "requested_by",
        "request_id",
        "execute_after",
        "claimed_at",
        "emergency_backup_id",
        "error",
        "completed_at",
    ):
        if key in data and data[key] is not None and not isinstance(data[key], str):
            return None
    if not isinstance(data.get("steps", []), list) or any(
        not isinstance(step, dict) for step in data.get("steps", [])
    ):
        return None
    safe_steps = []
    for step in data.get("steps", []):
        safe_step = dict(step)
        for key in ("name", "detail"):
            value = safe_step.get(key)
            if isinstance(value, str) and (
                "\\" in value or "/" in value or len(value) > 256
            ):
                safe_step[key] = "operation_failed"
        safe_steps.append(safe_step)
    fields = {
        "status",
        "backup_id",
        "requested_at",
        "requested_by",
        "request_id",
        "execute_after",
        "claimed_at",
        "emergency_backup_id",
        "steps",
        "error",
        "completed_at",
    }
    safe_error = data.get("error")
    if isinstance(safe_error, str) and (
        "\\" in safe_error or "/" in safe_error or len(safe_error) > 256
    ):
        safe_error = "restore_failed"
    try:
        return RestoreState(
            **{
                **{
                    key: value
                    for key, value in data.items()
                    if key in fields and key not in {"error", "steps"}
                },
                "storage_tier": storage_tier,
                "emergency_storage_tier": emergency_storage_tier,
                "error": safe_error,
                "steps": safe_steps,
            }
        )
    except (TypeError, ValueError):
        return None


def restore_state_is_unreadable(backup_dir: Path) -> bool:
    """Distinguish a corrupt existing state file from a never-used one."""
    path = restore_state_path(backup_dir)
    return path.exists() and read_restore_state(backup_dir) is None


def _as_aware_utc(value: datetime | str) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Restore timestamps must include an explicit timezone.")
    return parsed.astimezone(UTC)


def _safe_restore_error(exc: BaseException) -> str:
    """Keep path-bearing OS messages out of restore state/API responses."""
    if isinstance(exc, RestoreError):
        return str(exc)
    return type(exc).__name__


def write_restore_request(
    backup_dir: Path,
    *,
    backup_id: str,
    storage_tier: str = STORAGE_TIER_DEGRADED,
    protected_backup_dir: Path | None = None,
    db_path: Path | None = None,
    storage_provider: StorageTargetProvider | None = None,
    requested_by: str | None,
    grace_seconds: int = RESTORE_REQUEST_GRACE_SECONDS,
    now: datetime | None = None,
    assume_lock_held: bool = False,
) -> RestoreState:
    """Step 5 — what the API route calls after its own auth/password/
    confirmation checks pass. Validates the id is a bare uuid4 hex (never a
    client filesystem path — edge case 4.10), re-confirms it still maps to
    a valid, uncorrupted manifest-listed file inside `backup_dir`, and
    publishes the request via atomic rename. Never touches `adas.db`."""
    from app.maintenance.backup import get_valid_backup

    with nullcontext() if assume_lock_held else maintenance_lock(backup_dir):
        validate_backup_id(backup_id)
        validate_storage_tier(storage_tier)
        if restore_state_is_unreadable(backup_dir):
            raise RestoreStateUnreadableError(
                "Restore state is unreadable; refusing to publish a new request."
            )
        current = read_restore_state(backup_dir)
        if current is not None and current.status in {
            STATUS_REQUESTED,
            STATUS_IN_PROGRESS,
            STATUS_DB_RESTORED,
        }:
            raise RestoreRequestBusyError(
                "A restore request is already active; wait for it to finish."
            )
        manifest = get_valid_backup(
            backup_dir,
            backup_id,
            storage_tier,
            protected_backup_dir=protected_backup_dir,
            db_path=db_path,
            storage_provider=storage_provider,
        )
        if manifest is None:
            raise RestoreCandidateInvalidError(
                f"{backup_id} is not a valid, currently-listed restore point."
            )

        requested_at = _as_aware_utc(now or datetime.now(UTC))
        state = RestoreState(
            status=STATUS_REQUESTED,
            backup_id=backup_id,
            requested_at=requested_at.isoformat(),
            storage_tier=storage_tier,
            requested_by=requested_by,
            request_id=uuid.uuid4().hex,
            execute_after=(
                requested_at + timedelta(seconds=max(0, grace_seconds))
            ).isoformat(),
        )
        write_restore_state(backup_dir, state)
        return state


def _is_revision_compatible(revision: str) -> bool:
    """P9 — a backup's recorded schema revision must be one this codebase's
    own Alembic migration chain recognizes. Imports app.core.migrations
    lazily (alembic + Settings only, no ORM session) rather than at module
    scope, matching this package's existing preference for a minimal,
    late-bound dependency footprint (see record_restore_outcome_audit's
    docstring)."""
    from app.core.config import settings as app_settings
    from app.core.migrations import is_known_schema_revision

    return is_known_schema_revision(app_settings, revision)


def _selected_artifact_root(
    backup_dir: Path,
    *,
    storage_tier: str,
    protected_backup_dir: Path | None,
    db_path: Path,
    storage_provider: StorageTargetProvider | None,
) -> Path:
    validate_storage_tier(storage_tier)
    if storage_tier == STORAGE_TIER_DEGRADED:
        return Path(backup_dir)
    if protected_backup_dir is None:
        raise RestoreCandidateInvalidError(
            "The selected protected backup storage is not configured."
        )
    probe = probe_protected_storage(
        protected_backup_dir,
        live_db_path=db_path,
        required_bytes=1,
        provider=storage_provider,
    )
    if not probe.available:
        raise RestoreCandidateInvalidError(
            "The selected protected backup storage is unavailable."
        )
    return Path(protected_backup_dir)


def _verify_manifest_artifact(
    artifact_dir: Path,
    backup_id: str,
    *,
    full: bool,
    require_revision: bool = True,
):
    """Verify one manifest and return its path without exposing the root."""
    manifest = read_manifest(artifact_dir, backup_id)
    if manifest is None or not manifest.valid:
        raise RestoreError(f"Backup {backup_id} is not a valid restore point.")
    artifact_path = db_path_for(artifact_dir, backup_id)
    try:
        size_matches = (
            artifact_path.exists()
            and manifest.filename == artifact_path.name
            and manifest.file_size == artifact_path.stat().st_size
        )
        checksum_matches = size_matches and (
            compute_sha256(artifact_path) == manifest.sha256
        )
    except OSError as exc:
        raise RestoreError(f"Backup {backup_id} could not be read.") from exc
    if not checksum_matches:
        raise RestoreError(f"Backup {backup_id} failed checksum re-verification.")
    if full and not run_integrity_check(artifact_path):
        raise RestoreError(f"Backup {backup_id} failed integrity_check.")
    if not run_foreign_key_check(artifact_path):
        raise RestoreError(f"Backup {backup_id} failed foreign_key_check.")
    if require_revision and (
        manifest.schema_revision is None
        or not _is_revision_compatible(manifest.schema_revision)
    ):
        raise RestoreError(f"Backup {backup_id} has an incompatible schema revision.")
    return manifest, artifact_path


def _record_failed_state_if_current(
    backup_dir: Path,
    state: RestoreState,
    *,
    error: str,
    status: str = STATUS_FAILED,
) -> None:
    """Persist a failure without overwriting a newer restore request.

    The normal failure path runs after the operation's lease has been
    released. Reacquiring the same lease and comparing the durable request
    identity closes the race where the API accepts a new request before the
    old operation records its exception.
    """
    try:
        with maintenance_lock(backup_dir):
            current = read_restore_state(backup_dir)
            if current is None or current.backup_id != state.backup_id:
                return
            if state.request_id is None:
                if current.request_id is not None:
                    return
            elif current.request_id != state.request_id:
                return
            if current.status in {
                STATUS_COMPLETED,
                STATUS_FAILED,
                STATUS_ROLLED_BACK,
                STATUS_MANUAL_INTERVENTION,
            }:
                return
            state.status = status
            state.error = error
            state.completed_at = datetime.now(UTC).isoformat()
            write_restore_state(backup_dir, state)
    except (MaintenanceBusyError, OSError):
        logger.critical(
            "Could not persist a failure for restore request_id=%s without "
            "risking a concurrent state overwrite.",
            state.request_id,
            exc_info=True,
        )


@contextmanager
def _timed_step(state: RestoreState, name: str):
    step = RestoreStep(name=name, started_at=datetime.now(UTC).isoformat())
    t0 = time.perf_counter()
    try:
        yield step
        step.ok = True
    except Exception as exc:
        step.ok = False
        step.detail = _safe_restore_error(exc)
        raise
    finally:
        step.completed_at = datetime.now(UTC).isoformat()
        step.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        state.steps.append(asdict(step))


def perform_offline_restore(
    *,
    backup_dir: Path,
    db_path: Path,
    backup_id: str,
    storage_tier: str = STORAGE_TIER_DEGRADED,
    protected_backup_dir: Path | None = None,
    storage_provider: StorageTargetProvider | None = None,
) -> RestoreState:
    """D-011 Steps 3-7 — the pure file/DB manipulation that must run only
    while FastAPI and the AI engine are already stopped by the caller.
    Steps 1-2 and 8-9 (actually stopping/starting those OS processes) are
    the external orchestrator's job: a Python process cannot cleanly stop
    or restart itself, which is the whole reason this architecture exists.
    Always leaves a `RestoreState` recording success or failure; never
    leaves the primary database half-replaced."""
    validate_backup_id(backup_id)
    validate_storage_tier(storage_tier)
    state: RestoreState | None = None
    tmp_restore_path: Path | None = None
    state_owned = False
    emergency = None

    try:
        with maintenance_lock(backup_dir):
            if restore_state_is_unreadable(backup_dir):
                raise RestoreStateUnreadableError(
                    "Restore state is unreadable; refusing to continue."
                )
            state = read_restore_state(backup_dir)
            if (
                state is not None
                and state.backup_id != backup_id
                and state.status
                in {
                    STATUS_REQUESTED,
                    STATUS_IN_PROGRESS,
                    STATUS_DB_RESTORED,
                }
            ):
                raise RestoreError(
                    "A different restore request is already active; refusing to overwrite it."
                )
            if (
                state is not None
                and state.backup_id == backup_id
                and state.storage_tier != storage_tier
                and state.status
                in {
                    STATUS_REQUESTED,
                    STATUS_IN_PROGRESS,
                    STATUS_DB_RESTORED,
                }
            ):
                raise RestoreError(
                    "The selected restore tier does not match the active request."
                )
            if state is None or state.backup_id != backup_id:
                requested_at = datetime.now(UTC)
                state = RestoreState(
                    status=STATUS_REQUESTED,
                    backup_id=backup_id,
                    requested_at=requested_at.isoformat(),
                    storage_tier=storage_tier,
                    request_id=uuid.uuid4().hex,
                    execute_after=requested_at.isoformat(),
                )
            elif state.status in {
                STATUS_COMPLETED,
                STATUS_ROLLED_BACK,
                STATUS_MANUAL_INTERVENTION,
            }:
                raise RestoreError(
                    f"Restore request is already terminal ({state.status}); refusing to repeat it."
                )
            elif state.status == STATUS_DB_RESTORED:
                raise RestoreError(
                    "The database has already been swapped; complete readiness or roll back first."
                )

            state.status = STATUS_IN_PROGRESS
            state.storage_tier = storage_tier
            state.error = None
            state.completed_at = None
            state_owned = True
            write_restore_state(backup_dir, state)

            # Step 3 — emergency backup of the CURRENT (pre-restore) database.
            with _timed_step(state, "emergency_backup"):
                _check_disk_space(db_path, backup_dir)
                emergency = _perform_backup_write(
                    db_path,
                    backup_dir,
                    ORIGIN_PRE_RESTORE,
                    storage_tier=STORAGE_TIER_DEGRADED,
                    storage_reason="pre_restore_emergency",
                )
                _verify_manifest_artifact(backup_dir, emergency.backup_id, full=True)
            state.emergency_backup_id = emergency.backup_id
            state.emergency_storage_tier = STORAGE_TIER_DEGRADED
            write_restore_state(backup_dir, state)

            selected_root = _selected_artifact_root(
                backup_dir,
                storage_tier=storage_tier,
                protected_backup_dir=protected_backup_dir,
                db_path=db_path,
                storage_provider=storage_provider,
            )

            # Step 4 — re-verify the selected backup while the services are
            # offline.  The selected tier is resolved independently from the
            # local emergency state, so a duplicate id in both roots cannot
            # silently select the wrong database.
            with _timed_step(state, "verify_selected_backup"):
                _manifest, selected_path = _verify_manifest_artifact(
                    selected_root, backup_id, full=True
                )

            # Step 5 — restore to a temporary path and validate again.
            tmp_restore_path = db_path.with_name(db_path.name + ".restoring.tmp")
            with _timed_step(state, "restore_to_temp"):
                shutil.copyfile(selected_path, tmp_restore_path)
                if not run_integrity_check(tmp_restore_path):
                    tmp_restore_path.unlink(missing_ok=True)
                    _remove_sidecars(tmp_restore_path)
                    raise RestoreError("Restored temp database failed integrity_check.")
                if not run_foreign_key_check(tmp_restore_path):
                    tmp_restore_path.unlink(missing_ok=True)
                    _remove_sidecars(tmp_restore_path)
                    raise RestoreError(
                        "Restored temp database failed foreign_key_check."
                    )

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
        if (
            emergency is not None
            and state is not None
            and state.emergency_backup_id is None
        ):
            from app.maintenance.backup import _remove_backup_files

            _remove_backup_files(backup_dir, emergency.backup_id)
        if state is not None and state_owned:
            _record_failed_state_if_current(
                backup_dir,
                state,
                error="Restore failed; manual intervention may be required.",
            )
        logger.error(
            "Offline restore failed for backup_id=%s (%s).",
            backup_id,
            type(exc).__name__,
        )
        raise
    finally:
        if tmp_restore_path is not None:
            tmp_restore_path.unlink(missing_ok=True)
            _remove_sidecars(tmp_restore_path)


def perform_rollback(*, backup_dir: Path, db_path: Path) -> RestoreState:
    """Invoked by the orchestrator when readiness or a required startup
    check fails after `perform_offline_restore`. Restores the emergency
    pre-restore backup recorded in `restore_state.json`. A failed restore
    may never leave the system silently half-restored (D-011)."""
    state: RestoreState | None = None
    emergency_id: str | None = None
    tmp_restore_path: Path | None = None
    state_owned = False
    try:
        with maintenance_lock(backup_dir):
            state = read_restore_state(backup_dir)
            if state is None:
                raise RestoreError("No emergency backup recorded; cannot roll back.")
            state_owned = True
            if state.emergency_backup_id is None:
                raise RestoreError("No emergency backup recorded; cannot roll back.")

            emergency_id = state.emergency_backup_id
            validate_storage_tier(state.emergency_storage_tier)
            if state.emergency_storage_tier != STORAGE_TIER_DEGRADED:
                raise RestoreError(
                    "The emergency restore reserve is not on local degraded storage."
                )
            with _timed_step(state, "rollback_verify_emergency"):
                _manifest, emergency_path = _verify_manifest_artifact(
                    backup_dir, emergency_id, full=True
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
            state.error = None
            state.completed_at = datetime.now(UTC).isoformat()
            write_restore_state(backup_dir, state)
            try:
                from app.core.config import settings

                keep = settings.BACKUP_PRE_RESTORE_RETENTION
            except (ImportError, AttributeError):
                keep = 3
            _prune_pre_restore_backups_unlocked(backup_dir, keep=keep)
            return state
    except Exception as exc:
        if state is not None and state_owned:
            _record_failed_state_if_current(
                backup_dir,
                state,
                error="Rollback failed; manual intervention is required.",
                status=STATUS_MANUAL_INTERVENTION,
            )
        logger.critical(
            "Rollback FAILED for backup_id=%s emergency_backup_id=%s: %s — system "
            "may be left in an inconsistent state, manual intervention required.",
            state.backup_id if state is not None else None,
            emergency_id,
            type(exc).__name__,
        )
        raise
    finally:
        if tmp_restore_path is not None:
            tmp_restore_path.unlink(missing_ok=True)
            _remove_sidecars(tmp_restore_path)


def finalize_restore(backup_dir: Path, *, healthy: bool) -> RestoreState:
    """Called by the orchestrator once `/healthz/ready` and a fresh AI
    heartbeat are both confirmed. On failure, the orchestrator is expected
    to call `perform_rollback` instead/first — this only records the
    outcome that was reached."""
    with maintenance_lock(backup_dir):
        state = read_restore_state(backup_dir)
        if state is None:
            raise RestoreError("No restore in progress.")
        if state.status != STATUS_DB_RESTORED:
            raise RestoreError(
                f"Restore cannot be finalized from status {state.status!r}."
            )
        state.status = STATUS_COMPLETED if healthy else STATUS_FAILED
        state.completed_at = datetime.now(UTC).isoformat()
        write_restore_state(backup_dir, state)
        # A terminal outcome makes the emergency id eligible for the bounded
        # pre-restore retention sweep.  The newest reserves are retained for
        # the configured safety window; active requests remain protected by
        # _active_restore_protected_ids().
        if healthy:
            try:
                from app.core.config import settings

                keep = settings.BACKUP_PRE_RESTORE_RETENTION
            except (ImportError, AttributeError):
                keep = 3
            _prune_pre_restore_backups_unlocked(backup_dir, keep=keep)
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
        "storage_tier": state.storage_tier,
        "emergency_backup_id": state.emergency_backup_id,
        "request_id": state.request_id,
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
