"""
Tests for /api/internal.
Covers AI-engine alert ingestion (v1 legacy + v2 idempotent), camera
polling, status updates, the v2 heartbeat, and internal auth.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.redaction import redact_text
from app.models import AIStatus, ConnectionStatus, DetectionLog, DetectionStatus
from app.schemas.events import EventEnvelope
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import internal_headers, make_camera, make_detection


def _capture_broadcasts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> list[dict]:
    """Replaces RealtimeManager.broadcast on this test's app instance with a
    recorder, returning the envelopes (as plain dicts) in emission order."""
    payloads: list[dict] = []

    def fake_broadcast(event: EventEnvelope, *, roles=None) -> None:
        payloads.append(event.model_dump(mode="json"))

    monkeypatch.setattr(client.app.state.realtime_manager, "broadcast", fake_broadcast)
    return payloads


class TestReceiveAiAlertV1Legacy:
    def test_v1_creates_log_pauses_camera_and_broadcasts(
        self,
        client: TestClient,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        payloads = _capture_broadcasts(client, monkeypatch)

        camera = make_camera(
            session,
            name="Ingress Cam",
            channel_id=11,
            connection_status=ConnectionStatus.CONNECTED.value,
            ai_status=AIStatus.ACTIVE.value,
            desired_ai_state="Active",
        )

        resp = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json={
                "camera_id": camera.camera_id,
                "detected_at": datetime(2026, 4, 26, 12, 0).isoformat(),
                "snapshot_path": "snapshots/ingress.jpg",
                "confidence_score": 0.97,
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["camera_id"] == camera.camera_id
        assert body["detection_status"] == DetectionStatus.UNVERIFIED.value

        session.refresh(camera)
        assert camera.desired_ai_state == "Paused"
        assert camera.desired_state_reason == "incident"

        logs = session.exec(
            select(DetectionLog).where(DetectionLog.camera_id == camera.camera_id)
        ).all()
        assert len(logs) == 1
        assert logs[0].snapshot_key == "snapshots/ingress.jpg"
        assert logs[0].detected_at.tzinfo is not None

        assert [payload["type"] for payload in payloads] == [
            "NEW_DETECTION",
            "CAMERA_STATUS_UPDATE",
        ]
        assert payloads[0]["data"]["camera_id"] == camera.camera_id

    def test_v1_naive_local_time_is_not_treated_as_utc(
        self, client: TestClient, session: Session
    ):
        """05_PKG_incidents_cameras.md Step 8 — the exact bug this package
        exists to avoid: treating a naive v1 timestamp as UTC would shift
        every legacy detection by the server's local offset."""
        camera = make_camera(session, name="TZ Cam", channel_id=12)
        naive_local = datetime(2026, 4, 26, 20, 0, 0)

        resp = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json={
                "camera_id": camera.camera_id,
                "detected_at": naive_local.isoformat(),
                "snapshot_path": "cam12.jpg",
                "confidence_score": 0.9,
            },
        )

        assert resp.status_code == 200
        log = session.exec(
            select(DetectionLog).where(DetectionLog.camera_id == camera.camera_id)
        ).first()
        # If the naive value had been reinterpreted as UTC, this would be
        # naive_local.replace(tzinfo=UTC) instead — assert it is not.
        assert log.detected_at != naive_local.replace(tzinfo=UTC)

    def test_v1_generates_its_own_source_event_id(
        self, client: TestClient, session: Session
    ):
        camera = make_camera(session, name="UUID Cam", channel_id=13)
        resp = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json={
                "camera_id": camera.camera_id,
                "detected_at": datetime.now(UTC).isoformat(),
                "snapshot_path": "x.jpg",
                "confidence_score": 0.9,
            },
        )
        assert resp.status_code == 200
        assert uuid.UUID(resp.json()["source_event_id"])

    @pytest.mark.parametrize(
        ("is_enabled", "is_active"),
        [
            (False, True),
            (True, False),
        ],
    )
    def test_v1_rejects_disabled_or_inactive_camera(
        self,
        client: TestClient,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
        is_enabled: bool,
        is_active: bool,
    ):
        payloads = _capture_broadcasts(client, monkeypatch)

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
        assert (
            session.exec(
                select(DetectionLog).where(DetectionLog.camera_id == camera.camera_id)
            ).all()
            == []
        )
        assert payloads == []


