"""
Shared fixtures for the ADAS backend test suite.
Uses an in-memory SQLite database so tests are fully isolated
and never touch the real adas.db.
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.core.db import get_session
from app.core.security import get_password_hash
from app.models import User, UserRole, Camera, DetectionLog, DetectionStatus


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


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
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
    return user


def make_operator(session: Session, username="operator", password="Operator123") -> User:
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
    return user


def make_camera(session: Session, name="Test Camera", channel_id=1) -> Camera:
    camera = Camera(camera_name=name, channel_id=channel_id)
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
        detected_at=datetime.now(timezone.utc),
        snapshot_path="cam1_20260426_120000.jpg",
        confidence_score=confidence,
        detection_status=status.value,
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


# ---------------------------------------------------------------------------
# Auth helper — returns a Bearer token for a given user
# ---------------------------------------------------------------------------

def get_token(client: TestClient, username: str, password: str) -> str:
    resp = client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


def auth_headers(client: TestClient, username: str, password: str) -> dict:
    return {"Authorization": f"Bearer {get_token(client, username, password)}"}