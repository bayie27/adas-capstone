from fastapi import APIRouter

from app.schemas.events import (
    AlertStatusUpdateData,
    CameraStatusUpdateData,
    ConnectionReadyData,
    EventEnvelope,
    EventType,
    IncidentPayload,
    ReAlarmData,
    SnoozeActivatedData,
)

router = APIRouter(prefix="/api/events", tags=["Realtime Events (docs only)"])

_PAYLOAD_SCHEMAS = {
    EventType.CONNECTION_READY: ConnectionReadyData,
    EventType.NEW_DETECTION: IncidentPayload,
    EventType.ALERT_STATUS_UPDATE: AlertStatusUpdateData,
    EventType.CAMERA_STATUS_UPDATE: CameraStatusUpdateData,
    EventType.SNOOZE_ACTIVATED: SnoozeActivatedData,
    EventType.RE_ALARM: ReAlarmData,
}


@router.get("/schema")
def get_event_schemas() -> dict:
    """Documentation only — never consumed at runtime by the dashboard.

    FastAPI does not add schemas to the OpenAPI document for a bare
    `add_api_websocket_route`, so `/ws/alerts`'s envelope and six payload
    shapes (01_CONTRACTS.md §9) would otherwise have no machine-readable
    contract for the frontend to generate types against.
    """
    return {
        "envelope": EventEnvelope.model_json_schema(),
        "payloads": {
            event_type.value: schema.model_json_schema()
            for event_type, schema in _PAYLOAD_SCHEMAS.items()
        },
    }