class TestReceiveAiAlertV2:
    def _payload(self, camera_id: int, **overrides) -> dict:
        payload = {
            "source_event_id": str(uuid.uuid4()),
            "camera_id": camera_id,
            "detected_at": "2026-07-12T10:30:00+00:00",
            "snapshot_key": "2026/07/12/camera_5/x.jpg",
            "confidence_score": 0.87,
        }
        payload.update(overrides)
        return payload

    def test_v2_creates_with_201_and_given_source_event_id(
        self, client: TestClient, session: Session
    ):
        camera = make_camera(session, name="V2 Cam", channel_id=30)
        source_event_id = str(uuid.uuid4())
        resp = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json=self._payload(camera.camera_id, source_event_id=source_event_id),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["source_event_id"] == source_event_id

    def test_v2_idempotent_retry_returns_200_same_row(
        self, client: TestClient, session: Session
    ):
        camera = make_camera(session, name="Idempotent Cam", channel_id=31)
        payload = self._payload(camera.camera_id)

        first = client.post(
            "/api/internal/alert", headers=internal_headers(), json=payload
        )
        assert first.status_code == 201
        log_id = first.json()["log_id"]

        second = client.post(
            "/api/internal/alert", headers=internal_headers(), json=payload
        )
        assert second.status_code == 200
        assert second.json()["log_id"] == log_id

        rows = session.exec(
            select(DetectionLog).where(
                DetectionLog.source_event_id == payload["source_event_id"]
            )
        ).all()
        assert len(rows) == 1

    def test_v2_retry_after_resolved_returns_resolved_unchanged(
        self, client: TestClient, session: Session
    ):
        """Edge case 10.2 — a retry after the incident closed must not
        create a new one or reopen it."""
        camera = make_camera(session, name="Retry After Resolve Cam", channel_id=32)
        payload = self._payload(camera.camera_id)

        first = client.post(
            "/api/internal/alert", headers=internal_headers(), json=payload
        )
        log_id = first.json()["log_id"]
        log = session.get(DetectionLog, log_id)
        log.detection_status = DetectionStatus.RESOLVED.value
        session.add(log)
        session.commit()

        retry = client.post(
            "/api/internal/alert", headers=internal_headers(), json=payload
        )
        assert retry.status_code == 200
        assert retry.json()["log_id"] == log_id
        assert retry.json()["detection_status"] == DetectionStatus.RESOLVED.value

    def test_v2_open_camera_conflict_is_409(self, client: TestClient, session: Session):
        camera = make_camera(session, name="Conflict Cam", channel_id=33)
        first = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json=self._payload(camera.camera_id),
        )
        assert first.status_code == 201

        second = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json=self._payload(
                camera.camera_id, detected_at="2026-07-12T10:31:00+00:00"
            ),
        )
        assert second.status_code == 409
        assert second.json()["code"] == "CONFLICT_STATE"

    def test_v2_second_source_event_from_different_camera_is_409(
        self, client: TestClient, session: Session
    ):
        """Edge case 10.3 — a distinct source_event_id targeting a camera
        that already has an open incident must not silently overwrite it."""
        camera = make_camera(session, name="Cross Camera Conflict Cam", channel_id=34)
        first = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json=self._payload(camera.camera_id),
        )
        assert first.status_code == 201

        second = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json=self._payload(camera.camera_id),
        )
        assert second.status_code == 409

    def test_v2_broadcast_order_new_detection_then_camera(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        payloads = _capture_broadcasts(client, monkeypatch)
        camera = make_camera(session, name="Order Cam", channel_id=35)

        resp = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json=self._payload(camera.camera_id),
        )
        assert resp.status_code == 201
        assert [p["type"] for p in payloads] == [
            "NEW_DETECTION",
            "CAMERA_STATUS_UPDATE",
        ]

    def test_v2_unknown_camera_is_404(self, client: TestClient, session: Session):
        resp = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json=self._payload(999999),
        )
        assert resp.status_code == 404

    def test_v2_future_detected_at_is_accepted(
        self, client: TestClient, session: Session
    ):
        """Edge case 5.5 — decided: accept, do not reject or clamp."""
        camera = make_camera(session, name="Future Cam", channel_id=36)
        future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
        resp = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json=self._payload(camera.camera_id, detected_at=future),
        )
        assert resp.status_code == 201

    def test_v2_far_past_detected_at_is_accepted(
        self, client: TestClient, session: Session
    ):
        """Edge case 5.6 — an outbox drain after a long outage is legitimate."""
        camera = make_camera(session, name="Past Cam", channel_id=37)
        past = (datetime.now(UTC) - timedelta(hours=6)).isoformat()
        resp = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json=self._payload(camera.camera_id, detected_at=past),
        )
        assert resp.status_code == 201

    def test_malformed_dual_shape_payload_is_422(
        self, client: TestClient, session: Session
    ):
        camera = make_camera(session, name="Malformed Cam", channel_id=38)
        resp = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json={
                "source_event_id": str(uuid.uuid4()),
                "snapshot_key": "a.jpg",
                "snapshot_path": "b.jpg",
                "camera_id": camera.camera_id,
                "detected_at": "2026-07-12T10:30:00+00:00",
                "confidence_score": 0.9,
            },
        )
        assert resp.status_code == 422


