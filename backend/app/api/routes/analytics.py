"""
analytics.py — Dashboard Analytics (FR-15) and AI Performance (FR-14) endpoints.

Two UI modules, four endpoints:

  GET  /api/analytics/dashboard            — composite BFF: KPIs + charts
  GET  /api/analytics/export/dashboard     — CSV/PDF export
  GET  /api/analytics/performance          — global KPIs + per-camera breakdown
  GET  /api/analytics/export/performance   — CSV/PDF export

Accident definition (from the paper, FR-09 / Use Case 8):
  "Accidents" = Ongoing + Resolved  (operator-verified true positives)
  "Dismissed" = Dismissed           (operator-verified false positives)
  "Unverified" is excluded from all analytics — it has not yet been acted on.

Precision formula (Use Case 7 / paper §Precision Calibration):
  Precision = Confirmed / (Confirmed + Dismissed)
  Returns None when no detections exist in the window (zero-division guard).
"""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, func, select

from app.api.dependencies import get_current_user
from app.core.db import get_session
from app.core.errors import AppHTTPException
from app.models import AuditResult, Camera, DetectionLog, DetectionStatus, User
from app.schemas import DashboardAnalyticsResponse, PerformanceAnalyticsResponse
from app.services.cameras import format_camera_filter_line, resolve_camera_names
from app.services.filters import (
    IncidentFilters,
    apply_incident_filters,
    validate_common_filters,
)
from app.services.formatting import format_user_name
from app.services.reports.common import check_row_limit, record_export_attempt
from app.services.reports.csv_writer import csv_response
from app.services.reports.pdf_writer import build_dashboard_pdf, build_performance_pdf

