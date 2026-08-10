"""D-011 / 08_PKG_backup_ops.md Step 1 — the online backup sequence, using
`sqlite3.Connection.backup()`. Never copies `adas.db` with `shutil` and
never shells out to the `sqlite3` CLI binary.
"""

import logging
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.maintenance import verify
from app.maintenance.manifest import (
    APP_VERSION,
    ORIGIN_MANUAL,
    ORIGIN_SCHEDULED,
    VALID_ORIGINS,
    BackupManifest,
    db_path_for,
    list_manifests,
    manifest_path_for,
    new_backup_id,
    read_schema_revision,
    tmp_path_for,
    write_manifest,
)

logger = logging.getLogger("adas.maintenance")

# A disk-space cushion, not a tight estimate: the temp copy plus the final
# file both exist briefly during the atomic rename window, and WAL/journal
# growth during the copy is unpredictable — 2x the source file's current
# size is generous without being unreasonable at demo-laptop scale.
_DISK_SPACE_FACTOR = 2.0


class InsufficientDiskSpaceError(RuntimeError):
    pass


class MaintenanceBusyError(RuntimeError):
    """Raised when a backup or restore is already running in this process.
    The API layer (routes/maintenance.py) turns this into 409 CONFLICT_BUSY
    (edge cases 1.12, 1.13)."""


# Module-level, matching 08_PKG_backup_ops.md's "exclusive *in-process*
# lock" (Step 1) — this protects concurrent requests within one running
# FastAPI process (D-005's single-worker assumption), and is shared by
# both backup and restore since a restore mid-backup would capture a torn
# state (edge case 1.12). It is intentionally not a cross-process file
# lock: a CLI invocation racing the live server is out of scope, same as
# every other single-worker assumption in this codebase.
_maintenance_lock = threading.Lock()


def try_acquire_maintenance_lock() -> bool:
    """For a caller (the API route) that must know synchronously, before
    committing to any further work, whether a backup/restore is already
    running — used to turn a busy backup route into an immediate 409
    rather than only discovering it once a background task starts."""
    return _maintenance_lock.acquire(blocking=False)


def release_maintenance_lock() -> None:
    _maintenance_lock.release()


@contextmanager
def maintenance_lock():
    if not try_acquire_maintenance_lock():
        raise MaintenanceBusyError("A backup or restore operation is already running.")
    try:
        yield
    finally:
        release_maintenance_lock()


@dataclass
class RetentionConfig:
    daily: int
    manual: int


def resolve_sqlite_db_path(database_url: str) -> Path:
    """Mirrors backend/scripts/reset_db.py's parser, generalized to take an
    explicit URL rather than always reading the module-level `settings` —
    so both the real app and tests can point it at different databases."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError(
            "Maintenance operations only support file-based SQLite DATABASE_URL values."
        )
    path_str = database_url[len(prefix) :]
    if not path_str or path_str == ":memory:":
        raise ValueError("Maintenance operations require a file-based SQLite database.")
    return Path(path_str)


def _check_disk_space(db_path: Path, backup_dir: Path) -> None:
    """Step 1.1 — abort cleanly, before writing anything, if there isn't
    room for the new backup."""
    needed = int(db_path.stat().st_size * _DISK_SPACE_FACTOR) if db_path.exists() else 0
    usage_target = backup_dir if backup_dir.exists() else backup_dir.parent
    free = shutil.disk_usage(usage_target).free
    if free < needed:
        raise InsufficientDiskSpaceError(
            f"Insufficient disk space for backup: need ~{needed} bytes, {free} free."
        )


def _run_sqlite_backup(db_path: Path, tmp_path: Path) -> None:
    """The WAL-safe online backup itself. Source is opened read-only so this
    can never itself become a writer against the live database."""
    tmp_path.unlink(missing_ok=True)
    source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        dest = sqlite3.connect(tmp_path)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()


def _perform_backup_write(
    db_path: Path, backup_dir: Path, origin: str
) -> BackupManifest:
    """Steps 3-6 only: write-to-temp, validate, atomic rename, manifest.
    No disk-space check and no locking — the caller (`create_backup` for a
    standalone backup, or `restore.perform_offline_restore` for the
    emergency pre-restore copy, which already holds the lock for the whole
    restore sequence) is responsible for both."""
    if origin not in VALID_ORIGINS:
        raise ValueError(f"Unknown backup origin: {origin!r}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_id = new_backup_id()
    tmp_path = tmp_path_for(backup_dir, backup_id)
    final_path = db_path_for(backup_dir, backup_id)

    try:
        _run_sqlite_backup(db_path, tmp_path)
        checks = verify.validate_backup(tmp_path, full=False)
        sha256 = verify.compute_sha256(tmp_path)
        file_size = tmp_path.stat().st_size
        # Atomic rename — the final name only ever appears once the file is
        # complete and validated (Step 1.4/1.5). Never leaves a file at the
        # final path if anything above raised.
        tmp_path.replace(final_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    manifest = BackupManifest(
        backup_id=backup_id,
        filename=final_path.name,
        created_at=datetime.now(UTC).isoformat(),
        origin=origin,
        app_version=APP_VERSION,
        schema_revision=read_schema_revision(final_path),
        file_size=file_size,
        sha256=sha256,
        checks=checks,
    )

    if not manifest.valid:
        logger.error(
            "Backup %s failed validation after creation: %s", backup_id, checks
        )
    write_manifest(backup_dir, manifest)
    return manifest


def create_backup(
    *,
    db_path: Path,
    backup_dir: Path,
    origin: str = ORIGIN_MANUAL,
    retention: RetentionConfig | None = None,
) -> BackupManifest:
    """The full online backup sequence (Step 1), 1:1 with D-011's ordering:
    check disk space, take the exclusive lock, write+validate+publish, then
    prune only once the new backup is confirmed valid. Raises
    `MaintenanceBusyError` if a backup or restore is already in progress —
    never removes an older valid backup because this one failed."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    _check_disk_space(db_path, backup_dir)

    with maintenance_lock():
        manifest = _perform_backup_write(db_path, backup_dir, origin)

    if retention is not None and manifest.valid:
        prune_backups(backup_dir, retention=retention)

    return manifest


