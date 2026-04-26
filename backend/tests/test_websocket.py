"""
End-to-end websocket tests for live alert and camera-status broadcasts.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import AIStatus, ConnectionStatus, DetectionStatus
from app.ws_manager import manager

from .conftest import auth_headers, internal_headers, make_camera, make_detection, make_operator


@pytest.fixture(autouse=True)
def clear_websocket_connections():
    manager.active_connections.clear()
    yield
    manager.active_connections.clear()


def test_internal_alert_broadcasts_to_websocket_client(
    client: TestClient,
    session: Session,
):
    camera = make_camera(
        session,
        name="WS Alert Cam",
        channel_id=301,
        connection_status=ConnectionStatus.CONNECTED.value,
        ai_status=AIStatus.ACTIVE.value,
    )

    with client.websocket_connect("/ws/alerts") as websocket:
        resp = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json={
                "camera_id": camera.camera_id,
                "detected_at": datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc).isoformat(),
                "snapshot_path": "ws/alert.jpg",
                "confidence_score": 0.94,
            },
        )

        assert resp.status_code == 200

        detection_message = websocket.receive_json()
        status_message = websocket.receive_json()

    assert detection_message["type"] == "NEW_DETECTION"
    assert detection_message["camera_id"] == camera.camera_id
    assert detection_message["detection_status"] == DetectionStatus.UNVERIFIED.value

    assert status_message == {
        "type": "CAMERA_STATUS_UPDATE",
        "camera_id": camera.camera_id,
        "connection_status": ConnectionStatus.CONNECTED.value,
        "ai_status": AIStatus.PAUSED.value,
    }


def test_status_patch_broadcasts_to_all_connected_websocket_clients(
    client: TestClient,
    session: Session,
):
    camera = make_camera(
        session,
        name="WS Patch Cam",
        channel_id=302,
        connection_status=ConnectionStatus.DISCONNECTED.value,
        ai_status=AIStatus.INACTIVE.value,
    )

    with client.websocket_connect("/ws/alerts") as ws_one, client.websocket_connect("/ws/alerts") as ws_two:
        resp = client.patch(
            f"/api/internal/cameras/{camera.camera_id}/status",
            headers=internal_headers(),
            json={
                "connection_status": ConnectionStatus.CONNECTED.value,
                "ai_status": AIStatus.ACTIVE.value,
            },
        )

        assert resp.status_code == 200

        first_message = ws_one.receive_json()
        second_message = ws_two.receive_json()

    expected = {
        "type": "CAMERA_STATUS_UPDATE",
        "camera_id": camera.camera_id,
        "connection_status": ConnectionStatus.CONNECTED.value,
        "ai_status": AIStatus.ACTIVE.value,
    }
    assert first_message == expected
    assert second_message == expected


def test_resolve_alert_broadcasts_camera_status_update_over_websocket(
    client: TestClient,
    session: Session,
):
    operator = make_operator(session, username="wsoperator", password="Operator123")
    headers = auth_headers(client, "wsoperator", "Operator123")
    camera = make_camera(
        session,
        name="WS Resolve Cam",
        channel_id=303,
        ai_status=AIStatus.PAUSED.value,
        connection_status=ConnectionStatus.CONNECTED.value,
    )
    detection = make_detection(session, camera, status=DetectionStatus.ONGOING)

    with client.websocket_connect("/ws/alerts") as websocket:
        resp = client.post(f"/api/alerts/{detection.log_id}/resolve", headers=headers)

        assert resp.status_code == 200

        message = websocket.receive_json()

    assert operator.user_id is not None
    assert message == {
        "type": "CAMERA_STATUS_UPDATE",
        "camera_id": camera.camera_id,
        "connection_status": ConnectionStatus.CONNECTED.value,
        "ai_status": AIStatus.ACTIVE.value,
    }


def test_dismiss_ongoing_broadcasts_camera_status_update_over_websocket(
    client: TestClient,
    session: Session,
):
    make_operator(session, username="wsdismiss", password="Operator123")
    headers = auth_headers(client, "wsdismiss", "Operator123")
    camera = make_camera(
        session,
        name="WS Dismiss Cam",
        channel_id=304,
        ai_status=AIStatus.PAUSED.value,
        connection_status=ConnectionStatus.CONNECTED.value,
    )
    detection = make_detection(session, camera, status=DetectionStatus.ONGOING)

    with client.websocket_connect("/ws/alerts") as websocket:
        resp = client.post(f"/api/alerts/{detection.log_id}/dismiss", headers=headers)

        assert resp.status_code == 200

        message = websocket.receive_json()

    assert message == {
        "type": "CAMERA_STATUS_UPDATE",
        "camera_id": camera.camera_id,
        "connection_status": ConnectionStatus.CONNECTED.value,
        "ai_status": AIStatus.ACTIVE.value,
    }
