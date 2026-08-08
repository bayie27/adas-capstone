from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel

from app.models.camera import Camera
from app.models.enums import DetectionStatus
from app.models.user import User


class DetectionLogBase(SQLModel):
    camera_id: int = Field(foreign_key="camera.camera_id", index=True)
    detected_at: datetime
    snapshot_path: str = Field(min_length=1)
    confidence_score: float = Field(ge=0.0, le=1.0)


class DetectionLog(DetectionLogBase, table=True):
    log_id: int | None = Field(default=None, primary_key=True)

    detected_at: datetime = Field(index=True)

    detection_status: str = Field(default=DetectionStatus.UNVERIFIED.value, index=True)

    # Audit Trail
    verified_by_id: int | None = Field(default=None, foreign_key="user.user_id")
    verified_at: datetime | None = Field(default=None)
    closed_by_id: int | None = Field(default=None, foreign_key="user.user_id")
    closed_at: datetime | None = Field(default=None)

    # Relationships
    camera: Camera | None = Relationship(back_populates="detections")
    verified_by: User | None = Relationship(
        back_populates="verified_detections",
        sa_relationship_kwargs={"foreign_keys": "[DetectionLog.verified_by_id]"},
    )
    closed_by: User | None = Relationship(
        back_populates="closed_detections",
        sa_relationship_kwargs={"foreign_keys": "[DetectionLog.closed_by_id]"},
    )
