"""10_PKG_migration_evidence.md Step 3 — NFR-04 / TC-R-201 (alert delivery
< 2s) and D-008 (slow-client isolation): a stalled connection must never
delay a healthy one's alert.

Both tests use a camera the perf dataset deliberately keeps incident-free
(see conftest.py's `latency_camera_id` / `isolation_camera_id`) so the
timed `POST /api/internal/alert` creates a genuinely new incident instead
of hitting `ux_detection_open_camera`'s 409 against one of the 100,000
pre-seeded rows.
"""

import time

from fastapi.testclient import TestClient

from .conftest import internal_headers, operator_auth_headers

ALERT_DELIVERY_BUDGET_SECONDS = 2.0


def _post_alert(client: TestClient, settings, *, camera_id: int, label: str) -> None:
    resp = client.post(
        "/api/internal/alert",
        headers=internal_headers(settings),
        json={
            "camera_id": camera_id,
            "detected_at": "2026-08-10T12:00:00+00:00",
            "snapshot_path": f"perf/{label}.jpg",
            "confidence_score": 0.93,
        },
    )
    assert resp.status_code in (200, 201), resp.text


class TestAlertDeliveryLatency:
    def test_alert_reaches_a_connected_client_under_2s(
        self, perf_client: TestClient, perf_settings, perf_seeded: dict
    ):
        headers = operator_auth_headers(perf_client, perf_seeded)

        with perf_client.websocket_connect("/ws/alerts", headers=headers) as ws:
            ready = ws.receive_json()
            assert ready["type"] == "CONNECTION_READY"

            started = time.perf_counter()
            _post_alert(
                perf_client,
                perf_settings,
                camera_id=perf_seeded["latency_camera_id"],
                label="latency",
            )
            event = ws.receive_json()
            elapsed = time.perf_counter() - started

        assert event["type"] == "NEW_DETECTION"
        assert event["data"]["camera_id"] == perf_seeded["latency_camera_id"]

        print(
            f"\n[PERF] POST /api/internal/alert -> NEW_DETECTION on a "
            f"connected WebSocket client, against a 100,000-row database: "
            f"{elapsed:.3f}s (budget {ALERT_DELIVERY_BUDGET_SECONDS}s)"
        )
        assert elapsed < ALERT_DELIVERY_BUDGET_SECONDS


class TestSlowClientIsolation:
    def test_stalled_client_does_not_delay_a_healthy_client(
        self, perf_client: TestClient, perf_settings, perf_seeded: dict
    ):
        headers = operator_auth_headers(perf_client, perf_seeded)

        with (
            perf_client.websocket_connect("/ws/alerts", headers=headers) as stalled,
            perf_client.websocket_connect("/ws/alerts", headers=headers) as healthy,
        ):
            assert stalled.receive_json()["type"] == "CONNECTION_READY"
            assert healthy.receive_json()["type"] == "CONNECTION_READY"

            # `stalled` never calls receive() again from here on — it
            # simulates D-008's "one frozen workstation" scenario. Only
            # `healthy` is timed.
            started = time.perf_counter()
            _post_alert(
                perf_client,
                perf_settings,
                camera_id=perf_seeded["isolation_camera_id"],
                label="isolation",
            )
            event = healthy.receive_json()
            elapsed = time.perf_counter() - started

        assert event["type"] == "NEW_DETECTION"
        assert event["data"]["camera_id"] == perf_seeded["isolation_camera_id"]

        print(
            f"[PERF] D-008 slow-client isolation: healthy client received "
            f"NEW_DETECTION in {elapsed:.3f}s with a stalled peer connected "
            f"(budget {ALERT_DELIVERY_BUDGET_SECONDS}s)"
        )
        assert elapsed < ALERT_DELIVERY_BUDGET_SECONDS
