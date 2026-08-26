"""The sidecar manifest format and safe id/path resolution shared by every
other module in this package (08_PKG_backup_ops.md Step 1).

A backup id is always a uuid4 hex string minted by `new_backup_id()` —
never accepted as a client-supplied filesystem path. `validate_backup_id`
is the one gate every id (from an API request body, a CLI argument, or a
manifest filename) must pass before it is ever joined onto `BACKUP_DIR`.
Because a valid id can never contain `/`, `\\`, `..`, or a drive letter,
passing the regex *is* the path-traversal defense (edge case 4.10) — no
separate `Path.resolve()`-escapes-the-root check is needed once every
caller uses `db_path_for`/`manifest_path_for` instead of building paths by
hand.
"""

import json
import os
import re
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Matches main.py's FastAPI(version=...); duplicated here rather than
# imported so this package never imports anything FastAPI-adjacent.
APP_VERSION = "1.0.0"

ORIGIN_MANUAL = "manual"
ORIGIN_SCHEDULED = "scheduled"
ORIGIN_PRE_RESTORE = "pre-restore"
VALID_ORIGINS = frozenset({ORIGIN_MANUAL, ORIGIN_SCHEDULED, ORIGIN_PRE_RESTORE})

_BACKUP_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

# The required check set for *any* listed restore point (08_PKG_backup_ops.md
# Step 2). integrity_check is additionally required for restore candidates
# and archives, but is never required merely to appear in a backup list.
_REQUIRED_CHECKS = ("checksum", "quick_check", "foreign_key_check")


class InvalidBackupIdError(ValueError):
    """Raised for any backup id that isn't a bare uuid4 hex string."""


def new_backup_id() -> str:
    return uuid.uuid4().hex


def read_schema_revision(db_path: Path) -> str | None:
    """The Alembic revision stamped in a completed SQLite file, read via
    raw `sqlite3` — this package stays free of an app.models/SQLAlchemy
    dependency (see restore.py's `record_restore_outcome_audit`). `None`
    means "unknown": the file predates Alembic (P9), is unreadable, or has
    no `alembic_version` row — never an error, since a backup must still
    be creatable even if its revision can't be determined."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None
    try:
        row = conn.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
        return row[0] if row else None
    except sqlite3.DatabaseError:
        return None
    finally:
        conn.close()


def validate_backup_id(backup_id: str) -> str:
    if not isinstance(backup_id, str) or not _BACKUP_ID_PATTERN.fullmatch(backup_id):
        raise InvalidBackupIdError(f"Not a valid backup id: {backup_id!r}")
    return backup_id


def db_path_for(backup_dir: Path, backup_id: str) -> Path:
    """The final `.db` path for an already-validated backup id. Callers
    must validate the id first — this never re-derives safety from path
    resolution, only from the id having already passed the regex."""
    return backup_dir / f"adas_backup_{backup_id}.db"


def tmp_path_for(backup_dir: Path, backup_id: str) -> Path:
    return backup_dir / f"adas_backup_{backup_id}.tmp"


def manifest_path_for(backup_dir: Path, backup_id: str) -> Path:
    return backup_dir / f"adas_backup_{backup_id}.json"


@dataclass
class BackupManifest:
    backup_id: str
    filename: str
    created_at: str  # ISO 8601 UTC with explicit offset, 01_CONTRACTS.md §1.1
    origin: str
    app_version: str
    schema_revision: str | None
    file_size: int
    sha256: str
    checks: dict[str, bool] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        """A file is not listed as a valid restore point unless its
        required checks passed (Step 1). Missing keys count as failed. The
        live listing adds artifact-name and file-size checks; older manifests
        without those additive keys remain backward compatible."""
        if not all(self.checks.get(name) for name in _REQUIRED_CHECKS):
            return False
        return all(
            self.checks[name]
            for name in ("artifact_name", "file_size")
            if name in self.checks
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BackupManifest":
        return cls(
            backup_id=data["backup_id"],
            filename=data["filename"],
            created_at=data["created_at"],
            origin=data["origin"],
            app_version=data["app_version"],
            schema_revision=data.get("schema_revision"),
            file_size=data["file_size"],
            sha256=data["sha256"],
            checks=data.get("checks", {}),
        )


def write_manifest(backup_dir: Path, manifest: BackupManifest) -> Path:
    """Atomic rename, matching the backup file itself — a reader must never
    observe a half-written manifest."""
    path = manifest_path_for(backup_dir, manifest.backup_id)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest.to_dict(), indent=2))
    os.replace(tmp, path)
    return path


def read_manifest(backup_dir: Path, backup_id: str) -> BackupManifest | None:
    path = manifest_path_for(backup_dir, validate_backup_id(backup_id))
    if not path.exists():
        return None
    try:
        manifest = BackupManifest.from_dict(json.loads(path.read_text()))
        if manifest.backup_id != backup_id:
            return None
        return manifest
    except (json.JSONDecodeError, TypeError, KeyError, OSError):
        return None


def list_manifests(backup_dir: Path) -> list[BackupManifest]:
    """Newest first. A corrupt/unreadable manifest is skipped rather than
    raising — one bad sidecar must not break the whole listing."""
    if not backup_dir.exists():
        return []
    manifests: list[BackupManifest] = []
    for path in backup_dir.glob("adas_backup_*.json"):
        try:
            manifests.append(BackupManifest.from_dict(json.loads(path.read_text())))
        except (json.JSONDecodeError, TypeError, KeyError, OSError):
            continue
    manifests.sort(key=lambda m: m.created_at, reverse=True)
    return manifests
