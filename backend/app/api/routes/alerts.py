import csv
import io
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, func, or_, select

from app.api.dependencies import get_current_user, get_realtime_manager, get_scheduler
from app.core.config import settings
from app.core.db import get_session
from app.core.errors import AppHTTPException
from app.models import AuditResult, Camera, DetectionLog, DetectionStatus, User
from app.schemas import AlertSnoozeRequest, DetectionLogListResponse, DetectionLogRead
from app.services import audit
from app.services.cameras import apply_desired_state, schedule_pending_cooldowns
from app.services.events import (
    alert_status_update_event,
    camera_status_update_event,
    snooze_activated_event,
)
from app.services.filters import validate_common_filters
from app.services.formatting import format_user_name
from app.services.incidents import (
    ConflictState,
    IncidentNotFound,
    PreconditionFailed,
    dismiss_transition,
    transition,
)
from app.services.realtime import RealtimeManager
from app.services.snoozes import schedule_snooze_job, snooze_incident

router = APIRouter(
    prefix="/api/alerts",
    tags=["Alerts & Accident Management"],
    dependencies=[Depends(get_current_user)],
)

# Module-level singleton (ruff B008 — a Depends() default must not call a
# function inline): the empty-body default for the snooze route below.
_EMPTY_SNOOZE_REQUEST = AlertSnoozeRequest()


def _to_detection_log_read(log: DetectionLog) -> DetectionLogRead:
    log_read = DetectionLogRead.model_validate(log)
    log_read.camera_name = log.camera.camera_name if log.camera else None
    log_read.verified_by_name = format_user_name(log.verified_by)
    log_read.closed_by_name = format_user_name(log.closed_by)
    return log_read


def _conflict_response(exc: ConflictState) -> AppHTTPException:
    """01_CONTRACTS.md §5.3 — the exact 409 body the frontend's
    already-handled modal depends on."""
    return AppHTTPException(
        409,
        "This incident was already handled by another operator.",
        code="CONFLICT_STATE",
        extra={
            "current_status": exc.current_status,
            "handled_action": exc.handled_action,
            "handled_by": exc.handled_by,
            "handled_at": exc.handled_at.isoformat() if exc.handled_at else None,
        },
    )


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


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
    """Fetches paginated incident logs with robust multi-select filtering.

    01_CONTRACTS.md §9.5 recovery sequence: after every WebSocket (re)connect,
    the client fetches `?status=Unverified&status=Ongoing` to rebuild alarm
    state, including `snoozed_until`/`snoozed_by_id` (columns exist from P1;
    P4 populates them). `updated_at` is the merge key — an event carrying an
    older `updated_at` than what the client already has for that `log_id`
    must not overwrite the newer state.
    """
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
        snapshot_url = f"{base_url}/snapshots/{log.snapshot_key}"
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
def confirm_alert(
    log_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    manager: RealtimeManager = Depends(get_realtime_manager),
):
    """Operator confirms an incident as a true positive. The camera's desired
    state is unchanged (§10.2: "Confirm | Paused (unchanged) | incident |
    —") — it was already Paused/incident when the alert arrived."""
    try:
        result = transition(
            session,
            log_id=log_id,
            expected=DetectionStatus.UNVERIFIED,
            new=DetectionStatus.ONGOING,
            actor=current_user,
        )
    except IncidentNotFound as exc:
        raise HTTPException(status_code=404, detail="Incident log not found") from exc
    except ConflictState as exc:
        raise _conflict_response(exc) from exc

    log = result.log
    audit.record(
        session,
        action=result.action.value,
        result=AuditResult.SUCCESS,
        actor=current_user,
        target_type="incident",
        target_ref=str(log_id),
        detail={"camera_id": log.camera_id},
        source_ip=_client_ip(request),
    )
    session.commit()
    session.refresh(log)

    # Enqueue only after commit (01_CONTRACTS.md §9.4).
    manager.broadcast(
        alert_status_update_event(
            log,
            action=result.action.value,
            camera_name=log.camera.camera_name if log.camera else None,
        )
    )

    return _to_detection_log_read(log)


