from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, func, select

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
from app.services.filters import (
    IncidentFilters,
    apply_incident_filters,
    apply_sort,
    validate_common_filters,
)
from app.services.formatting import format_user_name
from app.services.incidents import (
    ConflictState,
    IncidentNotFound,
    PreconditionFailed,
    dismiss_transition,
    transition,
)
from app.services.realtime import RealtimeManager
from app.services.reports.common import check_row_limit, record_export_attempt
from app.services.reports.csv_writer import csv_response
from app.services.reports.pdf_writer import build_incident_pdf
from app.services.snapshots import resolve as resolve_snapshot
from app.services.snoozes import schedule_snooze_job, snooze_incident

router = APIRouter(
    prefix="/api/alerts",
    tags=["Alerts & Accident Management"],
    dependencies=[Depends(get_current_user)],
)

# 01_CONTRACTS.md §1.5 — the allowlisted `sort_by` fields for incident
# list/export routes. `log_id` is the tie-breaker so equal-`detected_at`
# rows (e.g. a seeded batch) never shuffle between pages.
ALERT_SORT_FIELDS = {
    "log_id",
    "detected_at",
    "confidence_score",
    "detection_status",
    "camera_id",
    "verified_at",
    "closed_at",
    "created_at",
    "updated_at",
}

# Module-level singleton (ruff B008 — a Depends() default must not call a
# function inline): the empty-body default for the snooze route below.
_EMPTY_SNOOZE_REQUEST = AlertSnoozeRequest()


def _to_detection_log_read(log: DetectionLog) -> DetectionLogRead:
    return DetectionLogRead(
        log_id=log.log_id,
        source_event_id=log.source_event_id,
        camera_id=log.camera_id,
        camera_name=log.camera.camera_name if log.camera else None,
        detected_at=log.detected_at,
        confidence_score=log.confidence_score,
        detection_status=log.detection_status,
        snapshot_url=f"/api/alerts/{log.log_id}/snapshot",
        verified_by_id=log.verified_by_id,
        verified_by_name=format_user_name(log.verified_by),
        verified_at=log.verified_at,
        closed_by_id=log.closed_by_id,
        closed_by_name=format_user_name(log.closed_by),
        closed_at=log.closed_at,
        snoozed_at=log.snoozed_at,
        snoozed_until=log.snoozed_until,
        snoozed_by_id=log.snoozed_by_id,
        created_at=log.created_at,
        updated_at=log.updated_at,
    )


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


def _incident_filters_from_query(
    *,
    start_date: datetime | None,
    end_date: datetime | None,
    status: list[DetectionStatus] | None,
    camera_id: list[int] | None,
    user_id: list[int] | None,
    search: str | None,
) -> IncidentFilters:
    return IncidentFilters(
        start_date=start_date,
        end_date=end_date,
        statuses=tuple(status or ()),
        camera_ids=tuple(camera_id or ()),
        user_ids=tuple(user_id or ()),
        search=search,
    )


def _filters_as_dict(f: IncidentFilters) -> dict:
    return {
        "start_date": f.start_date.isoformat() if f.start_date else None,
        "end_date": f.end_date.isoformat() if f.end_date else None,
        "status": [s.value for s in f.statuses],
        "camera_id": list(f.camera_ids),
        "user_id": list(f.user_ids),
        "search": f.search,
    }


def _filters_summary(f: IncidentFilters, *, sort_by: str, sort_order: str) -> list[str]:
    lines = []
    if f.start_date or f.end_date:
        lines.append(
            f"Date range: {f.start_date.isoformat() if f.start_date else '…'} "
            f"to {f.end_date.isoformat() if f.end_date else '…'}"
        )
    if f.statuses:
        lines.append("Status: " + ", ".join(s.value for s in f.statuses))
    if f.camera_ids:
        lines.append("Camera IDs: " + ", ".join(str(c) for c in f.camera_ids))
    if f.user_ids:
        lines.append("User IDs: " + ", ".join(str(u) for u in f.user_ids))
    if f.search:
        lines.append(f"Search: {f.search!r}")
    lines.append(f"Sort: {sort_by} {sort_order}")
    return lines


def _incident_csv_row(log: DetectionLog) -> list:
    return [
        log.log_id,
        log.detected_at.isoformat(),
        log.camera_id,
        log.camera.camera_name if log.camera else None,
        log.detection_status,
        log.confidence_score,
        f"/api/alerts/{log.log_id}/snapshot",
        log.verified_by_id,
        format_user_name(log.verified_by),
        log.verified_at.isoformat() if log.verified_at else None,
        log.closed_by_id,
        format_user_name(log.closed_by),
        log.closed_at.isoformat() if log.closed_at else None,
    ]


