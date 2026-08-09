from datetime import datetime

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.core.validation import reject_null_bytes
from app.models import AIStatus, CameraBase, ConnectionStatus


class CameraCreate(CameraBase):
    pass


class CameraRead(CameraBase):
    camera_id: int
    is_enabled: bool
    is_active: bool
    # Backend-owned desired state (D-003) — the merge key for CAMERA_STATUS_UPDATE
    # events is config_version, per 01_CONTRACTS.md §9.5's recovery sequence.
    desired_ai_state: str
    desired_state_reason: str | None = None
    cooldown_until: datetime | None = None
    config_version: int
    # AI-owned observed state, presented at read time (staleness-aware —
    # see app.services.cameras.presented_statuses()).
    connection_status: str
    ai_status: str
    created_at: datetime
    updated_at: datetime


class CameraKpis(SQLModel):
    total: int
    enabled: int
    network_connected: int
    active_detection: int


class ConnectionBreakdown(SQLModel):
    connected: int
    disconnected: int
    reconnecting: int
    unresponsive: int


class AiBreakdown(SQLModel):
    active: int
    paused: int
    inactive: int
    unresponsive: int


class CameraBreakdowns(SQLModel):
    connection: ConnectionBreakdown
    ai: AiBreakdown


class CameraListResponse(SQLModel):
    """01_CONTRACTS.md §5.9 — kpis/breakdowns share one population
    (is_active=1); `cameras` is the paginated, filtered page."""

    kpis: CameraKpis
    breakdowns: CameraBreakdowns
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
