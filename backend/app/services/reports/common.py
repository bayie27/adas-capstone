"""07_PKG_reports.md Step 4 — shared synchronous-export orchestration:
row-limit enforcement and the REPORT_EXPORT / AUDIT_EXPORT audit record
every export attempt writes, regardless of outcome (success, over-limit
rejection, or failure).
"""

import json
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


# Plain-language labels for the audit trail's action codes (app/models/audit.py
# AUDIT_ACTIONS). The audit export is CDRRMO's compliance record, not a
# developer log — a reader who is not a programmer still needs to be able
# to tell what happened from this column alone.
_AUDIT_ACTION_LABELS = {
    "LOGIN_SUCCESS": "Signed in",
    "LOGIN_FAILURE": "Failed sign-in attempt",
    "LOGOUT": "Signed out",
    "ALERT_CONFIRM": "Confirmed incident",
    "ALERT_DISMISS": "Dismissed incident",
    "ALERT_RESOLVE": "Resolved incident",
    "ALERT_CORRECTION": "Corrected incident status",
    "ALERT_SNOOZE": "Snoozed alerts",
    "CAMERA_CREATE": "Added camera",
    "CAMERA_UPDATE": "Updated camera",
    "CAMERA_ENABLE": "Enabled camera",
    "CAMERA_DISABLE": "Disabled camera",
    "CAMERA_DELETE": "Removed camera",
    "CAMERA_RESTORE": "Restored camera",
    "REPORT_EXPORT": "Exported a report",
    "AUDIT_EXPORT": "Exported the audit log",
    "USER_CREATE": "Added a user",
    "USER_UPDATE": "Updated a user",
    "USER_ENABLE": "Enabled a user",
    "USER_DISABLE": "Disabled a user",
    "USER_ROLE_CHANGE": "Changed a user's role",
    "USER_PASSWORD_RESET": "Reset a user's password",
    "USER_PROFILE_UPDATE": "Updated a profile",
    "USER_PASSWORD_CHANGE": "Changed password",
    "ALARM_SETTINGS_UPDATE": "Updated alarm settings",
    "BACKUP_TRIGGER": "Started a backup",
    "RESTORE_TRIGGER": "Started a restore",
}

_AUDIT_RESULT_LABELS = {
    "success": "Success",
    "denied": "Denied",
    "failure": "Failed",
}


def format_audit_action(action: str) -> str:
    """Plain-language label for an audit action code, falling back to a
    title-cased version of the code itself for anything not in the map
    (never hides an action the code doesn't yet have a label for)."""
    return _AUDIT_ACTION_LABELS.get(action, action.replace("_", " ").title())


def format_audit_result(result: str | None) -> str | None:
    if result is None:
        return None
    return _AUDIT_RESULT_LABELS.get(result, result.title())


def format_audit_target(target_type: str | None, target_ref: str | None) -> str | None:
    """ "user:5" -> "User: 5" — the record a given audit entry acted on,
    written the way a person would describe it rather than as a raw
    type:id pair."""
    if target_type is None and target_ref is None:
        return None
    type_label = (target_type or "Record").replace("_", " ").title()
    return f"{type_label}: {target_ref}" if target_ref else type_label


def format_audit_detail(raw: str | None) -> str:
    """Turns the audit trail's raw JSON `detail` blob into a plain-language
    list, e.g. `{"report_type": "audit", "format": "pdf", "row_count": 12}`
    becomes "Report type: audit; Format: pdf; Row count: 12" — a generic
    transform (snake_case -> Title Case, drop empty/null values) rather
    than a per-action template, so it stays correct as new action types
    and detail shapes are added without this function needing to know
    about them."""
    if not raw:
        return "No additional details"
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
    if not isinstance(data, dict) or not data:
        return "No additional details"
    parts = _humanize_detail_pairs(data)
    return "; ".join(parts) if parts else "No additional details"


def _humanize_detail_pairs(data: dict) -> list[str]:
    parts: list[str] = []
    for key, value in data.items():
        if value in (None, "", [], {}):
            continue
        # Nested dicts (e.g. "filters", "sort") are flattened one level
        # rather than prefixed with the parent key's label — "sort_by" is
        # already self-explanatory, and prefixing would read as "Sort
        # Sort by: ...".
        if isinstance(value, dict):
            parts.extend(_humanize_detail_pairs(value))
            continue
        label = key.replace("_", " ").capitalize()
        if isinstance(value, list):
            parts.append(f"{label}: {', '.join(str(item) for item in value)}")
        elif isinstance(value, bool):
            parts.append(f"{label}: {'Yes' if value else 'No'}")
        else:
            parts.append(f"{label}: {value}")
    return parts


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
