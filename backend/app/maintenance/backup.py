"""D-011 / 08_PKG_backup_ops.md Step 1 — the online backup sequence, using
`sqlite3.Connection.backup()`. Never copies `adas.db` with `shutil` and
never shells out to the `sqlite3` CLI binary.
"""

import json
import logging
import os
import shutil
import sqlite3
import threading
from contextlib import contextmanager, suppress
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
    validate_backup_id,
    write_manifest,
)
from app.maintenance.storage import (
    STORAGE_REASON_FULL,
    STORAGE_TIER_DEGRADED,
    STORAGE_TIER_PROTECTED,
    StorageTargetProvider,
    probe_protected_storage,
    reason_for_publish_failure,
    validate_storage_tier,
)

logger = logging.getLogger("adas.maintenance")

# A disk-space cushion, not a tight estimate: the temp copy plus the final
# file both exist briefly during the atomic rename window, and WAL/journal
# growth during the copy is unpredictable — 2x the source file's current
# size is generous without being unreasonable at demo-laptop scale.
_DISK_SPACE_FACTOR = 2.0
_RESTORE_STATE_FILENAME = "restore_state.json"


class InsufficientDiskSpaceError(RuntimeError):
    pass


class MaintenanceBusyError(RuntimeError):
    """Raised when a backup or restore is already running in this process.
    The API layer (routes/maintenance.py) turns this into 409 CONFLICT_BUSY
    (edge cases 1.12, 1.13)."""


class BackupTargetsFailedError(RuntimeError):
    """Both the protected target and the local fallback failed.

    Only stable reason codes are retained so an orchestrator can safely
    display this exception without leaking target paths or raw OS errors.
    """

    def __init__(self, protected_reason: str, fallback_reason: str):
        self.protected_reason = protected_reason
        self.fallback_reason = fallback_reason
        super().__init__(
            "Protected and degraded backup targets both failed "
            f"({protected_reason}; {fallback_reason})."
        )


# The thread lock remains useful for immediate same-process 409 responses,
# but it is only the first half of the lease.  The file lease below is what
# closes the API/CLI race: a coordinator or maintenance process in another
# process must not mutate the database while a backup is being published.
_maintenance_lock = threading.Lock()
_held_maintenance_lease: "MaintenanceLease | None" = None
_held_maintenance_lease_guard = threading.Lock()


class CrossProcessFileLock:
    """Small, dependency-free non-blocking advisory file lock.

    The handle stays open for the entire lease.  Existence of the lock file
    is deliberately not used as a lock signal because stale files are normal
    after a process crash.  ``msvcrt`` is used on Windows and ``flock`` on
    POSIX, keeping the same coordinator code usable by the systemd profile.
    """

    def __init__(self, path: Path):
        self.path = path
        self._handle = None

    def acquire(self, *, blocking: bool = False) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # The systemd coordinator is intentionally root-supervised so it can
        # control fixed service units, while the maintenance runner executes
        # as the dedicated application user. Keep the shared lease file
        # writable by both deployment roles; POSIX flock requires a writable
        # descriptor for an exclusive lock. This file contains no secret and
        # is only an advisory coordination primitive.
        existing_mode = "r+b"
        try:
            handle = (
                self.path.open(existing_mode)
                if self.path.exists()
                else self.path.open("a+b")
            )
        except FileNotFoundError:
            # The existence check can race a cleanup from another process;
            # fall back to creation and let the normal lock path decide.
            try:
                handle = self.path.open("a+b")
            except OSError:
                return False
        except OSError:
            return False
        if os.name != "nt":
            # An existing deployment-owned file may intentionally have
            # stricter permissions; the open above still decides whether
            # this process can participate in the lease.
            with suppress(OSError):
                os.chmod(self.path, 0o666)
        try:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
                msvcrt.locking(handle.fileno(), mode, 1)
            else:
                import fcntl

                flags = fcntl.LOCK_EX
                if not blocking:
                    flags |= fcntl.LOCK_NB
                fcntl.flock(handle.fileno(), flags)
        except (BlockingIOError, OSError):
            handle.close()
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


