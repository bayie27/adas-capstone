"""
analytics.py — Dashboard Analytics (FR-15) and AI Performance (FR-14) endpoints.

Two UI modules, four endpoints:

  GET  /api/analytics/dashboard            — composite BFF: KPIs + charts
  GET  /api/analytics/export/dashboard     — CSV export of confirmed accidents
  GET  /api/analytics/performance          — global KPIs + per-camera breakdown
  GET  /api/analytics/export/performance   — CSV export of per-camera table

Accident definition (from the paper, FR-09 / Use Case 8):
  "Accidents" = Ongoing + Resolved  (operator-verified true positives)
  "Dismissed" = Dismissed           (operator-verified false positives)
  "Unverified" is excluded from all analytics — it has not yet been acted on.

Precision formula (Use Case 7 / paper §Precision Calibration):
  Precision = Confirmed / (Confirmed + Dismissed)
  Returns None when no detections exist in the window (zero-division guard).
"""

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, func, select

from app.api.dependencies import get_current_user
from app.core.db import get_session
from app.models import Camera, DetectionLog, DetectionStatus
from app.services.filters import validate_common_filters
from app.services.formatting import format_user_name

router = APIRouter(
    prefix="/api/analytics",
    tags=["Analytics"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_ACCIDENT_STATUSES = [DetectionStatus.ONGOING.value, DetectionStatus.RESOLVED.value]
_DISMISSED_STATUSES = [DetectionStatus.DISMISSED.value]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _apply_log_filters(query, *, start_date, end_date, camera_ids):
    """
    Apply the three common query-time filters (date window, camera whitelist)
    to any SELECT that already targets DetectionLog.
    """
    if start_date:
        query = query.where(col(DetectionLog.detected_at) >= start_date)
    if end_date:
        query = query.where(col(DetectionLog.detected_at) <= end_date)
    if camera_ids:
        query = query.where(col(DetectionLog.camera_id).in_(camera_ids))
    return query


def _compute_precision(confirmed: int, dismissed: int) -> float | None:
    """
    Precision = confirmed / (confirmed + dismissed).
    Returns None — not 0 — when there are no detections, per paper Use Case 7 §2a.
    """
    total = confirmed + dismissed
    return round(confirmed / total, 4) if total > 0 else None


def _format_pct(value: float | None) -> str:
    """Format a 0-1 float as a percentage string for CSV export, or 'N/A'."""
    return f"{value * 100:.1f}%" if value is not None else "N/A"


# ---------------------------------------------------------------------------
# Module 1 — Dashboard Analytics  (FR-15)
# ---------------------------------------------------------------------------


@router.get("/dashboard")
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

    # --- KPI counts (one query, GROUP BY status) --------------------------
    # GROUP BY instead of two separate COUNT queries halves the round trips.

    status_counts_query = _apply_log_filters(
        select(
            DetectionLog.detection_status,
            func.count(DetectionLog.log_id).label("n"),
        )
        .where(col(DetectionLog.detection_status).in_(_ACCIDENT_STATUSES))
        .group_by(DetectionLog.detection_status),
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_id,
    )

    status_counts: dict[str, int] = {
        row[0]: row[1] for row in session.exec(status_counts_query).all()
    }

    ongoing_count = status_counts.get(DetectionStatus.ONGOING.value, 0)
    resolved_count = status_counts.get(DetectionStatus.RESOLVED.value, 0)
    total_accidents = ongoing_count + resolved_count

    # --- Accident frequency by location -----------------------------------

    freq_query = _apply_log_filters(
        select(
            Camera.camera_name,
            func.count(DetectionLog.log_id).label("accident_count"),
        )
        .join(Camera, DetectionLog.camera_id == Camera.camera_id)
        .where(col(DetectionLog.detection_status).in_(_ACCIDENT_STATUSES))
        .group_by(Camera.camera_id, Camera.camera_name)
        .order_by(
            func.count(DetectionLog.log_id).desc(),
            Camera.camera_name.asc(),
            Camera.camera_id.asc(),
        ),
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_id,
    )

    frequency_by_location = [
        {"camera_name": row[0], "accident_count": row[1]}
        for row in session.exec(freq_query).all()
    ]

    # --- Peak accident times (hour-of-day distribution) -------------------
    # SQLite strftime('%H', datetime_column) extracts the UTC hour as a
    # zero-padded two-character string ("00"-"23"). We cast to int in Python.

    hour_query = _apply_log_filters(
        select(
            func.strftime("%H", DetectionLog.detected_at).label("hour_str"),
            func.count(DetectionLog.log_id).label("n"),
        )
        .join(Camera, DetectionLog.camera_id == Camera.camera_id)
        .where(col(DetectionLog.detection_status).in_(_ACCIDENT_STATUSES))
        .group_by(func.strftime("%H", DetectionLog.detected_at))
        .order_by(func.strftime("%H", DetectionLog.detected_at)),
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_id,
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
            "ongoing": ongoing_count,
            "total_accidents": total_accidents,
            "total_resolved": resolved_count,
        },
        "frequency_by_location": frequency_by_location,
        "peak_accident_times": peak_accident_times,
    }


@router.get("/export/dashboard")
def export_dashboard_csv(
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    camera_id: list[int] | None = Query(default=None),
    session: Session = Depends(get_session),
):
    """
    Export confirmed accident logs (Ongoing + Resolved) matching the
    active dashboard filters as a downloadable CSV.
    """
    validate_common_filters(
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_id,
    )

    logs_query = _apply_log_filters(
        select(DetectionLog)
        .options(
            selectinload(DetectionLog.camera),
            selectinload(DetectionLog.verified_by),
            selectinload(DetectionLog.closed_by),
        )
        .where(col(DetectionLog.detection_status).in_(_ACCIDENT_STATUSES))
        .order_by(col(DetectionLog.detected_at).desc()),
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_id,
    )
    logs = session.exec(logs_query).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
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
        ]
    )

    for log in logs:
        writer.writerow(
            [
                log.log_id,
                log.detected_at.isoformat(),
                log.camera_id,
                log.camera.camera_name if log.camera else "N/A",
                log.detection_status,
                _format_pct(log.confidence_score),
                log.verified_by_id or "N/A",
                format_user_name(log.verified_by) or "N/A",
                log.verified_at.isoformat() if log.verified_at else "N/A",
                log.closed_by_id or "N/A",
                format_user_name(log.closed_by) or "N/A",
                log.closed_at.isoformat() if log.closed_at else "N/A",
            ]
        )

    response = Response(content=output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = (
        "attachment; filename=adas_dashboard_export.csv"
    )
    return response


# ---------------------------------------------------------------------------
# Module 2 — AI Performance  (FR-14)
# ---------------------------------------------------------------------------


def _fetch_per_camera_stats(
    session: Session,
    *,
    statuses: list[str],
    start_date: datetime | None,
    end_date: datetime | None,
    camera_ids: list[int] | None,
) -> dict[int, tuple[int, float | None]]:
    """
    Return {camera_id: (count, avg_confidence)} for all logs whose
    detection_status is in `statuses`, within the filter window.
    """
    query = _apply_log_filters(
        select(
            DetectionLog.camera_id,
            func.count(DetectionLog.log_id).label("n"),
            func.avg(DetectionLog.confidence_score).label("avg_conf"),
        )
        .where(col(DetectionLog.detection_status).in_(statuses))
        .group_by(DetectionLog.camera_id),
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_ids,
    )
    return {
        row[0]: (row[1], float(row[2]) if row[2] is not None else None)
        for row in session.exec(query).all()
    }


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


@router.get("/performance")
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
    session: Session = Depends(get_session),
):
    """
    AI Performance module (FR-14).

    **global_kpis** — five keycards covering the entire filtered window:
    Total Accidents, Total Dismissed, Precision Score, Avg Accident Confidence,
    Avg Dismissed Confidence. Confidence and Precision are null when no data exists.

    **per_camera** — same five metrics broken down per camera, sorted by total
    activity (accidents + dismissed) descending. Optionally filtered by camera
    name via `?search=`. Only cameras that have at least one detection in the
    filtered window appear in the table.
    """
    validate_common_filters(
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_id,
    )

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

    # --- Global KPIs ------------------------------------------------------

    global_confirmed = sum(v[0] for v in confirmed_map.values())
    global_dismissed = sum(v[0] for v in dismissed_map.values())
    global_precision = _compute_precision(global_confirmed, global_dismissed)
    global_avg_accident_conf = _weighted_avg(confirmed_map)
    global_avg_dismissed_conf = _weighted_avg(dismissed_map)

    # --- Per-camera breakdown ---------------------------------------------

    all_camera_ids = set(confirmed_map.keys()) | set(dismissed_map.keys())

    # Resolve camera names in one query rather than N individual lookups
    camera_name_map: dict[int, str] = {}
    if all_camera_ids:
        camera_name_map = {
            c.camera_id: c.camera_name
            for c in session.exec(
                select(Camera).where(col(Camera.camera_id).in_(list(all_camera_ids)))
            ).all()
        }

    per_camera: list[dict] = []
    for cam_id in all_camera_ids:
        cam_name = camera_name_map.get(cam_id, f"Camera {cam_id}")

        # Apply search filter (case-insensitive substring match on camera name)
        if search and search.lower() not in cam_name.lower():
            continue

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


@router.get("/export/performance")
def export_performance_csv(
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    camera_id: list[int] | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    session: Session = Depends(get_session),
):
    """
    Export the per-camera AI performance breakdown as a downloadable CSV.
    Applies the same filters as GET /api/analytics/performance so the CSV
    always matches exactly what the operator sees on screen.
    """
    # Delegate entirely to the performance endpoint so filter logic lives in
    # one place and the export is guaranteed to stay in sync with the UI.
    data = get_ai_performance(
        start_date=start_date,
        end_date=end_date,
        camera_id=camera_id,
        search=search,
        session=session,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Camera ID",
            "Camera Name",
            "Total Accidents",
            "Total Dismissed",
            "Precision Score",
            "Avg Accident Confidence",
            "Avg Dismissed Confidence",
        ]
    )

    for row in data["per_camera"]:
        writer.writerow(
            [
                row["camera_id"],
                row["camera_name"],
                row["total_accidents"],
                row["total_dismissed"],
                _format_pct(row["precision_score"]),
                _format_pct(row["avg_accident_confidence"]),
                _format_pct(row["avg_dismissed_confidence"]),
            ]
        )

    response = Response(content=output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = (
        "attachment; filename=adas_performance_export.csv"
    )
    return response
