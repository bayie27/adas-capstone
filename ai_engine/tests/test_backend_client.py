from unittest.mock import MagicMock, patch

import backend_client
import pytest
import requests
from backend_client import DeliveryOutcome


def _mock_response(status_code, json_body=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_body if json_body is not None else {}
    return response


@pytest.mark.parametrize(
    "status_code,expected",
    [
        (200, DeliveryOutcome.ACKNOWLEDGED),  # idempotent retry
        (201, DeliveryOutcome.ACKNOWLEDGED),  # new incident committed
        (409, DeliveryOutcome.CONFLICT),
        (404, DeliveryOutcome.CAMERA_GONE),
        (401, DeliveryOutcome.AUTH_FAILURE),
        (403, DeliveryOutcome.AUTH_FAILURE),
        (422, DeliveryOutcome.QUARANTINE),
        (500, DeliveryOutcome.RETRY),
        (503, DeliveryOutcome.RETRY),
        (418, DeliveryOutcome.RETRY),  # unexpected code: never crash
    ],
)
def test_post_event_outcome_classification(status_code, expected):
    with patch(
        "backend_client.requests.post", return_value=_mock_response(status_code)
    ):
        outcome = backend_client.post_event({"source_event_id": "x"})
    assert outcome is expected


def test_post_event_timeout_maps_to_retry():
    with patch(
        "backend_client.requests.post", side_effect=requests.Timeout("timed out")
    ):
        outcome = backend_client.post_event({"source_event_id": "x"})
    assert outcome is DeliveryOutcome.RETRY


def test_post_event_connection_error_maps_to_retry():
    with patch(
        "backend_client.requests.post",
        side_effect=requests.ConnectionError("connection refused"),
    ):
        outcome = backend_client.post_event({"source_event_id": "x"})
    assert outcome is DeliveryOutcome.RETRY


def test_send_heartbeat_returns_none_on_network_failure():
    with patch(
        "backend_client.requests.post",
        side_effect=requests.ConnectionError("backend is down"),
    ):
        result = backend_client.send_heartbeat("engine-1", [])
    assert result is None


def test_send_heartbeat_returns_none_on_non_200():
    with patch("backend_client.requests.post", return_value=_mock_response(500)):
        result = backend_client.send_heartbeat("engine-1", [])
    assert result is None


def test_send_heartbeat_returns_parsed_snapshot_on_success():
    body = {
        "server_time": "2026-07-12T10:30:05+00:00",
        "heartbeat_interval_seconds": 3,
        "cameras": [],
    }
    with patch("backend_client.requests.post", return_value=_mock_response(200, body)):
        result = backend_client.send_heartbeat("engine-1", [])
    assert result == body


def test_rtsp_url_never_appears_in_log_output(caplog):
    # The heartbeat response is credential-bearing (rtsp_url) — it must
    # never be logged, at any level, on success or failure.
    body = {
        "server_time": "2026-07-12T10:30:05+00:00",
        "heartbeat_interval_seconds": 3,
        "cameras": [
            {
                "camera_id": 5,
                "channel_id": 3,
                "camera_name": "Ayala Highway",
                "rtsp_url": "rtsp://svc_user:s3cr3t@dss.example/cam/realmonitor",
                "is_enabled": True,
                "desired_ai_state": "Active",
                "desired_state_reason": None,
                "cooldown_until": None,
                "config_version": 1,
            }
        ],
    }
    with caplog.at_level("DEBUG"):
        with patch(
            "backend_client.requests.post", return_value=_mock_response(200, body)
        ):
            backend_client.send_heartbeat("engine-1", [])
        with patch(
            "backend_client.requests.post", return_value=_mock_response(500, body)
        ):
            backend_client.send_heartbeat("engine-1", [])

    assert "rtsp://" not in caplog.text
    assert "s3cr3t" not in caplog.text
