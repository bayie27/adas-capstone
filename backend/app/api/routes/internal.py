import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.api.dependencies import get_realtime_manager, verify_internal_api_key
from app.core.config import settings
from app.core.db import get_session
from app.core.errors import AppHTTPException
from app.core.types import parse_legacy_local_datetime, parse_utc_query_datetime
from app.models import AIStatus, Camera, DetectionLog, DetectionStatus
from app.schemas import (
    CameraRead,
    CameraStatusUpdate,
    DetectionLogCreate,
    DetectionLogCreateV2,
)
from app.schemas.internal import (
    HeartbeatCameraSnapshot,
    HeartbeatRequest,
    HeartbeatResponse,
)
from app.services.cameras import ObservedReport, apply_desired_state, apply_observed
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

_OPEN_STATUSES = (DetectionStatus.UNVERIFIED.value, DetectionStatus.ONGOING.value)

_legacy_alert_warned = False


def _warn_legacy_alert_once() -> None:
    """Step 8 — a one-time, process-lifetime warning so the v1-to-v2 cutover
    is visible in the logs without spamming on every legacy detection."""
    global _legacy_alert_warned
    if not _legacy_alert_warned:
        logger.warning(
            "Received a v1 legacy AI alert payload (no source_event_id). "
            "detected_at is interpreted as naive server-local time per "
            "01_CONTRACTS.md §6.1 — do not 'simplify' this to UTC."
        )
        _legacy_alert_warned = True


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
def receive_ai_alert(
    alert_in: DetectionLogCreate | DetectionLogCreateV2,
    response: Response,
    session: Session = Depends(get_session),
    manager: RealtimeManager = Depends(get_realtime_manager),
) -> DetectionLog:
    """Accepts both the v1 legacy payload (01_CONTRACTS.md §6.1, frozen —
    ai_engine/ sends this today) and the v2 idempotent payload (§6.3).
    `alert_in`'s actual type discriminates which one arrived — Pydantic's
    union validation, not dict-sniffing.
    """
    is_v2 = isinstance(alert_in, DetectionLogCreateV2)

    camera = session.get(Camera, alert_in.camera_id)
    if not camera or not camera.is_active or not camera.is_enabled:
        raise HTTPException(
            status_code=404,
            detail=f"Camera with ID {alert_in.camera_id} not found, inactive, or disabled.",
        )

    if is_v2:
        source_event_id = alert_in.source_event_id
        snapshot_key = alert_in.snapshot_key
        detected_at = parse_utc_query_datetime(alert_in.detected_at)
        # Idempotent retry (01_CONTRACTS.md §6.3): a pre-check here is safe
        # (unlike the open-camera check below) because a genuinely
        # concurrent duplicate is still caught by the ux_detection_source_event
        # unique constraint as a backstop.
        existing = session.exec(
            select(DetectionLog).where(DetectionLog.source_event_id == source_event_id)
        ).first()
        if existing is not None:
            response.status_code = 200
            return existing
    else:
        _warn_legacy_alert_once()
        source_event_id = str(uuid.uuid4())
        snapshot_key = alert_in.snapshot_path
        detected_at = parse_legacy_local_datetime(alert_in.detected_at)

    now = datetime.now(UTC)
    db_alert = DetectionLog(
        camera_id=alert_in.camera_id,
        detected_at=detected_at,
        snapshot_key=snapshot_key,
        confidence_score=alert_in.confidence_score,
        source_event_id=source_event_id,
    )
    session.add(db_alert)
    # The self-blindfold: pause this camera the instant the incident is
    # committed. Never pre-checked for an existing open incident — the
    # ux_detection_open_camera partial unique index is what makes this
    # race-proof, not a SELECT before the INSERT.
    apply_desired_state(camera, has_open_incident=True, now=now)
    session.add(camera)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if is_v2:
            existing = session.exec(
                select(DetectionLog).where(
                    DetectionLog.source_event_id == source_event_id
                )
            ).first()
            if existing is not None:
                # A concurrent duplicate committed first — this is the
                # ux_detection_source_event backstop, not the open-camera one.
                response.status_code = 200
                return existing
        open_alert = session.exec(
            select(DetectionLog).where(
                col(DetectionLog.camera_id) == alert_in.camera_id,
                col(DetectionLog.detection_status).in_(_OPEN_STATUSES),
            )
        ).first()
        raise AppHTTPException(
            409,
            f"Camera {alert_in.camera_id} already has an open incident.",
            code="CONFLICT_STATE",
            extra={
                "existing_log_id": open_alert.log_id if open_alert else None,
                "current_status": (open_alert.detection_status if open_alert else None),
            },
        ) from exc

    session.refresh(db_alert)
    session.refresh(camera)

    # Enqueue only after commit (01_CONTRACTS.md §9.4) — a broadcast inside
    # the transaction could announce a row a later rollback undoes.
    manager.broadcast(new_detection_event(db_alert, camera_name=camera.camera_name))
    manager.broadcast(camera_status_update_event(camera))

    response.status_code = 201 if is_v2 else 200
    return db_alert


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
    """v1 legacy poll (01_CONTRACTS.md §6.1) — ai_engine/sync.py polls this
    every 3 seconds and reads `ai_status` to decide whether to pause/resume,
    which is desired-state semantics. This route therefore reports
    `desired_ai_state` under the `ai_status` field name — a deliberate,
    documented divergence from what `ai_status` means everywhere else
    (the true AI-reported observed status). Only `is_enabled AND is_active`
    cameras are returned, so `desired_ai_state` here is never `Inactive`.
    """
    cameras = session.exec(
        select(Camera).where(
            col(Camera.is_enabled).is_(True),
            col(Camera.is_active).is_(True),
        )
    ).all()
    results = []
    for camera in cameras:
        camera_read = CameraRead.model_validate(camera)
        camera_read.ai_status = camera.desired_ai_state
        results.append(camera_read)
    return results


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
