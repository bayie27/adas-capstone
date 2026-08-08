from datetime import UTC, datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel

from app.core.types import UtcDateTime


class ExportJob(SQLModel, table=True):
    """D-010 — async export job tracking. `artifact_path` is under
    EXPORT_DIR and is never returned to a client directly."""

    __tablename__ = "export_job"
    __table_args__ = (
        CheckConstraint(
            "report_type IN ('incidents', 'dashboard', 'performance', 'audit', 'retraining')",
            name="ck_export_job_report_type_valid",
        ),
        CheckConstraint(
            "format IN ('csv', 'pdf', 'zip')", name="ck_export_job_format_valid"
        ),
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'expired')",
            name="ck_export_job_status_valid",
        ),
    )

    job_id: str = Field(primary_key=True)
    requested_by_id: int = Field(foreign_key="user.user_id", ondelete="RESTRICT")
    report_type: str
    format: str
    filters_json: str | None = Field(default=None)
    sort_json: str | None = Field(default=None)
    status: str = Field(default="queued")
    progress_current: int = Field(default=0)
    progress_total: int | None = Field(default=None)
    artifact_path: str | None = Field(default=None)
    artifact_bytes: int | None = Field(default=None)
    failure_category: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=UtcDateTime
    )
    started_at: datetime | None = Field(default=None, sa_type=UtcDateTime)
    completed_at: datetime | None = Field(default=None, sa_type=UtcDateTime)
    expires_at: datetime | None = Field(default=None, sa_type=UtcDateTime)
