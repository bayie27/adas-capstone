"""
Tests for the create_app() factory and test-harness isolation (P1 Step 6).
"""

import sqlite3
from pathlib import Path

import pytest
from app.core.config import Settings, settings
from app.core.db import get_engine, get_session
from app.main import create_app
from app.models import Camera
from fastapi.testclient import TestClient
from sqlmodel import Session


def _real_db_path() -> Path:
    prefix = "sqlite:///"
    assert settings.DATABASE_URL.startswith(prefix)
    return Path(settings.DATABASE_URL[len(prefix) :])


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


class TestSnapshotRootStartupFailure:
    def test_unwritable_snapshot_root_fails_startup_cleanly(self, tmp_path):
        """Edge case 6.9 — an unwritable SNAPSHOT_ROOT must fail startup
        loudly (the lifespan raises, so the server never comes up) rather
        than starting cleanly and only surfacing as a per-request 500 the
        first time something tries to write a snapshot."""
        blocker_file = tmp_path / "blocker"
        blocker_file.write_text("not a directory")

        app_settings = Settings(
            _env_file=None,
            SECRET_KEY="test-secret-key-not-for-production-use",
            INTERNAL_API_KEY="test-internal-api-key-not-for-production",
            DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
            DATABASE_URL=f"sqlite:///{tmp_path / 'snap.db'}",
            SCHEDULER_ENABLED=False,
            SNAPSHOT_ROOT=blocker_file / "snapshots",
        )
        app = create_app(app_settings)

        with pytest.raises(OSError), TestClient(app):
            pass


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
                resp = client.patch(
                    f"/api/internal/cameras/{camera_id}/status",
                    # verify_internal_api_key checks the process-global
                    # `settings`, not this app's own per-instance settings —
                    # see app/api/dependencies.py.
                    headers={"x-api-key": settings.INTERNAL_API_KEY.get_secret_value()},
                    json={"connection_status": "Connected"},
                )
            finally:
                blocking_conn.execute("ROLLBACK")
                blocking_conn.close()

        assert resp.status_code == 503
        assert resp.json()["code"] == "TEMPORARILY_UNAVAILABLE"
