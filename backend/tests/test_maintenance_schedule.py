"""be_plan/18_PKG_scheduled_maintenance.md Step 1/Step 7 — the in-app daily
backup job (NFR-18), its due-check, and the cron trigger's timezone
correctness.

`TestRunDailyBackup` / `TestScheduledBackupIsDue` / `TestRunDailyBackupIfDue`
exercise `app.services.maintenance_schedule` directly against a real
temporary SQLite file, matching test_maintenance.py's "pure Python core"
convention — `run_daily_backup` only needs a bare SQLAlchemy `Engine`, no
FastAPI TestClient. `TestDailyBackupCronTimezone` and
`TestDailyBackupCronDstBehavior` replace the old edge-case-5.10/5.11
`pytest.skip` in test_maintenance.py::TestSchedulingEdgeCases for the
backup half — see that class's docstring for why the restart half stays a
documented skip.
"""

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from app.core.config import Settings
from app.main import create_app
from app.maintenance.backup import create_backup, maintenance_lock
from app.maintenance.manifest import ORIGIN_MANUAL, ORIGIN_SCHEDULED, db_path_for
from app.models import AuditLog
from app.services.maintenance_schedule import (
    newest_scheduled_manifest,
    run_daily_backup,
    run_daily_backup_if_due,
    scheduled_backup_is_due,
)
from fastapi.testclient import TestClient
from sqlmodel import select


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO t (v) VALUES ('seed')")
    conn.commit()
    conn.close()


@pytest.fixture
def sched_paths(tmp_path, monkeypatch):
    """Points the module-global app.core.config.settings at tmp_path
    locations, since run_daily_backup() (unlike create_backup()) reads
    DATABASE_URL/BACKUP_DIR/retention from that global rather than taking
    them as arguments — matching cli.py's "the one place those two worlds
    meet" convention, which app.services.maintenance_schedule shares."""
    from app.core.config import settings as app_settings

    db_path = tmp_path / "adas.db"
    backup_dir = tmp_path / "backups"
    _make_db(db_path)

    monkeypatch.setattr(app_settings, "DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setattr(app_settings, "BACKUP_DIR", backup_dir)

    return SimpleNamespace(db_path=db_path, backup_dir=backup_dir)


@pytest.fixture(autouse=True)
def _release_stray_lock():
    yield
    from app.maintenance.backup import _maintenance_lock

    if _maintenance_lock.locked():
        _maintenance_lock.release()


# ---------------------------------------------------------------------------
# TestRunDailyBackup
# ---------------------------------------------------------------------------


class TestRunDailyBackup:
    def test_creates_a_scheduled_backup_and_audits_success(self, sched_paths, session):
        engine = session.get_bind()

        run_daily_backup(engine, trigger="scheduled")

        manifests = list(sched_paths.backup_dir.glob("adas_backup_*.json"))
        assert len(manifests) == 1

        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "BACKUP_TRIGGER")
        ).all()
        assert len(rows) == 1
        assert rows[0].result == "success"
        assert rows[0].actor_type == "system"
        detail = json.loads(rows[0].detail)
        assert detail["trigger"] == "scheduled"
        assert "backup_id" in detail

    def test_busy_lock_is_a_logged_noop_not_an_error(self, sched_paths, session):
        engine = session.get_bind()

        with maintenance_lock():
            run_daily_backup(engine, trigger="scheduled")  # must not raise

        # A busy backup is never even attempted, so it writes no row at all
        # — not a success row, not a failure row.
        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "BACKUP_TRIGGER")
        ).all()
        assert rows == []

    def test_failure_path_audits_failure_and_does_not_raise(
        self, sched_paths, session, monkeypatch
    ):
        def _boom(*_args, **_kwargs):
            raise RuntimeError("simulated backup failure")

        monkeypatch.setattr("app.services.maintenance_schedule.create_backup", _boom)
        engine = session.get_bind()

        run_daily_backup(engine, trigger="scheduled")  # must not raise

        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "BACKUP_TRIGGER")
        ).all()
        assert len(rows) == 1
        assert rows[0].result == "failure"
        assert json.loads(rows[0].detail)["trigger"] == "scheduled"


# ---------------------------------------------------------------------------
# TestScheduledBackupIsDue
# ---------------------------------------------------------------------------


