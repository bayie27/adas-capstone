"""
Shared fixtures for the ADAS backend test suite.
Uses an in-memory SQLite database so tests are fully isolated
and never touch the real adas.db.
"""

import uuid
from datetime import UTC, datetime

import pytest
from app.core.config import Settings, settings
from app.core.db import get_engine, get_session
from app.core.security import get_password_hash
from app.main import create_app
from app.models import (
    AIStatus,
    AlarmSettings,
    Camera,
    ConnectionStatus,
    DetectionLog,
    DetectionStatus,
    User,
    UserRole,
)
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# ---------------------------------------------------------------------------
# Database fixture — fresh in-memory DB per test
# ---------------------------------------------------------------------------


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


def _build_test_settings(tmp_path) -> Settings:
    """A disposable Settings instance, decoupled from the real .env, whose
    engine (built inside create_app()) never touches the repo-root adas.db —
    that engine is unused anyway once get_session/get_engine are overridden
    below, but lifespan still runs init_db() against it on TestClient
    startup, and that must land somewhere harmless."""
    return Settings(
        _env_file=None,
        SECRET_KEY="test-secret-key-not-for-production-use",
        INTERNAL_API_KEY="test-internal-api-key-not-for-production",
        DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
        DATABASE_URL=f"sqlite:///{tmp_path / 'lifespan-only.db'}",
        SCHEDULER_ENABLED=False,
        # F7 — tests drive export jobs directly via process_export_job(),
        # not through the worker pool; a live pool would race those calls.
        EXPORT_JOB_WORKERS=0,
    )


@pytest.fixture(name="client")
def client_fixture(session: Session, tmp_path):
    app = create_app(_build_test_settings(tmp_path))

    def get_session_override():
        yield session

    def get_engine_override():
        return session.get_bind()

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_engine] = get_engine_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers — reusable across test modules
# ---------------------------------------------------------------------------


def make_admin(session: Session, username="admin", password="Admin123") -> User:
    user = User(
        username=username,
        first_name="System",
        last_name="Admin",
        role=UserRole.ADMIN,
        password_hash=get_password_hash(password),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.add(AlarmSettings(user_id=user.user_id))
    session.commit()
    return user


def make_operator(
    session: Session, username="operator", password="Operator123"
) -> User:
    user = User(
        username=username,
        first_name="Test",
        last_name="Operator",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash(password),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.add(AlarmSettings(user_id=user.user_id))
    session.commit()
    return user


def make_camera(
    session: Session,
    name="Test Camera",
    channel_id=1,
    *,
    connection_status: str = ConnectionStatus.DISCONNECTED.value,
    ai_status: str = AIStatus.INACTIVE.value,
    is_enabled: bool = True,
    is_active: bool = True,
    desired_ai_state: str | None = None,
    desired_state_reason: str | None = None,
    cooldown_until=None,
    last_heartbeat_at=None,
) -> Camera:
    camera = Camera(
        camera_name=name,
        channel_id=channel_id,
        connection_status=connection_status,
        ai_status=ai_status,
        is_enabled=is_enabled,
        is_active=is_active,
        last_heartbeat_at=last_heartbeat_at,
    )
    if desired_ai_state is not None:
        camera.desired_ai_state = desired_ai_state
    if desired_state_reason is not None:
        camera.desired_state_reason = desired_state_reason
    if cooldown_until is not None:
        camera.cooldown_until = cooldown_until
    session.add(camera)
    session.commit()
    session.refresh(camera)
    return camera


def make_detection(
    session: Session,
    camera: Camera,
    status: DetectionStatus = DetectionStatus.UNVERIFIED,
    confidence: float = 0.95,
) -> DetectionLog:
    assert camera.camera_id is not None
    log = DetectionLog(
        camera_id=camera.camera_id,
        detected_at=datetime.now(UTC),
        snapshot_key="cam1_20260426_120000.jpg",
        confidence_score=confidence,
        detection_status=status.value,
        source_event_id=str(uuid.uuid4()),
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


# ---------------------------------------------------------------------------
# Auth helper — logs in and returns the session cookie for a given user
# ---------------------------------------------------------------------------


def login(client: TestClient, username: str, password: str) -> dict:
    """Logs in and returns the response body's `user` dict."""
    resp = client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["user"]


def auth_headers(client: TestClient, username: str, password: str) -> dict:
    """Logs in and returns a `Cookie` header carrying the session — kept as
    an explicit header (rather than relying on the client's cookie jar) so
    call sites across the suite don't need to change shape for the P2
    cookie-based auth flow."""
    resp = client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    cookie_value = resp.cookies.get(settings.SESSION_COOKIE_NAME)
    return {"Cookie": f"{settings.SESSION_COOKIE_NAME}={cookie_value}"}


def internal_headers() -> dict:
    return {"x-api-key": settings.INTERNAL_API_KEY.get_secret_value()}
