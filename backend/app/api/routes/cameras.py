from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.api.dependencies import get_current_user
from app.core.db import get_session
from app.models import AIStatus, AuditResult, Camera, ConnectionStatus, User
from app.schemas import CameraCreate, CameraListResponse, CameraRead, CameraUpdate
from app.services import audit

router = APIRouter(
    prefix="/api/cameras",
    tags=["Camera Management"],
    dependencies=[Depends(get_current_user)],
)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


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
    """Fetches paginated camera list with global KPIs and multi-select filtering."""

    # ---------------------------------------------------------
    # 1. GLOBAL KPIs (always unfiltered)
    # ---------------------------------------------------------
    total_cameras = session.exec(
        select(func.count()).select_from(Camera).where(col(Camera.is_active).is_(True))
    ).one()

    network_connected = session.exec(
        select(func.count())
        .select_from(Camera)
        .where(
            col(Camera.is_active).is_(True),
            col(Camera.connection_status) == ConnectionStatus.CONNECTED.value,
        )
    ).one()

    active_detection = session.exec(
        select(func.count())
        .select_from(Camera)
        .where(
            col(Camera.is_active).is_(True),
            col(Camera.ai_status) == AIStatus.ACTIVE.value,
        )
    ).one()

    # ---------------------------------------------------------
    # 2. FILTERED QUERY
    # ---------------------------------------------------------
    query = select(Camera).where(col(Camera.is_active).is_(True))
    query = _apply_camera_filters(
        query,
        search=search,
        connection_statuses=connection_status,
        ai_statuses=ai_status,
        is_enabled=is_enabled,
    )
    query = query.order_by(col(Camera.created_at).desc())

    # ---------------------------------------------------------
    # 3. PAGINATE AND RETURN
    # ---------------------------------------------------------
    total_filtered = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()

    cameras = session.exec(query.offset(offset).limit(limit)).all()

    return CameraListResponse(
        total_cameras=total_cameras,
        network_connected=network_connected,
        active_detection=active_detection,
        total_filtered=total_filtered,
        cameras=[CameraRead.model_validate(c) for c in cameras],
    )


@router.post("/", response_model=CameraRead, status_code=status.HTTP_201_CREATED)
def add_camera(
    camera_in: CameraCreate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    existing_cam = session.exec(
        select(Camera).where(
            col(Camera.is_active).is_(True),
            (
                (col(Camera.channel_id) == camera_in.channel_id)
                | (func.lower(Camera.camera_name) == camera_in.camera_name.lower())
            ),
        )
    ).first()

    if existing_cam:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera with this Name or Channel ID already exists.",
        )

    new_camera = Camera.model_validate(camera_in)
    session.add(new_camera)
    # Flush (not commit) to assign the autoincrement PK so the audit row's
    # target_ref can be known before the two commit together.
    session.flush()
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
    return new_camera


@router.patch("/{camera_id}", response_model=CameraRead)
def update_camera(
    camera_id: int,
    camera_update: CameraUpdate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    db_camera = session.get(Camera, camera_id)
    if not db_camera or not db_camera.is_active:
        raise HTTPException(status_code=404, detail="Camera not found")

    update_data = camera_update.model_dump(exclude_unset=True)
    source_ip = _client_ip(request)

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

    for key, value in update_data.items():
        setattr(db_camera, key, value)

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
        return db_camera
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Camera with this Name or Channel ID already exists.",
        ) from exc


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(
    camera_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    db_camera = session.get(Camera, camera_id)
    if not db_camera or not db_camera.is_active:
        raise HTTPException(status_code=404, detail="Camera not found")

    db_camera.is_active = False
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
    return None
