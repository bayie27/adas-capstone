"""SQLModel table definitions and shared enums. Pydantic-only request/response
schemas live in app.schemas, not here — see 02_PKG_foundation.md Step 3."""

from app.models.audit import AUDIT_ACTIONS, AuditLog
from app.models.camera import Camera, CameraBase
from app.models.detection import DetectionLog, DetectionLogBase
from app.models.enums import (
    AIStatus,
    AuditResult,
    ConnectionStatus,
    DesiredAIState,
    DesiredStateReason,
    DetectionStatus,
    UserRole,
)
from app.models.export import ExportJob
from app.models.health import (
    SysHealthHourly,
    SysHealthHourlyBase,
    SysHealthRaw,
    SysHealthRawBase,
)
from app.models.help import HelpArticle
from app.models.user import AlarmSettings, AuthSession, User, UserBase

__all__ = [
    "AIStatus",
    "AUDIT_ACTIONS",
    "AlarmSettings",
    "AuditLog",
    "AuditResult",
    "AuthSession",
    "Camera",
    "CameraBase",
    "ConnectionStatus",
    "DesiredAIState",
    "DesiredStateReason",
    "DetectionLog",
    "DetectionLogBase",
    "DetectionStatus",
    "ExportJob",
    "HelpArticle",
    "SysHealthHourly",
    "SysHealthHourlyBase",
    "SysHealthRaw",
    "SysHealthRawBase",
    "User",
    "UserBase",
    "UserRole",
]
