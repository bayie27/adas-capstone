"""
Camera desired-state recomputation (D-003).

recompute_desired_state() is the single source of truth for what
desired_ai_state/desired_state_reason/cooldown_until should be, given a
camera's current facts. It's called from lifespan's startup reconciliation
(P1, below) and, later, the cooldown-expiry scheduler job and heartbeat
processing (P4) — anywhere the desired state needs to be *derived* rather
than assumed, which is exactly what makes a mid-cooldown restart durable
instead of stranding the camera Paused forever.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.redaction import redact_text
from app.models import (
    AIStatus,
    Camera,
    ConnectionStatus,
    DesiredAIState,
    DesiredStateReason,
    DetectionLog,
    DetectionStatus,
)
from app.services.events import camera_status_update_event
from app.services.realtime import RealtimeManager

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

_OPEN_STATUSES = (DetectionStatus.UNVERIFIED.value, DetectionStatus.ONGOING.value)


def presented_statuses(camera: Camera, *, now: datetime) -> tuple[str, str]:
    """05_PKG_incidents_cameras.md Step 2/10 — the read-time presentation
    layer over the stored observed columns. Never written to the row, so a
    stale value never becomes indistinguishable from a genuinely reported
    one (that's the whole point of computing it here instead).

    - never heartbeated yet (enabled, no report received): presented as
      Reconnecting rather than the raw Disconnected default — camera create
      doesn't block on an RTSP handshake, so a brand-new camera legitimately
      has no heartbeat yet (Step 10).
    - heartbeated before but now stale (>= HEARTBEAT_STALE_SECONDS):
      presented as Unresponsive for both dimensions (Step 2). The AI engine
      never emits Unresponsive itself.
    - a disabled camera is never "stale" — it isn't expected to heartbeat.
    - otherwise: the raw stored values.
    """
    if not camera.is_enabled:
        return camera.connection_status, camera.ai_status

    if camera.last_heartbeat_at is None:
        return ConnectionStatus.RECONNECTING.value, camera.ai_status

    elapsed = (now - camera.last_heartbeat_at).total_seconds()
    if elapsed >= settings.HEARTBEAT_STALE_SECONDS:
        return ConnectionStatus.UNRESPONSIVE.value, AIStatus.UNRESPONSIVE.value

    return camera.connection_status, camera.ai_status


def compute_kpis_and_breakdowns(
    session: Session, *, now: datetime
) -> tuple[dict, dict]:
    """01_CONTRACTS.md §5.9 — one query over the unfiltered `is_active=1`
    population (replacing three separate unfiltered COUNTs), aggregated in
    Python because the breakdown is over *presented* status, which is a
    staleness computation no plain SQL GROUP BY can express without
    duplicating presented_statuses()'s logic in SQL."""
    cameras = session.exec(select(Camera).where(col(Camera.is_active).is_(True))).all()

    total = len(cameras)
    enabled = sum(1 for camera in cameras if camera.is_enabled)
    connection_counts = {status.value: 0 for status in ConnectionStatus}
    ai_counts = {status.value: 0 for status in AIStatus}

    for camera in cameras:
        connection_status, ai_status = presented_statuses(camera, now=now)
        connection_counts[connection_status] += 1
        ai_counts[ai_status] += 1

    kpis = {
        "total": total,
        "enabled": enabled,
        "network_connected": connection_counts[ConnectionStatus.CONNECTED.value],
        "active_detection": ai_counts[AIStatus.ACTIVE.value],
    }
    breakdowns = {
        "connection": {
            "connected": connection_counts[ConnectionStatus.CONNECTED.value],
            "disconnected": connection_counts[ConnectionStatus.DISCONNECTED.value],
            "reconnecting": connection_counts[ConnectionStatus.RECONNECTING.value],
            "unresponsive": connection_counts[ConnectionStatus.UNRESPONSIVE.value],
        },
        "ai": {
            "active": ai_counts[AIStatus.ACTIVE.value],
            "paused": ai_counts[AIStatus.PAUSED.value],
            "inactive": ai_counts[AIStatus.INACTIVE.value],
            "unresponsive": ai_counts[AIStatus.UNRESPONSIVE.value],
        },
    }
    return kpis, breakdowns


# 05_PKG_incidents_cameras.md Step 2 — fields that matter to the AI engine.
# Renaming a camera does not bump config_version; the engine does not care
# about names.
_AI_RELEVANT_FIELDS = (
    "channel_id",
    "is_enabled",
    "is_active",
    "desired_ai_state",
    "desired_state_reason",
    "cooldown_until",
)


def snapshot_ai_relevant_fields(camera: Camera) -> tuple:
    return tuple(getattr(camera, field) for field in _AI_RELEVANT_FIELDS)


def bump_config_version(camera: Camera) -> None:
    camera.config_version += 1


def bump_if_ai_relevant_changed(camera: Camera, before: tuple) -> bool:
    """Compares `before` (captured via snapshot_ai_relevant_fields() prior to
    mutating `camera`) against its current values and bumps config_version
    at most once if anything AI-relevant changed."""
    changed = snapshot_ai_relevant_fields(camera) != before
    if changed:
        bump_config_version(camera)
    return changed


def apply_desired_state(
    camera: Camera, *, has_open_incident: bool, now: datetime
) -> bool:
    """recompute_desired_state() plus the config_version bump, for call
    sites (incident transitions, cooldown expiry) where desired state is the
    only thing that can change. Returns True if it actually changed."""
    before = snapshot_ai_relevant_fields(camera)
    recompute_desired_state(camera, has_open_incident=has_open_incident, now=now)
    return bump_if_ai_relevant_changed(camera, before)


@dataclass
class ObservedReport:
    """One camera's entry from a v2 heartbeat request (01_CONTRACTS.md §6.2)."""

    connection_status: str
    ai_status: str
    applied_config_version: int | None
    measured_fps: float | None
    inference_latency_ms: float | None
    error_code: str | None
    error_message: str | None


def apply_observed(camera: Camera, report: ObservedReport, *, now: datetime) -> bool:
    """The only writer of AI-owned observed state (D-003). Returns whether
    anything meaningfully changed, *excluding* last_heartbeat_at (which
    always changes) — heartbeat processing broadcasts only on a real change,
    not every three seconds."""
    before = (
        camera.connection_status,
        camera.ai_status,
        camera.applied_config_version,
        camera.measured_fps,
        camera.inference_latency_ms,
        camera.last_error_code,
        camera.last_error_message,
    )
    camera.connection_status = report.connection_status
    camera.ai_status = report.ai_status
    camera.applied_config_version = report.applied_config_version
    camera.measured_fps = report.measured_fps
    camera.inference_latency_ms = report.inference_latency_ms
    camera.last_error_code = report.error_code
    camera.last_error_message = (
        redact_text(report.error_message) if report.error_message else None
    )
    camera.last_heartbeat_at = now
    after = (
        camera.connection_status,
        camera.ai_status,
        camera.applied_config_version,
        camera.measured_fps,
        camera.inference_latency_ms,
        camera.last_error_code,
        camera.last_error_message,
    )
    return before != after


def recompute_desired_state(
    camera: Camera, *, has_open_incident: bool, now: datetime
) -> None:
    """Mutates `camera` in place. Does not commit — callers own the session."""
    if not camera.is_active or not camera.is_enabled:
        camera.desired_ai_state = DesiredAIState.INACTIVE.value
        camera.desired_state_reason = DesiredStateReason.DISABLED.value
        camera.cooldown_until = None
        return

    if has_open_incident:
        camera.desired_ai_state = DesiredAIState.PAUSED.value
        camera.desired_state_reason = DesiredStateReason.INCIDENT.value
        camera.cooldown_until = None
        return

    if camera.cooldown_until is not None and camera.cooldown_until > now:
        camera.desired_ai_state = DesiredAIState.PAUSED.value
        camera.desired_state_reason = DesiredStateReason.COOLDOWN.value
        return

    camera.desired_ai_state = DesiredAIState.ACTIVE.value
    camera.desired_state_reason = None
    camera.cooldown_until = None


def _camera_ids_with_open_incidents(
    session: Session, camera_ids: list[int]
) -> set[int]:
    if not camera_ids:
        return set()
    rows = session.exec(
        select(DetectionLog.camera_id)
        .where(
            col(DetectionLog.camera_id).in_(camera_ids),
            col(DetectionLog.detection_status).in_(_OPEN_STATUSES),
        )
        .distinct()
    ).all()
    return set(rows)


def reconcile_camera_desired_states(
    engine: Engine, *, now: datetime | None = None
) -> list[Camera]:
    """Startup reconciliation (P1 Step 9). Recomputes desired state for
    every soft-deleted-excluded camera — never resets it blindly, unlike
    observed state, which genuinely has no reporter until the AI engine
    reconnects.

    `now` is injectable so dev seeding can pass its own pinned time through
    instead of silently falling back to wall-clock `datetime.now(UTC)` —
    a seeded `cooldown_until` computed relative to a pinned `now` would
    otherwise read as already-expired the moment real time moves past that
    pinned value, and recompute_desired_state() clears an expired cooldown
    as part of its normal, correct behavior. The real startup caller
    (app/main.py) always wants wall-clock time, so the default is unchanged.

    Returns the cameras left Paused with reason='cooldown' so the caller
    can reschedule their resume jobs.
    """
    now = now if now is not None else datetime.now(UTC)
    with Session(engine) as session:
        cameras = session.exec(
            select(Camera).where(col(Camera.is_active).is_(True))
        ).all()
        open_camera_ids = _camera_ids_with_open_incidents(
            session, [c.camera_id for c in cameras if c.camera_id is not None]
        )

        pending_cooldowns: list[Camera] = []
        for camera in cameras:
            recompute_desired_state(
                camera,
                has_open_incident=camera.camera_id in open_camera_ids,
                now=now,
            )
            session.add(camera)
            if camera.desired_state_reason == DesiredStateReason.COOLDOWN.value:
                pending_cooldowns.append(camera)

        session.commit()
        for camera in pending_cooldowns:
            session.refresh(camera)
        return pending_cooldowns


def resume_camera_after_cooldown(
    engine: Engine, camera_id: int, manager: RealtimeManager | None = None
) -> None:
    """Scheduler job fired at a camera's cooldown_until (also reused by the
    periodic sweep for a lost job). Re-reads the camera and recomputes its
    desired state rather than assuming Active — a new incident may have
    opened in the meantime (edge case 1.8), in which case this correctly
    leaves it Paused with reason='incident'.

    `cooldown_until` in SQLite is authoritative; this function is the
    optimization, not the correctness mechanism (05_PKG_incidents_cameras.md
    Step 4) — a job firing early, late, or twice all converge on the same
    answer because recompute_desired_state() re-derives it from current
    facts every time.
    """
    now = datetime.now(UTC)
    with Session(engine) as session:
        camera = session.get(Camera, camera_id)
        if camera is None or not camera.is_active:
            return

        has_open_incident = (
            session.exec(
                select(DetectionLog.log_id).where(
                    col(DetectionLog.camera_id) == camera_id,
                    col(DetectionLog.detection_status).in_(_OPEN_STATUSES),
                )
            ).first()
            is not None
        )
        changed = apply_desired_state(
            camera, has_open_incident=has_open_incident, now=now
        )
        session.add(camera)
        session.commit()

        if changed and manager is not None:
            session.refresh(camera)
            manager.broadcast(camera_status_update_event(camera))


def schedule_pending_cooldowns(
    scheduler: "AsyncIOScheduler",
    engine: Engine,
    cameras: list[Camera],
    manager: RealtimeManager | None = None,
) -> None:
    """Reschedules the resume-from-cooldown job for each camera startup
    reconciliation found still mid-cooldown. Without this, a restart inside
    the dismiss cooldown window would strand the camera Paused forever,
    since the previous cooldown was only an asyncio.create_task whose
    handle nothing kept around.
    """
    from app.core.scheduler import add_job

    for camera in cameras:
        if camera.camera_id is None or camera.cooldown_until is None:
            continue
        add_job(
            scheduler,
            lambda cid=camera.camera_id: resume_camera_after_cooldown(
                engine, cid, manager
            ),
            job_id=f"cooldown:{camera.camera_id}",
            trigger="date",
            run_date=camera.cooldown_until,
        )


def sweep_expired_cooldowns(
    engine: Engine, manager: RealtimeManager | None = None
) -> int:
    """Periodic safety net (every 30s) for cooldown deadlines whose one-shot
    scheduler job was lost — e.g. to a scheduler-level failure rather than a
    process restart, which the P1 lifespan reconciliation already covers.
    Returns the number of cameras swept."""
    now = datetime.now(UTC)
    with Session(engine) as session:
        due_camera_ids = session.exec(
            select(Camera.camera_id).where(
                col(Camera.is_active).is_(True),
                col(Camera.desired_state_reason) == DesiredStateReason.COOLDOWN.value,
                col(Camera.cooldown_until).is_not(None),
                col(Camera.cooldown_until) <= now,
            )
        ).all()

    for camera_id in due_camera_ids:
        resume_camera_after_cooldown(engine, camera_id, manager)
    return len(due_camera_ids)
