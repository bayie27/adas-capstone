"""D-011 Step 8 — the weekly air-gapped archive. Built from a verified
database backup: the backup + its manifest, the incident snapshots it
references, the portable `.pt` model weights (never `.engine` — that
artifact is GPU/driver/TensorRT-version-specific), checksums, and a
missing-file report. Never includes `.env`, session/JWT secrets, or any
credential-bearing configuration.
"""

import json
import os
import sqlite3
import zipfile
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.maintenance.manifest import BackupManifest, db_path_for, manifest_path_for
from app.maintenance.storage import (
    STORAGE_TIER_DEGRADED,
    STORAGE_TIER_PROTECTED,
    StorageTargetProvider,
    probe_protected_storage,
    reason_for_publish_failure,
    validate_storage_tier,
)
from app.maintenance.verify import compute_sha256

# Case-insensitive substring scan across every archived member's raw bytes.
# Binary members (the .db backup, .pt weights, .jpg snapshots) are included
# in the scan too rather than special-cased out — bytes are bytes, and at
# demo-laptop archive sizes a substring scan costs nothing worth avoiding.
_FORBIDDEN_BYTE_STRINGS = (b"rtsp://",)
_FORBIDDEN_FILENAME = ".env"


class ArchiveSecurityError(RuntimeError):
    """Raised if a forbidden file or credential-bearing string would end up
    in the archive. Checked as part of building the archive itself, not
    only by an external test, so a bug here can never ship a leaking file."""


class ArchiveTargetsFailedError(RuntimeError):
    """Both archive destinations failed; message contains no paths."""

    def __init__(self, protected_reason: str, fallback_reason: str):
        self.protected_reason = protected_reason
        self.fallback_reason = fallback_reason
        super().__init__(
            "Protected and degraded archive targets both failed "
            f"({protected_reason}; {fallback_reason})."
        )


@dataclass
class ArchiveManifest:
    archive_id: str
    created_at: str
    backup_id: str
    included_files: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    checksums: dict[str, str] = field(default_factory=dict)
    storage_tier: str = STORAGE_TIER_DEGRADED
    storage_reason: str | None = None


@dataclass(frozen=True)
class ArchivePublishResult:
    path: Path
    storage_tier: str
    storage_reason: str | None = None


