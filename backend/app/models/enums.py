from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "Admin"
    OPERATOR = "Operator"


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


class DetectionStatus(StrEnum):
    UNVERIFIED = "Unverified"
    ONGOING = "Ongoing"
    DISMISSED = "Dismissed"
    RESOLVED = "Resolved"
