from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.db import get_session
from app.models import DetectionLog, DetectionLogCreate
from app.api.dependencies import verify_internal_api_key
from app.ws_manager import manager

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
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))