def perform_backup_assuming_lock_held(
    db_path: Path,
    backup_dir: Path,
    origin: str,
    *,
    retention: RetentionConfig | None = None,
) -> BackupManifest:
    """For a caller that has already acquired `maintenance_lock`/
    `try_acquire_maintenance_lock` itself — the manual-backup API route
    acquires it synchronously (so a busy second request gets an immediate
    409) and runs this in a background task afterwards. Calling
    `create_backup()` there instead would try to re-acquire the same
    (non-reentrant) lock and immediately raise `MaintenanceBusyError`."""
    manifest = _perform_backup_write(db_path, backup_dir, origin)
    if retention is not None and manifest.valid:
        prune_backups(backup_dir, retention=retention)
    return manifest


def list_backups(backup_dir: Path) -> list[BackupManifest]:
    """Newest first, restricted to backups that are still verifiably intact
    *right now* — the checksum is re-computed and compared to the recorded
    value on every call, so a backup file corrupted after creation stops
    being listed (and therefore stops being selectable for restore)
    immediately, without waiting for a separate re-scan job."""
    listed: list[BackupManifest] = []
    for manifest in list_manifests(backup_dir):
        if not manifest.valid:
            continue
        path = db_path_for(backup_dir, manifest.backup_id)
        if not path.exists():
            continue
        try:
            if verify.compute_sha256(path) != manifest.sha256:
                continue
        except OSError:
            continue
        listed.append(manifest)
    return listed


def get_valid_backup(backup_dir: Path, backup_id: str) -> BackupManifest | None:
    """A single-item version of `list_backups`'s live re-verification, used
    by the restore-request path to confirm a specific id is still a valid,
    uncorrupted restore point."""
    for manifest in list_backups(backup_dir):
        if manifest.backup_id == backup_id:
            return manifest
    return None


def prune_backups(
    backup_dir: Path,
    *,
    retention: RetentionConfig,
    protected_ids: frozenset[str] = frozenset(),
) -> list[str]:
    """Step 3 — keeps the newest `retention.daily` scheduled backups and the
    newest `retention.manual` manual backups; only runs after the caller's
    own new backup is already confirmed valid. Pre-restore (emergency)
    backups are never touched here — `restore.py` manages that file's
    lifetime itself, since it must survive until restore success is
    verified regardless of count. Anything in `protected_ids` (an active
    restore candidate or the current emergency file) is skipped regardless
    of age."""
    manifests = list_manifests(backup_dir)
    removed: list[str] = []

    for origin, keep in (
        (ORIGIN_SCHEDULED, retention.daily),
        (ORIGIN_MANUAL, retention.manual),
    ):
        candidates = [
            m
            for m in manifests
            if m.origin == origin and m.valid and m.backup_id not in protected_ids
        ]
        # list_manifests() already sorts newest-first.
        for stale in candidates[keep:]:
            _remove_backup_files(backup_dir, stale.backup_id)
            removed.append(stale.backup_id)

    return removed


def _remove_backup_files(backup_dir: Path, backup_id: str) -> None:
    db_path_for(backup_dir, backup_id).unlink(missing_ok=True)
    manifest_path_for(backup_dir, backup_id).unlink(missing_ok=True)
