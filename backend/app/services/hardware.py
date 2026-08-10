"""06_PKG_system_health.md Step 1 — the provider layer.

Every OS/driver call is isolated behind a small function that returns a
value object with an explicit availability flag, so the collector
(app.core.monitor) is testable without real hardware and a single sensor
failure never takes down the rest of the sample (D-009: "sensor/provider
failure does not make the complete endpoint fail when other metrics remain
available").

NVML (`pynvml`, from the `nvidia-ml-py` package) is imported lazily inside
read_gpus() — CI runners and most dev machines have no GPU, and importing
it eagerly would make every import of this module depend on the NVIDIA
driver being present.
"""

import contextlib
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

import psutil

logger = logging.getLogger("uvicorn.error")


@dataclass
class CpuSample:
    available: bool
    usage_percent: float | None = None
    temp_c: float | None = None
    temp_available: bool = False


@dataclass
class MemorySample:
    available: bool
    usage_percent: float | None = None


@dataclass
class DiskSample:
    available: bool
    total_bytes: int | None = None
    used_bytes: int | None = None
    available_bytes: int | None = None
    percent: float | None = None


@dataclass
class GpuSample:
    index: int
    name: str
    usage_percent: float | None = None
    temp_c: float | None = None
    mem_used_mb: float | None = None
    mem_total_mb: float | None = None
    mem_pct: float | None = None


@dataclass
class UptimeSample:
    available: bool
    host_uptime_seconds: float | None = None
    process_uptime_seconds: float | None = None


def read_cpu() -> CpuSample:
    """Usage percent plus temperature where the platform exposes it.

    `psutil.sensors_temperatures()` does not exist as an attribute on
    Windows at all (not an empty dict — the attribute is absent), which is
    why this is a `hasattr` check rather than a call wrapped in try/except:
    on the Windows demo laptop this is expected, not a bug to work around.
    """
    try:
        usage_percent = psutil.cpu_percent(interval=None)
    except Exception:
        logger.warning("read_cpu: usage unavailable", exc_info=True)
        return CpuSample(available=False)

    temp_c: float | None = None
    temp_available = False
    if hasattr(psutil, "sensors_temperatures"):
        try:
            temps = psutil.sensors_temperatures()
            for readings in temps.values():
                if readings:
                    temp_c = readings[0].current
                    temp_available = True
                    break
        except Exception:
            logger.warning("read_cpu: temperature unavailable", exc_info=True)

    return CpuSample(
        available=True,
        usage_percent=usage_percent,
        temp_c=temp_c,
        temp_available=temp_available,
    )


def read_memory() -> MemorySample:
    try:
        return MemorySample(
            available=True, usage_percent=psutil.virtual_memory().percent
        )
    except Exception:
        logger.warning("read_memory: unavailable", exc_info=True)
        return MemorySample(available=False)


def read_disk(path: Path) -> DiskSample:
    """Measured on the volume containing the data root (database +
    snapshots), not C:\\ — the caller passes that path in."""
    try:
        usage = psutil.disk_usage(str(path))
        return DiskSample(
            available=True,
            total_bytes=usage.total,
            used_bytes=usage.used,
            available_bytes=usage.free,
            percent=usage.percent,
        )
    except Exception:
        logger.warning("read_disk: unavailable for %s", path, exc_info=True)
        return DiskSample(available=False)


def read_uptime() -> UptimeSample:
    try:
        now = time.time()
        host_uptime = now - psutil.boot_time()
        process_uptime = now - psutil.Process(os.getpid()).create_time()
        return UptimeSample(
            available=True,
            host_uptime_seconds=host_uptime,
            process_uptime_seconds=process_uptime,
        )
    except Exception:
        logger.warning("read_uptime: unavailable", exc_info=True)
        return UptimeSample(available=False)


def read_gpus() -> list[GpuSample]:
    """Empty list on any failure — no driver, no NVML bindings, no GPUs,
    or an NVML call raising mid-run all degrade the same way: "no GPUs
    available", never a crash."""
    try:
        import pynvml
    except ImportError:
        return []

    try:
        pynvml.nvmlInit()
    except Exception:
        return []

    samples: list[GpuSample] = []
    try:
        device_count = pynvml.nvmlDeviceGetCount()
        for index in range(device_count):
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(index)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8", errors="replace")

                usage_percent: float | None = None
                try:
                    utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    usage_percent = float(utilization.gpu)
                except Exception:
                    logger.warning(
                        "read_gpus: utilization unavailable for device %d",
                        index,
                        exc_info=True,
                    )

                temp_c: float | None = None
                try:
                    temp_c = float(
                        pynvml.nvmlDeviceGetTemperature(
                            handle, pynvml.NVML_TEMPERATURE_GPU
                        )
                    )
                except Exception:
                    logger.warning(
                        "read_gpus: temperature unavailable for device %d",
                        index,
                        exc_info=True,
                    )

                mem_used_mb: float | None = None
                mem_total_mb: float | None = None
                mem_pct: float | None = None
                try:
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    mem_used_mb = mem_info.used / (1024 * 1024)
                    mem_total_mb = mem_info.total / (1024 * 1024)
                    if mem_info.total:
                        mem_pct = (mem_info.used / mem_info.total) * 100.0
                except Exception:
                    logger.warning(
                        "read_gpus: memory unavailable for device %d",
                        index,
                        exc_info=True,
                    )

                samples.append(
                    GpuSample(
                        index=index,
                        name=name,
                        usage_percent=usage_percent,
                        temp_c=temp_c,
                        mem_used_mb=mem_used_mb,
                        mem_total_mb=mem_total_mb,
                        mem_pct=mem_pct,
                    )
                )
            except Exception:
                logger.warning("read_gpus: device %d unavailable", index, exc_info=True)
    except Exception:
        logger.warning("read_gpus: device enumeration failed", exc_info=True)
        return []
    finally:
        with contextlib.suppress(Exception):
            pynvml.nvmlShutdown()

    return samples
