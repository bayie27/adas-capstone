from datetime import datetime

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.core.validation import reject_null_bytes


class DetectionLogCreate(SQLModel):
    """v1 legacy AI-engine payload — 01_CONTRACTS.md §6.1, frozen.

    `snapshot_path` is the wire field name (a bare filename resolved against
    LEGACY_SNAPSHOT_DIR); internal.py maps it onto the table's `snapshot_key`
    column when persisting, alongside a backend-generated `source_event_id`.

    `extra="forbid"` is what lets `DetectionLogCreate | DetectionLogCreateV2`
    discriminate cleanly on Pydantic's own "smart union" validation instead
    of dict-sniffing a raw body for `source_event_id`: a v2-shaped payload
    carries `source_event_id`/`snapshot_key`, which this model would
    otherwise silently ignore.
    """

    model_config = {"extra": "forbid"}

    camera_id: int
    detected_at: datetime
    snapshot_path: str = Field(min_length=1)
    confidence_score: float = Field(ge=0.0, le=1.0)

    @field_validator("snapshot_path")
    @classmethod
    def snapshot_path_no_null_bytes(cls, v: str) -> str:
        return reject_null_bytes(v)


class DetectionLogCreateV2(SQLModel):
    """v2 idempotent AI-engine payload — 01_CONTRACTS.md §6.3. The AI engine
    generates `source_event_id` once per genuine event and reuses it for
    every retry."""

    model_config = {"extra": "forbid"}

    source_event_id: str = Field(min_length=1)
    camera_id: int
    detected_at: datetime
    snapshot_key: str = Field(min_length=1)
    confidence_score: float = Field(ge=0.0, le=1.0)

    @field_validator("source_event_id", "snapshot_key")
    @classmethod
    def no_null_bytes(cls, v: str) -> str:
        return reject_null_bytes(v)


class DetectionLogRead(SQLModel):
    """Operator-facing incident detail. Deliberately does NOT inherit
    DetectionLogBase — it never exposes `snapshot_key` or any filesystem
    path (05_PKG_incidents_cameras.md Step 9); `snapshot_url` is an
    authorized API path instead."""

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
    snoozed_at: datetime | None = None
    snoozed_until: datetime | None = None
    snoozed_by_id: int | None = None
    created_at: datetime
    updated_at: datetime


class DetectionLogListResponse(SQLModel):
    total_filtered: int
    logs: list[DetectionLogRead]


class AlertSnoozeRequest(SQLModel):
    """POST /api/alerts/{log_id}/snooze accepts no body — duration comes
    from the actor's saved settings, never the client (D-004). `extra`
    forbids a client-supplied duration; sending one is a 422."""

    model_config = {"extra": "forbid"}
