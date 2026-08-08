"""SQLModel table definitions and shared enums. Pydantic-only request/response
schemas live in app.schemas, not here — see 02_PKG_foundation.md Step 3."""

from app.models.camera import Camera, CameraBase
from app.models.detection import DetectionLog, DetectionLogBase
from app.models.enums import AIStatus, ConnectionStatus, DetectionStatus, UserRole
from app.models.health import (
    SystemHealthHourly,
    SystemHealthHourlyBase,
    SystemHealthRaw,
    SystemHealthRawBase,
)
from app.models.user import User, UserBase

__all__ = [
    "AIStatus",
    "Camera",
    "CameraBase",
    "ConnectionStatus",
    "DetectionLog",
    "DetectionLogBase",
    "DetectionStatus",
    "SystemHealthHourly",
    "SystemHealthHourlyBase",
    "SystemHealthRaw",
    "SystemHealthRawBase",
    "User",
    "UserBase",
    "UserRole",
]
