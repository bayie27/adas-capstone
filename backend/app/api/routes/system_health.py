"""06_PKG_system_health.md Step 4. Deliberately its own module (not
routes/system.py, which holds only the P1 unauthenticated probes, and not
routes/maintenance.py, P7's parallel module) so this package can be built
without editing a file either of those own. The URL prefix is still
`/api/system/...`; only the Python module boundary differs.
"""

from datetime import UTC, datetime, timedelta
from statistics import mean
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, col, select

from app.api.dependencies import get_current_user, get_health_store
from app.core.config import settings
from app.core.db import get_session
from app.core.monitor import HealthStore, LiveHealthSample, is_stale
from app.models import HealthState, SysHealthHourly, SysHealthRaw
from app.schemas.health import (
    GpuRead,
    HealthHistoryPoint,
    HealthHistoryResponse,
    HealthWarning,
    SysHealthLive,
)
from app.services.hardware import GpuSample

router = APIRouter(
    prefix="/api/system",
    tags=["System Health"],
    dependencies=[Depends(get_current_user)],
)


def _gpu_read(gpu: GpuSample) -> GpuRead:
    return GpuRead(
        index=gpu.index,
        name=gpu.name,
        usage_percent=gpu.usage_percent,
        temp_c=gpu.temp_c,
        mem_used_mb=gpu.mem_used_mb,
        mem_total_mb=gpu.mem_total_mb,
        mem_pct=gpu.mem_pct,
    )


def _gpu_aggregates(
    gpus: list[GpuSample],
) -> tuple[float | None, float | None, float | None]:
    """D-009's deliberately different aggregates: utilization is the mean
    of available devices, temperature and memory pressure are each the
    max — a mean for memory would hide one nearly exhausted GPU."""
    usages = [g.usage_percent for g in gpus if g.usage_percent is not None]
    temps = [g.temp_c for g in gpus if g.temp_c is not None]
    mem_pcts = [g.mem_pct for g in gpus if g.mem_pct is not None]
    return (
        mean(usages) if usages else None,
        max(temps) if temps else None,
        max(mem_pcts) if mem_pcts else None,
    )


def _build_warnings(
    sample: LiveHealthSample, *, gpu_temp_max: float | None
) -> list[HealthWarning]:
    """Machine-readable code + severity + measurement + threshold only —
    the frontend controls presentation (D-009)."""
    warnings: list[HealthWarning] = []

    if gpu_temp_max is not None and gpu_temp_max >= settings.GPU_TEMP_CRITICAL_C:
        warnings.append(
            HealthWarning(
                code="GPU_TEMP_CRITICAL",
                severity="critical",
                measurement=gpu_temp_max,
                threshold=settings.GPU_TEMP_CRITICAL_C,
            )
        )

    if (
        sample.memory.available
        and sample.memory.usage_percent is not None
        and sample.memory.usage_percent >= settings.RAM_CRITICAL_PCT
    ):
        warnings.append(
            HealthWarning(
                code="RAM_CRITICAL",
                severity="critical",
                measurement=sample.memory.usage_percent,
                threshold=settings.RAM_CRITICAL_PCT,
            )
        )

    if sample.disk.available and sample.disk.percent is not None:
        if sample.disk.percent >= settings.DISK_CRITICAL_PCT:
            warnings.append(
                HealthWarning(
                    code="DISK_CRITICAL",
                    severity="critical",
                    measurement=sample.disk.percent,
                    threshold=settings.DISK_CRITICAL_PCT,
                )
            )
        elif sample.disk.percent >= settings.DISK_WARNING_PCT:
            warnings.append(
                HealthWarning(
                    code="DISK_WARNING",
                    severity="warning",
                    measurement=sample.disk.percent,
                    threshold=settings.DISK_WARNING_PCT,
                )
            )

    # Cameras are configured but none reported a fresh heartbeat — distinct
    # from simply having zero cameras registered (edge case 3.6), which
    # must not trip this warning.
    if sample.configured_camera_count > 0 and sample.sample_camera_count == 0:
        warnings.append(
            HealthWarning(
                code="AI_HEARTBEAT_STALE",
                severity="warning",
                measurement=0,
                threshold=settings.HEARTBEAT_STALE_SECONDS,
            )
        )

    return warnings


def _compute_state(warnings: list[HealthWarning]) -> HealthState:
    if any(w.severity == "critical" for w in warnings):
        return HealthState.CRITICAL
    if warnings:
        return HealthState.DEGRADED
    return HealthState.HEALTHY


_NO_SAMPLE_YET = SysHealthLive(
    collected_at=None,
    stale=False,
    host_uptime_seconds=None,
    process_uptime_seconds=None,
    cpu_usage=None,
    cpu_usage_available=False,
    cpu_temp=None,
    cpu_temp_available=False,
    ram_usage=None,
    ram_usage_available=False,
    disk_total_bytes=None,
    disk_used_bytes=None,
    disk_available_bytes=None,
    disk_percent=None,
    disk_available=False,
    gpus=[],
    gpu_usage_avg=None,
    gpu_temp_max=None,
    gpu_mem_pct_max=None,
    avg_inference_latency_ms=None,
    avg_fps=None,
    sample_camera_count=0,
    warnings=[],
    state=HealthState.DEGRADED,
)


