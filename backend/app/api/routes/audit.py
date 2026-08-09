from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, col, func, select

from app.api.dependencies import get_current_admin
from app.core.db import get_session
from app.core.types import parse_utc_query_datetime
from app.models import AuditAction, AuditLog, AuditResult
from app.schemas import AuditLogListResponse, AuditLogRead
from app.services.filters import validate_common_filters

router = APIRouter(
    prefix="/api/audit-logs",
    tags=["Audit"],
    dependencies=[Depends(get_current_admin)],
)


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
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> AuditLogListResponse:
    """Admin only — Operators get 403, not an empty list (01_CONTRACTS.md
    §5.7). Viewing this endpoint is itself never audited: that would be
    recursive noise. Exporting it (P6) is."""
    validate_common_filters(start_date=start_date, end_date=end_date, user_ids=user_id)

    query = select(AuditLog)

    if action:
        query = query.where(col(AuditLog.action).in_([a.value for a in action]))
    if user_id:
        query = query.where(col(AuditLog.user_id).in_(user_id))
    if result:
        query = query.where(col(AuditLog.result).in_([r.value for r in result]))
    if target_type:
        query = query.where(col(AuditLog.target_type) == target_type)
    if target_ref:
        query = query.where(col(AuditLog.target_ref) == target_ref)
    if start_date:
        query = query.where(
            col(AuditLog.created_at) >= parse_utc_query_datetime(start_date)
        )
    if end_date:
        query = query.where(
            col(AuditLog.created_at) <= parse_utc_query_datetime(end_date)
        )
    if search:
        query = query.where(
            col(AuditLog.username).icontains(search)
            | col(AuditLog.target_ref).icontains(search)
            | col(AuditLog.detail).icontains(search)
        )

    total_filtered = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()

    # Stable pagination: equal-timestamp rows can never shuffle between
    # pages (01_CONTRACTS.md Step 11).
    query = query.order_by(
        col(AuditLog.created_at).desc(), col(AuditLog.audit_id).desc()
    )
    logs = session.exec(query.offset(offset).limit(limit)).all()

    return AuditLogListResponse(
        total_filtered=total_filtered,
        items=[AuditLogRead.model_validate(log) for log in logs],
    )
