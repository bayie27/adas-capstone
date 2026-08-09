import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from app.api.dependencies import get_realtime_manager, verify_internal_api_key
from app.core.config import settings
from app.core.db import get_session
from app.core.types import parse_utc_query_datetime
from app.models import AIStatus, Camera, DetectionLog, DetectionStatus
from app.schemas import CameraRead, CameraStatusUpdate, DetectionLogCreate
from app.schemas.internal import (
    HeartbeatCameraSnapshot,
    HeartbeatRequest,
    HeartbeatResponse,
)
from app.services.cameras import ObservedReport, apply_observed
from app.services.events import camera_status_update_event, new_detection_event
from app.services.realtime import RealtimeManager

logger = logging.getLogger("uvicorn.error")

router = APIRouter(
    prefix="/api/internal",
    tags=["Internal AI System"],
    dependencies=[Depends(verify_internal_api_key)],
)

# D-003: fixed protocol cadence, not an operator-tunable setting.
_HEARTBEAT_INTERVAL_SECONDS = 3


def _build_rtsp_url(channel_id: int) -> str:
    """01_CONTRACTS.md §7.2 — backend-owned RTSP construction. Credential-
    bearing in production; never logged (see app.core.redaction, which
    already strips any `scheme://user:pass@host` URL generically)."""
    return settings.RTSP_URL_TEMPLATE.format(
        channel_id=channel_id,
        dss_ip=settings.DSS_IP,
        dss_port=settings.DSS_PORT,
        dss_username=settings.DSS_USERNAME,
        dss_password=(
            settings.DSS_PASS.get_secret_value() if settings.DSS_PASS else None
        ),
    )


@router.post("/alert", response_model=DetectionLog)
async def receive_ai_alert(
    alert_in: DetectionLogCreate,
    session: Session = Depends(get_session),
    manager: RealtimeManager = Depends(get_realtime_manager),
) -> DetectionLog:
    try:
        camera = session.get(Camera, alert_in.camera_id)
        if not camera or not camera.is_active or not camera.is_enabled:
            raise HTTPException(
                status_code=404,
                detail=f"Camera with ID {alert_in.camera_id} not found, inactive, or disabled.",
            )

        # Immediately mark camera as Paused in DB so FE reflects the self-blindfold
        camera.ai_status = AIStatus.PAUSED.value
        session.add(camera)

        # v1 legacy payload — 01_CONTRACTS.md §6.1. No source_event_id is
        # supplied, so the backend generates one; `snapshot_path` (the wire
        # field) becomes `snapshot_key` (the DB column). The AI engine
        # currently sends naive local time — assumed UTC, same policy as
        # query-parameter datetimes (§1.1), so the raw wall-clock value
        # written to the DB is unchanged from today, just now tz-aware.
        db_alert = DetectionLog(
            camera_id=alert_in.camera_id,
            detected_at=parse_utc_query_datetime(alert_in.detected_at),
            snapshot_key=alert_in.snapshot_path,
            confidence_score=alert_in.confidence_score,
            source_event_id=str(uuid.uuid4()),
        )
        session.add(db_alert)
        session.commit()
        session.refresh(db_alert)
        session.refresh(camera)

        # Enqueue only after commit (01_CONTRACTS.md §9.4) — a broadcast
        # inside the transaction could announce a row a later rollback
        # undoes.
        manager.broadcast(new_detection_event(db_alert, camera_name=camera.camera_name))
        manager.broadcast(camera_status_update_event(camera))

        return db_alert

    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        logger.exception("Failed to process AI alert")
        raise HTTPException(status_code=500, detail="Failed to process alert.") from exc


