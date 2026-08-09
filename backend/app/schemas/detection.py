from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models import DetectionLogBase


class DetectionLogCreate(SQLModel):
    """v1 legacy AI-engine payload — 01_CONTRACTS.md §6.1, frozen.

    `snapshot_path` is the wire field name (a bare filename resolved against
    LEGACY_SNAPSHOT_DIR); internal.py maps it onto the table's `snapshot_key`
    column when persisting, alongside a backend-generated `source_event_id`.
    """

    camera_id: int
    detected_at: datetime
    snapshot_path: str = Field(min_length=1)
    confidence_score: float = Field(ge=0.0, le=1.0)


class DetectionLogRead(DetectionLogBase):
    log_id: int
    source_event_id: str
    detection_status: str
    verified_by_id: int | None = None
    verified_by_name: str | None = None
    verified_at: datetime | None = None
    closed_by_id: int | None = None
    closed_by_name: str | None = None
    closed_at: datetime | None = None
    snoozed_at: datetime | None = None
    snoozed_until: datetime | None = None
    snoozed_by_id: int | None = None
    camera_name: str | None = None


class DetectionLogListResponse(SQLModel):
    total_filtered: int
    logs: list[DetectionLogRead]
