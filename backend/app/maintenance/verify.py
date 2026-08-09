"""D-011 Step 2 — backup validation. Every check here runs against the
completed backup file, never the live database (08_PKG_backup_ops.md).
"""

import hashlib
import sqlite3
from pathlib import Path

_CHUNK_SIZE = 1024 * 1024


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_readonly(path: Path) -> sqlite3.Connection:
    # mode=ro: these checks only ever read the backup file, never the live
    # database, and never risk creating a stray file if `path` is missing.
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def run_quick_check(path: Path) -> bool:
    try:
        conn = _open_readonly(path)
    except sqlite3.OperationalError:
        return False
    try:
        result = conn.execute("PRAGMA quick_check").fetchone()
        return result is not None and result[0] == "ok"
    except sqlite3.DatabaseError:
        return False
    finally:
        conn.close()


def run_integrity_check(path: Path) -> bool:
    try:
        conn = _open_readonly(path)
    except sqlite3.OperationalError:
        return False
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        return result is not None and result[0] == "ok"
    except sqlite3.DatabaseError:
        return False
    finally:
        conn.close()


def run_foreign_key_check(path: Path) -> bool:
    try:
        conn = _open_readonly(path)
    except sqlite3.OperationalError:
        return False
    try:
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        return len(violations) == 0
    except sqlite3.DatabaseError:
        return False
    finally:
        conn.close()


def validate_backup(path: Path, *, full: bool = False) -> dict[str, bool]:
    """Runs the required check set for a completed backup file: checksum
    computability, `quick_check`, and `foreign_key_check` always;
    `integrity_check` additionally for restore candidates and weekly
    archives (`full=True`). The checksum here only proves the file is
    readable and hashable — comparing it against a *recorded* value is a
    separate re-verification step (see backup.list_backups), since at
    creation time there is nothing yet to compare against."""
    checks: dict[str, bool] = {}
    try:
        compute_sha256(path)
        checks["checksum"] = True
    except OSError:
        checks["checksum"] = False

    checks["quick_check"] = run_quick_check(path)
    checks["foreign_key_check"] = run_foreign_key_check(path)
    if full:
        checks["integrity_check"] = run_integrity_check(path)

    return checks
