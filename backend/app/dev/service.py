"""Reseed orchestration for the dev panel (dev_plan/02_PKG_dev_api.md Step 4).

**This module deliberately writes no audit rows**, and that is the one
sanctioned exception to CLAUDE.md's "every audited state change is one
transaction" rule. It is not an oversight. The audit-aware helpers in
app/services/audit.py exist to make real operator actions accountable;
none of these are one, and a reseed wipes audit_log wholesale anyway, so
a row recording the wipe would be deleted by the wipe that wrote it.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.config import Settings
from app.core.db import init_db
from app.dev.seed import SeedResult, seed_profile
from app.dev.wipe import wipe_operational_data
from app.schemas.events import EventType, MaintenanceNoticeData, make_event
from app.services.realtime import RealtimeManager

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger("uvicorn.error")

# Two overlapping reseeds would interleave a wipe with another run's insert.
# Module-level, so it is shared by every request into this process.
_reseed_lock = asyncio.Lock()


def _wipe_and_seed(
    engine: Engine,
    *,
    profile: str,
    snapshot_root: Path,
    target_settings: Settings | None,
) -> SeedResult:
    """The synchronous half, run off the event loop. app.dev.seed is
    blocking and `perf` takes ~33s — holding the loop for that would stall
    every WebSocket heartbeat in the process."""
    # Before the wipe, not just inside seed_profile() afterwards: the wipe
    # issues DELETEs against tables that a never-migrated database does not
    # have yet. In the real request path the schema always exists (lifespan
    # ran init_db at startup), but a reseed against a fresh file would
    # otherwise die on `no such table: detection_log`. Idempotent — the
    # second call inside seed_profile() hits check_schema_revision's
    # current_rev == head_rev fast path.
    init_db(engine, target_settings)
    wipe_operational_data(engine, snapshot_root=snapshot_root)
    return seed_profile(
        engine,
        profile=profile,
        target_settings=target_settings,
        snapshot_root=snapshot_root,
    )


async def reseed(
    engine: Engine,
    *,
    profile: str,
    scheduler: AsyncIOScheduler | None,
    snapshot_root: Path,
    manager: RealtimeManager | None = None,
    target_settings: Settings | None = None,
) -> SeedResult:
    """Wipes and reseeds in-process, with the server still up.

    `target_settings` must be the Settings `engine` was built from: seeding
    calls init_db(), whose schema check reopens target_settings.DATABASE_URL
    itself and ignores the engine (F18 in be_audit/00_FINDINGS.md).

    `scheduler` may be None — get_scheduler() returns None whenever
    SCHEDULER_ENABLED is false, which is the whole test suite.
    """
    async with _reseed_lock:
        # APScheduler is running the cooldown/snooze sweeps every 30s, the
        # health sampler, and the export workers. Letting those run against
        # a table mid-wipe risks `database is locked` and jobs operating on
        # rows that vanish under them.
        if scheduler is not None:
            scheduler.pause()
        try:
            result = await run_in_threadpool(
                _wipe_and_seed,
                engine,
                profile=profile,
                snapshot_root=snapshot_root,
                target_settings=target_settings,
            )
            # Otherwise the -wal file keeps the pre-wipe pages around, which
            # makes a "fresh" database look anything but on disk.
            await run_in_threadpool(_checkpoint_wal, engine)
        finally:
            if scheduler is not None:
                scheduler.resume()

    logger.info("Dev reseed complete: %s", result)

    if manager is not None:
        # Tells *other* connected browsers their view is stale. The client
        # that asked for the reseed does its own cache/store reset from the
        # response and does not need this.
        manager.broadcast(
            make_event(
                EventType.MAINTENANCE_NOTICE,
                MaintenanceNoticeData(
                    message=(
                        f"The database was reseeded with the '{profile}' "
                        f"profile. Reload to see the new data."
                    )
                ),
            )
        )

    return result


def _checkpoint_wal(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.connect() as conn:
        conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
