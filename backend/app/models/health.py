from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class SystemHealthRawBase(SQLModel):
    cpu_usage: float = Field(ge=0.0, le=100.0)
    gpu_usage: float = Field(ge=0.0, le=100.0)
    ram_usage: float = Field(ge=0.0, le=100.0)
    gpu_temperature: float = Field(ge=0.0, le=120.0)


class SystemHealthRaw(SystemHealthRawBase, table=True):
    sys_health_id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class SystemHealthHourlyBase(SQLModel):
    avg_cpu_usage: float = Field(ge=0.0, le=100.0)
    avg_gpu_usage: float = Field(ge=0.0, le=100.0)
    avg_ram_usage: float = Field(ge=0.0, le=100.0)
    peak_gpu_temp: float = Field(ge=0.0, le=120.0)


class SystemHealthHourly(SystemHealthHourlyBase, table=True):
    hourly_sys_health_id: int | None = Field(default=None, primary_key=True)
    created_at_hour: datetime = Field(unique=True, index=True)
