"""06_PKG_system_health.md — P5 system health and hardware telemetry.

Three layers, tested at the level that actually proves them:

- `TestReadCpu` / `TestReadMemory` / `TestReadDisk` / `TestReadUptime` /
  `TestReadGpus` exercise `app.services.hardware` directly with
  `psutil`/`pynvml` monkeypatched to raise or return controlled values —
  Step 1's whole point is that a collector can be tested without real
  hardware.
- `TestCollectAiMetrics` / `TestPersistRawSample` / `TestRollupHour` /
  `TestPruneRaw` / `TestPruneHourly` exercise `app.core.monitor` directly
  against a throwaway SQLite engine — Steps 2-3, no FastAPI involved.
- `TestHealthLiveEndpoint` / `TestHealthHistoryEndpoint` exercise the
  routes through the `client` fixture, injecting a controlled
  `LiveHealthSample` into `client.app.state.health_store` rather than
  relying on real sensors — Step 4.

Covers 06_PKG_system_health.md's "Tests to write" table and the P5-tagged
rows in 14_EDGE_CASES.md: 1.17, 2.14, 2.15, 2.18, 3.6, 3.10, 3.11, 3.12,
3.13, 5.7, 6.7, 6.8, 9.8, 10.7. Camera KPI invariants (the doc's Step 5)
live in test_cameras.py, where the KPI semantics themselves live.
"""

import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from app.core.monitor import (
    HealthStore,
    LiveHealthSample,
    collect_ai_metrics,
    is_stale,
    persist_raw_sample,
    previous_hour_start,
    prune_hourly,
    prune_raw,
    rollup_hour,
)
from app.models import SysHealthHourly, SysHealthRaw
from app.services import hardware
from app.services.hardware import CpuSample, DiskSample, GpuSample, MemorySample
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import auth_headers, make_camera, make_operator

# ---------------------------------------------------------------------------
# Step 1 — provider layer
# ---------------------------------------------------------------------------


class TestReadCpu:
    def test_usage_available(self, monkeypatch):
        monkeypatch.setattr(hardware.psutil, "cpu_percent", lambda interval=None: 42.0)
        monkeypatch.delattr(hardware.psutil, "sensors_temperatures", raising=False)

        sample = hardware.read_cpu()

        assert sample.available is True
        assert sample.usage_percent == 42.0

    def test_usage_unavailable_on_raise(self, monkeypatch):
        def _boom(interval=None):
            raise OSError("no cpu stats")

        monkeypatch.setattr(hardware.psutil, "cpu_percent", _boom)

        sample = hardware.read_cpu()

        assert sample.available is False
        assert sample.usage_percent is None

    def test_temp_absent_attribute_is_none_never_zero(self, monkeypatch):
        """Edge case / Step 1 — `sensors_temperatures` doesn't exist as an
        attribute on Windows at all. Null with a False flag, not 0."""
        monkeypatch.setattr(hardware.psutil, "cpu_percent", lambda interval=None: 10.0)
        monkeypatch.delattr(hardware.psutil, "sensors_temperatures", raising=False)

        sample = hardware.read_cpu()

        assert sample.available is True
        assert sample.temp_c is None
        assert sample.temp_available is False

    def test_temp_available_when_platform_reports_it(self, monkeypatch):
        monkeypatch.setattr(hardware.psutil, "cpu_percent", lambda interval=None: 10.0)
        monkeypatch.setattr(
            hardware.psutil,
            "sensors_temperatures",
            lambda: {"coretemp": [SimpleNamespace(current=55.5)]},
            raising=False,
        )

        sample = hardware.read_cpu()

        assert sample.temp_c == 55.5
        assert sample.temp_available is True

    def test_temp_read_failure_does_not_fail_the_whole_sample(self, monkeypatch):
        monkeypatch.setattr(hardware.psutil, "cpu_percent", lambda interval=None: 10.0)

        def _boom():
            raise OSError("sensor gone")

        monkeypatch.setattr(
            hardware.psutil, "sensors_temperatures", _boom, raising=False
        )

        sample = hardware.read_cpu()

        assert sample.available is True
        assert sample.usage_percent == 10.0
        assert sample.temp_c is None
        assert sample.temp_available is False


class TestReadMemory:
    def test_available(self, monkeypatch):
        monkeypatch.setattr(
            hardware.psutil,
            "virtual_memory",
            lambda: SimpleNamespace(percent=61.2),
        )
        sample = hardware.read_memory()
        assert sample.available is True
        assert sample.usage_percent == 61.2

    def test_unavailable_on_raise(self, monkeypatch):
        def _boom():
            raise OSError("no memory stats")

        monkeypatch.setattr(hardware.psutil, "virtual_memory", _boom)
        sample = hardware.read_memory()
        assert sample.available is False
        assert sample.usage_percent is None


