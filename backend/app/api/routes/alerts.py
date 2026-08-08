import asyncio
import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, func, or_, select

from app.api.dependencies import get_current_user
from app.core.db import get_session
from app.models import AIStatus, Camera, DetectionLog, DetectionStatus, User
from app.schemas import DetectionLogListResponse, DetectionLogRead
from app.services.filters import validate_common_filters
from app.services.formatting import format_user_name
from app.ws_manager import manager

router = APIRouter(
    prefix="/api/alerts",
    tags=["Alerts & Accident Management"],
    dependencies=[Depends(get_current_user)],
)


def _to_detection_log_read(log: DetectionLog) -> DetectionLogRead:
    log_read = DetectionLogRead.model_validate(log)
    log_read.camera_name = log.camera.camera_name if log.camera else None
    log_read.verified_by_name = format_user_name(log.verified_by)
    log_read.closed_by_name = format_user_name(log.closed_by)
    return log_read


async def _broadcast_camera_status(camera: Camera) -> None:
    """Broadcast a CAMERA_STATUS_UPDATE payload to all connected FE clients."""
    await manager.broadcast_alert(
        {
            "type": "CAMERA_STATUS_UPDATE",
            "camera_id": camera.camera_id,
            "connection_status": camera.connection_status,
            "ai_status": camera.ai_status,
        }
    )


async def _resume_camera_after_cooldown(camera_id: int) -> None:
    """
    Background task: wait 60 seconds then set ai_status = Active in DB
    and broadcast the update to FE. Used for the Unverified → Dismissed
    false-positive cooldown.
    """
    await asyncio.sleep(60)

    # Import here to avoid circular imports at module level

    # We need a fresh DB session since this runs outside the request lifecycle
    from sqlmodel import Session as SyncSession

    from app.core.db import engine

    with SyncSession(engine) as session:
        camera = session.get(Camera, camera_id)
        if camera and camera.is_active and camera.is_enabled:
            camera.ai_status = AIStatus.ACTIVE.value
            session.add(camera)
            session.commit()
            session.refresh(camera)

            await _broadcast_camera_status(camera)


def _apply_alert_filters(
    query,
    *,
    search: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    status_values: list[DetectionStatus] | None,
    camera_ids: list[int] | None,
    user_ids: list[int] | None,
):
    if search:
        query = query.join(Camera)
        if search.isdigit():
            query = query.where(
                or_(
                    DetectionLog.log_id == int(search),
                    col(Camera.camera_name).icontains(search),
                )
            )
        else:
            query = query.where(col(Camera.camera_name).icontains(search))

    if start_date:
        query = query.where(col(DetectionLog.detected_at) >= start_date)
    if end_date:
        query = query.where(col(DetectionLog.detected_at) <= end_date)
    if status_values:
        query = query.where(
            col(DetectionLog.detection_status).in_(
                [status.value for status in status_values]
            )
        )
    if camera_ids:
        query = query.where(col(DetectionLog.camera_id).in_(camera_ids))
    if user_ids:
        query = query.where(
            or_(
                col(DetectionLog.verified_by_id).in_(user_ids),
                col(DetectionLog.closed_by_id).in_(user_ids),
            )
        )

    return query


