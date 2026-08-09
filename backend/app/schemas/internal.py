"""01_CONTRACTS.md §6.2 — the v2 AI-engine heartbeat contract."""

from datetime import datetime

from pydantic import Field, field_validator
from sqlmodel import SQLModel

from app.core.validation import reject_null_bytes
from app.models import AIStatus, ConnectionStatus


class HeartbeatCameraReport(SQLModel):
    """One camera's locally-observed runtime state, as reported by the AI
    engine's supervisor (D-003)."""

    camera_id: int
    connection_status: ConnectionStatus
    ai_status: AIStatus
    applied_config_version: int | None = None
    # Edge case 4.17 — an absurd or negative reading is rejected outright
    # (422) rather than silently poisoning a downstream average.
    measured_fps: float | None = Field(default=None, ge=0, le=1000)
    inference_latency_ms: float | None = Field(default=None, ge=0, le=60_000)
    error_code: str | None = None
    error_message: str | None = Field(default=None, max_length=1000)

    @field_validator("error_code", "error_message")
    @classmethod
    def _no_null_bytes(cls, v: str | None) -> str | None:
        return reject_null_bytes(v)


class HeartbeatRequest(SQLModel):
    engine_id: str
    sent_at: datetime
    cameras: list[HeartbeatCameraReport] = []


class HeartbeatCameraSnapshot(SQLModel):
    """One camera's entry in the authoritative snapshot the backend hands
    back every heartbeat — a complete list, not a change set, so either side
    can restart and recover deterministically (D-003)."""

    camera_id: int
    channel_id: int
    camera_name: str
    rtsp_url: str
    is_enabled: bool
    desired_ai_state: str
    desired_state_reason: str | None
    cooldown_until: datetime | None
    config_version: int


class HeartbeatResponse(SQLModel):
    server_time: datetime
    heartbeat_interval_seconds: int
    cameras: list[HeartbeatCameraSnapshot]