class TestReadDisk:
    def test_available(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            hardware.psutil,
            "disk_usage",
            lambda path: SimpleNamespace(total=1000, used=800, free=200, percent=80.0),
        )
        sample = hardware.read_disk(tmp_path)
        assert sample.available is True
        assert sample.total_bytes == 1000
        assert sample.used_bytes == 800
        assert sample.available_bytes == 200
        assert sample.percent == 80.0

    def test_unavailable_on_raise(self, monkeypatch, tmp_path):
        def _boom(path):
            raise OSError("no such volume")

        monkeypatch.setattr(hardware.psutil, "disk_usage", _boom)
        sample = hardware.read_disk(tmp_path)
        assert sample.available is False
        assert sample.total_bytes is None


class TestReadUptime:
    def test_available(self, monkeypatch):
        monkeypatch.setattr(hardware.time, "time", lambda: 1_000_000.0)
        monkeypatch.setattr(hardware.psutil, "boot_time", lambda: 999_000.0)
        monkeypatch.setattr(
            hardware.psutil,
            "Process",
            lambda pid: SimpleNamespace(create_time=lambda: 999_500.0),
        )

        sample = hardware.read_uptime()

        assert sample.available is True
        assert sample.host_uptime_seconds == 1000.0
        assert sample.process_uptime_seconds == 500.0

    def test_unavailable_on_raise(self, monkeypatch):
        def _boom():
            raise OSError("no boot time")

        monkeypatch.setattr(hardware.psutil, "boot_time", _boom)
        sample = hardware.read_uptime()
        assert sample.available is False


class TestReadGpus:
    def test_no_nvml_bindings_returns_empty_list(self, monkeypatch):
        """NVML isn't installed / importable at all — degrade to "no GPUs",
        never raise. `sys.modules["pynvml"] = None` is the documented way
        to make `import pynvml` raise ImportError deterministically."""
        import sys

        monkeypatch.setitem(sys.modules, "pynvml", None)
        assert hardware.read_gpus() == []

    def test_nvml_init_failure_returns_empty_list(self, monkeypatch):
        import pynvml

        def _boom():
            raise pynvml.NVMLError(pynvml.NVML_ERROR_LIBRARY_NOT_FOUND)

        monkeypatch.setattr(pynvml, "nvmlInit", _boom)
        assert hardware.read_gpus() == []

    def test_no_devices_present_returns_empty_list(self, monkeypatch):
        import pynvml

        monkeypatch.setattr(pynvml, "nvmlInit", lambda: None)
        monkeypatch.setattr(pynvml, "nvmlShutdown", lambda: None)
        monkeypatch.setattr(pynvml, "nvmlDeviceGetCount", lambda: 0)

        assert hardware.read_gpus() == []

    def test_multi_gpu_reads_each_device_independently(self, monkeypatch):
        """Step 1 / "Tests to write": mocked 4-GPU NVML. Aggregation
        (mean/max/max) is verified separately against the live endpoint —
        this just proves each device's raw reading is captured correctly."""
        import pynvml

        usages = [10.0, 20.0, 30.0, 40.0]
        temps = [40.0, 50.0, 60.0, 70.0]
        used_mb = [1000.0, 2000.0, 3000.0, 4000.0]
        total_mb = 4096.0

        monkeypatch.setattr(pynvml, "nvmlInit", lambda: None)
        monkeypatch.setattr(pynvml, "nvmlShutdown", lambda: None)
        monkeypatch.setattr(pynvml, "nvmlDeviceGetCount", lambda: 4)
        monkeypatch.setattr(pynvml, "nvmlDeviceGetHandleByIndex", lambda i: i)
        monkeypatch.setattr(pynvml, "nvmlDeviceGetName", lambda h: f"GPU-{h}".encode())
        monkeypatch.setattr(
            pynvml,
            "nvmlDeviceGetUtilizationRates",
            lambda h: SimpleNamespace(gpu=usages[h]),
        )
        monkeypatch.setattr(
            pynvml,
            "nvmlDeviceGetTemperature",
            lambda h, sensor: temps[h],
        )
        monkeypatch.setattr(
            pynvml,
            "nvmlDeviceGetMemoryInfo",
            lambda h: SimpleNamespace(
                used=used_mb[h] * 1024 * 1024, total=total_mb * 1024 * 1024
            ),
        )

        gpus = hardware.read_gpus()

        assert len(gpus) == 4
        assert [g.index for g in gpus] == [0, 1, 2, 3]
        assert [g.name for g in gpus] == ["GPU-0", "GPU-1", "GPU-2", "GPU-3"]
        assert [g.usage_percent for g in gpus] == usages
        assert [g.temp_c for g in gpus] == temps
        assert gpus[3].mem_pct == used_mb[3] / total_mb * 100

    def test_one_device_failing_does_not_drop_the_others(self, monkeypatch):
        """A single-device read failure degrades that device's field to
        None rather than aborting enumeration of the rest."""
        import pynvml

        monkeypatch.setattr(pynvml, "nvmlInit", lambda: None)
        monkeypatch.setattr(pynvml, "nvmlShutdown", lambda: None)
        monkeypatch.setattr(pynvml, "nvmlDeviceGetCount", lambda: 2)
        monkeypatch.setattr(pynvml, "nvmlDeviceGetHandleByIndex", lambda i: i)
        monkeypatch.setattr(pynvml, "nvmlDeviceGetName", lambda h: f"GPU-{h}")

        def _util(h):
            if h == 0:
                raise pynvml.NVMLError(pynvml.NVML_ERROR_UNKNOWN)
            return SimpleNamespace(gpu=99.0)

        monkeypatch.setattr(pynvml, "nvmlDeviceGetUtilizationRates", _util)
        monkeypatch.setattr(pynvml, "nvmlDeviceGetTemperature", lambda h, s: 50.0)
        monkeypatch.setattr(
            pynvml,
            "nvmlDeviceGetMemoryInfo",
            lambda h: SimpleNamespace(used=1024 * 1024, total=4096 * 1024 * 1024),
        )

        gpus = hardware.read_gpus()

        assert len(gpus) == 2
        assert gpus[0].usage_percent is None
        assert gpus[1].usage_percent == 99.0