@router.post("/heartbeat", response_model=HeartbeatResponse)
def receive_heartbeat(
    heartbeat_in: HeartbeatRequest,
    session: Session = Depends(get_session),
    manager: RealtimeManager = Depends(get_realtime_manager),
) -> HeartbeatResponse:
    """01_CONTRACTS.md §6.2 (v2, P4, new). Processes the engine's observed
    report through apply_observed(), then returns a complete authoritative
    snapshot of every active camera's desired state — a change list would
    make recovery after either side restarts nondeterministic (D-003)."""
    now = datetime.now(UTC)

    reported_ids = [report.camera_id for report in heartbeat_in.cameras]
    cameras_by_id: dict[int, Camera] = {}
    if reported_ids:
        rows = session.exec(
            select(Camera).where(col(Camera.camera_id).in_(reported_ids))
        ).all()
        cameras_by_id = {camera.camera_id: camera for camera in rows}

    changed_cameras: list[Camera] = []
    for report in heartbeat_in.cameras:
        camera = cameras_by_id.get(report.camera_id)
        if camera is None:
            # Unknown camera_id: ignore it, not an error — the engine will
            # drop it once it applies the next snapshot.
            continue
        observed = ObservedReport(
            connection_status=report.connection_status.value,
            ai_status=report.ai_status.value,
            applied_config_version=report.applied_config_version,
            measured_fps=report.measured_fps,
            inference_latency_ms=report.inference_latency_ms,
            error_code=report.error_code,
            error_message=report.error_message,
        )
        if apply_observed(camera, observed, now=now):
            changed_cameras.append(camera)
        session.add(camera)

    session.commit()
    for camera in changed_cameras:
        session.refresh(camera)

    active_cameras = session.exec(
        select(Camera).where(col(Camera.is_active).is_(True))
    ).all()
    snapshot = [
        HeartbeatCameraSnapshot(
            camera_id=camera.camera_id,
            channel_id=camera.channel_id,
            camera_name=camera.camera_name,
            rtsp_url=_build_rtsp_url(camera.channel_id),
            is_enabled=camera.is_enabled,
            desired_ai_state=camera.desired_ai_state,
            desired_state_reason=camera.desired_state_reason,
            cooldown_until=camera.cooldown_until,
            config_version=camera.config_version,
        )
        for camera in active_cameras
    ]

    # Enqueue only after commit (01_CONTRACTS.md §9.4) — broadcast only
    # cameras whose observed state meaningfully changed, or dozens of
    # cameras heartbeating every 3 seconds would flood every dashboard.
    for camera in changed_cameras:
        manager.broadcast(camera_status_update_event(camera))

    return HeartbeatResponse(
        server_time=now,
        heartbeat_interval_seconds=_HEARTBEAT_INTERVAL_SECONDS,
        cameras=snapshot,
    )


@router.get("/cameras", response_model=list[CameraRead])
def get_enabled_cameras(session: Session = Depends(get_session)) -> list[CameraRead]:
    """
    AI engine polls this every 3 seconds to get the list of cameras it should
    be monitoring. Returns all is_enabled=True, is_active=True cameras with
    their current statuses so the engine can reconcile its state on restart.
    """
    cameras = session.exec(
        select(Camera).where(
            col(Camera.is_enabled).is_(True),
            col(Camera.is_active).is_(True),
        )
    ).all()
    return [CameraRead.model_validate(c) for c in cameras]


@router.patch("/cameras/{camera_id}/status", response_model=CameraRead)
async def update_camera_status(
    camera_id: int,
    status_update: CameraStatusUpdate,
    session: Session = Depends(get_session),
    manager: RealtimeManager = Depends(get_realtime_manager),
) -> CameraRead:
    """
    AI engine calls this to report connection and/or AI status changes.
    Updates DB and broadcasts to all connected FE clients.
    """
    camera = session.get(Camera, camera_id)
    if not camera or not camera.is_active or not camera.is_enabled:
        raise HTTPException(
            status_code=404,
            detail=f"Camera with ID {camera_id} not found, inactive, or disabled.",
        )

    # Guard against the AI engine overruling an operator-driven pause.
    # If the camera has an open (Unverified or Ongoing) alert, reject any attempt
    # to set ai_status=Active — the HITL state machine owns that transition.
    if status_update.ai_status == AIStatus.ACTIVE:
        open_alert = session.exec(
            select(DetectionLog).where(
                col(DetectionLog.camera_id) == camera_id,
                col(DetectionLog.detection_status).in_(
                    [
                        DetectionStatus.UNVERIFIED.value,
                        DetectionStatus.ONGOING.value,
                    ]
                ),
            )
        ).first()
        if open_alert:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Camera {camera_id} has an open alert (log_id={open_alert.log_id}, "
                    f"status={open_alert.detection_status}). "
                    "ai_status cannot be set to Active while a HITL resolution is pending."
                ),
            )

    if status_update.connection_status is not None:
        camera.connection_status = status_update.connection_status.value
    if status_update.ai_status is not None:
        camera.ai_status = status_update.ai_status.value

    session.add(camera)
    session.commit()
    session.refresh(camera)

    manager.broadcast(camera_status_update_event(camera))

    return CameraRead.model_validate(camera)