router = APIRouter(
    prefix="/api/analytics",
    tags=["Analytics"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_ACCIDENT_STATUSES = (DetectionStatus.ONGOING, DetectionStatus.RESOLVED)
_DISMISSED_STATUSES = (DetectionStatus.DISMISSED,)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _compute_precision(confirmed: int, dismissed: int) -> float | None:
    """
    Precision = confirmed / (confirmed + dismissed).
    Returns None — not 0 — when there are no detections, per paper Use Case 7 §2a.
    """
    total = confirmed + dismissed
    return round(confirmed / total, 4) if total > 0 else None


# ---------------------------------------------------------------------------
# Module 1 — Dashboard Analytics  (FR-15)
# ---------------------------------------------------------------------------


def _compute_dashboard_kpi_counts(
    session: Session,
    *,
    start_date: datetime | None,
    end_date: datetime | None,
    camera_id: list[int] | None,
) -> dict[str, int]:
    """The three headline KPI counts only — shared by the current-window
    computation below and P19 §5's previous-window comparison, neither of
    which needs frequency_by_location/peak_accident_times recomputed."""
    filters = IncidentFilters(
        start_date=start_date, end_date=end_date, camera_ids=tuple(camera_id or ())
    )

    # GROUP BY instead of two separate COUNT queries halves the round trips.
    status_counts_query = apply_incident_filters(
        select(
            DetectionLog.detection_status,
            func.count(DetectionLog.log_id).label("n"),
        )
        .where(
            col(DetectionLog.detection_status).in_(
                [s.value for s in _ACCIDENT_STATUSES]
            )
        )
        .group_by(DetectionLog.detection_status),
        filters,
    )

    status_counts: dict[str, int] = {
        row[0]: row[1] for row in session.exec(status_counts_query).all()
    }

    ongoing_count = status_counts.get(DetectionStatus.ONGOING.value, 0)
    resolved_count = status_counts.get(DetectionStatus.RESOLVED.value, 0)
    return {
        "ongoing": ongoing_count,
        "total_accidents": ongoing_count + resolved_count,
        "total_resolved": resolved_count,
    }


def _previous_window(
    start_date: datetime | None, end_date: datetime | None
) -> tuple[datetime, datetime] | None:
    """P19 §5 — the same-duration window immediately preceding
    [start_date, end_date]. None when the range isn't fully bounded: either
    date missing means there's no well-defined duration to shift, and "all
    time" (both unset) has no previous period at all.

    apply_incident_filters compares detected_at with `>=` start and `<=`
    end — both bounds inclusive — so previous_end is start_date minus one
    microsecond, not start_date itself, or a detection exactly at
    start_date would be counted in both windows."""
    if start_date is None or end_date is None:
        return None
    duration = end_date - start_date
    previous_end = start_date - timedelta(microseconds=1)
    previous_start = previous_end - duration
    return previous_start, previous_end


def _delta_pct(current: int, previous: int) -> float | None:
    """P19 §5 — None (never 0) when there's no previous window to compare
    against, and None (never +100%/inf) when the previous count was zero:
    growth from nothing isn't a figure an operator can act on. `0` would
    read as "no change", a different and wrong claim in both cases."""
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _compute_dashboard_data(
    session: Session,
    *,
    start_date: datetime | None,
    end_date: datetime | None,
    camera_id: list[int] | None,
) -> dict:
    filters = IncidentFilters(
        start_date=start_date, end_date=end_date, camera_ids=tuple(camera_id or ())
    )

    current = _compute_dashboard_kpi_counts(
        session, start_date=start_date, end_date=end_date, camera_id=camera_id
    )

    previous_window = _previous_window(start_date, end_date)
    if previous_window is None:
        ongoing_delta_pct = total_accidents_delta_pct = total_resolved_delta_pct = None
    else:
        previous_start, previous_end = previous_window
        previous = _compute_dashboard_kpi_counts(
            session,
            start_date=previous_start,
            end_date=previous_end,
            camera_id=camera_id,
        )
        ongoing_delta_pct = _delta_pct(current["ongoing"], previous["ongoing"])
        total_accidents_delta_pct = _delta_pct(
            current["total_accidents"], previous["total_accidents"]
        )
        total_resolved_delta_pct = _delta_pct(
            current["total_resolved"], previous["total_resolved"]
        )

    # --- Accident frequency by location -----------------------------------

    freq_query = apply_incident_filters(
        select(
            Camera.camera_name,
            func.count(DetectionLog.log_id).label("accident_count"),
        )
        .join(Camera, DetectionLog.camera_id == Camera.camera_id)
        .where(
            col(DetectionLog.detection_status).in_(
                [s.value for s in _ACCIDENT_STATUSES]
            )
        )
        .group_by(Camera.camera_id, Camera.camera_name)
        .order_by(
            func.count(DetectionLog.log_id).desc(),
            Camera.camera_name.asc(),
            Camera.camera_id.asc(),
        ),
        filters,
        camera_joined=True,
    )

    frequency_by_location = [
        {"camera_name": row[0], "accident_count": row[1]}
        for row in session.exec(freq_query).all()
    ]

    # --- Peak accident times (hour-of-day distribution) -------------------
    # SQLite strftime('%H', datetime_column) extracts the UTC hour as a
    # zero-padded two-character string ("00"-"23"). This is SQLite-only —
    # D-005 locks SQLite, so that's a deliberate, not accidental, coupling.

    hour_query = apply_incident_filters(
        select(
            func.strftime("%H", DetectionLog.detected_at).label("hour_str"),
            func.count(DetectionLog.log_id).label("n"),
        )
        .join(Camera, DetectionLog.camera_id == Camera.camera_id)
        .where(
            col(DetectionLog.detection_status).in_(
                [s.value for s in _ACCIDENT_STATUSES]
            )
        )
        .group_by(func.strftime("%H", DetectionLog.detected_at))
        .order_by(func.strftime("%H", DetectionLog.detected_at)),
        filters,
        camera_joined=True,
    )

    hour_map: dict[int, int] = {
        int(row[0]): row[1]
        for row in session.exec(hour_query).all()
        if row[0]
        is not None  # guard against NULL detected_at (schema forbids it, but be safe)
    }

    # Always emit all 24 buckets so the chart has a stable x-axis
    peak_accident_times = [{"hour": h, "count": hour_map.get(h, 0)} for h in range(24)]

    return {
        "kpis": {
            **current,
            "ongoing_delta_pct": ongoing_delta_pct,
            "total_accidents_delta_pct": total_accidents_delta_pct,
            "total_resolved_delta_pct": total_resolved_delta_pct,
        },
        "frequency_by_location": frequency_by_location,
        "peak_accident_times": peak_accident_times,
    }


@router.get("/dashboard", response_model=DashboardAnalyticsResponse)
def get_dashboard_analytics(
    start_date: datetime | None = Query(
        default=None,
        description="ISO 8601 start of window, e.g. 2026-01-01T00:00:00Z",
    ),
    end_date: datetime | None = Query(
        default=None,
        description="ISO 8601 end of window, e.g. 2026-12-31T23:59:59Z",
    ),
    camera_id: list[int] | None = Query(
        default=None,
        description="Filter by camera ID(s), e.g. ?camera_id=1&camera_id=2",
    ),
    session: Session = Depends(get_session),
):
    """
    Composite BFF endpoint for the main Dashboard page (FR-15).

    Returns three sections in a single round-trip to avoid waterfall fetches
    from the frontend:

    **kpis** — Ongoing count, Total Accidents (Ongoing + Resolved), Total Resolved.

    **frequency_by_location** — Accident count per camera name, sorted descending.
    Only confirmed accidents (Ongoing + Resolved) are counted.

    **peak_accident_times** — Hour-of-day distribution (0-23) of confirmed accidents.
    Always returns all 24 buckets so the frontend chart never needs gap-filling.
    This is a pattern chart: if you filter to a 7-day window you still see which
    hours of the day are most dangerous, not a timeline of the last 7 days.
    """
    validate_common_filters(
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_id,
    )
    return _compute_dashboard_data(
        session, start_date=start_date, end_date=end_date, camera_id=camera_id
    )


def _dashboard_filters_summary(
    *,
    start_date: datetime | None,
    end_date: datetime | None,
    camera_id: list[int] | None,
    camera_names: Mapping[str, str],
) -> list[str]:
    lines = []
    if start_date or end_date:
        lines.append(
            f"Date range: {start_date.isoformat() if start_date else '…'} "
            f"to {end_date.isoformat() if end_date else '…'}"
        )
    if camera_id:
        lines.append(format_camera_filter_line(camera_names, camera_id))
    return lines


def _performance_filters_summary(
    *,
    start_date: datetime | None,
    end_date: datetime | None,
    camera_id: list[int] | None,
    search: str | None,
    camera_names: Mapping[str, str],
) -> list[str]:
    lines = []
    if start_date or end_date:
        lines.append(
            f"Date range: {start_date.isoformat() if start_date else '…'} "
            f"to {end_date.isoformat() if end_date else '…'}"
        )
    if camera_id:
        lines.append(format_camera_filter_line(camera_names, camera_id))
    if search:
        lines.append(f"Search: {search!r}")
    return lines


@router.get("/export/dashboard")
def export_dashboard(
    request: Request,
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    camera_id: list[int] | None = Query(default=None),
    format: str = Query(default="csv", pattern="^(csv|pdf)$"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Export the dashboard's supporting data as CSV or PDF (`?format=csv|pdf`).

    The CSV is the underlying confirmed-accident (Ongoing + Resolved) log
    rows behind the dashboard — matching the active date/camera filters —
    so an analyst can drill from the KPI cards into the records that back
    them. The PDF instead renders the KPI/frequency/peak-times summary
    itself (D-010's "Dashboard report — filtered KPIs, location frequency,
    and peak-time results"), since that's what a print-ready dashboard
    report means.
    """
    validate_common_filters(
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_id,
    )
    filters = IncidentFilters(
        start_date=start_date, end_date=end_date, camera_ids=tuple(camera_id or ())
    )
    filters_dict = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "camera_id": list(camera_id or ()),
    }
    source_ip = _client_ip(request)
    # Resolved once and threaded through both the audit row (Step 5) and
    # the PDF filter-summary header (Step 6) so a camera-filtered export
    # issues exactly one resolve_camera_names query, not two.
    camera_names = resolve_camera_names(session, camera_id or ())

    # A count query, not a materialized id list: `WHERE log_id IN (...)`
    # with tens of thousands of bind parameters exceeds SQLite's default
    # variable limit (999) — found live-drilling a 50,000-row export.
    count_stmt = apply_incident_filters(
        select(func.count(col(DetectionLog.log_id))).where(
            col(DetectionLog.detection_status).in_(
                [s.value for s in _ACCIDENT_STATUSES]
            )
        ),
        filters,
    )
    row_count = session.exec(count_stmt).one()

    try:
        check_row_limit(row_count, format=format)
    except AppHTTPException:
        record_export_attempt(
            session,
            action="REPORT_EXPORT",
            report_type="dashboard",
            format=format,
            actor=current_user,
            filters=filters_dict,
            row_count=row_count,
            result=AuditResult.FAILURE,
            failure_category="row_limit_exceeded",
            source_ip=source_ip,
            camera_names=camera_names,
        )
        session.commit()
        raise

    record_export_attempt(
        session,
        action="REPORT_EXPORT",
        report_type="dashboard",
        format=format,
        actor=current_user,
        filters=filters_dict,
        row_count=row_count,
        result=AuditResult.SUCCESS,
        source_ip=source_ip,
        camera_names=camera_names,
    )
    session.commit()

    filters_summary = _dashboard_filters_summary(
        start_date=start_date,
        end_date=end_date,
        camera_id=camera_id,
        camera_names=camera_names,
    )

    if format == "pdf":
        data = _compute_dashboard_data(
            session, start_date=start_date, end_date=end_date, camera_id=camera_id
        )
        pdf_bytes = build_dashboard_pdf(
            kpis=data["kpis"],
            frequency_by_location=data["frequency_by_location"],
            peak_accident_times=data["peak_accident_times"],
            filters_summary=filters_summary,
            requested_by=format_user_name(current_user) or current_user.username,
            generated_at=datetime.now(UTC),
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="adas_dashboard_export.pdf"'
            },
        )

    logs_stmt = apply_incident_filters(
        select(DetectionLog)
        .options(
            selectinload(DetectionLog.camera),
            selectinload(DetectionLog.verified_by),
            selectinload(DetectionLog.closed_by),
        )
        .where(
            col(DetectionLog.detection_status).in_(
                [s.value for s in _ACCIDENT_STATUSES]
            )
        )
        .order_by(col(DetectionLog.detected_at).desc()),
        filters,
    )

    def _row(log: DetectionLog) -> list:
        return [
            log.log_id,
            log.detected_at.isoformat(),
            log.camera_id,
            log.camera.camera_name if log.camera else None,
            log.detection_status,
            log.confidence_score,
            log.verified_by_id,
            format_user_name(log.verified_by),
            log.verified_at.isoformat() if log.verified_at else None,
            log.closed_by_id,
            format_user_name(log.closed_by),
            log.closed_at.isoformat() if log.closed_at else None,
        ]

    rows_iter = (_row(log) for log in session.exec(logs_stmt).yield_per(500))
    return csv_response(
        "adas_dashboard_export.csv",
        [
            "Log ID",
            "Detected At",
            "Camera ID",
            "Camera Name",
            "Status",
            "Confidence",
            "Verified By ID",
            "Verified By Name",
            "Verified At",
            "Closed By ID",
            "Closed By Name",
            "Closed At",
        ],
        rows_iter,
    )


# ---------------------------------------------------------------------------
# Module 2 — AI Performance  (FR-14)
# ---------------------------------------------------------------------------


def _fetch_per_camera_stats(
    session: Session,
    *,
    statuses: tuple[DetectionStatus, ...],
    start_date: datetime | None,
    end_date: datetime | None,
    camera_ids: list[int] | None,
) -> dict[int, tuple[int, float | None]]:
    """
    Return {camera_id: (count, avg_confidence)} for all logs whose
    detection_status is in `statuses`, within the filter window.
    """
    filters = IncidentFilters(
        start_date=start_date,
        end_date=end_date,
        statuses=statuses,
        camera_ids=tuple(camera_ids or ()),
    )
    query = apply_incident_filters(
        select(
            DetectionLog.camera_id,
            func.count(DetectionLog.log_id).label("n"),
            func.avg(DetectionLog.confidence_score).label("avg_conf"),
        ).group_by(DetectionLog.camera_id),
        filters,
    )
    return {
        row[0]: (row[1], float(row[2]) if row[2] is not None else None)
        for row in session.exec(query).all()
    }


def _performance_camera_population(
    session: Session,
    *,
    camera_id: list[int] | None,
    search: str | None,
    ids_with_history: set[int],
) -> dict[int, str]:
    """The per-camera table's row population: every *active* camera matching
    the `camera_id`/`search` filters, whether or not it has any
    confirmed/dismissed incidents in range (edge case 3.5,
    be_audit/00_FINDINGS.md F24) — a quiet camera must still appear with
    null averages, not vanish from the table — **plus** any soft-deleted
    camera that does have history in range (edge case 9.7): removing a
    camera must not change what already happened. `is_active=0` cameras
    with no history in range are correctly excluded either way. Returns
    {camera_id: name}."""
    query = select(Camera.camera_id, Camera.camera_name).where(
        col(Camera.is_active).is_(True) | col(Camera.camera_id).in_(ids_with_history)
    )
    if camera_id:
        query = query.where(col(Camera.camera_id).in_(camera_id))
    if search:
        query = query.where(col(Camera.camera_name).icontains(search))
    return {row[0]: row[1] for row in session.exec(query).all()}


def _weighted_avg(stat_map: dict[int, tuple[int, float | None]]) -> float | None:
    """
    Compute a count-weighted average confidence across cameras.

    Uses weighted averaging (sum(conf * n) / sum(n)) rather than avg(avg) to
    avoid statistical distortion when cameras have very different detection volumes.
    Returns None when there are no detections.
    """
    valid_rows = [
        (count, avg_confidence)
        for count, avg_confidence in stat_map.values()
        if count > 0 and avg_confidence is not None
    ]
    total_weight = sum(count for count, _ in valid_rows)
    if total_weight == 0:
        return None
    weighted_sum = sum(count * avg_confidence for count, avg_confidence in valid_rows)
    return round(weighted_sum / total_weight, 4)


def _compute_performance_data(
    session: Session,
    *,
    start_date: datetime | None,
    end_date: datetime | None,
    camera_id: list[int] | None,
    search: str | None,
) -> dict:
    # Two focused queries rather than a single GROUP BY (status, camera_id) pivot,
    # which would require more complex unpacking and is harder to read and test.
    confirmed_map = _fetch_per_camera_stats(
        session,
        statuses=_ACCIDENT_STATUSES,
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_id,
    )
    dismissed_map = _fetch_per_camera_stats(
        session,
        statuses=_DISMISSED_STATUSES,
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_id,
    )

    # --- Global KPIs --------------------------------------------------------
    # Deliberately computed from the *unfiltered-by-search* maps — `search`
    # only narrows the per-camera table below, same as today's behavior.

    global_confirmed = sum(v[0] for v in confirmed_map.values())
    global_dismissed = sum(v[0] for v in dismissed_map.values())
    global_precision = _compute_precision(global_confirmed, global_dismissed)
    global_avg_accident_conf = _weighted_avg(confirmed_map)
    global_avg_dismissed_conf = _weighted_avg(dismissed_map)

    # --- Per-camera breakdown -------------------------------------------------
    # Population is every active camera matching the filters — not just
    # cameras that happen to have a confirmed/dismissed row — so a quiet
    # camera still appears with null averages rather than being omitted
    # (edge case 3.5, F24).
    camera_name_map = _performance_camera_population(
        session,
        camera_id=camera_id,
        search=search,
        ids_with_history=set(confirmed_map) | set(dismissed_map),
    )

    per_camera: list[dict] = []
    for cam_id, cam_name in camera_name_map.items():
        conf_count, acc_avg = confirmed_map.get(cam_id, (0, None))
        dis_count, dis_avg = dismissed_map.get(cam_id, (0, None))

        per_camera.append(
            {
                "camera_id": cam_id,
                "camera_name": cam_name,
                "total_accidents": conf_count,
                "total_dismissed": dis_count,
                "precision_score": _compute_precision(conf_count, dis_count),
                "avg_accident_confidence": (
                    round(acc_avg, 4) if acc_avg is not None else None
                ),
                "avg_dismissed_confidence": (
                    round(dis_avg, 4) if dis_avg is not None else None
                ),
            }
        )

    # Sort by total activity descending — most active cameras first in the table
    per_camera.sort(
        key=lambda row: (
            -(row["total_accidents"] + row["total_dismissed"]),
            row["camera_name"].lower(),
            row["camera_id"],
        )
    )

    return {
        "global_kpis": {
            "total_accidents": global_confirmed,
            "total_dismissed": global_dismissed,
            "precision_score": global_precision,
            "avg_accident_confidence": global_avg_accident_conf,
            "avg_dismissed_confidence": global_avg_dismissed_conf,
        },
        "per_camera": per_camera,
    }


@router.get("/performance", response_model=PerformanceAnalyticsResponse)
def get_ai_performance(
    start_date: datetime | None = Query(
        default=None,
        description="ISO 8601 start of window, e.g. 2026-01-01T00:00:00Z",
    ),
    end_date: datetime | None = Query(
        default=None,
        description="ISO 8601 end of window, e.g. 2026-12-31T23:59:59Z",
    ),
    camera_id: list[int] | None = Query(
        default=None,
        description="Filter by camera ID(s), e.g. ?camera_id=1&camera_id=2",
    ),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
        description="Filter per-camera table by camera name (case-insensitive substring)",
    ),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    """
    AI Performance module (FR-14).

    **global_kpis** — five keycards covering the entire filtered window:
    Total Accidents, Total Dismissed, Precision Score, Avg Accident Confidence,
    Avg Dismissed Confidence. Confidence and Precision are null when no data exists.

    **per_camera** — one page (`limit`/`offset`, matching every other list
    endpoint) of the same five metrics broken down per camera, sorted by
    total activity (accidents + dismissed) descending — stable sort, so
    pages don't shuffle between requests. `total_filtered` is the full
    filtered count, not `len(per_camera)`. Optionally filtered by camera
    name via `?search=`. Only cameras that have at least one detection in
    the filtered window appear in the table.

    **CHANGED (P19 §4, breaking):** previously returned every matching
    camera in one array with no `limit`/`offset`. `GET
    /api/analytics/export/performance` is unaffected — it still exports
    every matching row regardless of any `limit`/`offset` on the request.
    """
    validate_common_filters(
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_id,
    )
    # P19 §4 — _compute_performance_data always returns the FULL per_camera
    # list; slicing happens here, in the route, not in the shared helper.
    # export_performance() calls the same helper and relies on the full list
    # for both its row-limit pre-flight and the export itself — if
    # pagination leaked into the helper, a large export would silently
    # shrink to one page and the pre-flight would under-report the very
    # thing it's guarding.
    data = _compute_performance_data(
        session,
        start_date=start_date,
        end_date=end_date,
        camera_id=camera_id,
        search=search,
    )
    data["total_filtered"] = len(data["per_camera"])
    data["per_camera"] = data["per_camera"][offset : offset + limit]
    return data


@router.get("/export/performance")
def export_performance(
    request: Request,
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    camera_id: list[int] | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    format: str = Query(default="csv", pattern="^(csv|pdf)$"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Export the per-camera AI performance breakdown as CSV or PDF.
    Applies the same filters as GET /api/analytics/performance so the
    export always matches exactly what the operator sees on screen.
    """
    validate_common_filters(
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_id,
    )
    filters_dict = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "camera_id": list(camera_id or ()),
        "search": search,
    }
    source_ip = _client_ip(request)
    # Resolved once and threaded through both the audit row (Step 5) and
    # the PDF filter-summary header (Step 6) so a camera-filtered export
    # issues exactly one resolve_camera_names query, not two.
    camera_names = resolve_camera_names(session, camera_id or ())

    data = _compute_performance_data(
        session,
        start_date=start_date,
        end_date=end_date,
        camera_id=camera_id,
        search=search,
    )
    row_count = len(data["per_camera"])

    try:
        check_row_limit(row_count, format=format)
    except AppHTTPException:
        record_export_attempt(
            session,
            action="REPORT_EXPORT",
            report_type="performance",
            format=format,
            actor=current_user,
            filters=filters_dict,
            row_count=row_count,
            result=AuditResult.FAILURE,
            failure_category="row_limit_exceeded",
            source_ip=source_ip,
            camera_names=camera_names,
        )
        session.commit()
        raise

    record_export_attempt(
        session,
        action="REPORT_EXPORT",
        report_type="performance",
        format=format,
        actor=current_user,
        filters=filters_dict,
        row_count=row_count,
        result=AuditResult.SUCCESS,
        source_ip=source_ip,
        camera_names=camera_names,
    )
    session.commit()

    filters_summary = _performance_filters_summary(
        start_date=start_date,
        end_date=end_date,
        camera_id=camera_id,
        search=search,
        camera_names=camera_names,
    )

    if format == "pdf":
        pdf_bytes = build_performance_pdf(
            global_kpis=data["global_kpis"],
            per_camera=data["per_camera"],
            filters_summary=filters_summary,
            requested_by=format_user_name(current_user) or current_user.username,
            generated_at=datetime.now(UTC),
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="adas_performance_export.pdf"'
            },
        )

    rows = (
        [
            row["camera_id"],
            row["camera_name"],
            row["total_accidents"],
            row["total_dismissed"],
            row["precision_score"],
            row["avg_accident_confidence"],
            row["avg_dismissed_confidence"],
        ]
        for row in data["per_camera"]
    )
    return csv_response(
        "adas_performance_export.csv",
        [
            "Camera ID",
            "Camera Name",
            "Total Accidents",
            "Total Dismissed",
            "Precision Score",
            "Avg Accident Confidence",
            "Avg Dismissed Confidence",
        ],
        rows,
    )