@router.get("/", response_model=DetectionLogListResponse)
def get_alerts(
    start_date: datetime | None = Query(
        default=None, description="ISO 8601 format, e.g. 2026-01-01T00:00:00Z"
    ),
    end_date: datetime | None = Query(
        default=None, description="ISO 8601 format, e.g. 2026-12-31T23:59:59Z"
    ),
    status: list[DetectionStatus] | None = Query(
        default=None,
        description="Filter by status with repeated params, e.g. ?status=Unverified&status=Ongoing",
    ),
    camera_id: list[int] | None = Query(
        default=None,
        description="Filter by one or more camera IDs with repeated params, e.g. ?camera_id=1&camera_id=2",
    ),
    user_id: list[int] | None = Query(
        default=None,
        description=(
            "Filter by one or more operator IDs (verified_by OR closed_by) with repeated params, "
            "e.g. ?user_id=4&user_id=5"
        ),
    ),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    """Fetches paginated incident logs with robust multi-select filtering."""
    validate_common_filters(
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_id,
        user_ids=user_id,
    )

    query = select(DetectionLog).options(
        selectinload(DetectionLog.camera),
        selectinload(DetectionLog.verified_by),
        selectinload(DetectionLog.closed_by),
    )
    query = _apply_alert_filters(
        query,
        search=search,
        start_date=start_date,
        end_date=end_date,
        status_values=status,
        camera_ids=camera_id,
        user_ids=user_id,
    )
    query = query.order_by(col(DetectionLog.detected_at).desc())

    total_filtered = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()
    logs = session.exec(query.offset(offset).limit(limit)).all()

    logs_with_names = [_to_detection_log_read(log) for log in logs]

    return DetectionLogListResponse(
        total_filtered=total_filtered,
        logs=logs_with_names,
    )


@router.get("/export")
def export_alerts_csv(
    request: Request,
    start_date: datetime | None = Query(
        default=None, description="ISO 8601 format, e.g. 2026-01-01T00:00:00Z"
    ),
    end_date: datetime | None = Query(
        default=None, description="ISO 8601 format, e.g. 2026-12-31T23:59:59Z"
    ),
    status: list[DetectionStatus] | None = Query(default=None),
    camera_id: list[int] | None = Query(default=None),
    user_id: list[int] | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    session: Session = Depends(get_session),
):
    """Exports the filtered logs directly to a downloadable CSV file."""
    validate_common_filters(
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_id,
        user_ids=user_id,
    )

    query = select(DetectionLog).options(
        selectinload(DetectionLog.camera),
        selectinload(DetectionLog.verified_by),
        selectinload(DetectionLog.closed_by),
    )
    query = _apply_alert_filters(
        query,
        search=search,
        start_date=start_date,
        end_date=end_date,
        status_values=status,
        camera_ids=camera_id,
        user_ids=user_id,
    )
    query = query.order_by(col(DetectionLog.detected_at).desc())
    logs = session.exec(query).all()

    base_url = str(request.base_url).rstrip("/")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Log ID",
            "Detected At",
            "Camera ID",
            "Camera Name",
            "Status",
            "Confidence",
            "Snapshot URL",
            "Verified By ID",
            "Verified By Name",
            "Verified At",
            "Closed By ID",
            "Closed By Name",
            "Closed At",
        ]
    )

    for log in logs:
        snapshot_url = f"{base_url}/snapshots/{log.snapshot_path}"
        writer.writerow(
            [
                log.log_id,
                log.detected_at.isoformat(),
                log.camera_id,
                log.camera.camera_name if log.camera else "N/A",
                log.detection_status,
                f"{log.confidence_score * 100:.1f}%",
                snapshot_url,
                log.verified_by_id or "N/A",
                format_user_name(log.verified_by) or "N/A",
                log.verified_at.isoformat() if log.verified_at else "N/A",
                log.closed_by_id or "N/A",
                format_user_name(log.closed_by) or "N/A",
                log.closed_at.isoformat() if log.closed_at else "N/A",
            ]
        )

    response = Response(content=output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = (
        "attachment; filename=adas_incident_export.csv"
    )
    return response


@router.get("/{log_id}", response_model=DetectionLogRead)
def get_alert_details(log_id: int, session: Session = Depends(get_session)):
    """Retrieves the complete, detailed record when an operator clicks for full details."""
    log = session.exec(
        select(DetectionLog)
        .where(DetectionLog.log_id == log_id)
        .options(
            selectinload(DetectionLog.camera),
            selectinload(DetectionLog.verified_by),
            selectinload(DetectionLog.closed_by),
        )
    ).first()
    if not log:
        raise HTTPException(status_code=404, detail="Incident log not found")
    return _to_detection_log_read(log)


# ---------------------------------------------------------
# HITL STATE MACHINE TRANSITIONS
# ---------------------------------------------------------


@router.post("/{log_id}/confirm", response_model=DetectionLogRead)
async def confirm_alert(
    log_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Operator confirms an incident as a true positive.
    Camera is already Paused in DB from when the alert arrived (/api/internal/alert).
    This just transitions the detection log to Ongoing.
    """
    log = session.get(DetectionLog, log_id)
    if not log or log.detection_status != DetectionStatus.UNVERIFIED:
        raise HTTPException(
            status_code=400, detail="Only 'Unverified' alerts can be confirmed."
        )

    log.detection_status = DetectionStatus.ONGOING
    log.verified_by_id = current_user.user_id
    log.verified_by = current_user
    log.verified_at = datetime.now(UTC)

    session.add(log)
    session.commit()
    session.refresh(log)

    await manager.broadcast_alert(
        {
            "type": "ALERT_STATUS_UPDATE",
            "log_id": log.log_id,
            "detection_status": getattr(
                log.detection_status, "value", log.detection_status
            ),
        }
    )

    return _to_detection_log_read(log)


@router.post("/{log_id}/dismiss", response_model=DetectionLogRead)
async def dismiss_alert(
    log_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Operator dismisses an alert as a false positive (Unverified) or corrects
    a human error on a confirmed incident (Ongoing).

    - Unverified → Dismissed: camera gets a 60-second cooldown before resuming.
    - Ongoing → Dismissed: camera resumes immediately (human error correction).
    """
    log = session.get(DetectionLog, log_id)
    if not log or log.detection_status not in (
        DetectionStatus.UNVERIFIED,
        DetectionStatus.ONGOING,
    ):
        raise HTTPException(
            status_code=400,
            detail="Only 'Unverified' or 'Ongoing' alerts can be dismissed.",
        )

    was_unverified = log.detection_status == DetectionStatus.UNVERIFIED

    log.detection_status = DetectionStatus.DISMISSED
    log.closed_by_id = current_user.user_id
    log.closed_by = current_user
    log.closed_at = datetime.now(UTC)

    session.add(log)

    camera = session.get(Camera, log.camera_id)

    if was_unverified:
        # False positive: keep camera Paused during the 60s cooldown window.
        # The background task will set it back to Active after the cooldown.
        # Camera is already Paused from when the alert arrived; no DB change needed here.
        session.commit()
        session.refresh(log)

        if camera and camera.is_active and camera.is_enabled and camera.camera_id:
            asyncio.create_task(_resume_camera_after_cooldown(camera.camera_id))

    else:
        # Human error correction on an Ongoing incident: resume immediately.
        if camera and camera.is_active and camera.is_enabled:
            camera.ai_status = AIStatus.ACTIVE.value
            session.add(camera)

        session.commit()
        session.refresh(log)

        if camera and camera.is_active and camera.is_enabled:
            session.refresh(camera)
            await _broadcast_camera_status(camera)

    await manager.broadcast_alert(
        {
            "type": "ALERT_STATUS_UPDATE",
            "log_id": log.log_id,
            "detection_status": getattr(
                log.detection_status, "value", log.detection_status
            ),
        }
    )

    return _to_detection_log_read(log)


@router.post("/{log_id}/resolve", response_model=DetectionLogRead)
async def resolve_alert(
    log_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Operator marks the scene as cleared. Camera resumes AI detection immediately.
    """
    log = session.get(DetectionLog, log_id)
    if not log or log.detection_status != DetectionStatus.ONGOING:
        raise HTTPException(
            status_code=400, detail="Only 'Ongoing' alerts can be resolved."
        )

    log.detection_status = DetectionStatus.RESOLVED
    log.closed_by_id = current_user.user_id
    log.closed_by = current_user
    log.closed_at = datetime.now(UTC)

    session.add(log)

    camera = session.get(Camera, log.camera_id)
    if camera and camera.is_active and camera.is_enabled:
        camera.ai_status = AIStatus.ACTIVE.value
        session.add(camera)

    session.commit()
    session.refresh(log)

    if camera and camera.is_active and camera.is_enabled:
        session.refresh(camera)
        await _broadcast_camera_status(camera)

    await manager.broadcast_alert(
        {
            "type": "ALERT_STATUS_UPDATE",
            "log_id": log.log_id,
            "detection_status": getattr(
                log.detection_status, "value", log.detection_status
            ),
        }
    )

    return _to_detection_log_read(log)
