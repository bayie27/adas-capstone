"""
Tests for /api/internal.
Covers AI-engine alert ingestion, camera polling, status updates, and internal auth.
"""

from datetime import UTC, datetime

import app.api.routes.internal as internal_routes
import pytest
from app.models import AIStatus, ConnectionStatus, DetectionLog, DetectionStatus
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import internal_headers, make_camera, make_detection


def test_receive_ai_alert_creates_log_pauses_camera_and_broadcasts(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    payloads: list[dict] = []

    async def fake_broadcast(payload: dict) -> None:
        payloads.append(payload)

    monkeypatch.setattr(internal_routes.manager, "broadcast_alert", fake_broadcast)

    camera = make_camera(
        session,
        name="Ingress Cam",
        channel_id=11,
        connection_status=ConnectionStatus.CONNECTED.value,
        ai_status=AIStatus.ACTIVE.value,
    )

    resp = client.post(
        "/api/internal/alert",
        headers=internal_headers(),
        json={
            "camera_id": camera.camera_id,
            "detected_at": datetime(2026, 4, 26, 12, 0, tzinfo=UTC).isoformat(),
            "snapshot_path": "snapshots/ingress.jpg",
            "confidence_score": 0.97,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["camera_id"] == camera.camera_id
    assert body["detection_status"] == DetectionStatus.UNVERIFIED.value

    session.refresh(camera)
    assert camera.ai_status == AIStatus.PAUSED.value

    logs = session.exec(
        select(DetectionLog).where(DetectionLog.camera_id == camera.camera_id)
    ).all()
    assert len(logs) == 1
    assert logs[0].snapshot_key == "snapshots/ingress.jpg"

    assert [payload["type"] for payload in payloads] == [
        "NEW_DETECTION",
        "CAMERA_STATUS_UPDATE",
    ]
    assert payloads[0]["camera_id"] == camera.camera_id
    assert payloads[1] == {
        "type": "CAMERA_STATUS_UPDATE",
        "camera_id": camera.camera_id,
        "connection_status": ConnectionStatus.CONNECTED.value,
        "ai_status": AIStatus.PAUSED.value,
    }


@pytest.mark.parametrize(
    ("is_enabled", "is_active"),
    [
        (False, True),
        (True, False),
    ],
)
def test_receive_ai_alert_rejects_disabled_or_inactive_camera(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    is_enabled: bool,
    is_active: bool,
):
    payloads: list[dict] = []

    async def fake_broadcast(payload: dict) -> None:
        payloads.append(payload)

    monkeypatch.setattr(internal_routes.manager, "broadcast_alert", fake_broadcast)

    camera = make_camera(
        session,
        name=f"Rejected Cam {is_enabled}-{is_active}",
        channel_id=20 if is_enabled else 21,
        is_enabled=is_enabled,
        is_active=is_active,
    )

    resp = client.post(
        "/api/internal/alert",
        headers=internal_headers(),
        json={
            "camera_id": camera.camera_id,
            "detected_at": datetime.now(UTC).isoformat(),
            "snapshot_path": "snapshots/rejected.jpg",
            "confidence_score": 0.91,
        },
    )

    assert resp.status_code == 404
    assert "inactive, or disabled" in resp.json()["detail"]

    session.refresh(camera)
    assert camera.ai_status == AIStatus.INACTIVE.value
    assert (
        session.exec(
            select(DetectionLog).where(DetectionLog.camera_id == camera.camera_id)
        ).all()
        == []
    )
    assert payloads == []


def test_internal_routes_require_valid_api_key(client: TestClient):
    resp = client.get("/api/internal/cameras", headers={"x-api-key": "wrong-key"})

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid Internal API Key"


def test_get_enabled_cameras_returns_only_enabled_and_active(
    client: TestClient,
    session: Session,
):
    included_one = make_camera(
        session,
        name="Poll Cam 1",
        channel_id=31,
        connection_status=ConnectionStatus.CONNECTED.value,
        ai_status=AIStatus.ACTIVE.value,
    )
    included_two = make_camera(
        session,
        name="Poll Cam 2",
        channel_id=32,
        connection_status=ConnectionStatus.RECONNECTING.value,
        ai_status=AIStatus.PAUSED.value,
    )
    make_camera(session, name="Disabled Poll Cam", channel_id=33, is_enabled=False)
    make_camera(session, name="Inactive Poll Cam", channel_id=34, is_active=False)

    resp = client.get("/api/internal/cameras", headers=internal_headers())

    assert resp.status_code == 200
    body = resp.json()
    returned = {camera["camera_id"]: camera for camera in body}

    assert set(returned) == {included_one.camera_id, included_two.camera_id}
    assert (
        returned[included_one.camera_id]["connection_status"]
        == ConnectionStatus.CONNECTED.value
    )
    assert returned[included_one.camera_id]["ai_status"] == AIStatus.ACTIVE.value
    assert (
        returned[included_two.camera_id]["connection_status"]
        == ConnectionStatus.RECONNECTING.value
    )
    assert returned[included_two.camera_id]["ai_status"] == AIStatus.PAUSED.value


def test_update_camera_status_updates_fields_and_broadcasts(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    payloads: list[dict] = []

    async def fake_broadcast(payload: dict) -> None:
        payloads.append(payload)

    monkeypatch.setattr(internal_routes.manager, "broadcast_alert", fake_broadcast)

    camera = make_camera(
        session,
        name="Patch Cam",
        channel_id=41,
        connection_status=ConnectionStatus.DISCONNECTED.value,
        ai_status=AIStatus.INACTIVE.value,
    )

    resp = client.patch(
        f"/api/internal/cameras/{camera.camera_id}/status",
        headers=internal_headers(),
        json={
            "connection_status": ConnectionStatus.CONNECTED.value,
            "ai_status": AIStatus.ACTIVE.value,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["connection_status"] == ConnectionStatus.CONNECTED.value
    assert body["ai_status"] == AIStatus.ACTIVE.value

    session.refresh(camera)
    assert camera.connection_status == ConnectionStatus.CONNECTED.value
    assert camera.ai_status == AIStatus.ACTIVE.value
    assert payloads == [
        {
            "type": "CAMERA_STATUS_UPDATE",
            "camera_id": camera.camera_id,
            "connection_status": ConnectionStatus.CONNECTED.value,
            "ai_status": AIStatus.ACTIVE.value,
        }
    ]


def test_update_camera_status_supports_partial_updates(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    payloads: list[dict] = []

    async def fake_broadcast(payload: dict) -> None:
        payloads.append(payload)

    monkeypatch.setattr(internal_routes.manager, "broadcast_alert", fake_broadcast)

    camera = make_camera(
        session,
        name="Partial Patch Cam",
        channel_id=42,
        connection_status=ConnectionStatus.DISCONNECTED.value,
        ai_status=AIStatus.PAUSED.value,
    )

    resp = client.patch(
        f"/api/internal/cameras/{camera.camera_id}/status",
        headers=internal_headers(),
        json={"connection_status": ConnectionStatus.RECONNECTING.value},
    )

    assert resp.status_code == 200

    session.refresh(camera)
    assert camera.connection_status == ConnectionStatus.RECONNECTING.value
    assert camera.ai_status == AIStatus.PAUSED.value
    assert payloads[0]["connection_status"] == ConnectionStatus.RECONNECTING.value
    assert payloads[0]["ai_status"] == AIStatus.PAUSED.value


@pytest.mark.parametrize(
    ("is_enabled", "is_active"),
    [
        (False, True),
        (True, False),
    ],
)
def test_update_camera_status_rejects_disabled_or_inactive_camera(
    client: TestClient,
    session: Session,
    is_enabled: bool,
    is_active: bool,
):
    camera = make_camera(
        session,
        name=f"Unavailable Patch Cam {is_enabled}-{is_active}",
        channel_id=50 if is_enabled else 51,
        is_enabled=is_enabled,
        is_active=is_active,
    )

    resp = client.patch(
        f"/api/internal/cameras/{camera.camera_id}/status",
        headers=internal_headers(),
        json={"connection_status": ConnectionStatus.CONNECTED.value},
    )

    assert resp.status_code == 404
    assert "inactive, or disabled" in resp.json()["detail"]


@pytest.mark.parametrize(
    "alert_status",
    [DetectionStatus.UNVERIFIED, DetectionStatus.ONGOING],
)
def test_update_camera_status_rejects_active_override_while_alert_is_open(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    alert_status: DetectionStatus,
):
    payloads: list[dict] = []

    async def fake_broadcast(payload: dict) -> None:
        payloads.append(payload)

    monkeypatch.setattr(internal_routes.manager, "broadcast_alert", fake_broadcast)

    camera = make_camera(
        session,
        name=f"Conflict Cam {alert_status.value}",
        channel_id=61 if alert_status == DetectionStatus.UNVERIFIED else 62,
        ai_status=AIStatus.PAUSED.value,
        connection_status=ConnectionStatus.CONNECTED.value,
    )
    make_detection(session, camera, status=alert_status)

    resp = client.patch(
        f"/api/internal/cameras/{camera.camera_id}/status",
        headers=internal_headers(),
        json={"ai_status": AIStatus.ACTIVE.value},
    )

    assert resp.status_code == 409
    assert "cannot be set to Active" in resp.json()["detail"]

    session.refresh(camera)
    assert camera.ai_status == AIStatus.PAUSED.value
    assert payloads == []


@pytest.mark.parametrize(
    "closed_status",
    [DetectionStatus.DISMISSED, DetectionStatus.RESOLVED],
)
def test_update_camera_status_allows_active_when_no_open_alert_exists(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    closed_status: DetectionStatus,
):
    payloads: list[dict] = []

    async def fake_broadcast(payload: dict) -> None:
        payloads.append(payload)

    monkeypatch.setattr(internal_routes.manager, "broadcast_alert", fake_broadcast)

    camera = make_camera(
        session,
        name=f"Closed Alert Cam {closed_status.value}",
        channel_id=71 if closed_status == DetectionStatus.DISMISSED else 72,
        ai_status=AIStatus.PAUSED.value,
    )
    make_detection(session, camera, status=closed_status)

    resp = client.patch(
        f"/api/internal/cameras/{camera.camera_id}/status",
        headers=internal_headers(),
        json={"ai_status": AIStatus.ACTIVE.value},
    )

    assert resp.status_code == 200

    session.refresh(camera)
    assert camera.ai_status == AIStatus.ACTIVE.value
    assert payloads[0]["ai_status"] == AIStatus.ACTIVE.value


def test_update_camera_status_invalid_enum_returns_422(
    client: TestClient,
    session: Session,
):
    camera = make_camera(session, name="Enum Cam", channel_id=81)

    resp = client.patch(
        f"/api/internal/cameras/{camera.camera_id}/status",
        headers=internal_headers(),
        json={"ai_status": "Sleeping"},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_update_camera_status_allows_connection_update_while_alert_is_open(
    client: TestClient,
    session: Session,
):
    camera = make_camera(
        session,
        name="Open Alert Connection Cam",
        channel_id=82,
        connection_status=ConnectionStatus.DISCONNECTED.value,
        ai_status=AIStatus.PAUSED.value,
    )
    make_detection(session, camera, status=DetectionStatus.UNVERIFIED)

    resp = client.patch(
        f"/api/internal/cameras/{camera.camera_id}/status",
        headers=internal_headers(),
        json={"connection_status": ConnectionStatus.RECONNECTING.value},
    )

    assert resp.status_code == 200

    session.refresh(camera)
    assert camera.connection_status == ConnectionStatus.RECONNECTING.value
    assert camera.ai_status == AIStatus.PAUSED.value