class MaintenanceLease:
    """Combined in-process and cross-process exclusive maintenance lease."""

    def __init__(self, backup_dir: Path):
        self.backup_dir = Path(backup_dir)
        self._file_lock = CrossProcessFileLock(self.backup_dir / "maintenance.lock")
        self._thread_acquired = False

    def acquire(self, *, blocking: bool = False) -> bool:
        if not _maintenance_lock.acquire(blocking=blocking):
            return False
        self._thread_acquired = True
        if not self._file_lock.acquire(blocking=blocking):
            self._thread_acquired = False
            _maintenance_lock.release()
            return False
        return True

    def release(self) -> None:
        self._file_lock.release()
        if self._thread_acquired:
            self._thread_acquired = False
            _maintenance_lock.release()


def _default_backup_dir() -> Path:
    # Keep imports lazy so this pure maintenance package remains usable by
    # tests and the coordinator without constructing FastAPI settings.
    from app.core.config import settings

    return settings.BACKUP_DIR


def _target_failure_reason(exc: BaseException) -> str:
    if isinstance(exc, InsufficientDiskSpaceError):
        return STORAGE_REASON_FULL
    return reason_for_publish_failure(exc)


def try_acquire_maintenance_lock(backup_dir: Path | None = None) -> bool:
    """For a caller (the API route) that must know synchronously, before
    committing to any further work, whether a backup/restore is already
    running — used to turn a busy backup route into an immediate 409
    rather than only discovering it once a background task starts."""
    global _held_maintenance_lease
    # Be forgiving to test/process teardown code that released the legacy
    # thread primitive directly.  It must not strand the cross-process file
    # handle and make the next acquisition look like a stale lock.
    with _held_maintenance_lease_guard:
        orphan = (
            _held_maintenance_lease
            if _held_maintenance_lease is not None and not _maintenance_lock.locked()
            else None
        )
        if orphan is not None:
            _held_maintenance_lease = None
    if orphan is not None:
        orphan.release()
    lease = MaintenanceLease(backup_dir or _default_backup_dir())
    if not lease.acquire(blocking=False):
        return False
    with _held_maintenance_lease_guard:
        _held_maintenance_lease = lease
    return True


def release_maintenance_lock() -> None:
    global _held_maintenance_lease
    with _held_maintenance_lease_guard:
        lease = _held_maintenance_lease
        _held_maintenance_lease = None
    if lease is not None:
        lease.release()


@contextmanager
def maintenance_lock(backup_dir: Path | None = None):
    lease = MaintenanceLease(backup_dir or _default_backup_dir())
    if not lease.acquire(blocking=False):
        raise MaintenanceBusyError("A backup or restore operation is already running.")
    try:
        yield
    finally:
        lease.release()


@dataclass
class RetentionConfig:
    daily: int
    manual: int
    pre_restore: int = 3


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


def _ensure_restore_not_active(backup_dir: Path) -> None:
    """Prevent a backup from entering the claim-to-run restore handoff.

    The coordinator deliberately releases the claim lease before launching
    the platform runner, because the runner must acquire the same
    maintenance lease for the database write. Once the durable state says
    ``in_progress`` or ``db_restored``, a backup must therefore refuse even
    if it wins the file-lock race in that handoff window. A ``requested``
    state remains allowed: a backup that acquires the lease before the
    coordinator claims the request may finish first, exactly as the
    cross-process policy permits.
    """
    state_path = backup_dir / _RESTORE_STATE_FILENAME
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        return
    if isinstance(data, dict) and data.get("status") in {"in_progress", "db_restored"}:
        raise MaintenanceBusyError("A backup or restore operation is already running.")