@router.post("/{log_id}/dismiss", response_model=DetectionLogRead)
def dismiss_alert(
    log_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    manager: RealtimeManager = Depends(get_realtime_manager),
    scheduler=Depends(get_scheduler),
):
    """Operator dismisses an alert as a false positive (Unverified) or
    corrects a human error on a confirmed incident (Ongoing).

    - Unverified -> Dismissed: camera gets a 60-second cooldown before
      resuming (D-002/D-004), enforced entirely backend-side.
    - Ongoing -> Dismissed: camera resumes immediately (human correction).
    """
    now = datetime.now(UTC)
    try:
        result = dismiss_transition(session, log_id=log_id, actor=current_user, now=now)
    except IncidentNotFound as exc:
        raise HTTPException(status_code=404, detail="Incident log not found") from exc
    except ConflictState as exc:
        raise _conflict_response(exc) from exc

    log = result.log
    was_unverified = result.expected == DetectionStatus.UNVERIFIED

    camera = session.get(Camera, log.camera_id)
    camera_changed = False
    if camera is not None:
        if was_unverified:
            camera.cooldown_until = now + timedelta(
                seconds=settings.DISMISS_COOLDOWN_SECONDS
            )
        camera_changed = apply_desired_state(camera, has_open_incident=False, now=now)
        session.add(camera)

    audit.record(
        session,
        action=result.action.value,
        result=AuditResult.SUCCESS,
        actor=current_user,
        target_type="incident",
        target_ref=str(log_id),
        detail={"camera_id": log.camera_id},
        source_ip=_client_ip(request),
    )
    session.commit()
    session.refresh(log)
    if camera is not None:
        session.refresh(camera)

    # Broadcast ordering is a contract (05_PKG_incidents_cameras.md Step 3):
    # from Unverified the alert event leads (the cooldown is a side effect
    # of it); from Ongoing the camera resuming leads.
    camera_name = camera.camera_name if camera is not None else None
    if was_unverified:
        manager.broadcast(
            alert_status_update_event(
                log, action=result.action.value, camera_name=camera_name
            )
        )
        if camera_changed and camera is not None:
            manager.broadcast(camera_status_update_event(camera))
        if (
            scheduler is not None
            and camera is not None
            and camera.cooldown_until is not None
        ):
            schedule_pending_cooldowns(scheduler, session.get_bind(), [camera], manager)
    else:
        if camera_changed and camera is not None:
            manager.broadcast(camera_status_update_event(camera))
        manager.broadcast(
            alert_status_update_event(
                log, action=result.action.value, camera_name=camera_name
            )
        )

    return _to_detection_log_read(log)


@router.post("/{log_id}/resolve", response_model=DetectionLogRead)
def resolve_alert(
    log_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    manager: RealtimeManager = Depends(get_realtime_manager),
):
    """Operator marks the scene as cleared. Camera resumes AI detection
    immediately (§10.2)."""
    now = datetime.now(UTC)
    try:
        result = transition(
            session,
            log_id=log_id,
            expected=DetectionStatus.ONGOING,
            new=DetectionStatus.RESOLVED,
            actor=current_user,
            now=now,
        )
    except IncidentNotFound as exc:
        raise HTTPException(status_code=404, detail="Incident log not found") from exc
    except ConflictState as exc:
        raise _conflict_response(exc) from exc

    log = result.log
    camera = session.get(Camera, log.camera_id)
    camera_changed = False
    if camera is not None:
        camera_changed = apply_desired_state(camera, has_open_incident=False, now=now)
        session.add(camera)

    audit.record(
        session,
        action=result.action.value,
        result=AuditResult.SUCCESS,
        actor=current_user,
        target_type="incident",
        target_ref=str(log_id),
        detail={"camera_id": log.camera_id},
        source_ip=_client_ip(request),
    )
    session.commit()
    session.refresh(log)
    if camera is not None:
        session.refresh(camera)

    if camera_changed and camera is not None:
        manager.broadcast(camera_status_update_event(camera))
    manager.broadcast(
        alert_status_update_event(
            log,
            action=result.action.value,
            camera_name=camera.camera_name if camera is not None else None,
        )
    )

    return _to_detection_log_read(log)


@router.post("/{log_id}/snooze", response_model=DetectionLogRead)
def snooze_alert(
    log_id: int,
    request: Request,
    snooze_in: AlertSnoozeRequest = _EMPTY_SNOOZE_REQUEST,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    manager: RealtimeManager = Depends(get_realtime_manager),
    scheduler=Depends(get_scheduler),
):
    """FR-07/FR-08 — mutes an `Unverified` incident for the actor's saved
    duration (01_CONTRACTS.md §11, D-004). Shared state: every dashboard
    mutes it until the same deadline. `snooze_in` only exists so a
    client-supplied duration is rejected with a 422 rather than ignored."""
    del snooze_in
    try:
        log = snooze_incident(session, log_id=log_id, actor=current_user)
    except IncidentNotFound as exc:
        raise HTTPException(status_code=404, detail="Incident log not found") from exc
    except PreconditionFailed as exc:
        raise AppHTTPException(400, exc.detail, code="PRECONDITION_FAILED") from exc
    except ConflictState as exc:
        raise _conflict_response(exc) from exc

    audit.record(
        session,
        action="ALERT_SNOOZE",
        result=AuditResult.SUCCESS,
        actor=current_user,
        target_type="incident",
        target_ref=str(log_id),
        detail={"snoozed_until": log.snoozed_until.isoformat()},
        source_ip=_client_ip(request),
    )
    session.commit()
    session.refresh(log)

    manager.broadcast(snooze_activated_event(log))
    if scheduler is not None:
        schedule_snooze_job(scheduler, session.get_bind(), log, manager)

    return _to_detection_log_read(log)
