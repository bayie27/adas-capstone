from datetime import UTC, datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel

from app.core.types import UtcDateTime

_PERCENT_CHECK = "{col} IS NULL OR ({col} >= 0.0 AND {col} <= 100.0)"


class SysHealthRawBase(SQLModel):
    cpu_usage: float = Field(ge=0.0, le=100.0)
    ram_usage: float = Field(ge=0.0, le=100.0)
    gpu_usage_avg: float | None = Field(default=None)
    gpu_temp_max: float | None = Field(default=None)
    cpu_temp: float | None = Field(default=None)  # null on Windows
    gpu_mem_pct_max: float | None = Field(default=None)


class SysHealthRaw(SysHealthRawBase, table=True):
    """One row every HEALTH_PERSIST_SECONDS (5 min); retained
    HEALTH_RAW_RETENTION_HOURS (48h)."""

    __tablename__ = "sys_health_raw"
    __table_args__ = (
        CheckConstraint(
            "cpu_usage >= 0.0 AND cpu_usage <= 100.0",
            name="ck_sys_health_raw_cpu_range",
        ),
        CheckConstraint(
            "ram_usage >= 0.0 AND ram_usage <= 100.0",
            name="ck_sys_health_raw_ram_range",
        ),
        CheckConstraint(
            _PERCENT_CHECK.format(col="gpu_usage_avg"),
            name="ck_sys_health_raw_gpu_usage_range",
        ),
        CheckConstraint(
            _PERCENT_CHECK.format(col="gpu_mem_pct_max"),
            name="ck_sys_health_raw_gpu_mem_range",
        ),
    )

    sys_health_id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=UtcDateTime, index=True
    )


class SysHealthHourlyBase(SQLModel):
    avg_cpu_usage: float = Field(ge=0.0, le=100.0)
    avg_ram_usage: float = Field(ge=0.0, le=100.0)
    avg_gpu_usage: float | None = Field(default=None)
    avg_cpu_temp: float | None = Field(default=None)
    peak_cpu_temp: float | None = Field(default=None)
    peak_gpu_temp: float | None = Field(default=None)
    avg_gpu_mem_pct: float | None = Field(default=None)
    peak_gpu_mem_pct: float | None = Field(default=None)


class SysHealthHourly(SysHealthHourlyBase, table=True):
    """One row per UTC hour (the idempotency key is `hour_start`); retained
    HEALTH_HOURLY_RETENTION_DAYS (30 days)."""

    __tablename__ = "sys_health_hourly"
    __table_args__ = (
        CheckConstraint(
            "avg_cpu_usage >= 0.0 AND avg_cpu_usage <= 100.0",
            name="ck_sys_health_hourly_avg_cpu_range",
        ),
        CheckConstraint(
            "avg_ram_usage >= 0.0 AND avg_ram_usage <= 100.0",
            name="ck_sys_health_hourly_avg_ram_range",
        ),
        CheckConstraint(
            _PERCENT_CHECK.format(col="avg_gpu_usage"),
            name="ck_sys_health_hourly_avg_gpu_range",
        ),
        CheckConstraint(
            _PERCENT_CHECK.format(col="avg_gpu_mem_pct"),
            name="ck_sys_health_hourly_avg_gpu_mem_range",
        ),
        CheckConstraint(
            _PERCENT_CHECK.format(col="peak_gpu_mem_pct"),
            name="ck_sys_health_hourly_peak_gpu_mem_range",
        ),
    )

    hourly_id: int | None = Field(default=None, primary_key=True)
    hour_start: datetime = Field(sa_type=UtcDateTime, unique=True, index=True)
    sample_count: int = Field(default=0)
