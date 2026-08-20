from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, col, func, select

from app.api.dependencies import get_current_user, get_realtime_manager
from app.core.db import get_session
from app.core.errors import AppHTTPException
from app.core.redaction import redact_text
from app.models import (
    AIStatus,
    AuditResult,
    Camera,
    ConnectionStatus,
    DetectionLog,
    DetectionStatus,
    User,
    UserRole,
)
from app.schemas import (
    AiBreakdown,
    CameraBreakdowns,
    CameraCreate,
    CameraDetailRead,
    CameraKpis,
    CameraListResponse,
    CameraRead,
    CameraUpdate,
    ConnectionBreakdown,
)
from app.services import audit
from app.services.cameras import (
    _build_rtsp_url,
    bump_if_ai_relevant_changed,
    compute_kpis_and_breakdowns,
    presented_ai_status_expr,
    presented_connection_status_expr,
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

# P19 §3's is_active tri-state, mirrored here (routes/users.py) rather than
# shared — a plain bool | None query param can't express three states over
# HTTP: with a non-None default, an *omitted* param and an *explicit* null
# are indistinguishable to FastAPI's query binding, and axios's own
# paramsSerializer silently drops null-valued params before the request is
# even sent. Accepting the raw string and treating the literal `null` as
# its own value keeps all three states reachable over the wire.
_IS_ACTIVE_FILTER_VALUES = {"true": True, "false": False, "null": None}


def _parse_is_active_filter(raw: str | None) -> bool | None:
    if raw is None:
        return True
    try:
        return _IS_ACTIVE_FILTER_VALUES[raw.strip().lower()]
    except KeyError:
        raise HTTPException(
            status_code=422,
            detail="is_active must be 'true', 'false', or 'null'.",
        ) from None


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _get_camera_or_404(camera_id: int, session: Session) -> Camera:
    """Like _get_active_camera_or_404, but does not require is_active — the
    counterpart to routes/users.py's _get_user_or_404 (P19 §3). Used only by
    update_camera (P23), the sole route that must be able to reach a
    soft-deleted row: it's the only way back from false to true. GET detail
    and DELETE keep requiring an active target, since neither makes sense on
    an already-deleted camera."""
    camera = session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


def _get_active_camera_or_404(camera_id: int, session: Session) -> Camera:
    camera = session.get(Camera, camera_id)
    if not camera or not camera.is_active:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


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
    now: datetime,
    search: str | None,
    connection_statuses: list[ConnectionStatus] | None,
    ai_statuses: list[AIStatus] | None,
    is_enabled: bool | None,
):
    """P19 §2 — filters compare the same staleness-aware *presented* status
    the rows and breakdowns show, via presented_connection_status_expr()/
    presented_ai_status_expr() (app.services.cameras), not the raw stored
    columns. Filtering, counting and pagination all stay in SQL."""
    if search:
        query = query.where(col(Camera.camera_name).icontains(search))
    if connection_statuses:
        query = query.where(
            presented_connection_status_expr(now=now).in_(
                [s.value for s in connection_statuses]
            )
        )
    if ai_statuses:
        query = query.where(
            presented_ai_status_expr(now=now).in_([s.value for s in ai_statuses])
        )
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
    is_active: str | None = Query(
        default=None,
        description="'true' (default when omitted) lists active cameras"
        " only; 'false' lists soft-deleted cameras; 'null' lists both.",
    ),
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

    Filters compare against the same staleness-aware *presented* status the
    rows and `breakdowns` show (P19 §2), so filtering by "Unresponsive"
    returns exactly the cameras that display it.

    is_active defaults to active-only (P23), pinning today's behaviour
    byte-for-byte for a caller that passes nothing. ?is_active=false
    surfaces soft-deleted cameras so they can be found and restored;
    ?is_active=null lists both. `kpis`/`breakdowns` are unaffected by this
    filter either way — they stay the unfiltered is_active=1 population
    (§5.9), never the soft-deleted population.
    """
    now = datetime.now(UTC)
    kpis, breakdowns = compute_kpis_and_breakdowns(session, now=now)

    is_active_filter = _parse_is_active_filter(is_active)
    query = select(Camera)
    if is_active_filter is not None:
        query = query.where(col(Camera.is_active).is_(is_active_filter))
    query = _apply_camera_filters(
        query,
        now=now,
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


@router.get("/{camera_id}", response_model=CameraDetailRead)
def get_camera_detail(
    camera_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """01_CONTRACTS.md §5.4/§7.2 (P21 Step 1) — operator-visible diagnostic
    detail: the six AI-owned telemetry columns plus a redacted RTSP URL.
    `rtsp_url_redacted` is admin-only *within* this route, not a reason to
    gate the whole thing to Admin — an Operator gets 200 with that one
    field null. Not audited — routine viewing, per D-007."""
    db_camera = _get_active_camera_or_404(camera_id, session)

    now = datetime.now(UTC)
    base = _to_camera_read(db_camera, now=now)

    rtsp_url_redacted = None
    if current_user.role == UserRole.ADMIN:
        rtsp_url_redacted = redact_text(_build_rtsp_url(db_camera.channel_id))

    return CameraDetailRead(
        **base.model_dump(),
        applied_config_version=db_camera.applied_config_version,
        last_heartbeat_at=db_camera.last_heartbeat_at,
        measured_fps=db_camera.measured_fps,
        inference_latency_ms=db_camera.inference_latency_ms,
        last_error_code=db_camera.last_error_code,
        last_error_message=db_camera.last_error_message,
        rtsp_url_redacted=rtsp_url_redacted,
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
    # P23 — the only camera route that must be able to reach a soft-deleted
    # row, since it's also how one gets restored (mirrors routes/users.py's
    # _get_user_or_404 vs _get_active_user_or_404, P19 §3).
    db_camera = _get_camera_or_404(camera_id, session)

    update_data = camera_update.model_dump(exclude_unset=True)

    # PATCH's is_active is one-directional: false -> true restores. true ->
    # false is DELETE's job, which additionally guards against deleting a
    # camera with an open incident (see delete_camera below) — accepting it
    # here too would silently duplicate that endpoint while bypassing its
    # precondition.
    if update_data.get("is_active") is False:
        raise HTTPException(
            status_code=400,
            detail="Cannot deactivate a camera via PATCH — use DELETE /api/cameras/{camera_id}.",
        )

    source_ip = _client_ip(request)
    now = datetime.now(UTC)

    # D-007 multi-action semantics: is_enabled toggling gets its own
    # CAMERA_ENABLE/CAMERA_DISABLE row, is_active going false->true gets its
    # own CAMERA_RESTORE row, and any other changed field gets CAMERA_UPDATE.
    # Renaming and disabling in the same request produces both, same
    # transaction; disabling alone produces only CAMERA_DISABLE.
    is_enabled_changed = (
        "is_enabled" in update_data
        and update_data["is_enabled"] != db_camera.is_enabled
    )
    is_being_restored = (
        "is_active" in update_data
        and update_data["is_active"] is True
        and db_camera.is_active is False
    )
    other_changed_fields = {
        k: v for k, v in update_data.items() if k not in ("is_enabled", "is_active")
    }
    new_is_enabled = update_data.get("is_enabled")

    # Computed *before* any mutation below — querying after would
    # autoflush the pending camera_name/channel_id change, and a duplicate
    # would then raise IntegrityError outside this function's try/except,
    # leaking an unhandled 500 instead of the intended 409.
    has_open_incident = _has_open_incident(session, camera_id)

    # Snapshot before *any* mutation — channel_id/is_enabled are themselves
    # AI-relevant, so the baseline must predate the setattr loop below.
    before = snapshot_ai_relevant_fields(db_camera)

    for key, value in update_data.items():
        setattr(db_camera, key, value)

    # Recompute everywhere (Step 2): enabling/disabling changes desired
    # state immediately, and re-deriving from current facts is always safe
    # even when nothing about desired state actually changed.
    recompute_desired_state(db_camera, has_open_incident=has_open_incident, now=now)
    ai_relevant_changed = bump_if_ai_relevant_changed(db_camera, before)

    # Edge case 1.7 (be_audit/A5_edge_cases.md): recompute_desired_state()'s
    # result can coincidentally equal *this session's own original read* of
    # these columns (e.g. a fresh camera's Inactive default) even though a
    # concurrent AI alert has, in between, committed a different value to
    # the row (Paused/incident). SQLAlchemy's dirty-tracking only diffs
    # against this session's own load, not the live row, so an unflagged
    # UPDATE would then silently omit that column from its SET clause and
    # leave the concurrent writer's value in place — a disabled camera
    # stuck presenting as Paused. Force these three into the UPDATE
    # regardless of whether this session thinks they changed.
    flag_modified(db_camera, "desired_ai_state")
    flag_modified(db_camera, "desired_state_reason")
    flag_modified(db_camera, "cooldown_until")

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
    if is_being_restored:
        audit.record(
            session,
            action="CAMERA_RESTORE",
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
    db_camera = _get_active_camera_or_404(camera_id, session)

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