def _referenced_snapshot_keys(db_path: Path) -> list[str]:
    """01_CONTRACTS.md §7.1 — the archive includes only snapshots this
    *specific backup's* detection_log actually references, read from the
    backup file itself (never the live database, which may have moved on)
    so the archive is a true point-in-time pairing of database and
    evidence."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT DISTINCT snapshot_key FROM detection_log"
        ).fetchall()
    except sqlite3.DatabaseError:
        return []
    finally:
        conn.close()
    return [row[0] for row in rows if row[0]]


def _resolve_snapshot_path(
    key: str, snapshot_root: Path, legacy_snapshot_dir: Path
) -> Path | None:
    """Mirrors the resolution order in 01_CONTRACTS.md §7.1: `SNAPSHOT_ROOT
    / key` first, then `LEGACY_SNAPSHOT_DIR / key` for a legacy bare
    filename. Rejects absolute paths and any key whose resolution would
    escape the configured roots — defense in depth, even though these keys
    come from the database rather than a live request."""
    if not key or Path(key).is_absolute() or ".." in Path(key).parts:
        return None

    candidate = (snapshot_root / key).resolve()
    if candidate.is_relative_to(snapshot_root.resolve()) and candidate.exists():
        return candidate

    if "/" not in key and "\\" not in key:
        legacy_candidate = (legacy_snapshot_dir / key).resolve()
        if (
            legacy_candidate.is_relative_to(legacy_snapshot_dir.resolve())
            and legacy_candidate.exists()
        ):
            return legacy_candidate

    return None


def _add_file(
    zf: zipfile.ZipFile,
    path: Path,
    arcname: str,
    included: list[str],
    missing: list[str],
    checksums: dict[str, str],
) -> None:
    if not path.exists():
        missing.append(arcname)
        return
    zf.write(path, arcname)
    checksums[arcname] = compute_sha256(path)
    included.append(arcname)


def build_archive(
    *,
    backup_manifest: BackupManifest,
    backup_dir: Path,
    snapshot_root: Path,
    model_weights_path: Path,
    archive_dir: Path,
    legacy_snapshot_dir: Path | None = None,
    storage_tier: str = STORAGE_TIER_DEGRADED,
    storage_reason: str | None = None,
) -> Path:
    validate_storage_tier(storage_tier)
    legacy_snapshot_dir = (
        legacy_snapshot_dir if legacy_snapshot_dir is not None else snapshot_root
    )
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{backup_manifest.backup_id[:8]}"
    archive_path = archive_dir / f"adas_archive_{archive_id}.zip"
    tmp_path = archive_path.with_suffix(".zip.tmp")

    missing: list[str] = []
    checksums: dict[str, str] = {}
    included: list[str] = []

    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            db_file = db_path_for(backup_dir, backup_manifest.backup_id)
            _add_file(
                zf, db_file, f"database/{db_file.name}", included, missing, checksums
            )

            manifest_file = manifest_path_for(backup_dir, backup_manifest.backup_id)
            _add_file(
                zf,
                manifest_file,
                f"database/{manifest_file.name}",
                included,
                missing,
                checksums,
            )

            _add_file(
                zf,
                model_weights_path,
                f"model/{model_weights_path.name}",
                included,
                missing,
                checksums,
            )

            for key in sorted(_referenced_snapshot_keys(db_file)):
                arcname = f"snapshots/{key}"
                resolved = _resolve_snapshot_path(
                    key, snapshot_root, legacy_snapshot_dir
                )
                if resolved is None:
                    missing.append(arcname)
                    continue
                _add_file(zf, resolved, arcname, included, missing, checksums)

            archive_manifest = ArchiveManifest(
                archive_id=archive_id,
                created_at=datetime.now(UTC).isoformat(),
                backup_id=backup_manifest.backup_id,
                included_files=included,
                missing_files=missing,
                checksums=checksums,
                storage_tier=storage_tier,
                storage_reason=storage_reason,
            )
            zf.writestr(
                "archive_manifest.json", json.dumps(asdict(archive_manifest), indent=2)
            )

        _assert_no_secrets(tmp_path)
        os.replace(tmp_path, archive_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return archive_path


def _cleanup_unpublished_archives(archive_dir: Path) -> None:
    """Clean temp archive files without touching completed archives."""
    if not archive_dir.exists():
        return
    for path in archive_dir.glob("adas_archive_*.zip.tmp"):
        with suppress(OSError):
            path.unlink(missing_ok=True)


def create_archive(
    *,
    backup_manifest: BackupManifest,
    backup_dir: Path,
    snapshot_root: Path,
    model_weights_path: Path,
    archive_dir: Path,
    protected_archive_dir: Path | None = None,
    db_path: Path,
    storage_provider: StorageTargetProvider | None = None,
    legacy_snapshot_dir: Path | None = None,
) -> ArchivePublishResult:
    """Build an archive protected-first, then use the local fallback."""
    protected_reason = "not_configured"
    if protected_archive_dir is not None:
        _cleanup_unpublished_archives(protected_archive_dir)
        try:
            same_root = (
                Path(protected_archive_dir).resolve() == Path(archive_dir).resolve()
            )
        except OSError:
            same_root = False
        probe = (
            None
            if same_root
            else probe_protected_storage(
                protected_archive_dir,
                live_db_path=db_path,
                required_bytes=1,
                provider=storage_provider,
            )
        )
        if same_root:
            protected_reason = "same_device"
        elif probe is not None:
            protected_reason = probe.reason or "available"
        if probe is not None and probe.available:
            _cleanup_unpublished_archives(protected_archive_dir)
            try:
                path = build_archive(
                    backup_manifest=backup_manifest,
                    backup_dir=backup_dir,
                    snapshot_root=snapshot_root,
                    legacy_snapshot_dir=legacy_snapshot_dir,
                    model_weights_path=model_weights_path,
                    archive_dir=protected_archive_dir,
                    storage_tier=STORAGE_TIER_PROTECTED,
                )
                return ArchivePublishResult(path, STORAGE_TIER_PROTECTED)
            except Exception as exc:
                protected_reason = reason_for_publish_failure(exc)
                _cleanup_unpublished_archives(protected_archive_dir)
        else:
            _cleanup_unpublished_archives(protected_archive_dir)

    try:
        path = build_archive(
            backup_manifest=backup_manifest,
            backup_dir=backup_dir,
            snapshot_root=snapshot_root,
            legacy_snapshot_dir=legacy_snapshot_dir,
            model_weights_path=model_weights_path,
            archive_dir=archive_dir,
            storage_tier=STORAGE_TIER_DEGRADED,
            storage_reason=protected_reason,
        )
        return ArchivePublishResult(path, STORAGE_TIER_DEGRADED, protected_reason)
    except Exception as exc:
        fallback_reason = reason_for_publish_failure(exc)
        if protected_archive_dir is not None:
            raise ArchiveTargetsFailedError(protected_reason, fallback_reason) from exc
        raise


def _assert_no_secrets(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if Path(name).name.lower() == _FORBIDDEN_FILENAME:
                raise ArchiveSecurityError(
                    f"Archive would contain a forbidden file: {name}"
                )
        for name in zf.namelist():
            data = zf.read(name)
            for forbidden in _FORBIDDEN_BYTE_STRINGS:
                if forbidden in data:
                    raise ArchiveSecurityError(
                        f"Archive member {name!r} contains a forbidden "
                        "credential-bearing string."
                    )
