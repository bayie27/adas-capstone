from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import field_validator
from sqlalchemy import CheckConstraint, Column, Index, column, func, text
from sqlmodel import Field, Relationship, SQLModel

from app.core.types import UtcDateTime
from app.models.enums import AIStatus, ConnectionStatus, DesiredAIState

if TYPE_CHECKING:
    from app.models.detection import DetectionLog


class CameraBase(SQLModel):
    camera_name: str = Field(min_length=1, max_length=100)
    channel_id: int = Field(gt=0)

    @field_validator("camera_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class Camera(CameraBase, table=True):
    """Desired/observed split (D-003). Only routes write the desired-state
    columns; only heartbeat processing writes the observed-state columns."""

    __tablename__ = "camera"
    __table_args__ = (
        CheckConstraint("channel_id > 0", name="ck_camera_channel_id_positive"),
        CheckConstraint(
            "desired_ai_state IN ('Active', 'Paused', 'Inactive')",
            name="ck_camera_desired_ai_state_valid",
        ),
        CheckConstraint(
            "desired_state_reason IS NULL OR desired_state_reason IN "
            "('incident', 'cooldown', 'disabled')",
            name="ck_camera_desired_state_reason_valid",
        ),
        CheckConstraint(
            "connection_status IN ('Connected', 'Disconnected', 'Reconnecting', 'Unresponsive')",
            name="ck_camera_connection_status_valid",
        ),
        CheckConstraint(
            "ai_status IN ('Active', 'Inactive', 'Paused', 'Unresponsive')",
            name="ck_camera_ai_status_valid",
        ),
        Index(
            "ux_camera_name_active",
            func.lower(column("camera_name")),
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
        Index(
            "ux_camera_channel_active",
            "channel_id",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
        Index(
            "ix_camera_active_state",
            "is_active",
            "is_enabled",
            "connection_status",
            "ai_status",
        ),
    )

    camera_id: int | None = Field(default=None, primary_key=True)
    is_active: bool = Field(default=True)
    is_enabled: bool = Field(default=True)

    # --- Backend-owned desired state (D-003) -------------------------------
    desired_ai_state: str = Field(default=DesiredAIState.INACTIVE.value)
    desired_state_reason: str | None = Field(default=None)
    cooldown_until: datetime | None = Field(default=None, sa_type=UtcDateTime)
    config_version: int = Field(default=1)

    # --- AI-owned observed state --------------------------------------------
    connection_status: str = Field(default=ConnectionStatus.DISCONNECTED.value)
    ai_status: str = Field(default=AIStatus.INACTIVE.value)
    applied_config_version: int | None = Field(default=None)
    last_heartbeat_at: datetime | None = Field(default=None, sa_type=UtcDateTime)
    measured_fps: float | None = Field(default=None)
    inference_latency_ms: float | None = Field(default=None)
    last_error_code: str | None = Field(default=None)
    last_error_message: str | None = Field(default=None, max_length=256)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=UtcDateTime
    )
    updated_at: datetime = Field(
        default=None,
        sa_column=Column(
            UtcDateTime,
            default=lambda: datetime.now(UTC),
            onupdate=lambda: datetime.now(UTC),
            nullable=False,
        ),
    )

    # Relationships
    detections: list["DetectionLog"] = Relationship(back_populates="camera")
