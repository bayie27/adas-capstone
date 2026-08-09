"""04_PKG_realtime.md Step 6 — builds the typed WebSocket payloads from ORM
rows, so every broadcast call site shares one implementation instead of
hand-building a dict. Kept separate from `app.services.realtime` so the
connection/queue mechanics stay ignorant of `DetectionLog`/`Camera`.

`detection_status` is read straight off `log.detection_status` (already a
plain string field, not an enum column — see `app.models.detection`). The
old code's `getattr(log.detection_status, "value", log.detection_status)`
was defensive against a StrEnum member still sitting in that attribute
in-memory; every call site broadcasts only after `session.commit()` +
`session.refresh(log)`, at which point the attribute is always the plain
string SQLite stored, so that fallback is dead code and is deleted here.
"""

from app.models import Camera, DetectionLog
from app.schemas.events import (
    AlertStatusUpdateData,
    CameraStatusUpdateData,
    EventEnvelope,
    EventType,
    IncidentPayload,
    ReAlarmData,
    SnoozeActivatedData,
    make_event,
)
from app.services.formatting import format_user_name


def _incident_payload_kwargs(log: DetectionLog, *, camera_name: str | None) -> dict:
    return {
        "log_id": log.log_id,
        "source_event_id": log.source_event_id,
        "camera_id": log.camera_id,
        "camera_name": camera_name,
        "detected_at": log.detected_at,
        "confidence_score": log.confidence_score,
        "detection_status": log.detection_status,
        # An authorized API path, never an OS path (01_CONTRACTS.md §9.3).
        # The route itself is P4's job; the shape is frozen now.
        "snapshot_url": f"/api/alerts/{log.log_id}/snapshot",
        "verified_by_id": log.verified_by_id,
        "verified_by_name": format_user_name(log.verified_by),
        "verified_at": log.verified_at,
        "closed_by_id": log.closed_by_id,
        "closed_by_name": format_user_name(log.closed_by),
        "closed_at": log.closed_at,
        "snoozed_until": log.snoozed_until,
        "snoozed_by_id": log.snoozed_by_id,
        "created_at": log.created_at,
        "updated_at": log.updated_at,
    }


def new_detection_event(log: DetectionLog, *, camera_name: str | None) -> EventEnvelope:
    data = IncidentPayload(**_incident_payload_kwargs(log, camera_name=camera_name))
    return make_event(EventType.NEW_DETECTION, data)


def alert_status_update_event(
    log: DetectionLog, *, action: str, camera_name: str | None
) -> EventEnvelope:
    """`action` is one of the §8 catalog's four incident-transition actions
    (ALERT_CONFIRM / ALERT_DISMISS / ALERT_RESOLVE / ALERT_CORRECTION); the
    actor/timestamp semantics for `handled_by`/`handled_at` follow §10.1 —
    a confirm reports the verifier, every other transition reports the
    closer."""
    if action == "ALERT_CONFIRM":
        handled_by = format_user_name(log.verified_by)
        handled_at = log.verified_at
    else:
        handled_by = format_user_name(log.closed_by)
        handled_at = log.closed_at

    data = AlertStatusUpdateData(
        **_incident_payload_kwargs(log, camera_name=camera_name),
        action=action,
        handled_by=handled_by,
        handled_at=handled_at,
    )
    return make_event(EventType.ALERT_STATUS_UPDATE, data)


def snooze_activated_event(log: DetectionLog) -> EventEnvelope:
    data = SnoozeActivatedData(
        log_id=log.log_id,
        camera_id=log.camera_id,
        snoozed_by=log.snoozed_by_id,
        snoozed_until=log.snoozed_until,
    )
    return make_event(EventType.SNOOZE_ACTIVATED, data)


def re_alarm_event(log: DetectionLog) -> EventEnvelope:
    data = ReAlarmData(log_id=log.log_id, camera_id=log.camera_id)
    return make_event(EventType.RE_ALARM, data)


def camera_status_update_event(camera: Camera) -> EventEnvelope:
    data = CameraStatusUpdateData(
        camera_id=camera.camera_id,
        camera_name=camera.camera_name,
        is_enabled=camera.is_enabled,
        desired_ai_state=camera.desired_ai_state,
        desired_state_reason=camera.desired_state_reason,
        connection_status=camera.connection_status,
        ai_status=camera.ai_status,
        cooldown_until=camera.cooldown_until,
        config_version=camera.config_version,
    )
    return make_event(EventType.CAMERA_STATUS_UPDATE, data)
