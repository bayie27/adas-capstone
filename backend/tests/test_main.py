"""
Focused tests for app startup behavior.
"""

from app.core.config import Settings
from app.main import create_app
from app.models import AIStatus, Camera, ConnectionStatus
from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import make_camera


def test_lifespan_resets_only_enabled_active_cameras(tmp_path):
    """A real restart (TestClient entered a second time) must reset
    connection/AI status for enabled+active cameras only, leaving
    disabled and inactive cameras untouched.

    Uses create_app() rather than pointing a hand-built in-memory engine at
    the module-level `app` singleton: check_schema_revision's auto-bootstrap
    (backend/alembic/env.py) always reopens `target_settings.DATABASE_URL`
    itself, ignoring whatever engine object is passed in — so an engine and
    a settings.DATABASE_URL that don't actually match (as the old version of
    this test had, via monkeypatch.setattr(..., "engine", ...) while leaving
    app.state.settings on the real process-global Settings) silently
    migrates the *wrong* database. This showed up as a "table already
    exists" collision against the real repo-root adas.db whenever some
    earlier test in the same session had already caused it to be migrated —
    order-dependent and unrelated to the cameras under test here."""
    app_settings = Settings(
        _env_file=None,
        SECRET_KEY="test-secret-key-not-for-production-use",
        INTERNAL_API_KEY="test-internal-api-key-not-for-production",
        DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
        DATABASE_URL=f"sqlite:///{tmp_path / 'lifespan.db'}",
        SCHEDULER_ENABLED=False,
        EXPORT_JOB_WORKERS=0,
    )
    app = create_app(app_settings)

    # First boot: creates the schema so cameras can be seeded below.
    with TestClient(app):
        pass

    with Session(app.state.engine) as session:
        enabled_active = make_camera(
            session,
            name="Enabled Active Reset Cam",
            channel_id=201,
            connection_status=ConnectionStatus.CONNECTED.value,
            ai_status=AIStatus.PAUSED.value,
        )
        disabled = make_camera(
            session,
            name="Disabled Reset Cam",
            channel_id=202,
            connection_status=ConnectionStatus.CONNECTED.value,
            ai_status=AIStatus.ACTIVE.value,
            is_enabled=False,
        )
        inactive = make_camera(
            session,
            name="Inactive Reset Cam",
            channel_id=203,
            connection_status=ConnectionStatus.UNRESPONSIVE.value,
            ai_status=AIStatus.UNRESPONSIVE.value,
            is_active=False,
        )
        enabled_active_id = enabled_active.camera_id
        disabled_id = disabled.camera_id
        inactive_id = inactive.camera_id

    # Second boot: the restart under test.
    with TestClient(app):
        pass

    with Session(app.state.engine) as session:
        enabled_active = session.get(Camera, enabled_active_id)
        disabled = session.get(Camera, disabled_id)
        inactive = session.get(Camera, inactive_id)

        assert enabled_active is not None
        assert enabled_active.connection_status == ConnectionStatus.DISCONNECTED.value
        assert enabled_active.ai_status == AIStatus.INACTIVE.value

        assert disabled is not None
        assert disabled.connection_status == ConnectionStatus.CONNECTED.value
        assert disabled.ai_status == AIStatus.ACTIVE.value

        assert inactive is not None
        assert inactive.connection_status == ConnectionStatus.UNRESPONSIVE.value
        assert inactive.ai_status == AIStatus.UNRESPONSIVE.value
