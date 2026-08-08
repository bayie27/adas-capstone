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

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.models import (
    Camera,
    DesiredAIState,
    DesiredStateReason,
    DetectionLog,
    DetectionStatus,
)

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

_OPEN_STATUSES = (DetectionStatus.UNVERIFIED.value, DetectionStatus.ONGOING.value)


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


def reconcile_camera_desired_states(engine: Engine) -> list[Camera]:
    """Startup reconciliation (P1 Step 9). Recomputes desired state for
    every soft-deleted-excluded camera — never resets it blindly, unlike
    observed state, which genuinely has no reporter until the AI engine
    reconnects.

    Returns the cameras left Paused with reason='cooldown' so the caller
    can reschedule their resume jobs.
    """
    now = datetime.now(UTC)
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


def resume_camera_after_cooldown(engine: Engine, camera_id: int) -> None:
    """Scheduler job fired at a camera's cooldown_until. Re-reads the camera
    and recomputes its desired state rather than assuming Active — a new
    incident may have opened in the meantime (edge case 1.8), in which case
    this correctly leaves it Paused with reason='incident'.
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
        recompute_desired_state(camera, has_open_incident=has_open_incident, now=now)
        session.add(camera)
        session.commit()


def schedule_pending_cooldowns(
    scheduler: "AsyncIOScheduler", engine: Engine, cameras: list[Camera]
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
            lambda cid=camera.camera_id: resume_camera_after_cooldown(engine, cid),
            job_id=f"cooldown:{camera.camera_id}",
            trigger="date",
            run_date=camera.cooldown_until,
        )
