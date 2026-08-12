"""In-process operational-data wipe (dev_plan/02_PKG_dev_api.md Step 3).

`backend/scripts/reset_db.py` deletes the SQLite file and its -wal/-shm
sidecars, which cannot happen while the backend holds it open — on Windows
the unlink raises PermissionError outright. A dev-panel reseed needs the
opposite: rows gone, schema intact, server up, WebSocket connections alive.

**The schema is never touched here.** No file delete, no
SQLModel.metadata.create_all(), no migration. Only DELETE statements, plus
the audit triggers being dropped and put back exactly as they were.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import delete, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.models import (
    AUDIT_IMMUTABILITY_TRIGGER_NAMES,
    AUDIT_IMMUTABILITY_TRIGGERS,
    AlarmSettings,
    AuditLog,
    AuthSession,
    Camera,
    DetectionLog,
    ExportJob,
    SysHealthHourly,
    SysHealthRaw,
    User,
)
from app.services import snapshots

logger = logging.getLogger("uvicorn.error")

# PRAGMA foreign_keys=ON is live on every connection (D-005, app/core/db.py),
# so this order is load-bearing rather than cosmetic. audit_log.user_id is
# ondelete="RESTRICT", which is why it genuinely has to precede `user`.
#
# Deliberately absent: help_article and help_article_fts, which init_db() ->
# seed_help_articles() owns and re-derives content-hash-idempotently (FR-20)
# — an FTS5 external-content table is not worth re-syncing for a dev reset.
# And alembic_version, obviously.
_DELETE_ORDER = (
    ("detection_log", DetectionLog),
    ("audit_log", AuditLog),
    ("auth_session", AuthSession),
    ("alarm_settings", AlarmSettings),
    ("export_job", ExportJob),
    ("sys_health_raw", SysHealthRaw),
    ("sys_health_hourly", SysHealthHourly),
    ("camera", Camera),
    ("user", User),
)


def _collect_snapshot_keys(session: Session) -> list[str]:
    return [
        row.snapshot_key
        for row in session.exec(select(DetectionLog))
        if row.snapshot_key
    ]


def _unlink_snapshots(keys: list[str], *, snapshot_root: Path) -> int:
    """Every path goes through services.snapshots.resolve(), so a hostile or
    malformed key cannot make the wipe delete outside the configured roots —
    resolve() returns None for anything that escapes them and we skip it.
    Without this the `empty` profile would not be empty: the rows would be
    gone and the images would still be on disk."""
    removed = 0
    for key in keys:
        path = snapshots.resolve(
            key, snapshot_root=snapshot_root, legacy_dir=snapshot_root
        )
        if path is None:
            continue
        try:
            path.unlink()
            removed += 1
        except OSError:
            logger.warning("Could not delete seeded snapshot %s", path)
    _prune_empty_dirs(snapshot_root)
    return removed


def _prune_empty_dirs(snapshot_root: Path) -> None:
    """Bottom-up, so YYYY/MM/DD/camera_N/ collapses fully. The root itself is
    kept — the next seed writes straight back into it."""
    if not snapshot_root.is_dir():
        return
    for path in sorted(
        (p for p in snapshot_root.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        try:
            next(path.iterdir())
        except StopIteration:
            path.rmdir()
        except OSError:
            continue


def wipe_operational_data(engine: Engine, *, snapshot_root: Path) -> dict[str, int]:
    """Deletes every operational row, returning per-table counts.

    audit_log carries BEFORE UPDATE/DELETE triggers that make
    `DELETE FROM audit_log` raise 'audit_log is append-only'. They are
    dropped, the deletes run, and then the *same* DDL objects from
    app/models/audit.py are re-executed — never a re-typed copy, which would
    give NFR-21's append-only guarantee a second source of truth.

    The recreate sits in a `finally` **with its own commit**, and that
    detail is the whole thing. An earlier version wrapped all of it in a
    single `engine.begin()`, reasoning that SQLite DDL is transactional so a
    rollback would undo both the drop and the recreate. It does not work
    that way: pysqlite does not open a transaction until the first DML
    statement, so the `DROP TRIGGER`s ran in autocommit and were already
    durable, while the recreate — issued after the failing DELETE had opened
    a real transaction — was rolled back with it. Result: rows intact,
    triggers gone, audit_log silently mutable. Reproduced, then fixed.

    The finally drops-if-exists before recreating, so it lands in exactly
    one state no matter where the failure hit — including a failure during
    the initial drop, where a bare CREATE would raise "trigger already
    exists" and mask the original error.
    """
    counts: dict[str, int] = {}

    with Session(engine) as session:
        snapshot_keys = _collect_snapshot_keys(session)

    with engine.connect() as conn:
        try:
            for name in AUDIT_IMMUTABILITY_TRIGGER_NAMES:
                conn.execute(text(f"DROP TRIGGER IF EXISTS {name}"))
            conn.commit()

            for table_name, model in _DELETE_ORDER:
                result = conn.execute(delete(model))
                counts[table_name] = result.rowcount or 0
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            for name in AUDIT_IMMUTABILITY_TRIGGER_NAMES:
                conn.execute(text(f"DROP TRIGGER IF EXISTS {name}"))
            for trigger in AUDIT_IMMUTABILITY_TRIGGERS:
                conn.execute(trigger)
            conn.commit()

    counts["snapshots"] = _unlink_snapshots(snapshot_keys, snapshot_root=snapshot_root)
    logger.info("Dev wipe removed: %s", counts)
    return counts
