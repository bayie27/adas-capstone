from datetime import datetime

from sqlmodel import SQLModel

from app.models import DetectionLogBase


class DetectionLogCreate(DetectionLogBase):
    pass


class DetectionLogRead(DetectionLogBase):
    log_id: int
    detection_status: str
    verified_by_id: int | None = None
    verified_by_name: str | None = None
    verified_at: datetime | None = None
    closed_by_id: int | None = None
    closed_by_name: str | None = None
    closed_at: datetime | None = None
    camera_name: str | None = None


class DetectionLogListResponse(SQLModel):
    total_filtered: int
    logs: list[DetectionLogRead]
