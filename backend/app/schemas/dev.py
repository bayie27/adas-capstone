"""Request/response models for the dev-tools routes.

Request bodies use `extra="forbid"` (as DetectionLogCreateV2 does), so a
typo'd field is a 422 rather than a silently ignored one.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models import AIStatus, ConnectionStatus, UserRole


class DevProfileInfo(BaseModel):
    name: str
    description: str


class DevStatusResponse(BaseModel):
    enabled: bool
    profiles: list[DevProfileInfo]


class DevSessionUser(BaseModel):
    """Who the caller is after a reseed or a switch — Package C writes this
    straight into useAuthStore."""

    user_id: int
    username: str
    role: UserRole


class DevReseedRequest(BaseModel):
    model_config = {"extra": "forbid"}

    profile: str
    # Defaults to the caller's own username at the route, falling back to
    # `admin` when that account no longer exists after the wipe.
    login_as: str | None = None


class DevReseedResponse(BaseModel):
    profile: str
    users: int
    cameras: int
    detections: int
    audit_rows: int
    health_samples: int
    export_jobs: int
    snapshots: int
    session: DevSessionUser


class DevLoginAsRequest(BaseModel):
    model_config = {"extra": "forbid"}

    username: str


class DevLoginAsResponse(BaseModel):
    session: DevSessionUser


class DevDetectionRequest(BaseModel):
    model_config = {"extra": "forbid"}

    # Omit to have the route pick a random enabled camera with no open
    # incident — the common case when you just want an alarm to fire.
    camera_id: int | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    detected_at: datetime | None = None


class DevCameraStateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    connection_status: ConnectionStatus | None = None
    ai_status: AIStatus | None = None
    # Backdates last_heartbeat_at past HEARTBEAT_STALE_SECONDS so
    # presented_statuses() reports Unresponsive. There is no way to store
    # that status directly, by design.
    stale_heartbeat: bool | None = None
    clear_cooldown: bool | None = None


class DevHealthHistoryRequest(BaseModel):
    model_config = {"extra": "forbid"}

    days: int = Field(ge=1, le=90)


class DevHealthHistoryResponse(BaseModel):
    rows_written: int