def _live_response(sample: LiveHealthSample | None, *, now: datetime) -> SysHealthLive:
    """Edge case 3.11 — before the first sample completes, `collected_at`
    is the explicit "no sample yet" signal; every metric is None with its
    own availability flag False rather than a fabricated zero."""
    if sample is None:
        return _NO_SAMPLE_YET

    stale = is_stale(
        sample.collected_at, now=now, interval_seconds=settings.HEALTH_SAMPLE_SECONDS
    )
    gpu_usage_avg, gpu_temp_max, gpu_mem_pct_max = _gpu_aggregates(sample.gpus)
    warnings = _build_warnings(sample, gpu_temp_max=gpu_temp_max)

    return SysHealthLive(
        collected_at=sample.collected_at,
        stale=stale,
        host_uptime_seconds=sample.host_uptime_seconds,
        process_uptime_seconds=sample.process_uptime_seconds,
        cpu_usage=sample.cpu.usage_percent,
        cpu_usage_available=sample.cpu.available,
        cpu_temp=sample.cpu.temp_c if sample.cpu.temp_available else None,
        cpu_temp_available=sample.cpu.temp_available,
        ram_usage=sample.memory.usage_percent,
        ram_usage_available=sample.memory.available,
        disk_total_bytes=sample.disk.total_bytes,
        disk_used_bytes=sample.disk.used_bytes,
        disk_available_bytes=sample.disk.available_bytes,
        disk_percent=sample.disk.percent,
        disk_available=sample.disk.available,
        gpus=[_gpu_read(g) for g in sample.gpus],
        gpu_usage_avg=gpu_usage_avg,
        gpu_temp_max=gpu_temp_max,
        gpu_mem_pct_max=gpu_mem_pct_max,
        avg_inference_latency_ms=sample.avg_inference_latency_ms,
        avg_fps=sample.avg_fps,
        sample_camera_count=sample.sample_camera_count,
        warnings=warnings,
        state=_compute_state(warnings),
    )


@router.get("/health/live", response_model=SysHealthLive)
def get_health_live(store: HealthStore = Depends(get_health_store)):
    return _live_response(store.sample, now=datetime.now(UTC))


def _raw_point(row: SysHealthRaw) -> HealthHistoryPoint:
    """A raw row is one instant, so its avg/peak variants of the same
    metric coincide — that's what makes it shape-compatible with an
    hourly point without the frontend needing to branch on `range`."""
    return HealthHistoryPoint(
        timestamp=row.created_at,
        cpu_usage=row.cpu_usage,
        ram_usage=row.ram_usage,
        gpu_usage=row.gpu_usage_avg,
        cpu_temp_avg=row.cpu_temp,
        cpu_temp_peak=row.cpu_temp,
        gpu_temp_peak=row.gpu_temp_max,
        gpu_mem_pct_avg=row.gpu_mem_pct_max,
        gpu_mem_pct_peak=row.gpu_mem_pct_max,
        sample_count=1,
    )


def _hourly_point(row: SysHealthHourly) -> HealthHistoryPoint:
    return HealthHistoryPoint(
        timestamp=row.hour_start,
        cpu_usage=row.avg_cpu_usage,
        ram_usage=row.avg_ram_usage,
        gpu_usage=row.avg_gpu_usage,
        cpu_temp_avg=row.avg_cpu_temp,
        cpu_temp_peak=row.peak_cpu_temp,
        gpu_temp_peak=row.peak_gpu_temp,
        gpu_mem_pct_avg=row.avg_gpu_mem_pct,
        gpu_mem_pct_peak=row.peak_gpu_mem_pct,
        sample_count=row.sample_count,
    )


@router.get("/health/history", response_model=HealthHistoryResponse)
def get_health_history(
    range: Literal["48h", "30d"] = Query(...),
    session: Session = Depends(get_session),
):
    """Oldest-to-newest. A collection gap simply has no row for that
    period — never a fabricated zero (D-009, edge case 3.12)."""
    now = datetime.now(UTC)

    if range == "48h":
        cutoff = now - timedelta(hours=settings.HEALTH_RAW_RETENTION_HOURS)
        raw_rows = session.exec(
            select(SysHealthRaw)
            .where(col(SysHealthRaw.created_at) >= cutoff)
            .order_by(col(SysHealthRaw.created_at).asc())
        ).all()
        points = [_raw_point(row) for row in raw_rows]
    else:
        cutoff = now - timedelta(days=settings.HEALTH_HOURLY_RETENTION_DAYS)
        hourly_rows = session.exec(
            select(SysHealthHourly)
            .where(col(SysHealthHourly.hour_start) >= cutoff)
            .order_by(col(SysHealthHourly.hour_start).asc())
        ).all()
        points = [_hourly_point(row) for row in hourly_rows]

    return HealthHistoryResponse(range=range, points=points)
