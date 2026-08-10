"""06_PKG_system_health.md Steps 2 and 3 — the live in-memory collector and
the historical persistence/rollup/pruning jobs built on top of it (D-009).

Two-layer design: a live sample is rebuilt every HEALTH_SAMPLE_SECONDS and
simply overwritten on a HealthStore instance living on app.state — never
individually persisted, so every workstation polling /health/live doesn't
trigger its own OS/driver query. Every HEALTH_PERSIST_SECONDS, the *latest*
live sample (if still fresh) is condensed into one sys_health_raw row.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import mean

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.core.config import settings
from app.models import Camera, SysHealthHourly, SysHealthRaw
from app.services.hardware import (
    CpuSample,
    DiskSample,
    GpuSample,
    MemorySample,
    read_cpu,
    read_disk,
    read_gpus,
    read_memory,
    read_uptime,
)

logger = logging.getLogger("uvicorn.error")


@dataclass
class AiMetrics:
    avg_inference_latency_ms: float | None
    avg_fps: float | None
    sample_camera_count: int
    configured_camera_count: int


@dataclass
class LiveHealthSample:
    collected_at: datetime
    cpu: CpuSample
    memory: MemorySample
    disk: DiskSample
    gpus: list[GpuSample]
    host_uptime_seconds: float | None
    process_uptime_seconds: float | None
    avg_inference_latency_ms: float | None
    avg_fps: float | None
    sample_camera_count: int
    configured_camera_count: int


class HealthStore:
    """Holds exactly one retained live sample, overwritten in place. Lives
    on app.state (like RealtimeManager) so tests can construct their own
    throwaway instance instead of reaching into a module global."""

    def __init__(self) -> None:
        self._sample: LiveHealthSample | None = None

    @property
    def sample(self) -> LiveHealthSample | None:
        return self._sample

    def set(self, sample: LiveHealthSample) -> None:
        self._sample = sample


def is_stale(collected_at: datetime, *, now: datetime, interval_seconds: int) -> bool:
    """A sample is stale once it's at least one collection interval old —
    by then a fresher one should already have replaced it."""
    return (now - collected_at).total_seconds() >= interval_seconds


def collect_ai_metrics(session: Session, *, now: datetime) -> AiMetrics:
    """FPS/latency averaged only across cameras with a heartbeat inside
    HEARTBEAT_STALE_SECONDS (D-003, D-009) — the same freshness window
    app.services.cameras.presented_statuses() uses to decide Unresponsive,
    so a camera never counts as "reporting" in one place and "silent" in
    the other. `configured_camera_count` (is_active AND is_enabled,
    regardless of freshness) lets the live endpoint tell "no cameras
    registered" (edge case 3.6) apart from "cameras registered but none
    reporting" (edge case 6.19), which look identical from
    sample_camera_count alone.
    """
    cameras = session.exec(
        select(Camera).where(
            col(Camera.is_active).is_(True),
            col(Camera.is_enabled).is_(True),
        )
    ).all()

    fresh = [
        camera
        for camera in cameras
        if camera.last_heartbeat_at is not None
        and (now - camera.last_heartbeat_at).total_seconds()
        < settings.HEARTBEAT_STALE_SECONDS
    ]
    latencies = [
        camera.inference_latency_ms
        for camera in fresh
        if camera.inference_latency_ms is not None
    ]
    fps_values = [
        camera.measured_fps for camera in fresh if camera.measured_fps is not None
    ]

    return AiMetrics(
        avg_inference_latency_ms=mean(latencies) if latencies else None,
        avg_fps=mean(fps_values) if fps_values else None,
        sample_camera_count=len(fresh),
        configured_camera_count=len(cameras),
    )


def collect_live_sample(engine: Engine) -> LiveHealthSample:
    """Builds one complete sample. Every provider call already degrades to
    "unavailable" on its own rather than raising (Step 1), so nothing here
    needs its own try/except — a single bad sensor never prevents the rest
    of the sample from being collected."""
    now = datetime.now(UTC)
    cpu = read_cpu()
    memory = read_memory()
    disk = read_disk(settings.SNAPSHOT_ROOT)
    gpus = read_gpus()
    uptime = read_uptime()

    with Session(engine) as session:
        ai_metrics = collect_ai_metrics(session, now=now)

    return LiveHealthSample(
        collected_at=now,
        cpu=cpu,
        memory=memory,
        disk=disk,
        gpus=gpus,
        host_uptime_seconds=uptime.host_uptime_seconds,
        process_uptime_seconds=uptime.process_uptime_seconds,
        avg_inference_latency_ms=ai_metrics.avg_inference_latency_ms,
        avg_fps=ai_metrics.avg_fps,
        sample_camera_count=ai_metrics.sample_camera_count,
        configured_camera_count=ai_metrics.configured_camera_count,
    )


def run_health_sample(engine: Engine, store: HealthStore) -> None:
    """Scheduler job body — every HEALTH_SAMPLE_SECONDS (5s default)."""
    store.set(collect_live_sample(engine))


# ---------------------------------------------------------------------------
# Step 3 — historical persistence, hourly rollup, and pruning
# ---------------------------------------------------------------------------


def persist_raw_sample(
    engine: Engine,
    store: HealthStore,
    *,
    now: datetime,
    persist_interval_seconds: int,
) -> SysHealthRaw | None:
    """Writes the raw subset (01_CONTRACTS.md §3.7) from the retained live
    sample. Skips entirely — never fabricates — when there is no sample
    yet, the retained sample has gone stale (the collector job itself must
    have stopped firing), or cpu/ram (the two NOT NULL columns) are
    unavailable.
    """
    sample = store.sample
    if sample is None:
        logger.info("health_persist_raw: no sample collected yet, skipping")
        return None

    if is_stale(
        sample.collected_at, now=now, interval_seconds=persist_interval_seconds
    ):
        logger.warning(
            "health_persist_raw: retained sample is stale (collected_at=%s), skipping",
            sample.collected_at,
        )
        return None

    if not sample.cpu.available or not sample.memory.available:
        logger.warning(
            "health_persist_raw: cpu or ram usage unavailable, skipping "
            "(both are required columns)"
        )
        return None

    gpu_usages = [g.usage_percent for g in sample.gpus if g.usage_percent is not None]
    gpu_temps = [g.temp_c for g in sample.gpus if g.temp_c is not None]
    gpu_mem_pcts = [g.mem_pct for g in sample.gpus if g.mem_pct is not None]

    row = SysHealthRaw(
        created_at=sample.collected_at,
        cpu_usage=sample.cpu.usage_percent,
        ram_usage=sample.memory.usage_percent,
        gpu_usage_avg=mean(gpu_usages) if gpu_usages else None,
        gpu_temp_max=max(gpu_temps) if gpu_temps else None,
        cpu_temp=sample.cpu.temp_c if sample.cpu.temp_available else None,
        gpu_mem_pct_max=max(gpu_mem_pcts) if gpu_mem_pcts else None,
    )
    with Session(engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def run_persist_raw(engine: Engine, store: HealthStore) -> None:
    persist_raw_sample(
        engine,
        store,
        now=datetime.now(UTC),
        persist_interval_seconds=settings.HEALTH_PERSIST_SECONDS,
    )


def previous_hour_start(now: datetime) -> datetime:
    current_hour_start = now.replace(minute=0, second=0, microsecond=0)
    return current_hour_start - timedelta(hours=1)


def rollup_hour(engine: Engine, hour_start: datetime) -> SysHealthHourly | None:
    """Aggregates every sys_health_raw row in [hour_start, hour_start+1h)
    into the one sys_health_hourly row for that hour. `hour_start` is the
    UNIQUE idempotency key (01_CONTRACTS.md §3.7) — re-running for the same
    hour overwrites the existing row with identical values rather than
    inserting a duplicate. An hour with zero raw rows produces no row at
    all: missed periods are gaps, not fabricated zeros.
    """
    hour_end = hour_start + timedelta(hours=1)
    with Session(engine) as session:
        rows = session.exec(
            select(SysHealthRaw).where(
                col(SysHealthRaw.created_at) >= hour_start,
                col(SysHealthRaw.created_at) < hour_end,
            )
        ).all()
        if not rows:
            return None

        cpu_usages = [r.cpu_usage for r in rows]
        ram_usages = [r.ram_usage for r in rows]
        gpu_usages = [r.gpu_usage_avg for r in rows if r.gpu_usage_avg is not None]
        cpu_temps = [r.cpu_temp for r in rows if r.cpu_temp is not None]
        gpu_temps = [r.gpu_temp_max for r in rows if r.gpu_temp_max is not None]
        gpu_mem_pcts = [
            r.gpu_mem_pct_max for r in rows if r.gpu_mem_pct_max is not None
        ]

        existing = session.exec(
            select(SysHealthHourly).where(col(SysHealthHourly.hour_start) == hour_start)
        ).first()
        hourly = existing or SysHealthHourly(hour_start=hour_start)

        hourly.avg_cpu_usage = mean(cpu_usages)
        hourly.avg_ram_usage = mean(ram_usages)
        hourly.avg_gpu_usage = mean(gpu_usages) if gpu_usages else None
        hourly.avg_cpu_temp = mean(cpu_temps) if cpu_temps else None
        hourly.peak_cpu_temp = max(cpu_temps) if cpu_temps else None
        hourly.peak_gpu_temp = max(gpu_temps) if gpu_temps else None
        hourly.avg_gpu_mem_pct = mean(gpu_mem_pcts) if gpu_mem_pcts else None
        hourly.peak_gpu_mem_pct = max(gpu_mem_pcts) if gpu_mem_pcts else None
        hourly.sample_count = len(rows)

        session.add(hourly)
        session.commit()
        session.refresh(hourly)
        return hourly


def run_hourly_rollup(engine: Engine) -> None:
    rollup_hour(engine, previous_hour_start(datetime.now(UTC)))


def prune_raw(engine: Engine, *, now: datetime, retention_hours: int) -> int:
    """Boundary is inclusive: a row exactly `retention_hours` old is
    pruned; one second younger survives (edge case 2.14)."""
    cutoff = now - timedelta(hours=retention_hours)
    with Session(engine) as session:
        rows = session.exec(
            select(SysHealthRaw).where(col(SysHealthRaw.created_at) <= cutoff)
        ).all()
        for row in rows:
            session.delete(row)
        session.commit()
        return len(rows)


def run_prune_raw(engine: Engine) -> None:
    prune_raw(
        engine,
        now=datetime.now(UTC),
        retention_hours=settings.HEALTH_RAW_RETENTION_HOURS,
    )


def prune_hourly(engine: Engine, *, now: datetime, retention_days: int) -> int:
    """Boundary is inclusive, same as prune_raw (edge case 2.15)."""
    cutoff = now - timedelta(days=retention_days)
    with Session(engine) as session:
        rows = session.exec(
            select(SysHealthHourly).where(col(SysHealthHourly.hour_start) <= cutoff)
        ).all()
        for row in rows:
            session.delete(row)
        session.commit()
        return len(rows)


def run_prune_hourly(engine: Engine) -> None:
    prune_hourly(
        engine,
        now=datetime.now(UTC),
        retention_days=settings.HEALTH_HOURLY_RETENTION_DAYS,
    )
