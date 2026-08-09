from datetime import datetime

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.core.validation import reject_null_bytes
from app.models import AIStatus, CameraBase, ConnectionStatus


class CameraCreate(CameraBase):
    pass


class CameraRead(CameraBase):
    camera_id: int
    connection_status: str
    ai_status: str
    is_enabled: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CameraListResponse(SQLModel):
    total_cameras: int
    network_connected: int
    active_detection: int
    total_filtered: int
    cameras: list[CameraRead]


class CameraUpdate(SQLModel):
    camera_name: str | None = Field(default=None, min_length=1, max_length=100)
    channel_id: int | None = Field(default=None, gt=0)
    is_enabled: bool | None = None

    @field_validator("camera_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if v is not None and isinstance(v, str):
            v = v.strip()
        return reject_null_bytes(v)


class CameraStatusUpdate(SQLModel):
    connection_status: ConnectionStatus | None = None
    ai_status: AIStatus | None = None