# ---------------------------------------------------------------------------
# Step 2 — the live collector's supporting pieces
# ---------------------------------------------------------------------------


class TestIsStale:
    def test_exactly_one_interval_old_is_stale(self):
        now = datetime.now(UTC)
        collected_at = now - timedelta(seconds=5)
        assert is_stale(collected_at, now=now, interval_seconds=5) is True

    def test_just_under_one_interval_is_fresh(self):
        now = datetime.now(UTC)
        collected_at = now - timedelta(seconds=4.9)
        assert is_stale(collected_at, now=now, interval_seconds=5) is False


class TestCollectAiMetrics:
    def test_only_fresh_heartbeats_contribute(self, session: Session):
        now = datetime.now(UTC)
        make_camera(
            session,
            name="Fresh",
            channel_id=1,
            last_heartbeat_at=now,
        )
        stale = make_camera(
            session,
            name="Stale",
            channel_id=2,
            last_heartbeat_at=now - timedelta(seconds=30),
        )
        stale.measured_fps = 15.0
        stale.inference_latency_ms = 5.0
        session.add(stale)
        session.commit()

        metrics = collect_ai_metrics(session, now=now)

        assert metrics.sample_camera_count == 1
        assert metrics.configured_camera_count == 2

    def test_averages_ignore_missing_fps_or_latency(self, session: Session):
        now = datetime.now(UTC)
        cam_a = make_camera(session, name="A", channel_id=1, last_heartbeat_at=now)
        cam_a.measured_fps = 10.0
        cam_a.inference_latency_ms = 40.0
        cam_b = make_camera(session, name="B", channel_id=2, last_heartbeat_at=now)
        cam_b.measured_fps = 20.0
        cam_b.inference_latency_ms = None
        session.add(cam_a)
        session.add(cam_b)
        session.commit()

        metrics = collect_ai_metrics(session, now=now)

        assert metrics.sample_camera_count == 2
        assert metrics.avg_fps == 15.0
        assert metrics.avg_inference_latency_ms == 40.0

    def test_disabled_or_inactive_cameras_excluded_from_configured_count(
        self, session: Session
    ):
        now = datetime.now(UTC)
        make_camera(session, name="Disabled", channel_id=1, is_enabled=False)
        make_camera(session, name="Enabled", channel_id=2)

        metrics = collect_ai_metrics(session, now=now)

        assert metrics.configured_camera_count == 1

    def test_soft_deleted_camera_excluded_from_configured_count(self, session: Session):
        """Edge case 9.8 — the population is is_active=1, same as the
        camera KPI invariants."""
        now = datetime.now(UTC)
        deleted = make_camera(session, name="Deleted", channel_id=1, is_active=False)
        make_camera(session, name="Kept", channel_id=2)

        metrics = collect_ai_metrics(session, now=now)

        assert metrics.configured_camera_count == 1
        assert deleted.is_active is False

    def test_heartbeat_staleness_boundary(self, session: Session):
        """Edge case 2.18 — exactly HEARTBEAT_STALE_SECONDS (10s) old does
        not contribute; 9.9s old does. Same threshold as
        app.services.cameras.presented_statuses(), applied here to AI
        metric averaging instead of presented connection/AI status."""
        now = datetime.now(UTC)
        fresh = make_camera(
            session,
            name="Fresh",
            channel_id=1,
            last_heartbeat_at=now - timedelta(seconds=9.9),
        )
        fresh.measured_fps = 10.0
        stale = make_camera(
            session,
            name="Stale",
            channel_id=2,
            last_heartbeat_at=now - timedelta(seconds=10),
        )
        stale.measured_fps = 99.0
        session.add(fresh)
        session.add(stale)
        session.commit()

        metrics = collect_ai_metrics(session, now=now)

        assert metrics.sample_camera_count == 1
        assert metrics.avg_fps == 10.0

    def test_zero_cameras_is_a_clean_zero_state(self, session: Session):
        """Edge case 3.6 — zero cameras registered still returns a valid,
        non-crashing shape."""
        metrics = collect_ai_metrics(session, now=datetime.now(UTC))

        assert metrics.sample_camera_count == 0
        assert metrics.configured_camera_count == 0
        assert metrics.avg_fps is None
        assert metrics.avg_inference_latency_ms is None


