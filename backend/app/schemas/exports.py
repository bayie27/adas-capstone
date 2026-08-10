"""07_PKG_reports.md Step 5 — request/response shapes for the async export
job endpoints (`/api/exports/jobs`)."""

from datetime import datetime
from typing import Literal

from pydantic import model_validator
from sqlmodel import SQLModel

ExportJobReportType = Literal["incidents", "dashboard", "performance", "audit"]
ExportJobFormat = Literal["csv", "pdf"]


class ExportJobCreate(SQLModel):
    """POST /api/exports/jobs body. The same filter/sort fields the
    matching synchronous export route accepts as query parameters — a
    report_type ignores fields that don't apply to it (e.g. `search` on a
    dashboard job)."""

    model_config = {"extra": "forbid"}

    report_type: ExportJobReportType
    format: ExportJobFormat
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: list[str] | None = None
    camera_id: list[int] | None = None
    user_id: list[int] | None = None
    search: str | None = None
    sort_by: str | None = None
    sort_order: str | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "ExportJobCreate":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError(
                "Invalid date range: `start_date` must be earlier than or equal to `end_date`."
            )
        return self


class ExportJobCreateResponse(SQLModel):
    job_id: str
    status: str


class ExportJobRead(SQLModel):
    """Status/progress polling response. `artifact_path` is deliberately
    absent — it is never returned to a client (01_CONTRACTS.md §3.8)."""

    job_id: str
    report_type: str
    format: str
    status: str
    progress_current: int
    progress_total: int | None
    failure_category: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime | None


class RetrainingExportRequest(SQLModel):
    """POST /api/exports/retraining body — same date/camera filters as
    every other report, no status/search (labels come from
    detection_status itself, per D-010's mapping table)."""

    model_config = {"extra": "forbid"}

    start_date: datetime | None = None
    end_date: datetime | None = None
    camera_id: list[int] | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "RetrainingExportRequest":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError(
                "Invalid date range: `start_date` must be earlier than or equal to `end_date`."
            )
        return self
