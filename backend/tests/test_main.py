"""
Focused tests for app startup behavior.
"""

import asyncio

from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

import app.main as main_module
from app.models import AIStatus, Camera, ConnectionStatus

from .conftest import make_camera


def test_lifespan_resets_only_enabled_active_cameras(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
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

    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.setattr(main_module, "init_db", lambda: None)

    async def run_lifespan_once() -> None:
        async with main_module.lifespan(main_module.app):
            pass

    asyncio.run(run_lifespan_once())

    with Session(engine) as session:
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
