from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, col
from typing import Optional
from pydantic import BaseModel
from app.core.db import get_session
from app.models import DetectionLog, DetectionLogCreate, Camera, CameraRead, ConnectionStatus, AIStatus, DetectionStatus, CameraStatusUpdate
from app.api.dependencies import verify_internal_api_key
from app.ws_manager import manager
import logging

logger = logging.getLogger("uvicorn.error")

router = APIRouter(
    prefix="/api/internal",
    tags=["Internal AI System"],
    dependencies=[Depends(verify_internal_api_key)]
)

@router.post("/alert", response_model=DetectionLog)
async def receive_ai_alert(
    alert_in: DetectionLogCreate,
    session: Session = Depends(get_session)
) -> DetectionLog:
    try:
        camera = session.get(Camera, alert_in.camera_id)
        if not camera or not camera.is_active or not camera.is_enabled:
            raise HTTPException(
                status_code=404,
                detail=f"Camera with ID {alert_in.camera_id} not found, inactive, or disabled."
            )

        # Immediately mark camera as Paused in DB so FE reflects the self-blindfold
        camera.ai_status = AIStatus.PAUSED.value
        session.add(camera)

        db_alert = DetectionLog(**alert_in.model_dump())
        session.add(db_alert)
        session.commit()
        session.refresh(db_alert)
        session.refresh(camera)

        # Broadcast the new detection alert
        alert_payload = {
            "type": "NEW_DETECTION",
            "log_id": db_alert.log_id,
            "camera_id": db_alert.camera_id,
            "detected_at": db_alert.detected_at.isoformat(),
            "snapshot_path": db_alert.snapshot_path,
            "confidence_score": db_alert.confidence_score,
            "detection_status": db_alert.detection_status
        }
        await manager.broadcast_alert(alert_payload)

        # Broadcast the camera status change so FE camera cards update live
        camera_status_payload = {
            "type": "CAMERA_STATUS_UPDATE",
            "camera_id": camera.camera_id,
            "connection_status": camera.connection_status,
            "ai_status": camera.ai_status,
        }
        await manager.broadcast_alert(camera_status_payload)

        return db_alert

    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to process AI alert")
        raise HTTPException(status_code=500, detail="Failed to process alert.")


@router.get("/cameras", response_model=list[CameraRead])
def get_enabled_cameras(session: Session = Depends(get_session)) -> list[CameraRead]:
    """
    AI engine polls this every 3 seconds to get the list of cameras it should
    be monitoring. Returns all is_enabled=True, is_active=True cameras with
    their current statuses so the engine can reconcile its state on restart.
    """
    cameras = session.exec(
        select(Camera).where(
            col(Camera.is_enabled).is_(True),
            col(Camera.is_active).is_(True),
        )
    ).all()
    return [CameraRead.model_validate(c) for c in cameras]


@router.patch("/cameras/{camera_id}/status", response_model=CameraRead)
async def update_camera_status(
    camera_id: int,
    status_update: CameraStatusUpdate,
    session: Session = Depends(get_session),
) -> CameraRead:
    """
    AI engine calls this to report connection and/or AI status changes.
    Updates DB and broadcasts to all connected FE clients.
    """
    camera = session.get(Camera, camera_id)
    if not camera or not camera.is_active or not camera.is_enabled:
        raise HTTPException(
            status_code=404,
            detail=f"Camera with ID {camera_id} not found, inactive, or disabled."
        )

    # Guard against the AI engine overruling an operator-driven pause.
    # If the camera has an open (Unverified or Ongoing) alert, reject any attempt
    # to set ai_status=Active — the HITL state machine owns that transition.
    if status_update.ai_status == AIStatus.ACTIVE:
        open_alert = session.exec(
            select(DetectionLog).where(
                col(DetectionLog.camera_id) == camera_id,
                col(DetectionLog.detection_status).in_([
                    DetectionStatus.UNVERIFIED.value,
                    DetectionStatus.ONGOING.value,
                ]),
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

    camera_status_payload = {
        "type": "CAMERA_STATUS_UPDATE",
        "camera_id": camera.camera_id,
        "connection_status": camera.connection_status,
        "ai_status": camera.ai_status,
    }
    await manager.broadcast_alert(camera_status_payload)

    return CameraRead.model_validate(camera)