class TestScheduledBackupIsDue:
    def test_due_when_no_scheduled_backup_exists_at_all(self, sched_paths):
        assert scheduled_backup_is_due(sched_paths.backup_dir, now=datetime.now(UTC))

    def test_due_at_25_hours_not_due_at_2_hours(self, sched_paths):
        manifest = create_backup(
            db_path=sched_paths.db_path,
            backup_dir=sched_paths.backup_dir,
            origin=ORIGIN_SCHEDULED,
        )
        created_at = datetime.fromisoformat(manifest.created_at)

        assert not scheduled_backup_is_due(
            sched_paths.backup_dir, now=created_at + timedelta(hours=2)
        )
        assert scheduled_backup_is_due(
            sched_paths.backup_dir, now=created_at + timedelta(hours=25)
        )

    def test_manual_backup_does_not_satisfy_the_daily_interval(self, sched_paths):
        """Only origin == 'scheduled' counts — a recent manual backup
        doesn't discharge the daily obligation, since 'did the automated
        schedule run?' is a different question."""
        manifest = create_backup(
            db_path=sched_paths.db_path,
            backup_dir=sched_paths.backup_dir,
            origin=ORIGIN_MANUAL,
        )
        created_at = datetime.fromisoformat(manifest.created_at)

        assert scheduled_backup_is_due(
            sched_paths.backup_dir, now=created_at + timedelta(minutes=5)
        )

    def test_missing_backup_file_does_not_satisfy_the_interval(self, sched_paths):
        manifest = create_backup(
            db_path=sched_paths.db_path,
            backup_dir=sched_paths.backup_dir,
            origin=ORIGIN_SCHEDULED,
        )
        db_path_for(sched_paths.backup_dir, manifest.backup_id).unlink()

        assert scheduled_backup_is_due(sched_paths.backup_dir, now=datetime.now(UTC))

    def test_checksum_mismatched_backup_file_does_not_satisfy_the_interval(
        self, sched_paths
    ):
        manifest = create_backup(
            db_path=sched_paths.db_path,
            backup_dir=sched_paths.backup_dir,
            origin=ORIGIN_SCHEDULED,
        )
        target = db_path_for(sched_paths.backup_dir, manifest.backup_id)
        with open(target, "r+b") as f:
            f.write(b"\xff\xff\xff\xff")

        assert scheduled_backup_is_due(sched_paths.backup_dir, now=datetime.now(UTC))

    def test_newest_scheduled_manifest_ignores_manual_origin(self, sched_paths):
        create_backup(
            db_path=sched_paths.db_path,
            backup_dir=sched_paths.backup_dir,
            origin=ORIGIN_MANUAL,
        )
        assert newest_scheduled_manifest(sched_paths.backup_dir) is None

        scheduled = create_backup(
            db_path=sched_paths.db_path,
            backup_dir=sched_paths.backup_dir,
            origin=ORIGIN_SCHEDULED,
        )
        found = newest_scheduled_manifest(sched_paths.backup_dir)
        assert found is not None
        assert found.backup_id == scheduled.backup_id


# ---------------------------------------------------------------------------
# TestRunDailyBackupIfDue
# ---------------------------------------------------------------------------


class TestRunDailyBackupIfDue:
    def test_skips_when_not_due(self, sched_paths, session):
        create_backup(
            db_path=sched_paths.db_path,
            backup_dir=sched_paths.backup_dir,
            origin=ORIGIN_SCHEDULED,
        )
        manifests_before = list(sched_paths.backup_dir.glob("adas_backup_*.json"))

        run_daily_backup_if_due(session.get_bind())

        manifests_after = list(sched_paths.backup_dir.glob("adas_backup_*.json"))
        assert len(manifests_after) == len(manifests_before)
        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "BACKUP_TRIGGER")
        ).all()
        assert rows == []

    def test_runs_and_labels_the_trigger_catch_up_when_due(self, sched_paths, session):
        run_daily_backup_if_due(session.get_bind())

        manifests = list(sched_paths.backup_dir.glob("adas_backup_*.json"))
        assert len(manifests) == 1

        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "BACKUP_TRIGGER")
        ).all()
        assert len(rows) == 1
        assert json.loads(rows[0].detail)["trigger"] == "catch_up"


# ---------------------------------------------------------------------------
# TestBackupCliDedup — Step 9. Both restart orchestrators
# (adas-maintenance.ps1's Restart action, daily_restart.sh) call
# `backup --origin scheduled` as their own backup phase, on top of the
# in-app cron job that already covers the daily obligation independently.
# Symmetric across both platforms for free, since they share this one
# command -- neither script needed its own dedup logic.
# ---------------------------------------------------------------------------


