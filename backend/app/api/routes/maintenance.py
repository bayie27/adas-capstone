"""08_PKG_backup_ops.md Steps 4-5 — the backup and restore-request API.

A NEW module, deliberately separate from routes/system.py (P1's
unauthenticated probes) and routes/system_health.py (P5) so those packages
never touch this file. The URL prefix is still `/api/system/...`; only the
Python module boundary differs (01_CONTRACTS.md §5.8).

FastAPI never replaces `adas.db` and never gets shell execution here: the
backup routes call straight into `app.maintenance.backup` (online, safe);
the restore route only ever writes a durable request via
`app.maintenance.restore.write_restore_request` — the actual offline
restore is performed later by the independently supervised coordinator.
"""

import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.api.dependencies import get_current_admin, get_realtime_manager, require_admin
from app.core.config import settings
from app.core.db import get_session
from app.core.errors import AppHTTPException
from app.core.security import verify_password
from app.maintenance import coordinator as coordinator_mod
from app.maintenance import restore as restore_mod
from app.maintenance.backup import (
    RetentionConfig,
    list_backup_candidates,
    perform_backup_assuming_lock_held,
    release_maintenance_lock,
    resolve_sqlite_db_path,
    try_acquire_maintenance_lock,
)
from app.maintenance.manifest import (
    ORIGIN_MANUAL,
    ORIGIN_SCHEDULED,
    InvalidBackupIdError,
    list_manifests,
    validate_backup_id,
)
from app.models import AuditResult, User
from app.schemas.events import EventType, MaintenanceNoticeData, make_event
from app.schemas.maintenance import (
    BackupListResponse,
    BackupRead,
    BackupSummaryRead,
    BackupTriggerResponse,
    LastRestartRead,
    MaintenanceStatusRead,
    RestoreCoordinatorRead,
    RestoreRequestIn,
    RestoreStateRead,
    RestoreTriggerResponse,
)
from app.services import audit
from app.services.maintenance_schedule import scheduled_backup_is_due
from app.services.realtime import RealtimeManager

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/system", tags=["Maintenance"])

_require_admin_for_backup = require_admin("BACKUP_TRIGGER")
_require_admin_for_restore = require_admin("RESTORE_TRIGGER")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _busy_error() -> AppHTTPException:
    return AppHTTPException(
        status.HTTP_409_CONFLICT,
        "A backup or restore operation is already running.",
        code="CONFLICT_BUSY",
    )


def _retention() -> RetentionConfig:
    return RetentionConfig(
        daily=settings.BACKUP_DAILY_RETENTION, manual=settings.BACKUP_MANUAL_RETENTION
    )


def _run_manual_backup_job(
    *,
    engine: Engine,
    admin_user_id: int,
    source_ip: str | None,
) -> None:
    """Runs after the response is sent (Starlette's threadpool, since this
    is a plain sync callable — no extra thread bookkeeping of our own).
    The maintenance lock is already held by the route that scheduled this;
    always released here, and the outcome always audited, regardless of
    success or failure."""
    backup_id: str | None = None
    try:
        db_path = resolve_sqlite_db_path(settings.DATABASE_URL)
        manifest = perform_backup_assuming_lock_held(
            db_path, settings.BACKUP_DIR, ORIGIN_MANUAL, retention=_retention()
        )
        backup_id = manifest.backup_id
        result = AuditResult.SUCCESS if manifest.valid else AuditResult.FAILURE
        detail = {
            "backup_id": manifest.backup_id,
            "created_at": manifest.created_at,
            "origin": manifest.origin,
            "checks": manifest.checks,
        }
    except Exception as exc:
        logger.exception("Manual backup failed.")
        result = AuditResult.FAILURE
        detail = {"error_type": type(exc).__name__}
    finally:
        release_maintenance_lock()

    with Session(engine) as session:
        admin = session.get(User, admin_user_id)
        audit.record(
            session,
            action="BACKUP_TRIGGER",
            result=result,
            actor=admin,
            target_type="backup",
            target_ref=backup_id,
            detail=detail,
            source_ip=source_ip,
        )
        session.commit()


