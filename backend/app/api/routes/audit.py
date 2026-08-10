from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlmodel import Session, col, func, select

from app.api.dependencies import get_current_admin
from app.core.db import get_session
from app.core.errors import AppHTTPException
from app.core.types import parse_utc_query_datetime
from app.models import AuditAction, AuditLog, AuditResult, User
from app.schemas import AuditLogListResponse, AuditLogRead
from app.services.filters import apply_sort, validate_common_filters
from app.services.formatting import format_user_name
from app.services.reports.common import check_row_limit, record_export_attempt
from app.services.reports.csv_writer import csv_response
from app.services.reports.pdf_writer import build_audit_pdf

router = APIRouter(
    prefix="/api/audit-logs",
    tags=["Audit"],
    dependencies=[Depends(get_current_admin)],
)

# 01_CONTRACTS.md §1.5 — allowlisted `sort_by` fields for the audit viewer
# and its export. `audit_id` is always applied as a secondary tie-breaker
# (Step 11's "equal-timestamp rows can never shuffle between pages") even
# when a caller sorts by something else.
AUDIT_SORT_FIELDS = {
    "audit_id",
    "created_at",
    "action",
    "result",
    "user_id",
    "target_type",
}


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _apply_audit_filters(
    stmt,
    *,
    action: list[AuditAction] | None,
    user_id: list[int] | None,
    result: list[AuditResult] | None,
    target_type: str | None,
    target_ref: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    search: str | None,
):
    if action:
        stmt = stmt.where(col(AuditLog.action).in_([a.value for a in action]))
    if user_id:
        stmt = stmt.where(col(AuditLog.user_id).in_(user_id))
    if result:
        stmt = stmt.where(col(AuditLog.result).in_([r.value for r in result]))
    if target_type:
        stmt = stmt.where(col(AuditLog.target_type) == target_type)
    if target_ref:
        stmt = stmt.where(col(AuditLog.target_ref) == target_ref)
    if start_date:
        stmt = stmt.where(
            col(AuditLog.created_at) >= parse_utc_query_datetime(start_date)
        )
    if end_date:
        stmt = stmt.where(
            col(AuditLog.created_at) <= parse_utc_query_datetime(end_date)
        )
    if search:
        stmt = stmt.where(
            col(AuditLog.username).icontains(search)
            | col(AuditLog.target_ref).icontains(search)
            | col(AuditLog.detail).icontains(search)
        )
    return stmt


@router.get("/", response_model=AuditLogListResponse)
def list_audit_logs(
    action: list[AuditAction] | None = Query(
        default=None,
        description="Filter by one or more actions, e.g. ?action=LOGIN_SUCCESS&action=LOGOUT",
    ),
    user_id: list[int] | None = Query(
        default=None,
        description="Filter by one or more actor user IDs, e.g. ?user_id=1&user_id=2",
    ),
    result: list[AuditResult] | None = Query(
        default=None,
        description="Filter by one or more results, e.g. ?result=denied&result=failure",
    ),
    target_type: str | None = Query(default=None, min_length=1, max_length=100),
    target_ref: str | None = Query(default=None, min_length=1, max_length=100),
    start_date: datetime | None = Query(
        default=None, description="ISO 8601 format, e.g. 2026-01-01T00:00:00Z"
    ),
    end_date: datetime | None = Query(
        default=None, description="ISO 8601 format, e.g. 2026-12-31T23:59:59Z"
    ),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
        description="Matches against username, target_ref, and detail",
    ),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> AuditLogListResponse:
    """Admin only — Operators get 403, not an empty list (01_CONTRACTS.md
    §5.7). Viewing this endpoint is itself never audited: that would be
    recursive noise. Exporting it (P6) is."""
    validate_common_filters(start_date=start_date, end_date=end_date, user_ids=user_id)

    query = _apply_audit_filters(
        select(AuditLog),
        action=action,
        user_id=user_id,
        result=result,
        target_type=target_type,
        target_ref=target_ref,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )

    total_filtered = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()

    # Stable pagination: equal-timestamp rows can never shuffle between
    # pages (01_CONTRACTS.md Step 11) — `audit_id` is always the tie-break.
    query = apply_sort(
        query,
        AuditLog,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed=AUDIT_SORT_FIELDS,
        tie_breaker="audit_id",
    )
    logs = session.exec(query.offset(offset).limit(limit)).all()

    return AuditLogListResponse(
        total_filtered=total_filtered,
        items=[AuditLogRead.model_validate(log) for log in logs],
    )


def _audit_filters_dict(
    *,
    action: list[AuditAction] | None,
    user_id: list[int] | None,
    result: list[AuditResult] | None,
    target_type: str | None,
    target_ref: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    search: str | None,
) -> dict:
    return {
        "action": [a.value for a in action] if action else [],
        "user_id": list(user_id or ()),
        "result": [r.value for r in result] if result else [],
        "target_type": target_type,
        "target_ref": target_ref,
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "search": search,
    }


