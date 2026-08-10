from dataclasses import dataclass, field
from datetime import datetime

from fastapi import HTTPException
from sqlmodel import col, or_

from app.core.types import parse_utc_query_datetime
from app.models import Camera, DetectionLog, DetectionStatus


def validate_common_filters(
    *,
    start_date: datetime | None,
    end_date: datetime | None,
    camera_ids: list[int] | None = None,
    user_ids: list[int] | None = None,
) -> None:
    """Raise 422 for invalid shared list-endpoint filters.

    Shared by alerts, analytics, audit, and P6 exports so the date-range
    and positive-id rules never drift between endpoints.
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="Invalid date range: `start_date` must be earlier than or equal to `end_date`.",
        )

    if camera_ids and any(camera_id <= 0 for camera_id in camera_ids):
        raise HTTPException(
            status_code=422,
            detail="Invalid `camera_id` value(s): values must be positive integers.",
        )

    if user_ids and any(user_id <= 0 for user_id in user_ids):
        raise HTTPException(
            status_code=422,
            detail="Invalid `user_id` value(s): values must be positive integers.",
        )


@dataclass(frozen=True)
class IncidentFilters:
    """P6 Step 1 — the one shape every `DetectionLog`-querying route (list,
    export, export job) builds from its query parameters, so the same
    filter can never behave differently depending on which endpoint you
    hit (D-010: "an export must match the screen's active filters
    exactly")."""

    start_date: datetime | None = None
    end_date: datetime | None = None
    statuses: tuple[DetectionStatus, ...] = field(default_factory=tuple)
    camera_ids: tuple[int, ...] = field(default_factory=tuple)
    user_ids: tuple[int, ...] = field(default_factory=tuple)  # verified_by OR closed_by
    search: str | None = None


def apply_incident_filters(stmt, f: IncidentFilters, *, camera_joined: bool = False):
    """Applies `IncidentFilters` to any SELECT already targeting
    `DetectionLog`. Datetime bounds go through `parse_utc_query_datetime`
    (P1) so a `+08:00`-offset or naive query param is normalized to UTC
    the same way everywhere.

    `search` matches a bare integer against `log_id`, otherwise a
    case-insensitive substring against `camera.camera_name` — this needs a
    join to `Camera`, done here unless the caller's statement already
    joined it (e.g. because it's grouping by camera name).
    """
    if f.search:
        if not camera_joined:
            stmt = stmt.join(Camera, DetectionLog.camera_id == Camera.camera_id)
        if f.search.isdigit():
            stmt = stmt.where(
                or_(
                    DetectionLog.log_id == int(f.search),
                    col(Camera.camera_name).icontains(f.search),
                )
            )
        else:
            stmt = stmt.where(col(Camera.camera_name).icontains(f.search))

    if f.start_date:
        stmt = stmt.where(
            col(DetectionLog.detected_at) >= parse_utc_query_datetime(f.start_date)
        )
    if f.end_date:
        stmt = stmt.where(
            col(DetectionLog.detected_at) <= parse_utc_query_datetime(f.end_date)
        )
    if f.statuses:
        stmt = stmt.where(
            col(DetectionLog.detection_status).in_([s.value for s in f.statuses])
        )
    if f.camera_ids:
        stmt = stmt.where(col(DetectionLog.camera_id).in_(f.camera_ids))
    if f.user_ids:
        stmt = stmt.where(
            or_(
                col(DetectionLog.verified_by_id).in_(f.user_ids),
                col(DetectionLog.closed_by_id).in_(f.user_ids),
            )
        )

    return stmt


def apply_sort(
    stmt,
    model,
    *,
    sort_by: str,
    sort_order: str,
    allowed: set[str],
    tie_breaker: str | None = None,
):
    """01_CONTRACTS.md §1.5 — `sort_by` accepts only an allowlisted field
    name per resource; `sort_order` accepts only `asc`/`desc`. Anything
    else is `422`, never raw SQL from the client.

    `tie_breaker` adds a second, always-descending ORDER BY column (e.g.
    the primary key) so equal-valued rows never shuffle between pages —
    required for stable pagination when `sort_by` isn't already unique.
    """
    if sort_by not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid `sort_by` value: must be one of {sorted(allowed)}.",
        )
    if sort_order not in ("asc", "desc"):
        raise HTTPException(
            status_code=422,
            detail="Invalid `sort_order` value: must be `asc` or `desc`.",
        )

    sort_column = col(getattr(model, sort_by))
    stmt = stmt.order_by(
        sort_column.asc() if sort_order == "asc" else sort_column.desc()
    )
    if tie_breaker and tie_breaker != sort_by:
        stmt = stmt.order_by(col(getattr(model, tie_breaker)).desc())
    return stmt