@router.get("/backups", response_model=BackupListResponse)
def list_backups_route(
    current_admin: User = Depends(get_current_admin),
) -> BackupListResponse:
    """Admin only. Never returns `artifact_path` or any absolute path — only
    the backup id, timestamps, origin, size, and validation status
    (01_CONTRACTS.md §1.6, §5.8)."""
    manifests = list_backup_candidates(settings.BACKUP_DIR)
    items = [
        BackupRead(
            backup_id=m.backup_id,
            created_at=m.created_at,
            origin=m.origin,
            file_size=m.file_size,
            valid=m.valid,
            checks=m.checks,
        )
        for m in manifests
    ]
    return BackupListResponse(total_filtered=len(items), items=items)


@router.post(
    "/backups",
    response_model=BackupTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_backup(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_admin: User = Depends(_require_admin_for_backup),
) -> BackupTriggerResponse:
    """Admin only — an admin can trigger an immediate backup before making
    config changes. The maintenance lock is acquired *synchronously* here
    (not inside the background task) so a second concurrent request gets
    an immediate `409 CONFLICT_BUSY` (edge case 1.13) rather than silently
    queuing; the actual write then runs in a bounded background task
    (Starlette's threadpool) and the route returns `202` right away. Both
    outcomes write a `BACKUP_TRIGGER` audit row — the busy rejection
    synchronously here, the eventual success/failure asynchronously once
    the background job finishes."""
    source_ip = _client_ip(request)

    if not try_acquire_maintenance_lock(settings.BACKUP_DIR):
        audit.record_out_of_band(
            session.get_bind(),
            action="BACKUP_TRIGGER",
            result=AuditResult.DENIED,
            actor=current_admin,
            target_type="backup",
            detail={"reason": "already_running"},
            source_ip=source_ip,
        )
        raise _busy_error()

    assert current_admin.user_id is not None
    background_tasks.add_task(
        _run_manual_backup_job,
        engine=request.app.state.engine,
        admin_user_id=current_admin.user_id,
        source_ip=source_ip,
    )
    return BackupTriggerResponse(
        detail="Backup started. Check GET /api/system/backups for the result."
    )


@router.post(
    "/restores",
    response_model=RestoreTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_restore(
    body: RestoreRequestIn,
    request: Request,
    session: Session = Depends(get_session),
    current_admin: User = Depends(_require_admin_for_restore),
    realtime_manager: RealtimeManager = Depends(get_realtime_manager),
) -> RestoreTriggerResponse:
    """Admin only, and deliberately heavy on authorization — this is
    destructive (08_PKG_backup_ops.md Step 5). Requires the current admin's
    password re-submitted in the body, the exact human-readable confirmation
    phrase, and a backup id that maps to a
    manifest-listed, currently-valid file inside BACKUP_DIR. Never accepts
    a client-supplied filesystem path — the id is validated (bare uuid4
    hex) before it is ever joined onto BACKUP_DIR (edge case 4.10). Writes
    only the restore-request file; never touches `adas.db`."""
    source_ip = _client_ip(request)

    if not verify_password(body.current_password, current_admin.password_hash):
        audit.record_out_of_band(
            session.get_bind(),
            action="RESTORE_TRIGGER",
            result=AuditResult.DENIED,
            actor=current_admin,
            target_type="restore",
            target_ref=body.backup_id,
            detail={"reason": "wrong_password"},
            source_ip=source_ip,
        )
        raise AppHTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Current password is incorrect.",
            code="AUTH_INVALID_CREDENTIALS",
        )

    expected = RestoreRequestIn.expected_confirmation()
    if body.confirmation != expected:
        audit.record_out_of_band(
            session.get_bind(),
            action="RESTORE_TRIGGER",
            result=AuditResult.DENIED,
            actor=current_admin,
            target_type="restore",
            target_ref=body.backup_id,
            detail={"reason": "confirmation_mismatch"},
            source_ip=source_ip,
        )
        raise AppHTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Confirmation must be exactly {expected!r}.",
            code="VALIDATION_ERROR",
        )

    # Reject path-unsafe input before consulting coordinator state.  This is
    # a pure input check; the selected manifest is still revalidated under
    # the lease immediately before publication.
    try:
        validate_backup_id(body.backup_id)
    except InvalidBackupIdError as exc:
        audit.record_out_of_band(
            session.get_bind(),
            action="RESTORE_TRIGGER",
            result=AuditResult.DENIED,
            actor=current_admin,
            target_type="restore",
            target_ref=body.backup_id,
            detail={"reason": "invalid_backup_id"},
            source_ip=source_ip,
        )
        raise AppHTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Not a valid backup id.",
            code="VALIDATION_ERROR",
        ) from exc

    availability = coordinator_mod.get_coordinator_availability(
        settings.BACKUP_DIR,
        stale_seconds=settings.RESTORE_COORDINATOR_STALE_SECONDS,
    )
    if not availability.available:
        if availability.reason == "busy":
            audit.record_out_of_band(
                session.get_bind(),
                action="RESTORE_TRIGGER",
                result=AuditResult.DENIED,
                actor=current_admin,
                target_type="restore",
                target_ref=body.backup_id,
                detail={"reason": "already_running"},
                source_ip=source_ip,
            )
            raise _busy_error()
        audit.record_out_of_band(
            session.get_bind(),
            action="RESTORE_TRIGGER",
            result=AuditResult.DENIED,
            actor=current_admin,
            target_type="restore",
            target_ref=body.backup_id,
            detail={"reason": "restore_coordinator_unavailable"},
            source_ip=source_ip,
        )
        raise AppHTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Automatic restore is unavailable because the maintenance service is not running.",
            code="RESTORE_COORDINATOR_UNAVAILABLE",
        )

    if not try_acquire_maintenance_lock(settings.BACKUP_DIR):
        audit.record_out_of_band(
            session.get_bind(),
            action="RESTORE_TRIGGER",
            result=AuditResult.DENIED,
            actor=current_admin,
            target_type="restore",
            target_ref=body.backup_id,
            detail={"reason": "already_running"},
            source_ip=source_ip,
        )
        raise _busy_error()

    try:
        # The heartbeat and restore document can change between the first
        # availability check and lease acquisition, so both are read again
        # while this process owns the publish lease.
        availability = coordinator_mod.get_coordinator_availability(
            settings.BACKUP_DIR,
            stale_seconds=settings.RESTORE_COORDINATOR_STALE_SECONDS,
        )
        current_state = restore_mod.read_restore_state(settings.BACKUP_DIR)
        if not availability.available:
            if availability.reason == "busy" or (
                current_state is not None
                and current_state.status in coordinator_mod.ACTIVE_RESTORE_STATUSES
            ):
                audit.record_out_of_band(
                    session.get_bind(),
                    action="RESTORE_TRIGGER",
                    result=AuditResult.DENIED,
                    actor=current_admin,
                    target_type="restore",
                    target_ref=body.backup_id,
                    detail={"reason": "already_running"},
                    source_ip=source_ip,
                )
                raise _busy_error()
            audit.record_out_of_band(
                session.get_bind(),
                action="RESTORE_TRIGGER",
                result=AuditResult.DENIED,
                actor=current_admin,
                target_type="restore",
                target_ref=body.backup_id,
                detail={"reason": "restore_coordinator_unavailable"},
                source_ip=source_ip,
            )
            raise AppHTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Automatic restore is unavailable because the maintenance service is not running.",
                code="RESTORE_COORDINATOR_UNAVAILABLE",
            )
        if (
            current_state is not None
            and current_state.status in coordinator_mod.ACTIVE_RESTORE_STATUSES
        ):
            audit.record_out_of_band(
                session.get_bind(),
                action="RESTORE_TRIGGER",
                result=AuditResult.DENIED,
                actor=current_admin,
                target_type="restore",
                target_ref=body.backup_id,
                detail={"reason": "already_running"},
                source_ip=source_ip,
            )
            raise _busy_error()

        state = restore_mod.write_restore_request(
            settings.BACKUP_DIR,
            backup_id=body.backup_id,
            requested_by=current_admin.username,
            grace_seconds=settings.RESTORE_REQUEST_GRACE_SECONDS,
            assume_lock_held=True,
        )
    except InvalidBackupIdError as exc:
        audit.record_out_of_band(
            session.get_bind(),
            action="RESTORE_TRIGGER",
            result=AuditResult.DENIED,
            actor=current_admin,
            target_type="restore",
            target_ref=body.backup_id,
            detail={"reason": "invalid_backup_id"},
            source_ip=source_ip,
        )
        raise AppHTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Not a valid backup id.",
            code="VALIDATION_ERROR",
        ) from exc
    except restore_mod.RestoreCandidateInvalidError as exc:
        audit.record_out_of_band(
            session.get_bind(),
            action="RESTORE_TRIGGER",
            result=AuditResult.DENIED,
            actor=current_admin,
            target_type="restore",
            target_ref=body.backup_id,
            detail={"reason": "not_a_valid_restore_point"},
            source_ip=source_ip,
        )
        raise AppHTTPException(
            status.HTTP_404_NOT_FOUND, "Backup not found.", code="NOT_FOUND"
        ) from exc
    except restore_mod.RestoreRequestBusyError as exc:
        audit.record_out_of_band(
            session.get_bind(),
            action="RESTORE_TRIGGER",
            result=AuditResult.DENIED,
            actor=current_admin,
            target_type="restore",
            target_ref=body.backup_id,
            detail={"reason": "already_running"},
            source_ip=source_ip,
        )
        raise _busy_error() from exc
    except restore_mod.RestoreStateUnreadableError as exc:
        audit.record_out_of_band(
            session.get_bind(),
            action="RESTORE_TRIGGER",
            result=AuditResult.DENIED,
            actor=current_admin,
            target_type="restore",
            target_ref=body.backup_id,
            detail={"reason": "restore_state_unavailable"},
            source_ip=source_ip,
        )
        raise AppHTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Automatic restore is temporarily unavailable. Please try again later.",
            code="RESTORE_STATE_UNAVAILABLE",
        ) from exc
    finally:
        release_maintenance_lock()

    audit.record(
        session,
        action="RESTORE_TRIGGER",
        result=AuditResult.SUCCESS,
        actor=current_admin,
        target_type="restore",
        target_ref=body.backup_id,
        detail={"status": state.status, "request_id": state.request_id},
        source_ip=source_ip,
    )
    session.commit()

    # Broadcast planned maintenance so connected dashboards can warn the
    # operator before the socket drops (08_PKG_backup_ops.md Step 5), on
    # D-008's typed event envelope now that P4/P3 realtime is in this
    # branch's history. broadcast() is synchronous and non-blocking
    # (04_PKG_realtime.md) — no await, and best-effort: a broadcast
    # failure must never fail this response.
    try:
        realtime_manager.broadcast(
            make_event(
                EventType.MAINTENANCE_NOTICE,
                MaintenanceNoticeData(
                    message="A database restore has been requested. The system "
                    "will go offline shortly for maintenance.",
                    backup_id=body.backup_id,
                ),
            )
        )
    except Exception:
        logger.warning(
            "Failed to broadcast the restore maintenance notice.", exc_info=True
        )

    return RestoreTriggerResponse(
        detail="Restore accepted. The system will restart automatically.",
        backup_id=body.backup_id,
        request_id=state.request_id or "",
        status="requested",
    )