def _audit_filters_summary(
    filters: dict, *, sort_by: str, sort_order: str
) -> list[str]:
    lines = []
    if filters["action"]:
        lines.append("Action: " + ", ".join(filters["action"]))
    if filters["user_id"]:
        lines.append("User IDs: " + ", ".join(str(u) for u in filters["user_id"]))
    if filters["result"]:
        lines.append("Result: " + ", ".join(filters["result"]))
    if filters["target_type"]:
        lines.append(f"Target Type: {filters['target_type']}")
    if filters["target_ref"]:
        lines.append(f"Target Ref: {filters['target_ref']}")
    if filters["start_date"] or filters["end_date"]:
        lines.append(
            f"Date range: {filters['start_date'] or '…'} to {filters['end_date'] or '…'}"
        )
    if filters["search"]:
        lines.append(f"Search: {filters['search']!r}")
    lines.append(f"Sort: {sort_by} {sort_order}")
    return lines


@router.get("/export")
def export_audit_logs(
    request: Request,
    action: list[AuditAction] | None = Query(default=None),
    user_id: list[int] | None = Query(default=None),
    result: list[AuditResult] | None = Query(default=None),
    target_type: str | None = Query(default=None, min_length=1, max_length=100),
    target_ref: str | None = Query(default=None, min_length=1, max_length=100),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    format: str = Query(default="csv", pattern="^(csv|pdf)$"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin),
):
    """Admin-only export of the append-only audit trail (01_CONTRACTS.md
    §5.7). Same filters as the list endpoint (D-010 screen/export parity).

    **The recursion trap**: this call itself writes an `AUDIT_EXPORT` row.
    To guarantee that row never appears in its own export, the set of
    matching `audit_id`s is captured *before* the new row is created or
    committed, and the actual export re-selects strictly by that static id
    list — never by re-evaluating the original filter predicate, which
    could otherwise pick up the just-inserted row depending on commit
    timing.
    """
    validate_common_filters(start_date=start_date, end_date=end_date, user_ids=user_id)

    filters_dict = _audit_filters_dict(
        action=action,
        user_id=user_id,
        result=result,
        target_type=target_type,
        target_ref=target_ref,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )
    sort_dict = {"sort_by": sort_by, "sort_order": sort_order}
    source_ip = _client_ip(request)

    id_stmt = _apply_audit_filters(
        select(AuditLog.audit_id),
        action=action,
        user_id=user_id,
        result=result,
        target_type=target_type,
        target_ref=target_ref,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )
    # Materialized BEFORE the AUDIT_EXPORT row is created — this snapshot is
    # what the recursion trap depends on.
    matching_ids = list(session.exec(id_stmt).all())
    row_count = len(matching_ids)

    try:
        check_row_limit(row_count, format=format)
    except AppHTTPException:
        record_export_attempt(
            session,
            action="AUDIT_EXPORT",
            report_type="audit",
            format=format,
            actor=current_user,
            filters=filters_dict,
            sort=sort_dict,
            row_count=row_count,
            result=AuditResult.FAILURE,
            failure_category="row_limit_exceeded",
            source_ip=source_ip,
        )
        session.commit()
        raise

    record_export_attempt(
        session,
        action="AUDIT_EXPORT",
        report_type="audit",
        format=format,
        actor=current_user,
        filters=filters_dict,
        sort=sort_dict,
        row_count=row_count,
        result=AuditResult.SUCCESS,
        source_ip=source_ip,
    )
    session.commit()

    stmt = select(AuditLog).where(col(AuditLog.audit_id).in_(matching_ids))
    stmt = apply_sort(
        stmt,
        AuditLog,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed=AUDIT_SORT_FIELDS,
        tie_breaker="audit_id",
    )

    def _actor(log: AuditLog) -> str | None:
        if log.username is None:
            return None
        return f"{log.username} ({log.role})" if log.role else log.username

    def _target(log: AuditLog) -> str | None:
        if log.target_type is None and log.target_ref is None:
            return None
        return f"{log.target_type or '?'}:{log.target_ref or '?'}"

    if format == "pdf":
        logs = session.exec(stmt).all()
        rows = [
            [
                log.audit_id,
                log.created_at.isoformat(),
                _actor(log),
                log.action,
                _target(log),
                log.result,
                log.detail,
            ]
            for log in logs
        ]
        pdf_bytes = build_audit_pdf(
            rows=rows,
            filters_summary=_audit_filters_summary(
                filters_dict, sort_by=sort_by, sort_order=sort_order
            ),
            requested_by=format_user_name(current_user) or current_user.username,
            generated_at=datetime.now(UTC),
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="adas_audit_export.pdf"'
            },
        )

    rows_iter = (
        [
            log.audit_id,
            log.created_at.isoformat(),
            _actor(log),
            log.action,
            _target(log),
            log.result,
            log.detail,
        ]
        for log in session.exec(stmt).yield_per(500)
    )
    return csv_response(
        "adas_audit_export.csv",
        [
            "Audit ID",
            "Created At",
            "Actor",
            "Action",
            "Target",
            "Result",
            "Detail",
        ],
        rows_iter,
    )
