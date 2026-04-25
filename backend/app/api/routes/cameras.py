from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func, col
from app.core.db import get_session
from app.models import Camera, CameraCreate, CameraRead, CameraUpdate, CameraListResponse
from app.api.dependencies import get_current_user
from typing import Optional


router = APIRouter(
    prefix="/api/cameras",
    tags=["Camera Management"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/", response_model=CameraListResponse)
def get_all_cameras(
    connection_status: Optional[str] = None,
    ai_status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 5,
    offset: int = 0,
    session: Session = Depends(get_session)
):
    
    # ---------------------------------------------------------
    # 1. CALCULATE TOP KEYCARDS (Unfiltered Global State)
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
            col(Camera.connection_status) == "Connected",
        )
    ).one()
    
    active_detection = session.exec(
        select(func.count())
        .select_from(Camera)
        .where(col(Camera.is_active).is_(True), col(Camera.ai_status) == "Active")
    ).one()

    # ---------------------------------------------------------
    # 2. BUILD THE FILTERED QUERY FOR THE TABLE
    # ---------------------------------------------------------
    query = select(Camera).where(col(Camera.is_active).is_(True))
    
    if connection_status:
        query = query.where(Camera.connection_status == connection_status)
    
    if ai_status:
        query = query.where(Camera.ai_status == ai_status)
        
    if search:
        # icontains makes the search case-insensitive
        query = query.where(col(Camera.camera_name).icontains(search))

    # ---------------------------------------------------------
    # 3. EXECUTE PAGINATION AND RETURN
    # ---------------------------------------------------------
    total_filtered = session.exec(select(func.count()).select_from(query.subquery())).one()

    paginated_query = query.offset(offset).limit(limit)
    cameras = session.exec(paginated_query).all()
    camera_reads = [CameraRead.model_validate(camera) for camera in cameras]

    return CameraListResponse(
        total_cameras=total_cameras,
        network_connected=network_connected,
        active_detection=active_detection,
        total_filtered=total_filtered,
        cameras=camera_reads
    )


@router.post("/", response_model=CameraRead, status_code=status.HTTP_201_CREATED)
def add_camera(camera_in: CameraCreate, session: Session = Depends(get_session)):
    existing_cam = session.exec(
        select(Camera).where(
            (Camera.channel_id == camera_in.channel_id)
            | (Camera.camera_name == camera_in.camera_name)
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
    camera_id: int, camera_update: CameraUpdate, session: Session = Depends(get_session)
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