# ---------------------------------------------------------------------------
# Step 3 — historical persistence, rollup, pruning
# ---------------------------------------------------------------------------


def _sample(
    *,
    collected_at: datetime,
    cpu_available: bool = True,
    cpu_usage: float | None = 50.0,
    ram_available: bool = True,
    ram_usage: float | None = 40.0,
    gpus: list[GpuSample] | None = None,
) -> LiveHealthSample:
    return LiveHealthSample(
        collected_at=collected_at,
        cpu=CpuSample(
            available=cpu_available,
            usage_percent=cpu_usage,
            temp_c=None,
            temp_available=False,
        ),
        memory=MemorySample(available=ram_available, usage_percent=ram_usage),
        disk=DiskSample(available=False),
        gpus=gpus or [],
        host_uptime_seconds=100.0,
        process_uptime_seconds=10.0,
        avg_inference_latency_ms=None,
        avg_fps=None,
        sample_camera_count=0,
        configured_camera_count=0,
    )


class TestPersistRawSample:
    def test_no_fabrication_when_store_is_empty(self, session: Session):
        """Edge case — no sample yet must never write a fabricated row."""
        store = HealthStore()
        row = persist_raw_sample(
            session.get_bind(),
            store,
            now=datetime.now(UTC),
            persist_interval_seconds=300,
        )
        assert row is None
        assert session.exec(select(SysHealthRaw)).all() == []

    def test_skips_when_retained_sample_is_stale(self, session: Session):
        now = datetime.now(UTC)
        store = HealthStore()
        store.set(_sample(collected_at=now - timedelta(seconds=301)))

        row = persist_raw_sample(
            session.get_bind(), store, now=now, persist_interval_seconds=300
        )

        assert row is None
        assert session.exec(select(SysHealthRaw)).all() == []

    def test_skips_when_cpu_or_ram_unavailable(self, session: Session):
        now = datetime.now(UTC)
        store = HealthStore()
        store.set(_sample(collected_at=now, cpu_available=False))

        row = persist_raw_sample(
            session.get_bind(), store, now=now, persist_interval_seconds=300
        )

        assert row is None
        assert session.exec(select(SysHealthRaw)).all() == []

    def test_writes_gpu_aggregates_max_not_mean(self, session: Session):
        """GPU temperature and memory pressure aggregate as the max across
        devices, never a mean that would hide one nearly exhausted GPU."""
        now = datetime.now(UTC)
        gpus = [
            GpuSample(
                index=0,
                name="A",
                usage_percent=10.0,
                temp_c=40.0,
                mem_pct=20.0,
            ),
            GpuSample(
                index=1,
                name="B",
                usage_percent=30.0,
                temp_c=80.0,
                mem_pct=95.0,
            ),
        ]
        store = HealthStore()
        store.set(_sample(collected_at=now, gpus=gpus))

        row = persist_raw_sample(
            session.get_bind(), store, now=now, persist_interval_seconds=300
        )

        assert row is not None
        assert row.gpu_usage_avg == 20.0  # mean(10, 30)
        assert row.gpu_temp_max == 80.0  # max, not mean
        assert row.gpu_mem_pct_max == 95.0  # max, not mean

    def test_no_gpus_yields_null_aggregates_not_zero(self, session: Session):
        now = datetime.now(UTC)
        store = HealthStore()
        store.set(_sample(collected_at=now, gpus=[]))

        row = persist_raw_sample(
            session.get_bind(), store, now=now, persist_interval_seconds=300
        )

        assert row is not None
        assert row.gpu_usage_avg is None
        assert row.gpu_temp_max is None
        assert row.gpu_mem_pct_max is None