def _active_restore_protected_ids(backup_dir: Path) -> frozenset[str]:
    """Keep an active request's selected artifacts out of retention pruning."""
    state_path = backup_dir / _RESTORE_STATE_FILENAME
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        return frozenset()
    if not isinstance(data, dict) or data.get("status") not in {
        "requested",
        "in_progress",
        "db_restored",
    }:
        return frozenset()
    protected: set[str] = set()
    for key in ("backup_id", "emergency_backup_id"):
        value = data.get(key)
        if isinstance(value, str):
            try:
                protected.add(validate_backup_id(value))
            except ValueError:
                continue
    return frozenset(protected)


def _remove_sidecars(path: Path) -> None:
    """Removes `path`'s own `-wal`/`-shm` companions.

    `sqlite3.Connection.backup()` carries the source's WAL journal mode into
    the destination, so a read-only validation open (verify.py) or a later
    read-only re-check (list_backups, cmd_verify, ...) can each create a
    fresh `-shm`/`-wal` next to a finished artifact — a read-only connection
    can't check-point or clean those up on close. `tmp_path.replace(...)`
    only ever renames the main file, so without this those sidecars are
    orphaned forever, one pair per backup, and archive.py's `.db`-only zip
    member would silently miss any content still resident in a `-wal`."""
    for suffix in ("-wal", "-shm"):
        path.with_name(path.name + suffix).unlink(missing_ok=True)


def _cleanup_unpublished_artifacts(artifact_dir: Path) -> None:
    """Remove only temporary protected-root publications.

    This intentionally does not match ``.db`` or ``.json`` files.  A
    protected device can lose power after a temp file is created; the next
    attempt may safely clean that unpublished residue without touching any
    previously valid restore point.  Local legacy artifacts are never swept
    by this helper.
    """
    if not artifact_dir.exists():
        return
    for pattern in (
        "adas_backup_*.tmp",
        "adas_backup_*.tmp-wal",
        "adas_backup_*.tmp-shm",
    ):
        for path in artifact_dir.glob(pattern):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not clean an unpublished backup artifact.")


def _run_sqlite_backup(db_path: Path, tmp_path: Path) -> None:
    """The WAL-safe online backup itself. Source is opened read-only so this
    can never itself become a writer against the live database."""
    tmp_path.unlink(missing_ok=True)
    source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        dest = sqlite3.connect(tmp_path)
        try:
            source.backup(dest)
            # Root fix for the sidecar leak: checkpoint whatever WAL content
            # source.backup() carried over, then switch off WAL mode
            # entirely, before dest is ever closed. Every backup artifact
            # becomes one self-contained file — no later read-only open
            # (validation here, list_backups' re-verification, cmd_verify,
            # archive.py) creates anything beside it.
            dest.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            dest.execute("PRAGMA journal_mode=DELETE")
        finally:
            dest.close()
    finally:
        source.close()


