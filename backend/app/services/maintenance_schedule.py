"""be_plan/18_PKG_scheduled_maintenance.md Step 1 — the in-app daily backup
job (NFR-18).

D-011's asymmetry: the backup and the restart get different owners because
they are different kinds of operation. An online backup can safely
self-heal on catch-up, so it lives here as an APScheduler job. The restart
is process-lifecycle (stop/start two OS processes, one of which — the AI
engine — this process has no handle on) and belongs to the Windows
Scheduled Task / systemd timer instead (18_PKG_scheduled_maintenance.md's
"one architectural decision").

Calls straight into app.maintenance.backup.create_backup() — the
maintenance core stays the single source of truth; nothing here
reimplements backup/validation logic.
"""

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.core.config import settings
from app.maintenance.backup import (
    MaintenanceBusyError,
    RetentionConfig,
    create_backup,
    resolve_sqlite_db_path,
)
from app.maintenance.manifest import (
    ORIGIN_SCHEDULED,
    BackupManifest,
    db_path_for,
    list_manifests,
)
from app.maintenance.verify import compute_sha256
from app.models import AuditResult
from app.services import audit

logger = logging.getLogger("uvicorn.error")

BACKUP_INTERVAL_HOURS = 24


def newest_scheduled_manifest(backup_dir: Path) -> BackupManifest | None:
    """Newest valid origin='scheduled' manifest, or None.

    Uses manifest.list_manifests() rather than backup.list_backups() — the
    latter re-computes SHA-256 over *every* retained backup on every call,
    correct for a restore-point listing but wasteful for an hourly due-check
    poll. This only re-verifies the single newest scheduled manifest, in
    scheduled_backup_is_due() below."""
    for manifest in list_manifests(backup_dir):
        if manifest.origin == ORIGIN_SCHEDULED and manifest.valid:
            return manifest
    return None


def scheduled_backup_is_due(
    backup_dir: Path, *, now: datetime, interval_hours: int = BACKUP_INTERVAL_HOURS
) -> bool:
    """True when there is no scheduled backup at all, or the newest one is
    older than `interval_hours`. Only `origin == "scheduled"` counts — a
    recent manual backup does not discharge the daily obligation, since
    "did the automated schedule run?" is a different question. A scheduled
    backup whose file has vanished or been corrupted since creation does
    not count as satisfying the interval either — re-verified here, not
    just trusted from the manifest's own recorded checks."""
    manifest = newest_scheduled_manifest(backup_dir)
    if manifest is None:
        return True

    path = db_path_for(backup_dir, manifest.backup_id)
    if not path.exists():
        return True
    try:
        if compute_sha256(path) != manifest.sha256:
            return True
    except OSError:
        return True

    age = now - datetime.fromisoformat(manifest.created_at)
    return age >= timedelta(hours=interval_hours)


def _retention() -> RetentionConfig:
    return RetentionConfig(
        daily=settings.BACKUP_DAILY_RETENTION, manual=settings.BACKUP_MANUAL_RETENTION
    )


def run_daily_backup(engine: Engine, *, trigger: str) -> None:
    """trigger is "scheduled" (the cron firing) or "catch_up" (the hourly
    due-check job, or the one-off check at lifespan startup).

    Never raises into the scheduler. `MaintenanceBusyError` means the API
    route or the PowerShell orchestrator already holds `_maintenance_lock`
    and is already backing up — the lock is doing its job, so this is a
    logged no-op, not a failure, and writes no audit row. Any other
    exception is caught, logged, and audited as a FAILURE."""
    db_path = resolve_sqlite_db_path(settings.DATABASE_URL)
    try:
        manifest = create_backup(
            db_path=db_path,
            backup_dir=settings.BACKUP_DIR,
            origin=ORIGIN_SCHEDULED,
            retention=_retention(),
        )
    except MaintenanceBusyError:
        logger.info(
            "Scheduled backup (trigger=%s) skipped: a backup or restore is "
            "already running.",
            trigger,
        )
        return
    except Exception:
        logger.exception("Scheduled backup (trigger=%s) failed.", trigger)
        with Session(engine) as session:
            audit.record(
                session,
                action="BACKUP_TRIGGER",
                result=AuditResult.FAILURE,
                actor=None,
                target_type="backup",
                detail={"trigger": trigger},
            )
            session.commit()
        return

    result = AuditResult.SUCCESS if manifest.valid else AuditResult.FAILURE
    with Session(engine) as session:
        audit.record(
            session,
            action="BACKUP_TRIGGER",
            result=result,
            actor=None,
            target_type="backup",
            target_ref=manifest.backup_id,
            detail={
                "backup_id": manifest.backup_id,
                "created_at": manifest.created_at,
                "origin": manifest.origin,
                "checks": manifest.checks,
                "trigger": trigger,
            },
        )
        session.commit()


def run_daily_backup_if_due(engine: Engine, *, now: datetime | None = None) -> None:
    """The hourly catch-up job, and the one-off call made during lifespan
    startup before `scheduler.start()` returns — this is what turns "the
    laptop was off at 3 AM" into "we got today's backup at 09:04" rather
    than nothing."""
    now = now if now is not None else datetime.now(UTC)
    if scheduled_backup_is_due(settings.BACKUP_DIR, now=now):
        run_daily_backup(engine, trigger="catch_up")
