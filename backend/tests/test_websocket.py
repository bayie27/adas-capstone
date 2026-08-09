"""
End-to-end websocket tests for live alert and camera-status broadcasts.

04_PKG_realtime.md Step 4 made the handshake authenticated: every connection
now needs a valid session cookie. Every test logs in first via
`auth_headers()` and passes the resulting `Cookie` header explicitly to
`websocket_connect(..., headers=...)` — the same workaround `auth_headers()`
already uses for plain HTTP calls in this suite, because httpx's cookie jar
(what `TestClient` is built on) does not attach cookies to `ws://`-scheme
requests even when the same value was just set for `http://testserver` by
the login response. (04_PKG_realtime.md's verification note that "TestClient
carries cookies between post and websocket_connect automatically" does not
hold for this httpx/starlette combination — see the P3 completion report.)
`app.state.realtime_manager` is a fresh instance per `client` fixture (see
conftest.py), so there is no manual connection-registry reset between tests
anymore.

Every connection also receives a `CONNECTION_READY` envelope immediately
after the handshake (before any broadcast triggered by the test body), and
every broadcast is now wrapped in the versioned envelope with the payload
under `data` — both are 04_PKG_realtime.md Step 1 requirements. The
underlying assertions (which event type, which camera/log id, which status
values, and the relative order between NEW_DETECTION/ALERT_STATUS_UPDATE and
CAMERA_STATUS_UPDATE) are unchanged from before P3.
"""

from datetime import UTC, datetime

from app.models import AIStatus, ConnectionStatus, DetectionStatus, UserRole
from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import (
    auth_headers,
    internal_headers,
    make_camera,
    make_detection,
    make_operator,
)


def _assert_envelope(message: dict, expected_type: str) -> dict:
    """Common envelope shape (01_CONTRACTS.md §9.1). Returns `data` for the
    caller to make type-specific assertions against."""
    assert message["version"] == 1
    assert isinstance(message["event_id"], str) and message["event_id"]
    assert message["type"] == expected_type
    assert isinstance(message["occurred_at"], str) and message["occurred_at"]
    return message["data"]


def test_internal_alert_broadcasts_to_websocket_client(
    client: TestClient,
    session: Session,
):
    operator = make_operator(session, username="wsalert", password="Operator123")
    headers = auth_headers(client, "wsalert", "Operator123")

    camera = make_camera(
        session,
        name="WS Alert Cam",
        channel_id=301,
        connection_status=ConnectionStatus.CONNECTED.value,
        ai_status=AIStatus.ACTIVE.value,
    )

    with client.websocket_connect("/ws/alerts", headers=headers) as websocket:
        ready_data = _assert_envelope(websocket.receive_json(), "CONNECTION_READY")
        assert ready_data["user_id"] == operator.user_id
        assert ready_data["role"] == UserRole.OPERATOR.value

        resp = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json={
                "camera_id": camera.camera_id,
                "detected_at": datetime(2026, 4, 26, 12, 0, tzinfo=UTC).isoformat(),
                "snapshot_path": "ws/alert.jpg",
                "confidence_score": 0.94,
            },
        )

        assert resp.status_code == 200

        detection_data = _assert_envelope(websocket.receive_json(), "NEW_DETECTION")
        status_data = _assert_envelope(websocket.receive_json(), "CAMERA_STATUS_UPDATE")

    assert detection_data["camera_id"] == camera.camera_id
    assert detection_data["detection_status"] == DetectionStatus.UNVERIFIED.value
    assert detection_data["confidence_score"] == 0.94
    assert (
        detection_data["snapshot_url"]
        == f"/api/alerts/{detection_data['log_id']}/snapshot"
    )

    assert status_data == {
        "camera_id": camera.camera_id,
        "camera_name": "WS Alert Cam",
        "is_enabled": True,
        "desired_ai_state": "Inactive",
        "desired_state_reason": None,
        "connection_status": ConnectionStatus.CONNECTED.value,
        "ai_status": AIStatus.PAUSED.value,
        "cooldown_until": None,
        "config_version": 1,
    }