class TestBackupCliDedup:
    def test_scheduled_origin_skips_when_a_recent_scheduled_backup_exists(
        self, sched_paths
    ):
        from app.maintenance import cli as cli_mod

        first = cli_mod.main(["backup", "--origin", "scheduled"])
        assert first == 0
        manifests_after_first = list(sched_paths.backup_dir.glob("adas_backup_*.json"))
        assert len(manifests_after_first) == 1

        second = cli_mod.main(["backup", "--origin", "scheduled"])
        assert second == 0
        manifests_after_second = list(sched_paths.backup_dir.glob("adas_backup_*.json"))
        assert len(manifests_after_second) == 1  # no new backup written

    def test_manual_origin_is_never_skipped(self, sched_paths):
        from app.maintenance import cli as cli_mod

        first = cli_mod.main(["backup", "--origin", "manual"])
        second = cli_mod.main(["backup", "--origin", "manual"])
        assert first == 0
        assert second == 0
        manifests = list(sched_paths.backup_dir.glob("adas_backup_*.json"))
        assert len(manifests) == 2  # both ran, dedup never applies to manual


# ---------------------------------------------------------------------------
# TestDailyBackupCronTimezone — the silent-8-hour-shift guard. Boots a real
# app with SCHEDULER_ENABLED=True and inspects the actual job app.main.py
# registers, rather than re-deriving the same add_job() call in the test.
# ---------------------------------------------------------------------------


class TestDailyBackupCronTimezone:
    def test_daily_backup_job_trigger_timezone_is_report_local_not_utc(
        self, tmp_path, monkeypatch
    ):
        # The lifespan-startup due-check (Step 1) calls
        # app.services.maintenance_schedule.run_daily_backup_if_due(), which
        # reads DATABASE_URL/BACKUP_DIR from the *global*
        # app.core.config.settings singleton, not app.state.settings — the
        # same convention routes/maintenance.py already uses. Patching only
        # the Settings() passed to create_app() below would not stop it
        # from reading/backing up the real repo-root adas.db into the real
        # var/backups/.
        from app.core.config import settings as global_settings

        monkeypatch.setattr(
            global_settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'scheduler.db'}"
        )
        monkeypatch.setattr(global_settings, "BACKUP_DIR", tmp_path / "backups")

        app_settings = Settings(
            _env_file=None,
            SECRET_KEY="test-secret-key-not-for-production-use",
            INTERNAL_API_KEY="test-internal-api-key-not-for-production",
            DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
            DATABASE_URL=f"sqlite:///{tmp_path / 'scheduler.db'}",
            SCHEDULER_ENABLED=True,
            SNAPSHOT_ROOT=tmp_path / "snapshots",
            MAINTENANCE_HOUR_LOCAL=3,
            REPORT_LOCAL_TIMEZONE="Asia/Manila",
        )
        app = create_app(app_settings)

        with TestClient(app):
            job = app.state.scheduler.get_job("daily_backup")
            assert job is not None
            # create_scheduler() is AsyncIOScheduler(timezone=UTC) — a bare
            # hour=3 with no explicit timezone= would silently fire at
            # 03:00 UTC (11:00 Manila), the middle of a demo day. This is
            # the test whose only job is to catch that regression.
            assert job.trigger.timezone == ZoneInfo("Asia/Manila")
            assert job.trigger.timezone != ZoneInfo("UTC")

            catch_up_job = app.state.scheduler.get_job("daily_backup_catch_up")
            assert catch_up_job is not None


# ---------------------------------------------------------------------------
# TestDailyBackupCronDstBehavior — replaces edge case 5.10's old
# pytest.skip for the backup half. America/New_York is used deliberately,
# not Asia/Manila (REPORT_LOCAL_TIMEZONE) — the Philippines observes no
# DST, so a Manila-based trigger would prove nothing about DST correctness.
# ---------------------------------------------------------------------------


class TestDailyBackupCronDstBehavior:
    def test_cron_trigger_keeps_firing_at_local_0300_across_dst_spring_forward(
        self,
    ):
        from apscheduler.triggers.cron import CronTrigger

        tz = ZoneInfo("America/New_York")
        # 2026 US spring-forward: 2026-03-08, clocks jump 02:00 -> 03:00.
        trigger = CronTrigger(hour=3, minute=0, timezone=tz)

        now = datetime(2026, 3, 6, 0, 0, tzinfo=tz)
        previous = None
        fire_times = []
        for _ in range(6):
            fire_time = trigger.get_next_fire_time(previous, now)
            assert fire_time is not None
            fire_times.append(fire_time)
            previous = fire_time
            now = fire_time

        for fire_time in fire_times:
            local = fire_time.astimezone(tz)
            assert local.hour == 3
            assert local.minute == 0

        # Confirms the loop actually spans the transition date, not five
        # days that all happen to sit on one side of it.
        fire_dates = {ft.astimezone(tz).date() for ft in fire_times}
        assert date(2026, 3, 8) in fire_dates
