import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.api.dependencies import get_realtime_manager, verify_internal_api_key
from app.core.config import settings
from app.core.db import get_session
from app.core.errors import AppHTTPException
from app.core.types import parse_utc_query_datetime
from app.models import Camera, DetectionLog, DetectionStatus
from app.schemas import DetectionLogCreateV2
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

# F9 (be_audit/A3_ai_seam.md) — a clock badly out of sync with the server
# poisons detected_at/last_heartbeat_at math without ever erroring, so this
# is a log-only tripwire, not a validation failure.
_CLOCK_SKEW_WARNING_SECONDS = 10

# F9 / edge case 1.18 (two engine instances) — process-lifetime, last-seen-
# engine tracker. A warning is sufficient: the backend is not the right
# place to arbitrate a lease, and rejecting the second engine could take
# down a legitimate failover. Not thread-safety-hardened on purpose — a
# missed or duplicate warning under a genuine race is an acceptable cost
# for a diagnostic-only signal.
_last_seen_engine: tuple[str, datetime] | None = None


def _check_engine_identity(engine_id: str, now: datetime) -> None:
    global _last_seen_engine
    if _last_seen_engine is not None:
        last_engine_id, last_seen_at = _last_seen_engine
        if (
            last_engine_id != engine_id
            and (now - last_seen_at).total_seconds() < settings.HEARTBEAT_STALE_SECONDS
        ):
            logger.warning(
                "Heartbeat from engine_id=%r arrived while engine_id=%r was "
                "still within the staleness window (edge case 1.18: two "
                "engine instances). Both will receive the full authoritative "
                "snapshot; any duplicate detections are absorbed by "
                "ux_detection_open_camera as 409s. Not rejected.",
                engine_id,
                last_engine_id,
            )
    _last_seen_engine = (engine_id, now)


def _check_clock_skew(engine_id: str, sent_at: datetime, now: datetime) -> None:
    # A naive sent_at is assumed UTC (parse_utc_query_datetime's convention)
    # rather than raising — this is a diagnostic warning, not validation,
    # and must never turn a missing offset into a 500.
    sent_at = parse_utc_query_datetime(sent_at)
    skew_seconds = abs((now - sent_at).total_seconds())
    if skew_seconds > _CLOCK_SKEW_WARNING_SECONDS:
        logger.warning(
            "Heartbeat from engine_id=%r has a %.1fs clock skew from the "
            "server (sent_at=%s, server now=%s) — check the AI engine "
            "host's clock.",
            engine_id,
            skew_seconds,
            sent_at.isoformat(),
            now.isoformat(),
        )


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
    alert_in: DetectionLogCreateV2,
    response: Response,
    session: Session = Depends(get_session),
    manager: RealtimeManager = Depends(get_realtime_manager),
) -> DetectionLog:
    """01_CONTRACTS.md §6.3 — the v2 idempotent AI-engine payload. The v1
    legacy shape (bare `snapshot_path`, no `source_event_id`) was removed by
    the A3 audit pack (be_audit/A3_ai_seam.md, F3): its only caller,
    ai_engine/sync.py, was already gone as of PR #67."""
    camera = session.get(Camera, alert_in.camera_id)
    if not camera or not camera.is_active or not camera.is_enabled:
        raise HTTPException(
            status_code=404,
            detail=f"Camera with ID {alert_in.camera_id} not found, inactive, or disabled.",
        )

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
        existing = session.exec(
            select(DetectionLog).where(DetectionLog.source_event_id == source_event_id)
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

    response.status_code = 201
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
    _check_engine_identity(heartbeat_in.engine_id, now)
    _check_clock_skew(heartbeat_in.engine_id, heartbeat_in.sent_at, now)

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
