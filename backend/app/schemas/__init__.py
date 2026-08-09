"""Pydantic request/response models. SQLModel table definitions live in
app.models, not here — see 02_PKG_foundation.md Step 3."""

from app.schemas.audit import AuditLogListResponse, AuditLogRead
from app.schemas.auth import LoginResponse
from app.schemas.camera import (
    CameraCreate,
    CameraListResponse,
    CameraRead,
    CameraStatusUpdate,
    CameraUpdate,
)
from app.schemas.common import ApiError, default_error_code, validate_password_strength
from app.schemas.detection import (
    DetectionLogCreate,
    DetectionLogListResponse,
    DetectionLogRead,
)
from app.schemas.health import SysHealthHourlyRead, SysHealthRawRead
from app.schemas.help import (
    HelpArticleDetail,
    HelpArticleListResponse,
    HelpArticleSummary,
)
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
    "AuditLogListResponse",
    "AuditLogRead",
    "CameraCreate",
    "CameraListResponse",
    "CameraRead",
    "CameraStatusUpdate",
    "CameraUpdate",
    "DetectionLogCreate",
    "DetectionLogListResponse",
    "DetectionLogRead",
    "default_error_code",
    "HelpArticleDetail",
    "HelpArticleListResponse",
    "HelpArticleSummary",
    "LoginResponse",
    "SysHealthHourlyRead",
    "SysHealthRawRead",
    "UserAdminUpdate",
    "UserCreate",
    "UserListResponse",
    "UserOperatorUpdate",
    "UserRead",
    "UserResetPassword",
    "UserUpdatePassword",
    "validate_password_strength",
]
