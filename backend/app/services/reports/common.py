"""07_PKG_reports.md Step 4 — shared synchronous-export orchestration:
row-limit enforcement and the REPORT_EXPORT / AUDIT_EXPORT audit record
every export attempt writes, regardless of outcome (success, over-limit
rejection, or failure).
"""

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from sqlmodel import Session

from app.core.config import settings
from app.core.errors import AppHTTPException
from app.models import AuditResult, User
from app.services import audit as audit_service
from app.services.cameras import resolve_camera_names

ReportFormat = Literal["csv", "pdf"]


def format_export_datetime(value: datetime | None) -> str | None:
    """Human-readable local timestamp for a report cell, e.g.
    "Sep 03, 2026 02:15 PM" — the CDRRMO-facing exports show this instead
    of a raw UTC ISO string. Only applied at the export row-building
    boundary, never inside a shared data-computation function that also
    backs a live JSON API (which must keep returning raw values)."""
    if value is None:
        return None
    tz = ZoneInfo(settings.REPORT_LOCAL_TIMEZONE)
    return value.astimezone(tz).strftime("%b %d, %Y %I:%M %p")


def format_confidence_pct(value: float | None) -> str | None:
    """Human-readable confidence/precision percentage, e.g. "87.3%" instead
    of the raw decimal `0.8734`."""
    if value is None:
        return None
    return f"{value * 100:.1f}%"


def row_limit_for(format: ReportFormat) -> int:
    return (
        settings.EXPORT_PDF_MAX_ROWS
        if format == "pdf"
        else settings.EXPORT_CSV_MAX_ROWS
    )


def check_row_limit(row_count: int, *, format: ReportFormat) -> None:
    """07_PKG_reports.md Step 4 — over the configured synchronous limit,
    reject with 413 naming the async jobs endpoint as the alternative.
    Raises `AppHTTPException`; the caller is responsible for auditing the
    rejected attempt before letting this propagate."""
    limit = row_limit_for(format)
    if row_count > limit:
        raise AppHTTPException(
            413,
            (
                f"This export has {row_count} rows, over the synchronous "
                f"{format.upper()} limit of {limit}. Use POST /api/exports/jobs "
                "for a larger export."
            ),
            code="PAYLOAD_TOO_LARGE",
        )


def record_export_attempt(
    session: Session,
    *,
    action: str,
    report_type: str,
    format: ReportFormat,
    actor: User,
    filters: dict,
    sort: dict | None = None,
    row_count: int | None,
    mode: str = "sync",
    result: AuditResult = AuditResult.SUCCESS,
    failure_category: str | None = None,
    job_id: str | None = None,
    source_ip: str | None = None,
    camera_names: dict[str, str] | None = None,
):
    """D-010 — "every export attempt writes REPORT_EXPORT (or AUDIT_EXPORT)
    with report type, format, filters, sorting, row count, sync/job mode,
    and result." Adds to the caller's session; does not commit — same
    contract as `app.services.audit.record`.

    `camera_names` lets a caller that already resolved the map (a PDF path
    also building the filter-summary header, P25 Step 6) pass it through so
    the id->name lookup runs once per export, not twice. Omitted, it's
    resolved here so CSV-only callers stay a one-liner.
    """
    detail: dict = {
        "report_type": report_type,
        "format": format,
        "mode": mode,
        "filters": filters,
    }
    camera_ids = filters.get("camera_id") or ()
    if camera_ids:
        names = (
            camera_names
            if camera_names is not None
            else resolve_camera_names(session, camera_ids)
        )
        if names:
            filters["camera_names"] = names
    if sort is not None:
        detail["sort"] = sort
    if row_count is not None:
        detail["row_count"] = row_count
    if job_id is not None:
        detail["job_id"] = job_id
    if failure_category is not None:
        detail["failure_category"] = failure_category

    return audit_service.record(
        session,
        action=action,
        result=result,
        actor=actor,
        target_type="export",
        target_ref=job_id or report_type,
        detail=detail,
        source_ip=source_ip,
    )
