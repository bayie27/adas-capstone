from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select, func, col
from app.core.db import get_session
from app.models import Camera, CameraCreate, CameraRead, CameraUpdate, CameraListResponse, ConnectionStatus, AIStatus
from app.api.dependencies import get_current_user
from typing import Optional
from enum import Enum

router = APIRouter(
    prefix="/api/cameras",
    tags=["Camera Management"],
    dependencies=[Depends(get_current_user)],
)


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
            col(Camera.connection_status).in_(
                [s.value for s in connection_statuses]
            )
        )
    if ai_statuses:
        query = query.where(
            col(Camera.ai_status).in_(
                [s.value for s in ai_statuses]
            )
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
    is_enabled: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=5, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    """Fetches paginated camera list with global KPIs and multi-select filtering."""

    # ---------------------------------------------------------
    # 1. GLOBAL KPIs (always unfiltered)
    # ---------------------------------------------------------
    total_cameras = session.exec(
        select(func.count())
        .select_from(Camera)
        .where(col(Camera.is_active).is_(True))
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
def add_camera(camera_in: CameraCreate, session: Session = Depends(get_session)):
    existing_cam = session.exec(
        select(Camera).where(
            col(Camera.is_active).is_(True),
            (
                (col(Camera.channel_id) == camera_in.channel_id)
                | (col(Camera.camera_name) == camera_in.camera_name)
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
    session.commit()
    session.refresh(new_camera)
    return new_camera


@router.patch("/{camera_id}", response_model=CameraRead)
def update_camera(
    camera_id: int,
    camera_update: CameraUpdate,
    session: Session = Depends(get_session),
):
    db_camera = session.get(Camera, camera_id)
    if not db_camera or not db_camera.is_active:
        raise HTTPException(status_code=404, detail="Camera not found")

    update_data = camera_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_camera, key, value)

    session.add(db_camera)
    session.commit()
    session.refresh(db_camera)
    return db_camera


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(camera_id: int, session: Session = Depends(get_session)):
    db_camera = session.get(Camera, camera_id)
    if not db_camera or not db_camera.is_active:
        raise HTTPException(status_code=404, detail="Camera not found")

    db_camera.is_active = False
    session.add(db_camera)
    session.commit()
    return None