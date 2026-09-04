from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "Admin"
    OPERATOR = "Operator"


class ConnectionStatus(StrEnum):
    """Observed, AI-reported."""

    CONNECTED = "Connected"
    DISCONNECTED = "Disconnected"
    RECONNECTING = "Reconnecting"
    UNRESPONSIVE = "Unresponsive"


class AIStatus(StrEnum):
    """Observed, AI-reported."""

    ACTIVE = "Active"
    INACTIVE = "Inactive"
    PAUSED = "Paused"
    UNRESPONSIVE = "Unresponsive"


class DesiredAIState(StrEnum):
    """Desired, backend-owned (D-003)."""

    ACTIVE = "Active"
    PAUSED = "Paused"
    INACTIVE = "Inactive"


class DesiredStateReason(StrEnum):
    INCIDENT = "incident"
    COOLDOWN = "cooldown"
    DISABLED = "disabled"


class DetectionStatus(StrEnum):
    UNVERIFIED = "Unverified"
    ONGOING = "Ongoing"
    DISMISSED = "Dismissed"
    CLEARED = "Cleared"


class AuditResult(StrEnum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILURE = "failure"


class HealthState(StrEnum):
    """Overall /api/system/health/live state (D-009). Response-only —
    never persisted."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
