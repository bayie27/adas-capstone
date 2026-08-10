"""07_PKG_reports.md Step 4 — shared synchronous-export orchestration:
row-limit enforcement and the REPORT_EXPORT / AUDIT_EXPORT audit record
every export attempt writes, regardless of outcome (success, over-limit
rejection, or failure).
"""

from typing import Literal

from sqlmodel import Session

from app.core.config import settings
from app.core.errors import AppHTTPException
from app.models import AuditResult, User
from app.services import audit as audit_service

ReportFormat = Literal["csv", "pdf"]


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
):
    """D-010 — "every export attempt writes REPORT_EXPORT (or AUDIT_EXPORT)
    with report type, format, filters, sorting, row count, sync/job mode,
    and result." Adds to the caller's session; does not commit — same
    contract as `app.services.audit.record`.
    """
    detail: dict = {
        "report_type": report_type,
        "format": format,
        "mode": mode,
        "filters": filters,
    }
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
