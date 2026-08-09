from datetime import datetime
from typing import Literal

from sqlmodel import SQLModel

from app.models import HealthState, SysHealthHourlyBase, SysHealthRawBase


class SysHealthRawRead(SysHealthRawBase):
    sys_health_id: int
    created_at: datetime


class SysHealthHourlyRead(SysHealthHourlyBase):
    hourly_id: int
    hour_start: datetime
    sample_count: int


class GpuRead(SQLModel):
    """One device's row in the live per-GPU list (01_CONTRACTS.md §5.8).
    Missing readings are null, never zero (D-009)."""

    index: int
    name: str
    usage_percent: float | None
    temp_c: float | None
    mem_used_mb: float | None
    mem_total_mb: float | None
    mem_pct: float | None


class HealthWarning(SQLModel):
    """Machine-readable only — the backend never returns presentation
    strings or colors (D-009); the frontend decides how to display these."""

    code: str
    severity: Literal["warning", "critical"]
    measurement: float | None
    threshold: float | None


class SysHealthLive(SQLModel):
    """GET /api/system/health/live response (01_CONTRACTS.md §5.8).

    `collected_at=None` means the collector hasn't completed its first
    sample yet (edge case 3.11) — distinct from a per-sensor `_available`
    flag being False, which means that specific sensor failed on an
    otherwise-successful sample.
    """

    collected_at: datetime | None
    stale: bool

    host_uptime_seconds: float | None
    process_uptime_seconds: float | None

    cpu_usage: float | None
    cpu_usage_available: bool
    cpu_temp: float | None
    cpu_temp_available: bool

    ram_usage: float | None
    ram_usage_available: bool

    disk_total_bytes: int | None
    disk_used_bytes: int | None
    disk_available_bytes: int | None
    disk_percent: float | None
    disk_available: bool

    gpus: list[GpuRead]
    gpu_usage_avg: float | None
    gpu_temp_max: float | None
    gpu_mem_pct_max: float | None

    avg_inference_latency_ms: float | None
    avg_fps: float | None
    sample_camera_count: int

    warnings: list[HealthWarning]
    state: HealthState


class HealthHistoryPoint(SQLModel):
    """One consistent point shape shared by both raw (48h) and hourly (30d)
    ranges (01_CONTRACTS.md §5.8), so the frontend chart component never
    branches on `range`. For a raw point, `_avg` and `_peak` variants of
    the same metric are identical — a single 5-minute sample has no
    distribution to average or peak over."""

    timestamp: datetime
    cpu_usage: float | None
    ram_usage: float | None
    gpu_usage: float | None
    cpu_temp_avg: float | None
    cpu_temp_peak: float | None
    gpu_temp_peak: float | None
    gpu_mem_pct_avg: float | None
    gpu_mem_pct_peak: float | None
    sample_count: int


class HealthHistoryResponse(SQLModel):
    range: Literal["48h", "30d"]
    points: list[HealthHistoryPoint]