class TestPreviousHourStart:
    def test_truncates_to_the_prior_hour(self):
        now = datetime(2026, 3, 5, 14, 37, 22, tzinfo=UTC)
        assert previous_hour_start(now) == datetime(2026, 3, 5, 13, 0, 0, tzinfo=UTC)

    def test_crosses_the_midnight_utc_day_boundary(self):
        """Edge case 5.8 — just after midnight rolls back to 23:00 on the
        *previous* date, not 23:00 on the same (wrong) date."""
        now = datetime(2026, 3, 5, 0, 30, 0, tzinfo=UTC)
        assert previous_hour_start(now) == datetime(2026, 3, 4, 23, 0, 0, tzinfo=UTC)


def _raw_row(
    created_at: datetime,
    *,
    cpu=50.0,
    ram=40.0,
    gpu_usage=None,
    gpu_temp=None,
    cpu_temp=None,
    gpu_mem=None,
) -> SysHealthRaw:
    return SysHealthRaw(
        created_at=created_at,
        cpu_usage=cpu,
        ram_usage=ram,
        gpu_usage_avg=gpu_usage,
        gpu_temp_max=gpu_temp,
        cpu_temp=cpu_temp,
        gpu_mem_pct_max=gpu_mem,
    )


class TestRollupHour:
    def test_no_rows_produces_no_row(self, session: Session):
        """Edge case 3.13 / 10.7's inverse — a missed period is a gap, not
        a fabricated row."""
        hour_start = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        result = rollup_hour(session.get_bind(), hour_start)
        assert result is None
        assert session.exec(select(SysHealthHourly)).all() == []

    def test_twelve_five_minute_rows_produce_one_row_with_correct_stats(
        self, session: Session
    ):
        hour_start = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        for i in range(12):
            session.add(
                _raw_row(
                    hour_start + timedelta(minutes=5 * i),
                    cpu=float(i),
                    ram=float(i) + 1,
                    gpu_usage=float(i) + 2,
                    gpu_temp=float(i) + 3,
                    cpu_temp=float(i) + 4,
                    gpu_mem=float(i) + 5,
                )
            )
        session.commit()

        hourly = rollup_hour(session.get_bind(), hour_start)

        assert hourly is not None
        assert hourly.sample_count == 12
        assert hourly.avg_cpu_usage == sum(range(12)) / 12
        assert hourly.avg_ram_usage == sum(i + 1 for i in range(12)) / 12
        assert hourly.avg_gpu_usage == sum(i + 2 for i in range(12)) / 12
        assert hourly.avg_cpu_temp == sum(i + 4 for i in range(12)) / 12
        assert hourly.peak_cpu_temp == 4 + 11
        assert hourly.peak_gpu_temp == 3 + 11
        assert hourly.avg_gpu_mem_pct == sum(i + 5 for i in range(12)) / 12
        assert hourly.peak_gpu_mem_pct == 5 + 11

    def test_boundary_rows_land_in_exactly_one_hour(self, session: Session):
        """Edge case 5.7 — a row exactly at a UTC hour boundary lands in
        exactly one bucket, not zero and not two."""
        hour_start = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        session.add(_raw_row(hour_start))  # in this hour
        session.add(_raw_row(hour_start + timedelta(hours=1)))  # next hour
        session.commit()

        hourly = rollup_hour(session.get_bind(), hour_start)

        assert hourly is not None
        assert hourly.sample_count == 1

    def test_rerunning_is_idempotent(self, session: Session):
        """Edge case 1.17 / 10.7 — running the rollup twice for the same
        hour produces one row with identical values via the hour_start
        unique key, not a duplicate."""
        hour_start = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        session.add(_raw_row(hour_start, cpu=10.0, ram=20.0))
        session.add(_raw_row(hour_start + timedelta(minutes=5), cpu=30.0, ram=40.0))
        session.commit()

        first = rollup_hour(session.get_bind(), hour_start)
        second = rollup_hour(session.get_bind(), hour_start)

        rows = session.exec(select(SysHealthHourly)).all()
        assert len(rows) == 1
        assert first.avg_cpu_usage == second.avg_cpu_usage == 20.0
        assert first.avg_ram_usage == second.avg_ram_usage == 30.0
        assert first.sample_count == second.sample_count == 2

    def test_hour_with_no_gpu_data_yields_null_not_zero(self, session: Session):
        hour_start = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        session.add(_raw_row(hour_start))
        session.add(_raw_row(hour_start + timedelta(minutes=5)))
        session.commit()

        hourly = rollup_hour(session.get_bind(), hour_start)

        assert hourly is not None
        assert hourly.avg_gpu_usage is None
        assert hourly.avg_cpu_temp is None
        assert hourly.peak_cpu_temp is None
        assert hourly.peak_gpu_temp is None
        assert hourly.avg_gpu_mem_pct is None
        assert hourly.peak_gpu_mem_pct is None


