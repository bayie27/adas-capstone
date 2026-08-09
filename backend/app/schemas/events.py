"""01_CONTRACTS.md §9 — the WebSocket event envelope and the six typed
payload models it carries (04_PKG_realtime.md Step 1).

`data` stays a plain dict on the envelope itself (matching the wire shape
exactly), but every caller builds it by handing a typed payload model to
`make_event()`, so `event_id`/`occurred_at` can never be forgotten and every
event type has a real schema instead of an arbitrary dict — see
GET /api/events/schema for where these are surfaced for the frontend.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel

from app.models import UserRole


class EventType(StrEnum):
    CONNECTION_READY = "CONNECTION_READY"
    NEW_DETECTION = "NEW_DETECTION"
    ALERT_STATUS_UPDATE = "ALERT_STATUS_UPDATE"
    CAMERA_STATUS_UPDATE = "CAMERA_STATUS_UPDATE"
    SNOOZE_ACTIVATED = "SNOOZE_ACTIVATED"
    RE_ALARM = "RE_ALARM"
    # 08_PKG_backup_ops.md Step 5 — sent just before a restore takes the
    # backend offline, so connected dashboards can warn the operator
    # before the socket drops.
    MAINTENANCE_NOTICE = "MAINTENANCE_NOTICE"


class ConnectionReadyData(BaseModel):
    connection_id: str
    server_time: datetime
    user_id: int
    role: UserRole


class IncidentPayload(BaseModel):
    """01_CONTRACTS.md §9.3 — the minimum incident field set, shared by
    NEW_DETECTION and (as a base for) ALERT_STATUS_UPDATE."""

    log_id: int
    source_event_id: str
    camera_id: int
    camera_name: str | None = None
    detected_at: datetime
    confidence_score: float
    detection_status: str
    snapshot_url: str
    verified_by_id: int | None = None
    verified_by_name: str | None = None
    verified_at: datetime | None = None
    closed_by_id: int | None = None
    closed_by_name: str | None = None
    closed_at: datetime | None = None
    snoozed_until: datetime | None = None
    snoozed_by_id: int | None = None
    created_at: datetime
    updated_at: datetime


class AlertStatusUpdateData(IncidentPayload):
    action: str
    handled_by: str | None = None
    handled_at: datetime | None = None


class CameraStatusUpdateData(BaseModel):
    camera_id: int
    camera_name: str
    is_enabled: bool
    desired_ai_state: str
    desired_state_reason: str | None = None
    connection_status: str
    ai_status: str
    cooldown_until: datetime | None = None
    config_version: int


class SnoozeActivatedData(BaseModel):
    log_id: int
    camera_id: int
    snoozed_by: int | None = None
    snoozed_until: datetime


class ReAlarmData(BaseModel):
    log_id: int
    camera_id: int


class MaintenanceNoticeData(BaseModel):
    message: str
    backup_id: str


class EventEnvelope(BaseModel):
    version: Literal[1] = 1
    event_id: str
    type: EventType
    occurred_at: datetime
    data: dict[str, Any]


def make_event[
    T: (
        ConnectionReadyData,
        IncidentPayload,
        AlertStatusUpdateData,
        CameraStatusUpdateData,
        SnoozeActivatedData,
        ReAlarmData,
        MaintenanceNoticeData,
    )
](event_type: EventType, data: T) -> EventEnvelope:
    """The only way to build an envelope — `event_id` and `occurred_at` are
    generated here so no call site can forget either."""
    return EventEnvelope(
        event_id=str(uuid.uuid4()),
        type=event_type,
        occurred_at=datetime.now(UTC),
        data=data.model_dump(mode="json"),
    )
