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
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.core.db import init_db
from app.dev.profiles import (
    UAT_RESTORE_ANCHOR_LABEL,
    UAT_TRAY_ALERT_LABEL,
    build_uat_alert_specs,
)
from app.dev.seed import SeedResult, seed_profile, seed_source_event_id
from app.dev.wipe import wipe_operational_data
from app.models import (
    AIStatus,
    AuditLog,
    Camera,
    ConnectionStatus,
    DetectionLog,
    DetectionStatus,
    User,
)
from app.schemas.events import EventType, MaintenanceNoticeData, make_event
from app.services import snapshots
from app.services.cameras import recompute_desired_state
from app.services.realtime import RealtimeManager

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger("uvicorn.error")

# Two overlapping reseeds would interleave a wipe with another run's insert.
# Module-level, so it is shared by every request into this process.
_reseed_lock = asyncio.Lock()


@dataclass(frozen=True)
class UatResetResult:
    phase: str
    removed_session_detections: int
    preserved_audit_rows: int
    tray_status: str
    readiness_camera_enabled: bool


class UatProfileRequired(RuntimeError):
    pass


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


def _require_uat_baseline(session: Session) -> tuple[dict[int, Camera], DetectionLog]:
    cameras = {
        camera.channel_id: camera
        for camera in session.exec(
            select(Camera).where(col(Camera.channel_id).in_(range(1, 7)))
        )
        if camera.is_active
    }
    expected_names = {
        1: "UAT Channel 1 - Genuine Alert Cam",
        2: "UAT Channel 2 - False Alert Cam",
        3: "UAT Channel 3 - Recovery Cam",
        4: "UAT Channel 4 - Readiness Cam",
        5: "UAT Channel 5 - Reference Cam",
        6: "UAT Channel 6 - Tray Review Cam",
    }
    if any(
        channel not in cameras or cameras[channel].camera_name != name
        for channel, name in expected_names.items()
    ):
        raise UatProfileRequired(
            "Load the 'uat' seed profile before preparing a UAT session."
        )

    usernames = {user.username for user in session.exec(select(User))}
    required_users = {
        *(f"uat_op{number:02d}" for number in range(1, 7)),
        *(f"uat_adm{number:02d}" for number in range(1, 3)),
    }
    if not required_users <= usernames:
        raise UatProfileRequired(
            "The database does not contain the complete UAT participant accounts."
        )

    tray = session.exec(
        select(DetectionLog).where(
            DetectionLog.source_event_id == seed_source_event_id(UAT_TRAY_ALERT_LABEL)
        )
    ).first()
    anchor = session.exec(
        select(DetectionLog).where(
            DetectionLog.source_event_id
            == seed_source_event_id(UAT_RESTORE_ANCHOR_LABEL)
        )
    ).first()
    if tray is None or anchor is None:
        raise UatProfileRequired(
            "The UAT tray incident or restoration anchor is missing; reseed 'uat'."
        )
    return cameras, tray


def _set_camera_observed_healthy(camera: Camera, *, now: datetime) -> None:
    camera.is_active = True
    camera.is_enabled = True
    camera.connection_status = ConnectionStatus.CONNECTED.value
    camera.ai_status = AIStatus.ACTIVE.value
    camera.last_heartbeat_at = now
    camera.measured_fps = 15.0
    camera.inference_latency_ms = 54.0
    camera.last_error_code = None
    camera.last_error_message = None
    camera.cooldown_until = None