def _serialize_restore_state(
    state: restore_mod.RestoreState | None,
) -> RestoreStateRead | None:
    if state is None:
        return None
    return RestoreStateRead(
        status=state.status,
        backup_id=state.backup_id,
        requested_at=state.requested_at,
        requested_by=state.requested_by,
        request_id=state.request_id,
        emergency_backup_id=state.emergency_backup_id,
        steps=state.steps,
        error=state.error,
        completed_at=state.completed_at,
    )


def _serialize_coordinator(
    availability: coordinator_mod.CoordinatorAvailability,
) -> RestoreCoordinatorRead:
    return RestoreCoordinatorRead(
        available=availability.available,
        state=availability.state,
        platform=availability.platform,
        last_seen_at=availability.last_seen_at,
        reason=availability.reason,
    )


@router.get("/restores/latest", response_model=RestoreStateRead | None)
def latest_restore_route(
    current_admin: User = Depends(get_current_admin),
) -> RestoreStateRead | None:
    """Admin only. `None` (serialized as `null`) when no restore has ever
    been requested."""
    state = restore_mod.read_restore_state(settings.BACKUP_DIR)
    return _serialize_restore_state(state)


def _newest_backup_summary(origin: str) -> BackupSummaryRead | None:
    for manifest in list_manifests(settings.BACKUP_DIR):
        if manifest.origin == origin and manifest.valid:
            return BackupSummaryRead(
                backup_id=manifest.backup_id,
                created_at=manifest.created_at,
                valid=manifest.valid,
            )
    return None


