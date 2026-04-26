from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.db import get_session
from app.models import DetectionLog, DetectionLogCreate, Camera
from app.api.dependencies import verify_internal_api_key
from app.ws_manager import manager
import logging

logger = logging.getLogger("uvicorn.error")

# Router protected by the internal API key dependency
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
        if not camera or not camera.is_active:
            raise HTTPException(
                status_code=404,
                detail=f"Camera with ID {alert_in.camera_id} not found or inactive."
            )
        
        db_alert = DetectionLog(**alert_in.model_dump())
        session.add(db_alert)
        session.commit()
        session.refresh(db_alert)
        
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
        
        return db_alert
        
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("Failed to process AI alert")
        raise HTTPException(status_code=500, detail="Failed to process alert.")