def test_status_patch_broadcasts_to_all_connected_websocket_clients(
    client: TestClient,
    session: Session,
):
    make_operator(session, username="wspatch", password="Operator123")
    headers = auth_headers(client, "wspatch", "Operator123")

    camera = make_camera(
        session,
        name="WS Patch Cam",
        channel_id=302,
        connection_status=ConnectionStatus.DISCONNECTED.value,
        ai_status=AIStatus.INACTIVE.value,
    )

    with (
        client.websocket_connect("/ws/alerts", headers=headers) as ws_one,
        client.websocket_connect("/ws/alerts", headers=headers) as ws_two,
    ):
        _assert_envelope(ws_one.receive_json(), "CONNECTION_READY")
        _assert_envelope(ws_two.receive_json(), "CONNECTION_READY")

        resp = client.patch(
            f"/api/internal/cameras/{camera.camera_id}/status",
            headers=internal_headers(),
            json={
                "connection_status": ConnectionStatus.CONNECTED.value,
                "ai_status": AIStatus.ACTIVE.value,
            },
        )

        assert resp.status_code == 200

        first_data = _assert_envelope(ws_one.receive_json(), "CAMERA_STATUS_UPDATE")
        second_data = _assert_envelope(ws_two.receive_json(), "CAMERA_STATUS_UPDATE")

    expected = {
        "camera_id": camera.camera_id,
        "camera_name": "WS Patch Cam",
        "is_enabled": True,
        "desired_ai_state": "Inactive",
        "desired_state_reason": None,
        "connection_status": ConnectionStatus.CONNECTED.value,
        "ai_status": AIStatus.ACTIVE.value,
        "cooldown_until": None,
        "config_version": 1,
    }
    assert first_data == expected
    assert second_data == expected


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

    with client.websocket_connect("/ws/alerts", headers=headers) as websocket:
        _assert_envelope(websocket.receive_json(), "CONNECTION_READY")

        resp = client.post(f"/api/alerts/{detection.log_id}/resolve", headers=headers)

        assert resp.status_code == 200

        camera_data = _assert_envelope(websocket.receive_json(), "CAMERA_STATUS_UPDATE")
        alert_data = _assert_envelope(websocket.receive_json(), "ALERT_STATUS_UPDATE")

    assert operator.user_id is not None
    assert camera_data == {
        "camera_id": camera.camera_id,
        "camera_name": "WS Resolve Cam",
        "is_enabled": True,
        "desired_ai_state": "Inactive",
        "desired_state_reason": None,
        "connection_status": ConnectionStatus.CONNECTED.value,
        "ai_status": AIStatus.ACTIVE.value,
        "cooldown_until": None,
        "config_version": 1,
    }
    assert alert_data["log_id"] == detection.log_id
    assert alert_data["detection_status"] == DetectionStatus.RESOLVED.value
    assert alert_data["action"] == "ALERT_RESOLVE"


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

    with client.websocket_connect("/ws/alerts", headers=headers) as websocket:
        _assert_envelope(websocket.receive_json(), "CONNECTION_READY")

        resp = client.post(f"/api/alerts/{detection.log_id}/dismiss", headers=headers)

        assert resp.status_code == 200

        camera_data = _assert_envelope(websocket.receive_json(), "CAMERA_STATUS_UPDATE")
        alert_data = _assert_envelope(websocket.receive_json(), "ALERT_STATUS_UPDATE")

    assert camera_data == {
        "camera_id": camera.camera_id,
        "camera_name": "WS Dismiss Cam",
        "is_enabled": True,
        "desired_ai_state": "Inactive",
        "desired_state_reason": None,
        "connection_status": ConnectionStatus.CONNECTED.value,
        "ai_status": AIStatus.ACTIVE.value,
        "cooldown_until": None,
        "config_version": 1,
    }
    assert alert_data["log_id"] == detection.log_id
    assert alert_data["detection_status"] == DetectionStatus.DISMISSED.value
    assert alert_data["action"] == "ALERT_CORRECTION"
