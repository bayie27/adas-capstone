"""07_PKG_reports.md Step 4 — real `response_model`s for the analytics
endpoints, which previously returned bare `dict`s (no OpenAPI contract)."""

from sqlmodel import SQLModel


class DashboardKpis(SQLModel):
    ongoing: int
    total_accidents: int
    total_cleared: int
    # P19 §5 — period-over-period change vs. the same-duration window
    # immediately preceding the request's [start_date, end_date]. None
    # (never 0) when there's no bounded window to compare, or when the
    # previous window's count was zero.
    ongoing_delta_pct: float | None = None
    total_accidents_delta_pct: float | None = None
    total_cleared_delta_pct: float | None = None


class LocationFrequency(SQLModel):
    camera_name: str
    accident_count: int


class PeakAccidentHour(SQLModel):
    hour: int
    count: int


class DashboardAnalyticsResponse(SQLModel):
    kpis: DashboardKpis
    frequency_by_location: list[LocationFrequency]
    peak_accident_times: list[PeakAccidentHour]


class PerformanceGlobalKpis(SQLModel):
    total_accidents: int
    total_dismissed: int
    precision_score: float | None
    avg_accident_confidence: float | None
    avg_dismissed_confidence: float | None


class PerformanceCameraRow(SQLModel):
    camera_id: int
    camera_name: str
    total_accidents: int
    total_dismissed: int
    precision_score: float | None
    avg_accident_confidence: float | None
    avg_dismissed_confidence: float | None


class PerformanceAnalyticsResponse(SQLModel):
    global_kpis: PerformanceGlobalKpis
    # P19 §4 — total rows matching the filters, NOT len(per_camera).
    # per_camera is now one page (default 10), not the full array.
    total_filtered: int
    per_camera: list[PerformanceCameraRow]