def _perform_backup_write(
    db_path: Path,
    backup_dir: Path,
    origin: str,
    *,
    storage_tier: str = STORAGE_TIER_DEGRADED,
    storage_reason: str | None = None,
) -> BackupManifest:
    """Steps 3-6 only: write-to-temp, validate, atomic rename, manifest.
    No disk-space check and no locking — the caller (`create_backup` for a
    standalone backup, or `restore.perform_offline_restore` for the
    emergency pre-restore copy, which already holds the lock for the whole
    restore sequence) is responsible for both."""
    if origin not in VALID_ORIGINS:
        raise ValueError(f"Unknown backup origin: {origin!r}")
    validate_storage_tier(storage_tier)

    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_id = new_backup_id()
    tmp_path = tmp_path_for(backup_dir, backup_id)
    final_path = db_path_for(backup_dir, backup_id)

    published = False
    try:
        _run_sqlite_backup(db_path, tmp_path)
        checks = verify.validate_backup(tmp_path, full=False)
        sha256 = verify.compute_sha256(tmp_path)
        file_size = tmp_path.stat().st_size
        # Belt and braces on top of _run_sqlite_backup's own checkpoint: the
        # read-only validate_backup/compute_sha256 opens just above can
        # themselves recreate a `-shm` next to tmp_path, so sweep again
        # right before the rename — the final path must never inherit a
        # sidecar.
        _remove_sidecars(tmp_path)
        # Atomic rename — the final name only ever appears once the file is
        # complete and validated (Step 1.4/1.5). Never leaves a file at the
        # final path if anything above raised.
        tmp_path.replace(final_path)
        published = True
        schema_revision = read_schema_revision(final_path)
        _remove_sidecars(final_path)
        manifest = BackupManifest(
            backup_id=backup_id,
            filename=final_path.name,
            created_at=datetime.now(UTC).isoformat(),
            origin=origin,
            app_version=APP_VERSION,
            schema_revision=schema_revision,
            file_size=file_size,
            sha256=sha256,
            checks=checks,
            storage_tier=storage_tier,
            storage_reason=storage_reason,
        )

        if not manifest.valid:
            logger.error(
                "Backup %s failed validation after creation: %s", backup_id, checks
            )
        write_manifest(backup_dir, manifest)
        return manifest
    except Exception:
        # A database file without its manifest is not a published restore
        # point.  Remove just this attempt; older valid artifacts survive.
        tmp_path.unlink(missing_ok=True)
        _remove_sidecars(tmp_path)
        if published:
            _remove_sidecars(final_path)
            final_path.unlink(missing_ok=True)
            manifest_path_for(backup_dir, backup_id).unlink(missing_ok=True)
            manifest_path_for(backup_dir, backup_id).with_suffix(".json.tmp").unlink(
                missing_ok=True
            )
        raise


