from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import field_validator
from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel


# -----------------------------------------
# 1. USER MANAGEMENT (RBAC) - Table 4.0
# -----------------------------------------
class TokenResponse(SQLModel):
    access_token: str
    token_type: str


class ApiError(SQLModel):
    detail: str
    code: str
    errors: list[dict[str, Any]] | None = None


class UserRole(StrEnum):
    ADMIN = "Admin"
    OPERATOR = "Operator"


def validate_password_strength(v: str) -> str:
    if not any(char.isdigit() for char in v):
        raise ValueError("Password must contain at least 1 number.")
    return v


class UserBase(SQLModel):
    username: str = Field(unique=True, index=True, min_length=3, max_length=20)
    first_name: str = Field(min_length=1, max_length=20)
    last_name: str = Field(min_length=1, max_length=20)
    role: UserRole

    @field_validator("username", "first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class User(UserBase, table=True):
    user_id: int | None = Field(default=None, primary_key=True)
    password_hash: str
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
    password_changed_at: datetime | None = Field(default=None)
    last_login: datetime | None = Field(default=None)

    # Relationships
    verified_detections: list["DetectionLog"] = Relationship(
        back_populates="verified_by",
        sa_relationship_kwargs={"foreign_keys": "DetectionLog.verified_by_id"},
    )
    closed_detections: list["DetectionLog"] = Relationship(
        back_populates="closed_by",
        sa_relationship_kwargs={"foreign_keys": "DetectionLog.closed_by_id"},
    )


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


class UserRead(UserBase):
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    password_changed_at: datetime | None = None
    last_login: datetime | None = None


class UserListResponse(SQLModel):
    total_filtered: int
    users: list[UserRead]


class UserOperatorUpdate(SQLModel):
    username: str | None = Field(default=None, min_length=3, max_length=20)
    first_name: str | None = Field(default=None, min_length=1, max_length=20)
    last_name: str | None = Field(default=None, min_length=1, max_length=20)

    @field_validator("username", "first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if v is not None and isinstance(v, str):
            return v.strip()
        return v


class UserAdminUpdate(UserOperatorUpdate):
    role: UserRole | None = None
    is_active: bool | None = None


class UserUpdatePassword(SQLModel):
    old_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


class UserResetPassword(SQLModel):
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


# -----------------------------------------
# 2. CAMERA MANAGEMENT - Table 5.0
# -----------------------------------------
class ConnectionStatus(StrEnum):
    CONNECTED = "Connected"
    DISCONNECTED = "Disconnected"
    RECONNECTING = "Reconnecting"
    UNRESPONSIVE = "Unresponsive"


class AIStatus(StrEnum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    PAUSED = "Paused"
    UNRESPONSIVE = "Unresponsive"


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
            return v.strip()
        return v


class CameraStatusUpdate(SQLModel):
    connection_status: ConnectionStatus | None = None
    ai_status: AIStatus | None = None


# ==========================================
# 3. DETECTION LOGS (HITL Workflow) - Table 6.0
# ==========================================
class DetectionStatus(StrEnum):
    UNVERIFIED = "Unverified"
    ONGOING = "Ongoing"
    DISMISSED = "Dismissed"
    RESOLVED = "Resolved"


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


# -----------------------------------------
# 4. SYSTEM HEALTH RAW - Table 7.0
# -----------------------------------------
class SystemHealthRawBase(SQLModel):
    cpu_usage: float = Field(ge=0.0, le=100.0)
    gpu_usage: float = Field(ge=0.0, le=100.0)
    ram_usage: float = Field(ge=0.0, le=100.0)
    gpu_temperature: float = Field(ge=0.0, le=120.0)


class SystemHealthRaw(SystemHealthRawBase, table=True):
    sys_health_id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class SystemHealthRawRead(SystemHealthRawBase):
    sys_health_id: int
    created_at: datetime


# -----------------------------------------
# 5. SYSTEM HEALTH HOURLY - Table 8.0
# -----------------------------------------
class SystemHealthHourlyBase(SQLModel):
    avg_cpu_usage: float = Field(ge=0.0, le=100.0)
    avg_gpu_usage: float = Field(ge=0.0, le=100.0)
    avg_ram_usage: float = Field(ge=0.0, le=100.0)
    peak_gpu_temp: float = Field(ge=0.0, le=120.0)


class SystemHealthHourly(SystemHealthHourlyBase, table=True):
    hourly_sys_health_id: int | None = Field(default=None, primary_key=True)
    created_at_hour: datetime = Field(unique=True, index=True)


class SystemHealthHourlyRead(SystemHealthHourlyBase):
    hourly_sys_health_id: int
    created_at_hour: datetime
