"""P18/P30 scheduled backup ownership and protected-storage catch-up."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.core.config import Settings, settings
from app.maintenance.backup import (
    BackupTargetsFailedError,
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
from app.maintenance.storage import (
    STORAGE_TIER_DEGRADED,
    STORAGE_TIER_PROTECTED,
    StorageTargetProvider,
    probe_protected_storage,
)
from app.maintenance.verify import compute_sha256
from app.models import AuditResult
from app.services import audit

logger = logging.getLogger("uvicorn.error")

BACKUP_INTERVAL_HOURS = 24


def _manifest_for_root(
    backup_dir: Path,
    *,
    storage_tier: str,
) -> BackupManifest | None:
    for manifest in list_manifests(backup_dir):
        if manifest.origin != ORIGIN_SCHEDULED or not manifest.valid:
            continue
        # The artifact root, not a manifest field, determines the tier.
        manifest.storage_tier = storage_tier
        return manifest
    return None


def _manifest_is_intact(backup_dir: Path, manifest: BackupManifest) -> bool:
    path = db_path_for(backup_dir, manifest.backup_id)
    try:
        return (
            path.exists()
            and path.stat().st_size == manifest.file_size
            and manifest.filename == path.name
            and compute_sha256(path) == manifest.sha256
        )
    except (OSError, ValueError):
        return False


def newest_protected_manifest(
    backup_dir: Path,
    *,
    protected_backup_dir: Path | None,
    db_path: Path,
    storage_provider: StorageTargetProvider | None = None,
) -> BackupManifest | None:
    """Return the newest intact scheduled manifest on protected storage."""
    del backup_dir  # kept in the signature for symmetry with list helpers
    if protected_backup_dir is None:
        return None
    probe = probe_protected_storage(
        protected_backup_dir,
        live_db_path=db_path,
        required_bytes=1,
        provider=storage_provider,
    )
    if not probe.available:
        return None
    manifest = _manifest_for_root(
        Path(protected_backup_dir), storage_tier=STORAGE_TIER_PROTECTED
    )
    if manifest is None or not _manifest_is_intact(
        Path(protected_backup_dir), manifest
    ):
        return None
    return manifest


def newest_scheduled_manifest(
    backup_dir: Path,
    *,
    protected_backup_dir: Path | None = None,
    db_path: Path | None = None,
    storage_provider: StorageTargetProvider | None = None,
) -> BackupManifest | None:
    """Newest valid scheduled manifest across currently available roots.

    The due-check hashes only the newest candidate in each root; it does not
    re-verify every retained backup on every hourly poll.
    """
    local = _manifest_for_root(Path(backup_dir), storage_tier=STORAGE_TIER_DEGRADED)
    candidates: list[BackupManifest] = []
    if local is not None:
        candidates.append(local)
    if protected_backup_dir is not None and db_path is not None:
        protected = newest_protected_manifest(
            Path(backup_dir),
            protected_backup_dir=Path(protected_backup_dir),
            db_path=Path(db_path),
            storage_provider=storage_provider,
        )
        if protected is not None:
            candidates.append(protected)
    return max(candidates, key=lambda manifest: manifest.created_at, default=None)


def scheduled_backup_is_due(
    backup_dir: Path,
    *,
    now: datetime,
    interval_hours: int = BACKUP_INTERVAL_HOURS,
    protected_backup_dir: Path | None = None,
    db_path: Path | None = None,
    storage_provider: StorageTargetProvider | None = None,
) -> bool:
    """Whether operational daily backup continuity is overdue.

    A recent valid degraded backup satisfies this continuity check.  Protected
    freshness is intentionally evaluated separately by
    :func:`protected_backup_is_due` so a missing USB does not cause a new
    local backup every hour.
    """
    manifest = newest_scheduled_manifest(
        backup_dir,
        protected_backup_dir=protected_backup_dir,
        db_path=db_path,
        storage_provider=storage_provider,
    )
    if manifest is None:
        return True
    root = (
        Path(protected_backup_dir)
        if manifest.storage_tier == STORAGE_TIER_PROTECTED
        and protected_backup_dir is not None
        else Path(backup_dir)
    )
    if not _manifest_is_intact(root, manifest):
        return True
    try:
        age = now.astimezone(UTC) - datetime.fromisoformat(manifest.created_at)
    except (TypeError, ValueError):
        return True
    return age >= timedelta(hours=interval_hours)


def protected_backup_is_due(
    backup_dir: Path,
    *,
    protected_backup_dir: Path | None,
    db_path: Path,
    now: datetime,
    interval_hours: int = BACKUP_INTERVAL_HOURS,
    storage_provider: StorageTargetProvider | None = None,
) -> bool:
    """Whether the protected tier is overdue, assuming its target is usable."""
    manifest = newest_protected_manifest(
        backup_dir,
        protected_backup_dir=protected_backup_dir,
        db_path=db_path,
        storage_provider=storage_provider,
    )
    if manifest is None:
        return True
    try:
        return now.astimezone(UTC) - datetime.fromisoformat(
            manifest.created_at
        ) >= timedelta(hours=interval_hours)
    except (TypeError, ValueError):
        return True


def _retention(app_settings: Settings) -> RetentionConfig:
    return RetentionConfig(
        daily=app_settings.BACKUP_DAILY_RETENTION,
        manual=app_settings.BACKUP_MANUAL_RETENTION,
        pre_restore=app_settings.BACKUP_PRE_RESTORE_RETENTION,
    )


def _settings_or_default(app_settings: Settings | None) -> Settings:
    return app_settings if app_settings is not None else settings


def _record_backup_failure(engine: Engine, *, trigger: str, exc: BaseException) -> None:
    detail = {"trigger": trigger, "reason": type(exc).__name__}
    if isinstance(exc, BackupTargetsFailedError):
        detail = {
            "trigger": trigger,
            "reason": "both_targets_failed",
            "protected_reason": exc.protected_reason,
            "fallback_reason": exc.fallback_reason,
        }
    try:
        with Session(engine) as session:
            audit.record(
                session,
                action="BACKUP_TRIGGER",
                result=AuditResult.FAILURE,
                actor=None,
                target_type="backup",
                detail=detail,
            )
            session.commit()
    except Exception:
        # A failed audit write must not turn a maintenance failure into an
        # uncaught scheduler exception or hide the original reason.
        logger.exception(
            "Scheduled backup failure could not be recorded (trigger=%s).",
            trigger,
        )


def run_daily_backup(
    engine: Engine,
    *,
    trigger: str,
    app_settings: Settings | None = None,
    storage_provider: StorageTargetProvider | None = None,
) -> None:
    """Run the scheduled backup and audit the safe outcome.

    ``MaintenanceBusyError`` is a logged no-op.  Every other failure is
    contained so APScheduler keeps the job registered for the next run.
    """
    runtime_settings = _settings_or_default(app_settings)
    try:
        db_path = resolve_sqlite_db_path(runtime_settings.DATABASE_URL)
        manifest = create_backup(
            db_path=db_path,
            backup_dir=runtime_settings.BACKUP_DIR,
            origin=ORIGIN_SCHEDULED,
            retention=_retention(runtime_settings),
            protected_backup_dir=runtime_settings.PROTECTED_BACKUP_DIR,
            storage_provider=storage_provider,
        )
    except MaintenanceBusyError:
        logger.info(
            "Scheduled backup (trigger=%s) skipped: a backup or restore is "
            "already running.",
            trigger,
        )
        return
    except Exception as exc:
        logger.exception("Scheduled backup (trigger=%s) failed.", trigger)
        _record_backup_failure(engine, trigger=trigger, exc=exc)
        return

    result = AuditResult.SUCCESS if manifest.valid else AuditResult.FAILURE
    detail = {
        "backup_id": manifest.backup_id,
        "created_at": manifest.created_at,
        "origin": manifest.origin,
        "checks": manifest.checks,
        "storage_tier": manifest.storage_tier,
        "storage_reason": manifest.storage_reason,
        "trigger": trigger,
    }
    try:
        with Session(engine) as session:
            audit.record(
                session,
                action="BACKUP_TRIGGER",
                result=result,
                actor=None,
                target_type="backup",
                target_ref=manifest.backup_id,
                detail=detail,
            )
            session.commit()
    except Exception:
        logger.exception(
            "Scheduled backup audit write failed (trigger=%s backup_id=%s).",
            trigger,
            manifest.backup_id,
        )


def run_daily_backup_if_due(
    engine: Engine,
    *,
    now: datetime | None = None,
    app_settings: Settings | None = None,
    storage_provider: StorageTargetProvider | None = None,
) -> None:
    """Catch up operational continuity and protected freshness independently."""
    runtime_settings = _settings_or_default(app_settings)
    current = now if now is not None else datetime.now(UTC)
    try:
        db_path = resolve_sqlite_db_path(runtime_settings.DATABASE_URL)
        operational_due = scheduled_backup_is_due(
            runtime_settings.BACKUP_DIR,
            now=current,
            protected_backup_dir=runtime_settings.PROTECTED_BACKUP_DIR,
            db_path=db_path,
            storage_provider=storage_provider,
        )
        protected_due = False
        if runtime_settings.PROTECTED_BACKUP_DIR is not None:
            probe = probe_protected_storage(
                runtime_settings.PROTECTED_BACKUP_DIR,
                live_db_path=db_path,
                required_bytes=1,
                provider=storage_provider,
            )
            if probe.available:
                protected_due = protected_backup_is_due(
                    runtime_settings.BACKUP_DIR,
                    protected_backup_dir=runtime_settings.PROTECTED_BACKUP_DIR,
                    db_path=db_path,
                    now=current,
                    storage_provider=storage_provider,
                )
    except Exception as exc:
        logger.exception("Scheduled backup due-check failed.")
        _record_backup_failure(engine, trigger="catch_up", exc=exc)
        return
    if operational_due or protected_due:
        run_daily_backup(
            engine,
            trigger="catch_up",
            app_settings=runtime_settings,
            storage_provider=storage_provider,
        )


__all__ = [
    "BACKUP_INTERVAL_HOURS",
    "newest_protected_manifest",
    "newest_scheduled_manifest",
    "protected_backup_is_due",
    "run_daily_backup",
    "run_daily_backup_if_due",
    "scheduled_backup_is_due",
]