class TestPruneRaw:
    def test_boundary_is_inclusive(self, session: Session):
        """Edge case 2.14 — exactly 48h old is pruned; 47h59m survives."""
        now = datetime(2026, 1, 3, 0, 0, 0, tzinfo=UTC)
        exactly_48h = _raw_row(now - timedelta(hours=48))
        just_under = _raw_row(now - timedelta(hours=47, minutes=59))
        session.add(exactly_48h)
        session.add(just_under)
        session.commit()

        deleted = prune_raw(session.get_bind(), now=now, retention_hours=48)

        remaining = session.exec(select(SysHealthRaw)).all()
        assert deleted == 1
        assert len(remaining) == 1
        assert remaining[0].created_at == just_under.created_at


class TestPruneHourly:
    def test_boundary_is_inclusive(self, session: Session):
        """Edge case 2.15 — exactly 30d old is pruned; 29d23h survives."""
        now = datetime(2026, 2, 1, 0, 0, 0, tzinfo=UTC)
        old = SysHealthHourly(
            hour_start=now - timedelta(days=30),
            avg_cpu_usage=1.0,
            avg_ram_usage=1.0,
            sample_count=1,
        )
        recent = SysHealthHourly(
            hour_start=now - timedelta(days=29, hours=23),
            avg_cpu_usage=1.0,
            avg_ram_usage=1.0,
            sample_count=1,
        )
        session.add(old)
        session.add(recent)
        session.commit()

        deleted = prune_hourly(session.get_bind(), now=now, retention_days=30)

        remaining = session.exec(select(SysHealthHourly)).all()
        assert deleted == 1
        assert len(remaining) == 1
        assert remaining[0].hour_start == recent.hour_start


# ---------------------------------------------------------------------------
# Step 4 — endpoints
# ---------------------------------------------------------------------------


def _operator_headers(client: TestClient, session: Session) -> dict:
    make_operator(session, username="healthop", password="Operator123")
    return auth_headers(client, "healthop", "Operator123")


