from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.api.dependencies import get_current_user, get_realtime_manager
from app.core.db import get_session
from app.core.errors import AppHTTPException
from app.models import (
    AIStatus,
    AuditResult,
    Camera,
    ConnectionStatus,
    DetectionLog,
    DetectionStatus,
    User,
)
from app.schemas import (
    AiBreakdown,
    CameraBreakdowns,
    CameraCreate,
    CameraKpis,
    CameraListResponse,
    CameraRead,
    CameraUpdate,
    ConnectionBreakdown,
)
from app.services import audit
from app.services.cameras import (
    bump_if_ai_relevant_changed,
    compute_kpis_and_breakdowns,
    presented_statuses,
    recompute_desired_state,
    snapshot_ai_relevant_fields,
)
from app.services.events import camera_status_update_event
from app.services.realtime import RealtimeManager

router = APIRouter(
    prefix="/api/cameras",
    tags=["Camera Management"],
    dependencies=[Depends(get_current_user)],
)

_OPEN_STATUSES = (DetectionStatus.UNVERIFIED.value, DetectionStatus.ONGOING.value)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _has_open_incident(session: Session, camera_id: int) -> bool:
    return (
        session.exec(
            select(DetectionLog.log_id).where(
                col(DetectionLog.camera_id) == camera_id,
                col(DetectionLog.detection_status).in_(_OPEN_STATUSES),
            )
        ).first()
        is not None
    )


def _to_camera_read(camera: Camera, *, now: datetime) -> CameraRead:
    connection_status, ai_status = presented_statuses(camera, now=now)
    camera_read = CameraRead.model_validate(camera)
    camera_read.connection_status = connection_status
    camera_read.ai_status = ai_status
    return camera_read


def _apply_camera_filters(
    query,
    *,
    search: str | None,
    connection_statuses: list[ConnectionStatus] | None,
    ai_statuses: list[AIStatus] | None,
    is_enabled: bool | None,
):
    if search:
        query = query.where(col(Camera.camera_name).icontains(search))
    if connection_statuses:
        query = query.where(
            col(Camera.connection_status).in_([s.value for s in connection_statuses])
        )
    if ai_statuses:
        query = query.where(col(Camera.ai_status).in_([s.value for s in ai_statuses]))
    if is_enabled is not None:
        query = query.where(col(Camera.is_enabled).is_(is_enabled))
    return query


