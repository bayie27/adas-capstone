"""Pydantic request/response models. SQLModel table definitions live in
app.models, not here — see 02_PKG_foundation.md Step 3."""

from app.schemas.auth import TokenResponse
from app.schemas.camera import (
    CameraCreate,
    CameraListResponse,
    CameraRead,
    CameraStatusUpdate,
    CameraUpdate,
)
from app.schemas.common import ApiError, validate_password_strength
from app.schemas.detection import (
    DetectionLogCreate,
    DetectionLogListResponse,
    DetectionLogRead,
)
from app.schemas.health import SystemHealthHourlyRead, SystemHealthRawRead
from app.schemas.user import (
    UserAdminUpdate,
    UserCreate,
    UserListResponse,
    UserOperatorUpdate,
    UserRead,
    UserResetPassword,
    UserUpdatePassword,
)

__all__ = [
    "ApiError",
    "CameraCreate",
    "CameraListResponse",
    "CameraRead",
    "CameraStatusUpdate",
    "CameraUpdate",
    "DetectionLogCreate",
    "DetectionLogListResponse",
    "DetectionLogRead",
    "SystemHealthHourlyRead",
    "SystemHealthRawRead",
    "TokenResponse",
    "UserAdminUpdate",
    "UserCreate",
    "UserListResponse",
    "UserOperatorUpdate",
    "UserRead",
    "UserResetPassword",
    "UserUpdatePassword",
    "validate_password_strength",
]
