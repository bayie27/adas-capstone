"""
Tests for the create_app() factory and test-harness isolation (P1 Step 6).
"""

import inspect
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings, settings
from app.core.db import get_engine, get_session
from app.main import create_app
from app.models import Camera
from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import make_operator


def _real_db_path() -> Path:
    prefix = "sqlite:///"
    assert settings.DATABASE_URL.startswith(prefix)
    return Path(settings.DATABASE_URL[len(prefix) :])


def _dev_tools_settings(tmp_path, **overrides) -> Settings:
    return Settings(
        _env_file=None,
        SECRET_KEY="dev-tools-gate-secret-key-not-for-production",
        INTERNAL_API_KEY="dev-tools-gate-internal-api-key",
        DEFAULT_ADMIN_PASSWORD="dev-tools-gate-admin-password-123",
        DATABASE_URL=f"sqlite:///{tmp_path / 'gate.db'}",
        SCHEDULER_ENABLED=False,
        EXPORT_JOB_WORKERS=0,
        **overrides,
    )


class TestDevToolsGate:
    """dev_plan/02_PKG_dev_api.md Step 1 (DT-3/DT-5). The flag is resolved
    from ENVIRONMENT only when it is left unset, so a production deployment
    is off by default while the LAN demo box can still turn it on."""

    def test_defaults_on_in_development_and_off_in_production(self, tmp_path):
        assert _dev_tools_settings(tmp_path).DEV_TOOLS_ENABLED is True
        assert (
            _dev_tools_settings(tmp_path, ENVIRONMENT="production").DEV_TOOLS_ENABLED
            is False
        )

    def test_an_explicit_value_wins_over_the_environment(self, tmp_path):
        enabled = _dev_tools_settings(
            tmp_path, ENVIRONMENT="production", DEV_TOOLS_ENABLED=True
        )
        disabled = _dev_tools_settings(
            tmp_path, ENVIRONMENT="development", DEV_TOOLS_ENABLED=False
        )
        assert enabled.DEV_TOOLS_ENABLED is True
        assert disabled.DEV_TOOLS_ENABLED is False

    def test_router_is_absent_when_disabled(self, tmp_path):
        """Absent, not merely refusing — Package C's probe treats the 404 as
        'no dev tools here', so a 401/403 would read as a different thing."""
        app = create_app(_dev_tools_settings(tmp_path, DEV_TOOLS_ENABLED=False))
        with TestClient(app) as client:
            assert client.get("/api/dev/status").status_code == 404

    def test_status_is_reachable_unauthenticated_when_enabled(self, tmp_path):
        app = create_app(_dev_tools_settings(tmp_path, DEV_TOOLS_ENABLED=True))
        with TestClient(app) as client:
            resp = client.get("/api/dev/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is True
        # Sourced from the registry, so a profile added later shows up here
        # without this route being touched.
        assert {"demo", "empty"} <= {p["name"] for p in body["profiles"]}
        # Nothing an anonymous caller could act on.
        assert set(body) == {"enabled", "profiles"}


class TestAppFactoryIsolation:
    def test_client_fixture_never_touches_the_real_repo_root_db(
        self, client: TestClient
    ):
        real_db_path = _real_db_path()
        existed_before = real_db_path.exists()
        mtime_before = real_db_path.stat().st_mtime if existed_before else None

        # Exercise the app enough to prove lifespan and a real request ran.
        resp = client.get("/")
        assert resp.status_code == 200

        existed_after = real_db_path.exists()
        mtime_after = real_db_path.stat().st_mtime if existed_after else None

        assert existed_after == existed_before
        assert mtime_after == mtime_before

    def test_create_app_builds_a_distinct_engine_per_settings_instance(self, tmp_path):
        settings_a = Settings(
            _env_file=None,
            SECRET_KEY="a" * 32,
            INTERNAL_API_KEY="key-a",
            DEFAULT_ADMIN_PASSWORD="password-a-123",
            DATABASE_URL=f"sqlite:///{tmp_path / 'a.db'}",
        )
        settings_b = Settings(
            _env_file=None,
            SECRET_KEY="b" * 32,
            INTERNAL_API_KEY="key-b",
            DEFAULT_ADMIN_PASSWORD="password-b-123",
            DATABASE_URL=f"sqlite:///{tmp_path / 'b.db'}",
        )

        app_a = create_app(settings_a)
        app_b = create_app(settings_b)

        assert app_a.state.engine is not app_b.state.engine
        assert app_a.state.settings is settings_a
        assert app_b.state.settings is settings_b

    def test_get_engine_and_get_session_are_overridden_in_tests(
        self, client: TestClient
    ):
        app = client.app
        assert get_engine in app.dependency_overrides
        assert get_session in app.dependency_overrides


class TestSchedulerJobWiring:
    def test_ws_session_revalidation_job_is_a_real_coroutine_function(self, tmp_path):
        """Regression test: `lambda: ws_session_revalidation(...)` wraps a
        coroutine call in a plain sync function, so APScheduler's
        AsyncIOExecutor (which dispatches on
        `inspect.iscoroutinefunction(job.func)`) would run it synchronously
        and drop the returned coroutine unawaited — the job silently never
        does anything. The scheduled job's `func` must itself satisfy
        `iscoroutinefunction` so APScheduler actually awaits it."""
        app_settings = Settings(
            _env_file=None,
            SECRET_KEY="test-secret-key-not-for-production-use",
            INTERNAL_API_KEY="test-internal-api-key-not-for-production",
            DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
            DATABASE_URL=f"sqlite:///{tmp_path / 'scheduler.db'}",
            SCHEDULER_ENABLED=True,
        )
        app = create_app(app_settings)

        with TestClient(app):
            job = app.state.scheduler.get_job("ws_session_revalidation")
            assert job is not None
            assert inspect.iscoroutinefunction(job.func)


class TestConcurrentWriteLockHandling:
    def test_real_lock_contention_returns_503_end_to_end(self, tmp_path):
        """Edge case 6.1 — a genuine SQLite write-lock held past
        SQLITE_BUSY_TIMEOUT_MS must surface as 503 TEMPORARILY_UNAVAILABLE.
        Unlike test_logging.py's TestOperationalErrorHandler (which feeds the
        handler a manufactured OperationalError), this exercises the real
        pragma + busy_timeout + handler wiring together."""
        db_path = tmp_path / "lock.db"
        app_settings = Settings(
            _env_file=None,
            SECRET_KEY="test-secret-key-not-for-production-use",
            INTERNAL_API_KEY="test-internal-api-key-not-for-production",
            DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
            DATABASE_URL=f"sqlite:///{db_path}",
            SCHEDULER_ENABLED=False,
            SQLITE_BUSY_TIMEOUT_MS=50,
        )
        app = create_app(app_settings)

        with TestClient(app) as client:
            with Session(app.state.engine) as session:
                camera = Camera(camera_name="Lock Cam", channel_id=1)
                session.add(camera)
                session.commit()
                camera_id = camera.camera_id

            # A second, raw connection to the same file holds the write lock
            # for the duration of the request below — the app's own engine
            # must then genuinely block, hit busy_timeout, and raise.
            blocking_conn = sqlite3.connect(str(db_path), timeout=0)
            blocking_conn.execute("BEGIN EXCLUSIVE")
            try:
                resp = client.post(
                    "/api/internal/heartbeat",
                    # verify_internal_api_key checks the process-global
                    # `settings`, not this app's own per-instance settings —
                    # see app/api/dependencies.py.
                    headers={"x-api-key": settings.INTERNAL_API_KEY.get_secret_value()},
                    json={
                        "engine_id": "adas-ai-1",
                        "sent_at": datetime.now(UTC).isoformat(),
                        "cameras": [
                            {
                                "camera_id": camera_id,
                                "connection_status": "Connected",
                                "ai_status": "Active",
                            }
                        ],
                    },
                )
            finally:
                blocking_conn.execute("ROLLBACK")
                blocking_conn.close()

        assert resp.status_code == 503
        assert resp.json()["code"] == "TEMPORARILY_UNAVAILABLE"


class TestExportWorkerGating:
    def test_export_worker_pool_runs_with_scheduler_disabled(self, tmp_path):
        """F7 regression — export workers must be gated on EXPORT_JOB_WORKERS,
        not on SCHEDULER_ENABLED. Before the fix, a scheduler-off boot never
        called ExportJobQueue.start(), so a queued job sat `queued` forever
        with no error. This drives a job through the real worker pool (no
        direct process_export_job() call) with the scheduler off."""
        app_settings = Settings(
            _env_file=None,
            SECRET_KEY="test-secret-key-not-for-production-use",
            INTERNAL_API_KEY="test-internal-api-key-not-for-production",
            DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
            DATABASE_URL=f"sqlite:///{tmp_path / 'export_workers.db'}",
            SCHEDULER_ENABLED=False,
            EXPORT_JOB_WORKERS=1,
        )
        app = create_app(app_settings)

        with TestClient(app) as client:
            with Session(app.state.engine) as session:
                make_operator(session, username="exportop", password="Operator123")

            login_resp = client.post(
                "/api/auth/login",
                data={"username": "exportop", "password": "Operator123"},
            )
            assert login_resp.status_code == 200, login_resp.text
            cookie_val = login_resp.cookies.get(app_settings.SESSION_COOKIE_NAME)
            headers = {"Cookie": f"{app_settings.SESSION_COOKIE_NAME}={cookie_val}"}

            create_resp = client.post(
                "/api/exports/jobs",
                json={"report_type": "incidents", "format": "csv"},
                headers=headers,
            )
            assert create_resp.status_code == 202
            job_id = create_resp.json()["job_id"]

            deadline = time.monotonic() + 5
            status = None
            while time.monotonic() < deadline:
                status_resp = client.get(f"/api/exports/jobs/{job_id}", headers=headers)
                assert status_resp.status_code == 200
                status = status_resp.json()["status"]
                if status == "completed":
                    break
                time.sleep(0.05)

        assert status == "completed"