def create_backup(
    *,
    db_path: Path,
    backup_dir: Path,
    origin: str = ORIGIN_MANUAL,
    retention: RetentionConfig | None = None,
    protected_backup_dir: Path | None = None,
    storage_provider: StorageTargetProvider | None = None,
) -> BackupManifest:
    """Create a backup under one local maintenance lease.

    Manual and scheduled backups prefer the explicitly configured protected
    root.  Any unavailable or failed protected attempt falls back once to the
    local root and records a path-free reason.  Pre-restore backups are always
    local because the emergency reserve must survive loss of the external
    device.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)

    with maintenance_lock(backup_dir):
        manifest = _create_backup_unlocked(
            db_path=db_path,
            backup_dir=backup_dir,
            origin=origin,
            retention=retention,
            protected_backup_dir=protected_backup_dir,
            storage_provider=storage_provider,
        )

    return manifest


def _create_backup_unlocked(
    *,
    db_path: Path,
    backup_dir: Path,
    origin: str,
    retention: RetentionConfig | None,
    protected_backup_dir: Path | None,
    storage_provider: StorageTargetProvider | None,
) -> BackupManifest:
    """Protected-first selection for a caller already holding the lease."""
    _ensure_restore_not_active(backup_dir)
    configured_protected = (
        None if protected_backup_dir is None else Path(protected_backup_dir)
    )

    # Emergency backups are deliberately local: losing the USB after the
    # swap must not also remove the only rollback state.
    if origin == "pre-restore":
        _check_disk_space(db_path, backup_dir)
        manifest = _perform_backup_write(
            db_path,
            backup_dir,
            origin,
            storage_tier=STORAGE_TIER_DEGRADED,
            storage_reason="pre_restore_emergency",
        )
        if retention is not None and manifest.valid:
            _prune_backups_unlocked(backup_dir, retention=retention)
        return manifest

    protected_attempted = configured_protected is not None
    protected_reason = "not_configured"
    if configured_protected is not None:
        _cleanup_unpublished_artifacts(configured_protected)
        try:
            same_root = configured_protected.resolve() == Path(backup_dir).resolve()
        except OSError:
            same_root = False
        probe = (
            None
            if same_root
            else probe_protected_storage(
                configured_protected,
                live_db_path=db_path,
                required_bytes=_required_backup_bytes(db_path),
                provider=storage_provider,
            )
        )
        if same_root:
            protected_reason = "same_device"
        elif probe is not None:
            protected_reason = probe.reason or "available"
        if probe is not None and probe.available:
            _cleanup_unpublished_artifacts(configured_protected)
            try:
                _check_disk_space(db_path, configured_protected)
                manifest = _perform_backup_write(
                    db_path,
                    configured_protected,
                    origin,
                    storage_tier=STORAGE_TIER_PROTECTED,
                )
                if not manifest.valid:
                    _remove_backup_files(configured_protected, manifest.backup_id)
                    raise RuntimeError("protected backup validation failed")
                if retention is not None:
                    try:
                        _prune_backups_unlocked(
                            configured_protected,
                            retention=retention,
                            storage_tier=STORAGE_TIER_PROTECTED,
                        )
                    except OSError:
                        # A valid protected restore point is still a success
                        # if retention cleanup loses the media or permissions.
                        # Never create a duplicate degraded point merely
                        # because old protected files could not be pruned.
                        logger.warning(
                            "Protected backup retention cleanup could not complete."
                        )
                return manifest
            except Exception as exc:
                protected_reason = _target_failure_reason(exc)
                _cleanup_unpublished_artifacts(configured_protected)
                logger.warning(
                    "Protected backup target failed; using degraded fallback "
                    "(reason=%s).",
                    protected_reason,
                )
        else:
            _cleanup_unpublished_artifacts(configured_protected)
            logger.warning(
                "Protected backup target unavailable; using degraded fallback "
                "(reason=%s).",
                protected_reason,
            )

    try:
        _check_disk_space(db_path, backup_dir)
        manifest = _perform_backup_write(
            db_path,
            backup_dir,
            origin,
            storage_tier=STORAGE_TIER_DEGRADED,
            storage_reason=protected_reason,
        )
        if not manifest.valid:
            raise RuntimeError("degraded backup validation failed")
        if retention is not None:
            _prune_backups_unlocked(backup_dir, retention=retention)
        return manifest
    except Exception as exc:
        fallback_reason = _target_failure_reason(exc)
        if protected_attempted:
            raise BackupTargetsFailedError(
                protected_reason,
                fallback_reason,
            ) from exc
        raise


def _required_backup_bytes(db_path: Path) -> int:
    try:
        return max(1, int(db_path.stat().st_size * _DISK_SPACE_FACTOR))
    except OSError:
        return 1


def perform_backup_assuming_lock_held(
    db_path: Path,
    backup_dir: Path,
    origin: str,
    *,
    retention: RetentionConfig | None = None,
    protected_backup_dir: Path | None = None,
    storage_provider: StorageTargetProvider | None = None,
) -> BackupManifest:
    """For a caller that has already acquired `maintenance_lock`/
    `try_acquire_maintenance_lock` itself — the manual-backup API route
    acquires it synchronously (so a busy second request gets an immediate
    409) and runs this in a background task afterwards. Calling
    `create_backup()` there instead would try to re-acquire the same
    (non-reentrant) lock and immediately raise `MaintenanceBusyError`."""
    return _create_backup_unlocked(
        db_path=db_path,
        backup_dir=backup_dir,
        origin=origin,
        retention=retention,
        protected_backup_dir=protected_backup_dir,
        storage_provider=storage_provider,
    )


def _list_backup_candidates_from_root(
    artifact_dir: Path,
    *,
    storage_tier: str,
) -> list[BackupManifest]:
    listed: list[BackupManifest] = []
    for manifest in list_manifests(artifact_dir):
        try:
            validate_backup_id(manifest.backup_id)
        except ValueError:
            continue
        path = db_path_for(artifact_dir, manifest.backup_id)
        checks = dict(manifest.checks)
        try:
            checks["checksum"] = path.exists() and (
                verify.compute_sha256(path) == manifest.sha256
            )
            checks["file_size"] = (
                path.exists() and path.stat().st_size == manifest.file_size
            )
            checks["artifact_name"] = manifest.filename == path.name
        except OSError:
            checks["checksum"] = False
            checks["file_size"] = False
            checks["artifact_name"] = False
        item = BackupManifest(
            backup_id=manifest.backup_id,
            filename=manifest.filename,
            created_at=manifest.created_at,
            origin=manifest.origin,
            app_version=manifest.app_version,
            schema_revision=manifest.schema_revision,
            file_size=manifest.file_size,
            sha256=manifest.sha256,
            checks=checks,
            # The root is authoritative.  A malicious/mistagged local
            # manifest can never turn itself into a protected restore point.
            storage_tier=storage_tier,
            storage_reason=manifest.storage_reason
            or ("legacy_local" if not manifest.storage_tier_explicit else None),
        )
        object.__setattr__(
            item, "_storage_tier_explicit", manifest.storage_tier_explicit
        )
        listed.append(item)
    return listed


def list_backup_candidates(
    backup_dir: Path,
    *,
    protected_backup_dir: Path | None = None,
    db_path: Path | None = None,
    storage_provider: StorageTargetProvider | None = None,
) -> list[BackupManifest]:
    """Return inspectable manifest rows, including invalid restore points.

    The dashboard needs to explain why a point is unusable.  Every artifact
    is still rechecked at read time, and malformed/path-unsafe IDs are
    ignored, so exposing an invalid row never makes it a filesystem input.
    """
    listed = _list_backup_candidates_from_root(
        Path(backup_dir), storage_tier=STORAGE_TIER_DEGRADED
    )
    configured_protected = (
        None if protected_backup_dir is None else Path(protected_backup_dir)
    )
    if configured_protected is not None:
        if db_path is None:
            try:
                from app.core.config import settings

                db_path = resolve_sqlite_db_path(settings.DATABASE_URL)
            except (ImportError, ValueError, AttributeError):
                db_path = None
        if db_path is not None:
            probe = probe_protected_storage(
                configured_protected,
                live_db_path=Path(db_path),
                required_bytes=1,
                provider=storage_provider,
            )
            if probe.available:
                listed.extend(
                    _list_backup_candidates_from_root(
                        configured_protected,
                        storage_tier=STORAGE_TIER_PROTECTED,
                    )
                )
    listed.sort(key=lambda item: (item.created_at, item.storage_tier), reverse=True)
    return listed


def list_backups(
    backup_dir: Path,
    *,
    protected_backup_dir: Path | None = None,
    db_path: Path | None = None,
    storage_provider: StorageTargetProvider | None = None,
) -> list[BackupManifest]:
    """Newest first, restricted to backups that are still verifiably intact."""
    return [
        manifest
        for manifest in list_backup_candidates(
            backup_dir,
            protected_backup_dir=protected_backup_dir,
            db_path=db_path,
            storage_provider=storage_provider,
        )
        if manifest.valid
    ]


def get_valid_backup(
    backup_dir: Path,
    backup_id: str,
    storage_tier: str = STORAGE_TIER_DEGRADED,
    *,
    protected_backup_dir: Path | None = None,
    db_path: Path | None = None,
    storage_provider: StorageTargetProvider | None = None,
) -> BackupManifest | None:
    """A single-item version of `list_backups`'s live re-verification, used
    by the restore-request path to confirm a specific id is still a valid,
    uncorrupted restore point."""
    validate_backup_id(backup_id)
    validate_storage_tier(storage_tier)
    for manifest in list_backups(
        backup_dir,
        protected_backup_dir=protected_backup_dir,
        db_path=db_path,
        storage_provider=storage_provider,
    ):
        if manifest.backup_id == backup_id and manifest.storage_tier == storage_tier:
            return manifest
    return None


def prune_backups(
    backup_dir: Path,
    *,
    retention: RetentionConfig,
    protected_ids: frozenset[str] = frozenset(),
    storage_tier: str = STORAGE_TIER_DEGRADED,
) -> list[str]:
    """Prune under the same cross-process lease used by backup/restore."""
    validate_storage_tier(storage_tier)
    with maintenance_lock(backup_dir):
        _ensure_restore_not_active(backup_dir)
        return _prune_backups_unlocked(
            backup_dir,
            retention=retention,
            protected_ids=protected_ids,
            storage_tier=storage_tier,
        )


def _prune_backups_unlocked(
    backup_dir: Path,
    *,
    retention: RetentionConfig,
    protected_ids: frozenset[str] = frozenset(),
    storage_tier: str = STORAGE_TIER_DEGRADED,
) -> list[str]:
    """Step 3 — keeps the newest `retention.daily` scheduled backups and the
    newest `retention.manual` manual backups; only runs after the caller's
    own new backup is already confirmed valid. Pre-restore (emergency)
    backups are never touched here — `restore.py` manages that file's
    lifetime itself, since it must survive until restore success is
    verified regardless of count. Anything in `protected_ids` (an active
    restore candidate or the current emergency file) is skipped regardless
    of age."""
    validate_storage_tier(storage_tier)
    protected_ids = frozenset(
        {*protected_ids, *_active_restore_protected_ids(backup_dir)}
    )
    manifests = list_manifests(backup_dir)
    removed: list[str] = []

    for origin, keep in (
        (ORIGIN_SCHEDULED, retention.daily),
        (ORIGIN_MANUAL, retention.manual),
    ):
        candidates = [
            m
            for m in manifests
            if m.origin == origin
            and m.storage_tier == storage_tier
            and m.valid
            and m.backup_id not in protected_ids
            # A pre-P30 local artifact is classified as degraded for display,
            # but is never deleted merely because protected storage was added.
            and (storage_tier != STORAGE_TIER_DEGRADED or m.storage_tier_explicit)
            and _is_safe_manifest_id(m.backup_id)
        ]
        # list_manifests() already sorts newest-first.
        for stale in candidates[keep:]:
            _remove_backup_files(backup_dir, stale.backup_id)
            removed.append(stale.backup_id)

    return removed


def _remove_backup_files(backup_dir: Path, backup_id: str) -> None:
    validate_backup_id(backup_id)
    db_file = db_path_for(backup_dir, backup_id)
    _remove_sidecars(db_file)
    db_file.unlink(missing_ok=True)
    manifest_path_for(backup_dir, backup_id).unlink(missing_ok=True)


def prune_pre_restore_backups(
    backup_dir: Path,
    *,
    keep: int = 3,
    protected_ids: frozenset[str] = frozenset(),
) -> list[str]:
    """Bound emergency-reserve retention after a restore outcome.

    The active emergency id is always protected by the durable restore state;
    once the outcome is terminal, older pre-restore artifacts can be pruned
    without allowing them to accumulate forever.
    """
    with maintenance_lock(backup_dir):
        return _prune_pre_restore_backups_unlocked(
            backup_dir, keep=keep, protected_ids=protected_ids
        )


def _prune_pre_restore_backups_unlocked(
    backup_dir: Path,
    *,
    keep: int,
    protected_ids: frozenset[str] = frozenset(),
) -> list[str]:
    protected_ids = frozenset(
        {*protected_ids, *_active_restore_protected_ids(backup_dir)}
    )
    candidates = [
        manifest
        for manifest in list_manifests(backup_dir)
        if manifest.origin == "pre-restore"
        and manifest.storage_tier == STORAGE_TIER_DEGRADED
        and manifest.valid
        and manifest.backup_id not in protected_ids
        and _is_safe_manifest_id(manifest.backup_id)
    ]
    removed: list[str] = []
    for stale in candidates[max(0, keep) :]:
        _remove_backup_files(backup_dir, stale.backup_id)
        removed.append(stale.backup_id)
    return removed


def _is_safe_manifest_id(backup_id: str) -> bool:
    try:
        validate_backup_id(backup_id)
    except ValueError:
        return False
    return True
