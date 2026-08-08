from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import field_validator
from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import AIStatus, ConnectionStatus

if TYPE_CHECKING:
    from app.models.detection import DetectionLog


class CameraBase(SQLModel):
    camera_name: str = Field(unique=True, min_length=1, max_length=100)
    channel_id: int = Field(gt=0)

    @field_validator("camera_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class Camera(CameraBase, table=True):
    camera_id: int | None = Field(default=None, primary_key=True)
    connection_status: str = Field(default=ConnectionStatus.DISCONNECTED.value)
    ai_status: str = Field(default=AIStatus.INACTIVE.value)
    is_enabled: bool = Field(default=True)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            default=lambda: datetime.now(UTC),
            onupdate=lambda: datetime.now(UTC),
            nullable=False,
        ),
    )

    # Relationships
    detections: list["DetectionLog"] = Relationship(back_populates="camera")
