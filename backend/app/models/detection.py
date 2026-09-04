from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, Column, Index, text
from sqlmodel import Field, Relationship, SQLModel

from app.core.types import UtcDateTime
from app.models.camera import Camera
from app.models.enums import DetectionStatus
from app.models.user import User


class DetectionLogBase(SQLModel):
    camera_id: int = Field(
        foreign_key="camera.camera_id", index=True, ondelete="RESTRICT"
    )
    detected_at: datetime = Field(sa_type=UtcDateTime, index=True)
    snapshot_key: str = Field(min_length=1)
    confidence_score: float = Field(ge=0.0, le=1.0)


class DetectionLog(DetectionLogBase, table=True):
    __tablename__ = "detection_log"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_detection_confidence_score_range",
        ),
        CheckConstraint(
            "detection_status IN ('Unverified', 'Ongoing', 'Dismissed', 'Cleared')",
            name="ck_detection_status_valid",
        ),
        Index("ux_detection_source_event", "source_event_id", unique=True),
        Index(
            "ux_detection_open_camera",
            "camera_id",
            unique=True,
            sqlite_where=text("detection_status IN ('Unverified', 'Ongoing')"),
        ),
        Index("ix_detection_status_time", "detection_status", "detected_at"),
        Index("ix_detection_camera_time", "camera_id", "detected_at"),
        Index("ix_detection_verified_by", "verified_by_id"),
        Index("ix_detection_closed_by", "closed_by_id"),
        Index(
            "ix_detection_snooze_due",
            "snoozed_until",
            sqlite_where=text("snoozed_until IS NOT NULL"),
        ),
    )

    log_id: int | None = Field(default=None, primary_key=True)
    source_event_id: str = Field(unique=True)

    detection_status: str = Field(default=DetectionStatus.UNVERIFIED.value)

    # Audit trail
    verified_by_id: int | None = Field(
        default=None, foreign_key="user.user_id", ondelete="RESTRICT"
    )
    verified_at: datetime | None = Field(default=None, sa_type=UtcDateTime)
    closed_by_id: int | None = Field(
        default=None, foreign_key="user.user_id", ondelete="RESTRICT"
    )
    closed_at: datetime | None = Field(default=None, sa_type=UtcDateTime)

    # Snooze (D-004)
    snoozed_at: datetime | None = Field(default=None, sa_type=UtcDateTime)
    snoozed_until: datetime | None = Field(default=None, sa_type=UtcDateTime)
    snoozed_by_id: int | None = Field(
        default=None, foreign_key="user.user_id", ondelete="RESTRICT"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=UtcDateTime
    )
    updated_at: datetime = Field(
        default=None,
        sa_column=Column(
            UtcDateTime,
            default=lambda: datetime.now(UTC),
            onupdate=lambda: datetime.now(UTC),
            nullable=False,
        ),
    )

    # Relationships
    camera: Camera | None = Relationship(back_populates="detections")
    verified_by: User | None = Relationship(
        back_populates="verified_detections",
        sa_relationship_kwargs={"foreign_keys": "[DetectionLog.verified_by_id]"},
    )
    closed_by: User | None = Relationship(
        back_populates="closed_detections",
        sa_relationship_kwargs={"foreign_keys": "[DetectionLog.closed_by_id]"},
    )
    snoozed_by: User | None = Relationship(
        back_populates="snoozed_detections",
        sa_relationship_kwargs={"foreign_keys": "[DetectionLog.snoozed_by_id]"},
    )