class TestHealthLiveEndpoint:
    def test_requires_auth(self, client: TestClient):
        resp = client.get("/api/system/health/live")
        assert resp.status_code == 401

    def test_no_sample_yet_is_explicit_not_fabricated(
        self, client: TestClient, session: Session
    ):
        """Edge case 3.11 — before the first sample completes, this is an
        explicit "no sample yet" state, not nulls masquerading as
        readings."""
        headers = _operator_headers(client, session)

        resp = client.get("/api/system/health/live", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["collected_at"] is None
        assert body["cpu_usage"] is None
        assert body["cpu_usage_available"] is False
        assert body["gpus"] == []
        assert body["gpu_usage_avg"] is None

    def test_fresh_sample_reports_readings_and_is_not_stale(
        self, client: TestClient, session: Session
    ):
        headers = _operator_headers(client, session)
        now = datetime.now(UTC)
        client.app.state.health_store.set(
            _sample(collected_at=now, cpu_usage=25.0, ram_usage=30.0)
        )

        resp = client.get("/api/system/health/live", headers=headers)

        body = resp.json()
        assert body["stale"] is False
        assert body["cpu_usage"] == 25.0
        assert body["ram_usage"] == 30.0

    def test_retained_sample_older_than_interval_is_flagged_stale(
        self, client: TestClient, session: Session
    ):
        """A sample older than one collection interval is flagged stale but
        keeps its original collection timestamp — never silently presented
        as fresh."""
        headers = _operator_headers(client, session)
        old_collected_at = datetime.now(UTC) - timedelta(seconds=999)
        client.app.state.health_store.set(_sample(collected_at=old_collected_at))

        resp = client.get("/api/system/health/live", headers=headers)

        body = resp.json()
        assert body["stale"] is True
        assert body["collected_at"] is not None
        assert datetime.fromisoformat(body["collected_at"]).replace(
            microsecond=0
        ) == old_collected_at.replace(microsecond=0)

    def test_no_gpu_present_yields_empty_list_and_null_aggregates(
        self, client: TestClient, session: Session
    ):
        headers = _operator_headers(client, session)
        client.app.state.health_store.set(
            _sample(collected_at=datetime.now(UTC), gpus=[])
        )

        resp = client.get("/api/system/health/live", headers=headers)

        body = resp.json()
        assert body["gpus"] == []
        assert body["gpu_usage_avg"] is None
        assert body["gpu_temp_max"] is None
        assert body["gpu_mem_pct_max"] is None
        assert resp.status_code == 200

    def test_single_sensor_unavailable_does_not_fail_the_endpoint(
        self, client: TestClient, session: Session
    ):
        """Edge case 6.8 — cpu usage unavailable (psutil raised) still
        returns 200 with every other metric intact, not a 500."""
        headers = _operator_headers(client, session)
        client.app.state.health_store.set(
            _sample(
                collected_at=datetime.now(UTC),
                cpu_available=False,
                cpu_usage=None,
                ram_usage=33.0,
            )
        )

        resp = client.get("/api/system/health/live", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["cpu_usage"] is None
        assert body["cpu_usage_available"] is False
        assert body["ram_usage"] == 33.0
        assert body["ram_usage_available"] is True

    def test_multi_gpu_aggregation_mean_max_max(
        self, client: TestClient, session: Session
    ):
        headers = _operator_headers(client, session)
        gpus = [
            GpuSample(index=0, name="A", usage_percent=10.0, temp_c=40.0, mem_pct=20.0),
            GpuSample(index=1, name="B", usage_percent=30.0, temp_c=80.0, mem_pct=95.0),
            GpuSample(index=2, name="C", usage_percent=50.0, temp_c=60.0, mem_pct=50.0),
        ]
        client.app.state.health_store.set(
            _sample(collected_at=datetime.now(UTC), gpus=gpus)
        )

        resp = client.get("/api/system/health/live", headers=headers)

        body = resp.json()
        assert body["gpu_usage_avg"] == 30.0  # mean(10, 30, 50)
        assert body["gpu_temp_max"] == 80.0  # max, not mean
        assert body["gpu_mem_pct_max"] == 95.0  # max, not mean

    def test_gpu_temp_critical_warning(self, client: TestClient, session: Session):
        headers = _operator_headers(client, session)
        gpus = [GpuSample(index=0, name="A", temp_c=85.0)]
        client.app.state.health_store.set(
            _sample(collected_at=datetime.now(UTC), gpus=gpus)
        )

        body = client.get("/api/system/health/live", headers=headers).json()

        codes = {w["code"] for w in body["warnings"]}
        assert "GPU_TEMP_CRITICAL" in codes
        warning = next(w for w in body["warnings"] if w["code"] == "GPU_TEMP_CRITICAL")
        assert warning["severity"] == "critical"
        assert warning["measurement"] == 85.0
        assert warning["threshold"] == 85.0
        assert body["state"] == "critical"

    def test_ram_critical_warning(self, client: TestClient, session: Session):
        headers = _operator_headers(client, session)
        client.app.state.health_store.set(
            _sample(collected_at=datetime.now(UTC), ram_usage=95.0)
        )

        body = client.get("/api/system/health/live", headers=headers).json()

        codes = {w["code"] for w in body["warnings"]}
        assert "RAM_CRITICAL" in codes
        assert body["state"] == "critical"

    def test_disk_warning_vs_critical(self, client: TestClient, session: Session):
        headers = _operator_headers(client, session)
        sample = _sample(collected_at=datetime.now(UTC))
        sample.disk = DiskSample(
            available=True,
            total_bytes=100,
            used_bytes=85,
            available_bytes=15,
            percent=85.0,
        )
        client.app.state.health_store.set(sample)

        body = client.get("/api/system/health/live", headers=headers).json()
        codes = {w["code"] for w in body["warnings"]}
        assert "DISK_WARNING" in codes
        assert "DISK_CRITICAL" not in codes
        assert body["state"] == "degraded"

        sample.disk = DiskSample(
            available=True,
            total_bytes=100,
            used_bytes=95,
            available_bytes=5,
            percent=95.0,
        )
        client.app.state.health_store.set(sample)
        body = client.get("/api/system/health/live", headers=headers).json()
        codes = {w["code"] for w in body["warnings"]}
        assert "DISK_CRITICAL" in codes
        assert body["state"] == "critical"

    def test_ai_heartbeat_stale_warning_only_when_cameras_configured(
        self, client: TestClient, session: Session
    ):
        """The warning must fire when cameras are configured but none
        reported fresh (edge case 6.19), and must NOT fire just because
        zero cameras are registered at all (edge case 3.6) — those look
        identical from sample_camera_count alone."""
        headers = _operator_headers(client, session)

        no_cameras = _sample(collected_at=datetime.now(UTC))
        no_cameras.configured_camera_count = 0
        no_cameras.sample_camera_count = 0
        client.app.state.health_store.set(no_cameras)
        body = client.get("/api/system/health/live", headers=headers).json()
        assert "AI_HEARTBEAT_STALE" not in {w["code"] for w in body["warnings"]}

        cameras_but_silent = _sample(collected_at=datetime.now(UTC))
        cameras_but_silent.configured_camera_count = 3
        cameras_but_silent.sample_camera_count = 0
        client.app.state.health_store.set(cameras_but_silent)
        body = client.get("/api/system/health/live", headers=headers).json()
        assert "AI_HEARTBEAT_STALE" in {w["code"] for w in body["warnings"]}

    def test_sustained_stale_ai_engine_never_logs_a_warning_line(
        self, client: TestClient, session: Session, caplog: pytest.LogCaptureFixture
    ):
        """Edge case 6.19's "no runaway logging" half. AI_HEARTBEAT_STALE
        is a per-request field in the JSON response (computed fresh each
        time from the current health sample, never written to a log), and
        presented camera status (Unresponsive) is likewise a pure,
        stateless read-time computation in app/services/cameras.py with no
        logging call in that path at all — so repeated polling under
        sustained AI-engine silence is bounded to zero log lines by
        construction, not merely "not too many." Simulates an extended
        outage as many polls in a tight loop rather than actually waiting,
        since the mechanism is stateless and doesn't care about wall time."""
        headers = _operator_headers(client, session)
        stale_sample = _sample(collected_at=datetime.now(UTC))
        stale_sample.configured_camera_count = 3
        stale_sample.sample_camera_count = 0
        client.app.state.health_store.set(stale_sample)

        with caplog.at_level(logging.WARNING):
            for _ in range(20):
                resp = client.get("/api/system/health/live", headers=headers)
                assert resp.status_code == 200
                cams = client.get("/api/cameras/", headers=headers)
                assert cams.status_code == 200

        assert caplog.records == []

    def test_healthy_state_when_no_warnings(self, client: TestClient, session: Session):
        headers = _operator_headers(client, session)
        client.app.state.health_store.set(
            _sample(collected_at=datetime.now(UTC), cpu_usage=10.0, ram_usage=10.0)
        )
        sample = client.app.state.health_store.sample
        sample.disk = DiskSample(
            available=True,
            total_bytes=100,
            used_bytes=10,
            available_bytes=90,
            percent=10.0,
        )
        client.app.state.health_store.set(sample)

        body = client.get("/api/system/health/live", headers=headers).json()
        assert body["warnings"] == []
        assert body["state"] == "healthy"


class TestHealthHistoryEndpoint:
    def test_requires_auth(self, client: TestClient):
        resp = client.get("/api/system/health/history?range=48h")
        assert resp.status_code == 401

    def test_invalid_range_is_422(self, client: TestClient, session: Session):
        headers = _operator_headers(client, session)
        resp = client.get("/api/system/health/history?range=bogus", headers=headers)
        assert resp.status_code == 422

    def test_gap_in_data_is_a_missing_point_not_a_zero(
        self, client: TestClient, session: Session
    ):
        """Edge case 3.12 — a collection gap must never render as a
        fabricated zero-valued point."""
        headers = _operator_headers(client, session)
        now = datetime.now(UTC)
        session.add(_raw_row(now - timedelta(hours=1), cpu=10.0))
        session.add(_raw_row(now - timedelta(minutes=5), cpu=20.0))
        session.commit()

        resp = client.get("/api/system/health/history?range=48h", headers=headers)

        body = resp.json()
        assert len(body["points"]) == 2  # not a padded/interpolated series

    def test_one_consistent_shape_for_raw_and_hourly(
        self, client: TestClient, session: Session
    ):
        headers = _operator_headers(client, session)
        now = datetime.now(UTC)
        session.add(_raw_row(now, cpu=10.0, ram=20.0, gpu_usage=5.0, gpu_temp=40.0))
        session.add(
            SysHealthHourly(
                hour_start=now - timedelta(days=1),
                avg_cpu_usage=15.0,
                avg_ram_usage=25.0,
                avg_gpu_usage=6.0,
                peak_gpu_temp=45.0,
                sample_count=12,
            )
        )
        session.commit()

        raw_body = client.get(
            "/api/system/health/history?range=48h", headers=headers
        ).json()
        hourly_body = client.get(
            "/api/system/health/history?range=30d", headers=headers
        ).json()

        assert set(raw_body["points"][0].keys()) == set(hourly_body["points"][0].keys())
        assert raw_body["points"][0]["sample_count"] == 1
        assert hourly_body["points"][0]["sample_count"] == 12

    def test_zero_matching_rows_returns_empty_list(
        self, client: TestClient, session: Session
    ):
        headers = _operator_headers(client, session)
        resp = client.get("/api/system/health/history?range=48h", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["points"] == []