class TestInternalAuth:
    def test_internal_routes_require_valid_api_key(self, client: TestClient):
        resp = client.get("/api/internal/cameras", headers={"x-api-key": "wrong-key"})

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid Internal API Key"

    def test_internal_routes_reject_missing_api_key(self, client: TestClient):
        """Edge case 8.13 — an absent x-api-key header must 401, not 422."""
        resp = client.get("/api/internal/cameras")

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid Internal API Key"


class TestLegacyCameraPoll:
    def test_returns_only_enabled_and_active(
        self,
        client: TestClient,
        session: Session,
    ):
        included_one = make_camera(
            session,
            name="Poll Cam 1",
            channel_id=41,
            connection_status=ConnectionStatus.CONNECTED.value,
        )
        included_two = make_camera(
            session,
            name="Poll Cam 2",
            channel_id=42,
            connection_status=ConnectionStatus.RECONNECTING.value,
        )
        make_camera(session, name="Disabled Poll Cam", channel_id=43, is_enabled=False)
        make_camera(session, name="Inactive Poll Cam", channel_id=44, is_active=False)

        resp = client.get("/api/internal/cameras", headers=internal_headers())

        assert resp.status_code == 200
        body = resp.json()
        returned = {camera["camera_id"]: camera for camera in body}
        assert set(returned) == {included_one.camera_id, included_two.camera_id}

    def test_ai_status_field_reports_desired_state_not_observed(
        self, client: TestClient, session: Session
    ):
        """Step 8 — the field named `ai_status` here means desired_ai_state,
        not the true observed status, because ai_engine/sync.py's pause/
        resume logic reads it as backend intent."""
        camera = make_camera(
            session,
            name="Divergence Cam",
            channel_id=45,
            ai_status=AIStatus.INACTIVE.value,  # true observed status
            desired_ai_state="Paused",  # what this route must report
        )

        resp = client.get("/api/internal/cameras", headers=internal_headers())

        row = next(c for c in resp.json() if c["camera_id"] == camera.camera_id)
        assert row["ai_status"] == "Paused"