def _last_restart_from_log() -> LastRestartRead | None:
    """Reads the last line of var/log/maintenance-runs.jsonl (Step 5's
    per-restart-run record). Missing or corrupt is `None`, never a 500 —
    this file is written by an external PowerShell/systemd orchestrator
    this route has no control over."""
    path = settings.LOG_DIR / "maintenance-runs.jsonl"
    if not path.exists():
        return None
    try:
        lines = [line for line in path.read_text().splitlines() if line.strip()]
        if not lines:
            return None
        record = json.loads(lines[-1])
        return LastRestartRead(
            ran_at=record["started_at"],
            downtime_seconds=record.get("downtime_s"),
            ready=bool(record.get("ready", False)),
            exit_code=int(record.get("exit_code", 1)),
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


@router.get("/maintenance/status", response_model=MaintenanceStatusRead)
def maintenance_status_route(
    request: Request,
    current_admin: User = Depends(get_current_admin),
) -> MaintenanceStatusRead:
    """Admin only. Not audited — a routine read, and D-007 excludes routine
    viewing. Serves two audiences: the demo ("prove it runs nightly") and
    the frontend's Maintenance screen. Never returns `artifact_path`, a log
    path, or any other absolute path (01_CONTRACTS.md §1.6)."""
    scheduler = request.app.state.scheduler
    next_scheduled_backup_at = None
    if scheduler is not None:
        job = scheduler.get_job("daily_backup")
        if job is not None and job.next_run_time is not None:
            next_scheduled_backup_at = job.next_run_time.astimezone(UTC)

    return MaintenanceStatusRead(
        last_scheduled_backup=_newest_backup_summary(ORIGIN_SCHEDULED),
        last_manual_backup=_newest_backup_summary(ORIGIN_MANUAL),
        next_scheduled_backup_at=next_scheduled_backup_at,
        backup_overdue=scheduled_backup_is_due(
            settings.BACKUP_DIR, now=datetime.now(UTC)
        ),
        maintenance_hour_local=settings.MAINTENANCE_HOUR_LOCAL,
        maintenance_timezone=settings.REPORT_LOCAL_TIMEZONE,
        last_restart=_last_restart_from_log(),
        latest_restore=_serialize_restore_state(
            restore_mod.read_restore_state(settings.BACKUP_DIR)
        ),
        restore_coordinator=_serialize_coordinator(
            coordinator_mod.get_coordinator_availability(
                settings.BACKUP_DIR,
                stale_seconds=settings.RESTORE_COORDINATOR_STALE_SECONDS,
            )
        ),
    )
