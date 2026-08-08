"""
Tests for the create_app() factory and test-harness isolation (P1 Step 6).
"""

from pathlib import Path

from app.core.config import Settings, settings
from app.core.db import get_engine, get_session
from app.main import create_app
from fastapi.testclient import TestClient


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