class TestUpdateCameraStatus:
    def test_updates_fields_and_broadcasts(
        self,
        client: TestClient,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        payloads = _capture_broadcasts(client, monkeypatch)

        camera = make_camera(
            session,
            name="Patch Cam",
            channel_id=51,
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
        assert [p["type"] for p in payloads] == ["CAMERA_STATUS_UPDATE"]

    def test_supports_partial_updates(
        self,
        client: TestClient,
        session: Session,
    ):
        camera = make_camera(
            session,
            name="Partial Patch Cam",
            channel_id=52,
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

    @pytest.mark.parametrize(
        ("is_enabled", "is_active"),
        [
            (False, True),
            (True, False),
        ],
    )
    def test_rejects_disabled_or_inactive_camera(
        self,
        client: TestClient,
        session: Session,
        is_enabled: bool,
        is_active: bool,
    ):
        camera = make_camera(
            session,
            name=f"Unavailable Patch Cam {is_enabled}-{is_active}",
            channel_id=60 if is_enabled else 61,
            is_enabled=is_enabled,
            is_active=is_active,
        )

        resp = client.patch(
            f"/api/internal/cameras/{camera.camera_id}/status",
            headers=internal_headers(),
            json={"connection_status": ConnectionStatus.CONNECTED.value},
        )

        assert resp.status_code == 404

    @pytest.mark.parametrize(
        "alert_status",
        [DetectionStatus.UNVERIFIED, DetectionStatus.ONGOING],
    )
    def test_rejects_active_override_while_alert_is_open(
        self,
        client: TestClient,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
        alert_status: DetectionStatus,
    ):
        payloads = _capture_broadcasts(client, monkeypatch)

        camera = make_camera(
            session,
            name=f"Conflict Cam {alert_status.value}",
            channel_id=70 if alert_status == DetectionStatus.UNVERIFIED else 71,
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
        session.refresh(camera)
        assert camera.ai_status == AIStatus.PAUSED.value
        assert payloads == []

    @pytest.mark.parametrize(
        "closed_status",
        [DetectionStatus.DISMISSED, DetectionStatus.RESOLVED],
    )
    def test_allows_active_when_no_open_alert_exists(
        self,
        client: TestClient,
        session: Session,
        closed_status: DetectionStatus,
    ):
        camera = make_camera(
            session,
            name=f"Closed Alert Cam {closed_status.value}",
            channel_id=80 if closed_status == DetectionStatus.DISMISSED else 81,
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

    def test_invalid_enum_returns_422(self, client: TestClient, session: Session):
        camera = make_camera(session, name="Enum Cam", channel_id=90)

        resp = client.patch(
            f"/api/internal/cameras/{camera.camera_id}/status",
            headers=internal_headers(),
            json={"ai_status": "Sleeping"},
        )

        assert resp.status_code == 422
        assert resp.json()["code"] == "VALIDATION_ERROR"


class TestHeartbeat:
    def test_roundtrip_updates_observed_state_and_returns_snapshot(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        payloads = _capture_broadcasts(client, monkeypatch)
        camera = make_camera(session, name="HB Cam", channel_id=100)

        resp = client.post(
            "/api/internal/heartbeat",
            headers=internal_headers(),
            json={
                "engine_id": "adas-ai-1",
                "sent_at": "2026-07-12T10:30:05.120+00:00",
                "cameras": [
                    {
                        "camera_id": camera.camera_id,
                        "connection_status": "Connected",
                        "ai_status": "Active",
                        "applied_config_version": 1,
                        "measured_fps": 11.8,
                        "inference_latency_ms": 42.5,
                    }
                ],
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["heartbeat_interval_seconds"] == 3
        row = next(c for c in body["cameras"] if c["camera_id"] == camera.camera_id)
        assert row["rtsp_url"].startswith("rtsp://")
        assert "config_version" in row

        session.refresh(camera)
        assert camera.connection_status == "Connected"
        assert camera.ai_status == "Active"
        assert camera.measured_fps == 11.8
        assert camera.last_heartbeat_at is not None
        assert [p["type"] for p in payloads] == ["CAMERA_STATUS_UPDATE"]

    def test_no_broadcast_when_nothing_changed(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        camera = make_camera(
            session,
            name="Steady Cam",
            channel_id=101,
            connection_status="Connected",
            ai_status="Active",
        )
        report = {
            "camera_id": camera.camera_id,
            "connection_status": "Connected",
            "ai_status": "Active",
        }
        client.post(
            "/api/internal/heartbeat",
            headers=internal_headers(),
            json={
                "engine_id": "adas-ai-1",
                "sent_at": "2026-07-12T10:30:05.120+00:00",
                "cameras": [report],
            },
        )

        payloads = _capture_broadcasts(client, monkeypatch)
        resp = client.post(
            "/api/internal/heartbeat",
            headers=internal_headers(),
            json={
                "engine_id": "adas-ai-1",
                "sent_at": "2026-07-12T10:30:08.120+00:00",
                "cameras": [report],
            },
        )
        assert resp.status_code == 200
        assert payloads == []

    def test_unknown_camera_id_ignored_not_an_error(
        self, client: TestClient, session: Session
    ):
        resp = client.post(
            "/api/internal/heartbeat",
            headers=internal_headers(),
            json={
                "engine_id": "adas-ai-1",
                "sent_at": "2026-07-12T10:30:05.120+00:00",
                "cameras": [
                    {
                        "camera_id": 999999,
                        "connection_status": "Connected",
                        "ai_status": "Active",
                    }
                ],
            },
        )
        assert resp.status_code == 200

    def test_snapshot_only_includes_active_cameras(
        self, client: TestClient, session: Session
    ):
        active_cam = make_camera(session, name="HB Active Cam", channel_id=102)
        deleted_cam = make_camera(
            session, name="HB Deleted Cam", channel_id=103, is_active=False
        )

        resp = client.post(
            "/api/internal/heartbeat",
            headers=internal_headers(),
            json={
                "engine_id": "adas-ai-1",
                "sent_at": "2026-07-12T10:30:05.120+00:00",
                "cameras": [],
            },
        )
        assert resp.status_code == 200
        ids = {c["camera_id"] for c in resp.json()["cameras"]}
        assert active_cam.camera_id in ids
        assert deleted_cam.camera_id not in ids

    @pytest.mark.parametrize("measured_fps", [-1, 1e9])
    def test_rejects_absurd_or_negative_fps(
        self, client: TestClient, session: Session, measured_fps: float
    ):
        camera = make_camera(session, name="Absurd FPS Cam", channel_id=104)
        resp = client.post(
            "/api/internal/heartbeat",
            headers=internal_headers(),
            json={
                "engine_id": "adas-ai-1",
                "sent_at": "2026-07-12T10:30:05.120+00:00",
                "cameras": [
                    {
                        "camera_id": camera.camera_id,
                        "connection_status": "Connected",
                        "ai_status": "Active",
                        "measured_fps": measured_fps,
                    }
                ],
            },
        )
        assert resp.status_code == 422

    def test_error_message_is_redacted_before_storage(
        self, client: TestClient, session: Session
    ):
        """Edge case 4.18 — a credential-bearing URL in an AI error message
        must be redacted before it's ever stored."""
        camera = make_camera(session, name="Leak Cam", channel_id=105)
        leaky = "connection failed: rtsp://opuser:sekret@10.0.0.5:554/x"
        resp = client.post(
            "/api/internal/heartbeat",
            headers=internal_headers(),
            json={
                "engine_id": "adas-ai-1",
                "sent_at": "2026-07-12T10:30:05.120+00:00",
                "cameras": [
                    {
                        "camera_id": camera.camera_id,
                        "connection_status": "Disconnected",
                        "ai_status": "Inactive",
                        "error_code": "RTSP_AUTH_FAILED",
                        "error_message": leaky,
                    }
                ],
            },
        )
        assert resp.status_code == 200
        session.refresh(camera)
        assert "sekret" not in (camera.last_error_message or "")

    def test_rtsp_url_covered_by_generic_credential_redaction(self):
        leaky = "rtsp://opuser:sekret@10.0.0.5:554/x"
        assert "sekret" not in redact_text(leaky)