INCIDENT_CSV_COLUMNS = [
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


def _incident_pdf_row(log: DetectionLog) -> list:
    return [
        log.log_id,
        log.detected_at.isoformat(),
        log.camera.camera_name if log.camera else None,
        log.detection_status,
        log.confidence_score,
        format_user_name(log.verified_by),
        log.verified_at.isoformat() if log.verified_at else None,
        format_user_name(log.closed_by),
        log.closed_at.isoformat() if log.closed_at else None,
    ]


def _incident_query_stmt(filters: IncidentFilters):
    stmt = select(DetectionLog).options(
        selectinload(DetectionLog.camera),
        selectinload(DetectionLog.verified_by),
        selectinload(DetectionLog.closed_by),
    )
    return apply_incident_filters(stmt, filters)


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
    sort_by: str = Query(default="detected_at"),
    sort_order: str = Query(default="desc"),
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
    filters = _incident_filters_from_query(
        start_date=start_date,
        end_date=end_date,
        status=status,
        camera_id=camera_id,
        user_id=user_id,
        search=search,
    )

    query = _incident_query_stmt(filters)
    query = apply_sort(
        query,
        DetectionLog,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed=ALERT_SORT_FIELDS,
        tie_breaker="log_id",
    )

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
def export_alerts(
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
    sort_by: str = Query(default="detected_at"),
    sort_order: str = Query(default="desc"),
    format: str = Query(default="csv", pattern="^(csv|pdf)$"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Exports the filtered incident logs as CSV or PDF (`?format=csv|pdf`,
    default `csv`) — the same filter/sort builders as `GET /api/alerts/`,
    so an export always matches the screen exactly (D-010)."""
    validate_common_filters(
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_id,
        user_ids=user_id,
    )
    filters = _incident_filters_from_query(
        start_date=start_date,
        end_date=end_date,
        status=status,
        camera_id=camera_id,
        user_id=user_id,
        search=search,
    )
    filters_dict = _filters_as_dict(filters)
    sort_dict = {"sort_by": sort_by, "sort_order": sort_order}
    source_ip = _client_ip(request)

    # A count query, not a materialized id list: `WHERE log_id IN (...)`
    # with tens of thousands of bind parameters exceeds SQLite's default
    # variable limit (999) — found live-drilling a 50,000-row export.
    count_stmt = apply_incident_filters(
        select(func.count(col(DetectionLog.log_id))), filters
    )
    row_count = session.exec(count_stmt).one()

    try:
        check_row_limit(row_count, format=format)
    except AppHTTPException:
        record_export_attempt(
            session,
            action="REPORT_EXPORT",
            report_type="incidents",
            format=format,
            actor=current_user,
            filters=filters_dict,
            sort=sort_dict,
            row_count=row_count,
            result=AuditResult.FAILURE,
            failure_category="row_limit_exceeded",
            source_ip=source_ip,
        )
        session.commit()
        raise

    record_export_attempt(
        session,
        action="REPORT_EXPORT",
        report_type="incidents",
        format=format,
        actor=current_user,
        filters=filters_dict,
        sort=sort_dict,
        row_count=row_count,
        result=AuditResult.SUCCESS,
        source_ip=source_ip,
    )
    session.commit()

    stmt = _incident_query_stmt(filters)
    stmt = apply_sort(
        stmt,
        DetectionLog,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed=ALERT_SORT_FIELDS,
        tie_breaker="log_id",
    )

    if format == "pdf":
        logs = session.exec(stmt).all()
        pdf_bytes = build_incident_pdf(
            rows=[_incident_pdf_row(log) for log in logs],
            filters_summary=_filters_summary(
                filters, sort_by=sort_by, sort_order=sort_order
            ),
            requested_by=format_user_name(current_user) or current_user.username,
            generated_at=datetime.now(UTC),
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="adas_incident_export.pdf"'
            },
        )

    rows_iter = (_incident_csv_row(log) for log in session.exec(stmt).yield_per(500))
    return csv_response("adas_incident_export.csv", INCIDENT_CSV_COLUMNS, rows_iter)


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


@router.get("/{log_id}/snapshot")
def get_alert_snapshot(log_id: int, session: Session = Depends(get_session)):
    """Session-authenticated evidence retrieval (05_PKG_incidents_cameras.md
    Step 9) — replaces the public `/snapshots` static mount. `404` both when
    the incident is missing and when its snapshot file is (the row can
    outlive the file)."""
    log = session.get(DetectionLog, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Incident log not found")

    path = resolve_snapshot(
        log.snapshot_key,
        snapshot_root=settings.SNAPSHOT_ROOT,
        legacy_dir=settings.LEGACY_SNAPSHOT_DIR,
    )
    if path is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    return FileResponse(path, headers={"Cache-Control": "private, max-age=3600"})


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
        detail={
            "camera_id": log.camera_id,
            "camera_name": log.camera.camera_name if log.camera else None,
        },
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
        detail={
            "camera_id": log.camera_id,
            "camera_name": camera.camera_name if camera is not None else None,
        },
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
        detail={
            "camera_id": log.camera_id,
            "camera_name": camera.camera_name if camera is not None else None,
        },
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
        detail={
            "snoozed_until": log.snoozed_until.isoformat(),
            "camera_id": log.camera_id,
            "camera_name": log.camera.camera_name if log.camera else None,
        },
        source_ip=_client_ip(request),
    )
    session.commit()
    session.refresh(log)

    manager.broadcast(snooze_activated_event(log))
    if scheduler is not None:
        schedule_snooze_job(scheduler, session.get_bind(), log, manager)

    return _to_detection_log_read(log)
