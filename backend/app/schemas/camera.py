from datetime import datetime

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.core.validation import reject_null_bytes
from app.models import CameraBase


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


class CameraDetailRead(CameraRead):
    """GET /api/cameras/{camera_id} (01_CONTRACTS.md §5.4/§7.2, P21 Step 1)
    — the six AI-owned telemetry columns CameraRead never exposed, plus a
    redacted RTSP URL. The route itself is operator-visible; only
    `rtsp_url_redacted` is admin-only within it (null for an Operator)."""

    applied_config_version: int | None = None
    last_heartbeat_at: datetime | None = None
    measured_fps: float | None = None
    inference_latency_ms: float | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    rtsp_url_redacted: str | None = None


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
    # P23 — false -> true restores a soft-deleted camera (the counterpart
    # to DELETE /api/cameras/{camera_id}). true -> false is rejected by the
    # route itself; DELETE stays the one guarded path for deactivating.
    is_active: bool | None = None

    @field_validator("camera_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if v is not None and isinstance(v, str):
            v = v.strip()
        return reject_null_bytes(v)