@router.get("/", response_model=CameraListResponse)
def get_all_cameras(
    connection_status: list[ConnectionStatus] | None = Query(
        default=None,
        description="Filter by one or more connection statuses, e.g. ?connection_status=Connected&connection_status=Disconnected",
    ),
    ai_status: list[AIStatus] | None = Query(
        default=None,
        description="Filter by one or more AI statuses, e.g. ?ai_status=Active&ai_status=Paused",
    ),
    is_enabled: bool | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=5, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    """Fetches paginated camera list with global KPIs and multi-select
    filtering (01_CONTRACTS.md §5.9).

    01_CONTRACTS.md §9.5 recovery sequence: after every WebSocket
    (re)connect, the client re-fetches this list to rebuild camera state.
    `config_version` is the merge key — a camera's `CAMERA_STATUS_UPDATE`
    events must not be allowed to overwrite a state fetched with a *higher*
    `config_version` than the event carries.

    Filters compare against the raw stored connection_status/ai_status
    columns, not the staleness-presented values `presented_statuses()`
    computes — filtering by "Unresponsive" is a known gap, not covered here.
    """
    now = datetime.now(UTC)
    kpis, breakdowns = compute_kpis_and_breakdowns(session, now=now)

    query = select(Camera).where(col(Camera.is_active).is_(True))
    query = _apply_camera_filters(
        query,
        search=search,
        connection_statuses=connection_status,
        ai_statuses=ai_status,
        is_enabled=is_enabled,
    )
    query = query.order_by(col(Camera.created_at).desc())

    total_filtered = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()

    cameras = session.exec(query.offset(offset).limit(limit)).all()

    return CameraListResponse(
        kpis=CameraKpis(**kpis),
        breakdowns=CameraBreakdowns(
            connection=ConnectionBreakdown(**breakdowns["connection"]),
            ai=AiBreakdown(**breakdowns["ai"]),
        ),
        total_filtered=total_filtered,
        cameras=[_to_camera_read(c, now=now) for c in cameras],
    )


@router.post("/", response_model=CameraRead, status_code=status.HTTP_201_CREATED)
def add_camera(
    camera_in: CameraCreate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """A new camera starts as observed Disconnected/Inactive (model
    defaults) and desired Active (no incident, no cooldown) — it does not
    block on an RTSP handshake (D-003); the AI engine applies it on its next
    heartbeat. `IntegrityError` (duplicate active name/channel) becomes 409,
    never an unhandled 500 — reusing a *soft-deleted* camera's name is
    allowed and must succeed (edge case 9.3)."""
    now = datetime.now(UTC)
    new_camera = Camera.model_validate(camera_in)
    recompute_desired_state(new_camera, has_open_incident=False, now=now)

    try:
        session.add(new_camera)
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise AppHTTPException(
            status.HTTP_409_CONFLICT,
            "Camera with this Name or Channel ID already exists.",
            code="CONFLICT_DUPLICATE",
        ) from exc

    audit.record(
        session,
        action="CAMERA_CREATE",
        result=AuditResult.SUCCESS,
        actor=current_user,
        target_type="camera",
        target_ref=str(new_camera.camera_id),
        detail={
            "camera_name": new_camera.camera_name,
            "channel_id": new_camera.channel_id,
        },
        source_ip=_client_ip(request),
    )
    session.commit()
    session.refresh(new_camera)
    return _to_camera_read(new_camera, now=now)


@router.patch("/{camera_id}", response_model=CameraRead)
def update_camera(
    camera_id: int,
    camera_update: CameraUpdate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    manager: RealtimeManager = Depends(get_realtime_manager),
):
    db_camera = session.get(Camera, camera_id)
    if not db_camera or not db_camera.is_active:
        raise HTTPException(status_code=404, detail="Camera not found")

    update_data = camera_update.model_dump(exclude_unset=True)
    source_ip = _client_ip(request)
    now = datetime.now(UTC)

    # D-007 multi-action semantics: is_enabled toggling gets its own
    # CAMERA_ENABLE/CAMERA_DISABLE row; any other changed field gets
    # CAMERA_UPDATE. Renaming and disabling in the same request produces
    # both, same transaction; disabling alone produces only CAMERA_DISABLE.
    is_enabled_changed = (
        "is_enabled" in update_data
        and update_data["is_enabled"] != db_camera.is_enabled
    )
    other_changed_fields = {k: v for k, v in update_data.items() if k != "is_enabled"}
    new_is_enabled = update_data.get("is_enabled")

    # Snapshot before *any* mutation — channel_id/is_enabled are themselves
    # AI-relevant, so the baseline must predate the setattr loop below.
    before = snapshot_ai_relevant_fields(db_camera)

    for key, value in update_data.items():
        setattr(db_camera, key, value)

    # Recompute everywhere (Step 2): enabling/disabling changes desired
    # state immediately, and re-deriving from current facts is always safe
    # even when nothing about desired state actually changed.
    recompute_desired_state(
        db_camera,
        has_open_incident=_has_open_incident(session, camera_id),
        now=now,
    )
    ai_relevant_changed = bump_if_ai_relevant_changed(db_camera, before)

    if other_changed_fields:
        audit.record(
            session,
            action="CAMERA_UPDATE",
            result=AuditResult.SUCCESS,
            actor=current_user,
            target_type="camera",
            target_ref=str(camera_id),
            detail={"changed_fields": sorted(other_changed_fields.keys())},
            source_ip=source_ip,
        )
    if is_enabled_changed:
        audit.record(
            session,
            action="CAMERA_ENABLE" if new_is_enabled else "CAMERA_DISABLE",
            result=AuditResult.SUCCESS,
            actor=current_user,
            target_type="camera",
            target_ref=str(camera_id),
            source_ip=source_ip,
        )

    try:
        session.add(db_camera)
        session.commit()
        session.refresh(db_camera)
    except IntegrityError as exc:
        session.rollback()
        raise AppHTTPException(
            status.HTTP_409_CONFLICT,
            "Camera with this Name or Channel ID already exists.",
            code="CONFLICT_DUPLICATE",
        ) from exc

    if ai_relevant_changed:
        manager.broadcast(camera_status_update_event(db_camera))

    return _to_camera_read(db_camera, now=now)


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(
    camera_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    manager: RealtimeManager = Depends(get_realtime_manager),
):
    db_camera = session.get(Camera, camera_id)
    if not db_camera or not db_camera.is_active:
        raise HTTPException(status_code=404, detail="Camera not found")

    if _has_open_incident(session, camera_id):
        raise AppHTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cannot delete a camera with an open incident.",
            code="PRECONDITION_FAILED",
        )

    now = datetime.now(UTC)
    before = snapshot_ai_relevant_fields(db_camera)
    db_camera.is_active = False
    recompute_desired_state(db_camera, has_open_incident=False, now=now)
    ai_relevant_changed = bump_if_ai_relevant_changed(db_camera, before)

    session.add(db_camera)
    audit.record(
        session,
        action="CAMERA_DELETE",
        result=AuditResult.SUCCESS,
        actor=current_user,
        target_type="camera",
        target_ref=str(camera_id),
        source_ip=_client_ip(request),
    )
    session.commit()
    session.refresh(db_camera)

    if ai_relevant_changed:
        manager.broadcast(camera_status_update_event(db_camera))
    return None