def _reset_uat_session_sync(
    engine: Engine,
    *,
    phase: str,
    snapshot_root: Path,
) -> UatResetResult:
    now = datetime.now(UTC)
    removed_snapshot_keys: list[str] = []

    with Session(engine) as session:
        cameras, tray = _require_uat_baseline(session)
        audit_count = len(session.exec(select(AuditLog)).all())

        if phase == "administrator_healthy":
            readiness = cameras[4]
            _set_camera_observed_healthy(readiness, now=now)
            readiness.config_version += 1
            recompute_desired_state(readiness, has_open_incident=False, now=now)
            session.add(readiness)
            session.commit()
            return UatResetResult(
                phase=phase,
                removed_session_detections=0,
                preserved_audit_rows=audit_count,
                tray_status=tray.detection_status,
                readiness_camera_enabled=readiness.is_enabled,
            )

        # Real RTSP/AI detections raised during the previous participant's
        # run are cleared from the three trigger cameras. The rows seeded for
        # reports remain, and AuditLog is deliberately untouched so AD-J06
        # can inspect every real participant action.
        seeded_source_ids = {
            seed_source_event_id(spec.label) for spec in build_uat_alert_specs(now)
        }
        trigger_ids = {cameras[channel].camera_id for channel in (1, 2, 3)}
        session_rows = session.exec(
            select(DetectionLog).where(col(DetectionLog.camera_id).in_(trigger_ids))
        ).all()
        removed_rows = [
            row for row in session_rows if row.source_event_id not in seeded_source_ids
        ]
        for row in removed_rows:
            removed_snapshot_keys.append(row.snapshot_key)
            session.delete(row)
        session.flush()

        verifier = session.exec(select(User).where(User.username == "uat_op01")).one()
        if phase == "operator":
            tray.detection_status = DetectionStatus.ONGOING.value
            tray.verified_by_id = verifier.user_id
            tray.closed_by_id = None
            tray.closed_at = None
        else:
            tray.detection_status = DetectionStatus.DISMISSED.value
            tray.closed_by_id = None
            tray.closed_at = now
        tray.snoozed_by_id = None
        tray.snoozed_at = None
        tray.snoozed_until = None
        session.add(tray)

        for channel in (1, 2, 3, 5, 6):
            camera = cameras[channel]
            _set_camera_observed_healthy(camera, now=now)
            camera.config_version += 1
            recompute_desired_state(
                camera,
                has_open_incident=(channel == 6 and phase == "operator"),
                now=now,
            )
            session.add(camera)

        readiness = cameras[4]
        readiness.is_active = True
        readiness.is_enabled = False
        readiness.connection_status = ConnectionStatus.DISCONNECTED.value
        readiness.ai_status = AIStatus.INACTIVE.value
        readiness.last_heartbeat_at = None
        readiness.measured_fps = None
        readiness.inference_latency_ms = None
        readiness.last_error_code = None
        readiness.last_error_message = None
        readiness.cooldown_until = None
        readiness.config_version += 1
        recompute_desired_state(readiness, has_open_incident=False, now=now)
        session.add(readiness)

        session.commit()

        if len(session.exec(select(AuditLog)).all()) != audit_count:
            raise RuntimeError("UAT reset changed the append-only audit row count.")

        tray_status = tray.detection_status
        readiness_enabled = readiness.is_enabled
        removed_count = len(removed_rows)

    for key in removed_snapshot_keys:
        path = snapshots.resolve(
            key,
            snapshot_root=snapshot_root,
            legacy_dir=snapshot_root,
        )
        if path is None:
            continue
        try:
            path.unlink()
        except OSError:
            logger.warning("Could not delete UAT session snapshot %s", path)

    return UatResetResult(
        phase=phase,
        removed_session_detections=removed_count,
        preserved_audit_rows=audit_count,
        tray_status=tray_status,
        readiness_camera_enabled=readiness_enabled,
    )


async def reset_uat_session(
    engine: Engine,
    *,
    phase: str,
    scheduler: AsyncIOScheduler | None,
    snapshot_root: Path,
    manager: RealtimeManager | None = None,
) -> UatResetResult:
    """Restore journey fixtures while retaining accumulated audit evidence."""
    async with _reseed_lock:
        if scheduler is not None:
            scheduler.pause()
        try:
            result = await run_in_threadpool(
                _reset_uat_session_sync,
                engine,
                phase=phase,
                snapshot_root=snapshot_root,
            )
        finally:
            if scheduler is not None:
                scheduler.resume()

    if manager is not None:
        manager.broadcast(
            make_event(
                EventType.MAINTENANCE_NOTICE,
                MaintenanceNoticeData(
                    message=(
                        f"The UAT environment was prepared for '{phase}'. "
                        "Reload to see the restored session fixtures."
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
