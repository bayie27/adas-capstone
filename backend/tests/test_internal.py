"""
Tests for /api/internal.
Covers AI-engine v2 idempotent alert ingestion, the v2 heartbeat, and
internal auth. The v1 poll/PATCH routes were removed by the A3 audit pack
(be_audit/A3_ai_seam.md, F3) — no caller since PR #67.
"""

import logging
import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import Settings, settings
from app.core.redaction import redact_text
from app.main import create_app
from app.models import AIStatus, Camera, ConnectionStatus, DetectionLog, DetectionStatus
from app.schemas.events import EventEnvelope
from app.services.cameras import recompute_desired_state
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import (
    auth_headers,
    internal_headers,
    make_camera,
    make_detection,
    make_operator,
)


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

    @pytest.mark.parametrize(
        ("is_enabled", "is_active"),
        [
            (False, True),
            (True, False),
        ],
    )
    def test_v2_rejects_disabled_or_inactive_camera(
        self,
        client: TestClient,
        session: Session,
        is_enabled: bool,
        is_active: bool,
    ):
        camera = make_camera(
            session,
            name=f"Rejected V2 Cam {is_enabled}-{is_active}",
            channel_id=39 if is_enabled else 40,
            is_enabled=is_enabled,
            is_active=is_active,
        )

        resp = client.post(
            "/api/internal/alert",
            headers=internal_headers(),
            json=self._payload(camera.camera_id),
        )

        assert resp.status_code == 404
        assert "inactive, or disabled" in resp.json()["detail"]
        assert (
            session.exec(
                select(DetectionLog).where(DetectionLog.camera_id == camera.camera_id)
            ).all()
            == []
        )

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
    def _valid_heartbeat_body(self) -> dict:
        return {
            "engine_id": "adas-ai-1",
            "sent_at": datetime.now(UTC).isoformat(),
            "cameras": [],
        }

    def test_internal_routes_require_valid_api_key(self, client: TestClient):
        resp = client.post(
            "/api/internal/heartbeat",
            headers={"x-api-key": "wrong-key"},
            json=self._valid_heartbeat_body(),
        )

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid Internal API Key"

    def test_internal_routes_reject_missing_api_key(self, client: TestClient):
        """Edge case 8.13 — an absent x-api-key header must 401, not 422."""
        resp = client.post("/api/internal/heartbeat", json=self._valid_heartbeat_body())

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid Internal API Key"

    def test_wrong_api_key_is_compared_constant_time(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        """Edge case 8.14 — asserting wall-clock timing is flaky; this
        instead pins the *mechanism*, the same way test_auth.py's
        test_unknown_username_still_runs_a_real_password_verification does
        for 8.8: verify_internal_api_key must go through
        secrets.compare_digest, not a short-circuiting `==`, which a
        future refactor could otherwise introduce without any existing
        test failing."""
        import app.api.dependencies as dependencies_module

        calls = []
        original = dependencies_module.secrets.compare_digest
        monkeypatch.setattr(
            dependencies_module.secrets,
            "compare_digest",
            lambda a, b: (calls.append((a, b)), original(a, b))[1],
        )

        resp = client.post(
            "/api/internal/heartbeat",
            headers={"x-api-key": "wrong-key"},
            json=self._valid_heartbeat_body(),
        )

        assert resp.status_code == 401
        assert calls == [("wrong-key", settings.INTERNAL_API_KEY.get_secret_value())]


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

    def test_self_reported_active_does_not_override_the_hitl_pause(
        self, client: TestClient, session: Session
    ):
        """The HITL guard `TestUpdateCameraStatus.test_rejects_active_override_
        while_alert_is_open` asserted against the now-deleted v1 PATCH route,
        ported here: v2 doesn't reject the engine's self-report (ai_status is
        purely observed state, recorded as-is by apply_observed()), but the
        engine reporting `ai_status=Active` while an incident is open must
        NOT change what the backend tells it to do next — desired_ai_state in
        the returned snapshot must still say Paused."""
        camera = make_camera(
            session,
            name="Rebel Cam",
            channel_id=106,
            ai_status=AIStatus.PAUSED.value,
            connection_status=ConnectionStatus.CONNECTED.value,
            desired_ai_state="Paused",
            desired_state_reason="incident",
        )
        make_detection(session, camera, status=DetectionStatus.UNVERIFIED)

        resp = client.post(
            "/api/internal/heartbeat",
            headers=internal_headers(),
            json={
                "engine_id": "adas-ai-1",
                "sent_at": datetime.now(UTC).isoformat(),
                "cameras": [
                    {
                        "camera_id": camera.camera_id,
                        "connection_status": ConnectionStatus.CONNECTED.value,
                        "ai_status": AIStatus.ACTIVE.value,
                    }
                ],
            },
        )

        assert resp.status_code == 200
        row = next(
            c for c in resp.json()["cameras"] if c["camera_id"] == camera.camera_id
        )
        assert row["desired_ai_state"] == "Paused"

        session.refresh(camera)
        # The observed report is still recorded as-is (D-003: apply_observed
        # is a pure recorder, not a gate) — it's the desired-state snapshot
        # that keeps the engine honest, not a rejection of this request.
        assert camera.ai_status == AIStatus.ACTIVE.value
        assert camera.desired_ai_state == "Paused"

    def test_disabled_camera_report_is_accepted_not_rejected(
        self, client: TestClient, session: Session
    ):
        """The v1 PATCH route 404'd on a disabled camera
        (`TestUpdateCameraStatus.test_rejects_disabled_or_inactive_camera`).
        v2 has no such per-report rejection — a disabled camera's observed
        state is still recorded, and the reconciliation snapshot tells the
        engine to stop it (is_enabled: false), matching P10's documented
        divergence from the legacy poll (be_plan/15_PKG_ai_engine_integration.md
        Step 4)."""
        camera = make_camera(
            session,
            name="Disabled HB Cam",
            channel_id=107,
            is_enabled=False,
        )

        resp = client.post(
            "/api/internal/heartbeat",
            headers=internal_headers(),
            json={
                "engine_id": "adas-ai-1",
                "sent_at": datetime.now(UTC).isoformat(),
                "cameras": [
                    {
                        "camera_id": camera.camera_id,
                        "connection_status": ConnectionStatus.CONNECTED.value,
                        "ai_status": AIStatus.ACTIVE.value,
                    }
                ],
            },
        )

        assert resp.status_code == 200
        session.refresh(camera)
        assert camera.connection_status == ConnectionStatus.CONNECTED.value

        row = next(
            c for c in resp.json()["cameras"] if c["camera_id"] == camera.camera_id
        )
        assert row["is_enabled"] is False
        assert row["desired_ai_state"] == "Inactive"

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

    def test_overlong_engine_id_is_422(self, client: TestClient, session: Session):
        resp = client.post(
            "/api/internal/heartbeat",
            headers=internal_headers(),
            json={
                "engine_id": "x" * 129,
                "sent_at": "2026-07-12T10:30:05.120+00:00",
                "cameras": [],
            },
        )
        assert resp.status_code == 422

    def test_null_byte_in_engine_id_is_422(self, client: TestClient, session: Session):
        resp = client.post(
            "/api/internal/heartbeat",
            headers=internal_headers(),
            json={
                "engine_id": "adas-ai-\x00-1",
                "sent_at": "2026-07-12T10:30:05.120+00:00",
                "cameras": [],
            },
        )
        assert resp.status_code == 422

    def test_overlong_cameras_list_is_422(self, client: TestClient, session: Session):
        cameras = [
            {
                "camera_id": i,
                "connection_status": "Connected",
                "ai_status": "Active",
            }
            for i in range(1, 2002)
        ]
        resp = client.post(
            "/api/internal/heartbeat",
            headers=internal_headers(),
            json={
                "engine_id": "adas-ai-1",
                "sent_at": "2026-07-12T10:30:05.120+00:00",
                "cameras": cameras,
            },
        )
        assert resp.status_code == 422

    def test_second_engine_id_within_staleness_window_logs_warning(
        self, client: TestClient, session: Session, caplog: pytest.LogCaptureFixture
    ):
        """Edge case 1.18 — two engine instances. A distinct engine_id
        heartbeating within the staleness window must be logged, not
        rejected: rejecting could take down a legitimate failover, and
        arbitrating a lease is deliberately out of scope for the backend
        (be_audit/A3_ai_seam.md F9)."""
        with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
            first = client.post(
                "/api/internal/heartbeat",
                headers=internal_headers(),
                json={
                    "engine_id": "adas-ai-fixture-primary",
                    "sent_at": datetime.now(UTC).isoformat(),
                    "cameras": [],
                },
            )
            assert first.status_code == 200

            second = client.post(
                "/api/internal/heartbeat",
                headers=internal_headers(),
                json={
                    "engine_id": "adas-ai-fixture-secondary",
                    "sent_at": datetime.now(UTC).isoformat(),
                    "cameras": [],
                },
            )
            assert second.status_code == 200

        assert "adas-ai-fixture-primary" in caplog.text
        assert "adas-ai-fixture-secondary" in caplog.text
        assert "two engine instances" in caplog.text

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


class TestConcurrentDisableRace:
    """Edge case 1.7 (be_audit/A5_edge_cases.md) — an AI event arriving
    while an operator disables that camera. Needs genuinely parallel
    requests, which the shared-session `client` fixture used everywhere
    else in this file cannot provide (every request would serialize
    through one Python-level `Session` object). Instead this builds its own
    app on a real file-backed database with the ordinary, non-overridden
    `get_session` dependency, so each thread's request gets its own
    session against the same engine — the same shape production traffic
    has."""

    def _make_client(self, tmp_path) -> TestClient:
        app_settings = Settings(
            _env_file=None,
            SECRET_KEY="test-secret-key-not-for-production-use",
            INTERNAL_API_KEY="test-internal-api-key-not-for-production",
            DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
            DATABASE_URL=f"sqlite:///{tmp_path / 'race.db'}",
            SCHEDULER_ENABLED=False,
            SNAPSHOT_ROOT=tmp_path / "snapshots",
        )
        app = create_app(app_settings)
        return TestClient(app)

    def test_ai_alert_racing_operator_disable_never_500s_and_stays_consistent(
        self, tmp_path
    ):
        with self._make_client(tmp_path) as client:
            with Session(client.app.state.engine) as session:
                make_operator(session, username="racer", password="Operator123")
            headers = auth_headers(client, "racer", "Operator123")

            outcomes: set[tuple[int, int]] = set()

            for attempt in range(25):
                with Session(client.app.state.engine) as session:
                    camera = make_camera(
                        session, name=f"Race Cam {attempt}", channel_id=1000 + attempt
                    )
                    camera_id = camera.camera_id

                alert_payload = {
                    "source_event_id": str(uuid.uuid4()),
                    "camera_id": camera_id,
                    "detected_at": datetime.now(UTC).isoformat(),
                    "snapshot_key": f"race/{attempt}.jpg",
                    "confidence_score": 0.9,
                }

                barrier = threading.Barrier(2)
                results: dict[str, object] = {}
                errors: list[BaseException] = []

                def send_alert(
                    barrier=barrier,
                    results=results,
                    errors=errors,
                    alert_payload=alert_payload,
                ):
                    try:
                        barrier.wait(timeout=5)
                        results["alert"] = client.post(
                            "/api/internal/alert",
                            headers=internal_headers(),
                            json=alert_payload,
                        )
                    except BaseException as exc:  # noqa: BLE001
                        errors.append(exc)

                def send_disable(
                    barrier=barrier,
                    results=results,
                    errors=errors,
                    camera_id=camera_id,
                ):
                    try:
                        barrier.wait(timeout=5)
                        results["disable"] = client.patch(
                            f"/api/cameras/{camera_id}",
                            headers=headers,
                            json={"is_enabled": False},
                        )
                    except BaseException as exc:  # noqa: BLE001
                        errors.append(exc)

                t_alert = threading.Thread(target=send_alert)
                t_disable = threading.Thread(target=send_disable)
                t_alert.start()
                t_disable.start()
                t_alert.join(timeout=10)
                t_disable.join(timeout=10)

                assert not errors, f"attempt {attempt}: {errors}"
                alert_resp = results["alert"]
                disable_resp = results["disable"]

                # No 500s, no unhandled OperationalError leaking as anything
                # but the documented 503.
                assert alert_resp.status_code in (201, 404, 503), (
                    attempt,
                    alert_resp.status_code,
                    alert_resp.text,
                )
                assert disable_resp.status_code in (200, 503), (
                    attempt,
                    disable_resp.status_code,
                    disable_resp.text,
                )
                outcomes.add((alert_resp.status_code, disable_resp.status_code))

                if alert_resp.status_code != 201 or disable_resp.status_code != 200:
                    # A 503 (lock timeout) is a legitimate, already-covered
                    # outcome (edge case 6.1) — nothing more to check for
                    # this attempt.
                    continue

                # Both succeeded — assert desired-state self-consistency and
                # that any created incident is not stranded.
                with Session(client.app.state.engine) as session:
                    db_camera = session.get(Camera, camera_id)
                    assert db_camera is not None
                    has_open_incident = (
                        session.exec(
                            select(DetectionLog).where(
                                DetectionLog.camera_id == camera_id,
                                DetectionLog.detection_status.in_(
                                    [
                                        DetectionStatus.UNVERIFIED.value,
                                        DetectionStatus.ONGOING.value,
                                    ]
                                ),
                            )
                        ).first()
                        is not None
                    )

                    # recompute_desired_state is the single source of truth
                    # for what desired state *should* be given the camera's
                    # current facts — replay it and compare, rather than
                    # hand-deriving the invariant here.
                    expected = Camera(
                        camera_name=db_camera.camera_name,
                        channel_id=db_camera.channel_id,
                        is_active=db_camera.is_active,
                        is_enabled=db_camera.is_enabled,
                        cooldown_until=db_camera.cooldown_until,
                    )
                    recompute_desired_state(
                        expected,
                        has_open_incident=has_open_incident,
                        now=datetime.now(UTC),
                    )
                    assert db_camera.desired_ai_state == expected.desired_ai_state, (
                        attempt,
                        db_camera.is_enabled,
                        has_open_incident,
                        db_camera.desired_ai_state,
                        expected.desired_ai_state,
                    )
                    assert (
                        db_camera.desired_state_reason == expected.desired_state_reason
                    )

                    if has_open_incident:
                        # An incident on a now-disabled camera must still be
                        # resolvable by an operator, not stranded.
                        log = session.exec(
                            select(DetectionLog).where(
                                DetectionLog.camera_id == camera_id
                            )
                        ).first()
                        assert log is not None
                        detail_resp = client.get(
                            f"/api/alerts/{log.log_id}", headers=headers
                        )
                        assert detail_resp.status_code == 200
                        confirm_resp = client.post(
                            f"/api/alerts/{log.log_id}/confirm", headers=headers
                        )
                        assert confirm_resp.status_code == 200

            # Documented per be_audit/A5_edge_cases.md: both outcomes are
            # acceptable, and this assertion is the record of which one(s)
            # this suite actually observes. If this ever starts failing
            # because a third status pair shows up, that is new information
            # worth looking at, not a flake to silence.
            assert outcomes <= {
                (201, 200),
                (404, 200),
                (201, 503),
                (404, 503),
                (503, 200),
                (503, 503),
            }


class TestConcurrentHeartbeatRace:
    """Edge case 1.18 (be_audit/00_FINDINGS.md F24) — two engine instances
    heartbeating the same camera concurrently. The same real-file-DB,
    real-thread harness as TestConcurrentDisableRace, because F21's bug
    hunt for edge case 1.7 showed sequential/deterministic simulation
    misses real SQLAlchemy dirty-tracking races — deterministic
    reproduction (be_audit/00_FINDINGS.md F24 writeup) found the identical
    mechanism here before it was fixed in apply_observed(): whichever
    heartbeat commits last must leave the row matching its own report in
    full, never a mixed-provenance row with some fields surviving from the
    other engine's concurrently committed report."""

    def _make_client(self, tmp_path) -> TestClient:
        app_settings = Settings(
            _env_file=None,
            SECRET_KEY="test-secret-key-not-for-production-use",
            INTERNAL_API_KEY="test-internal-api-key-not-for-production",
            DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
            DATABASE_URL=f"sqlite:///{tmp_path / 'hbrace.db'}",
            SCHEDULER_ENABLED=False,
            SNAPSHOT_ROOT=tmp_path / "snapshots",
        )
        app = create_app(app_settings)
        return TestClient(app)

    def test_two_engines_heartbeating_the_same_camera_never_corrupt_it(self, tmp_path):
        with self._make_client(tmp_path) as client:
            for attempt in range(25):
                with Session(client.app.state.engine) as session:
                    camera = make_camera(
                        session,
                        name=f"HB Race Cam {attempt}",
                        channel_id=2000 + attempt,
                        connection_status=ConnectionStatus.DISCONNECTED.value,
                        ai_status=AIStatus.INACTIVE.value,
                    )
                    camera_id = camera.camera_id

                # Deliberately varies per attempt so a report can't
                # coincidentally match the *initial* seed state above and
                # mask the bug this test targets.
                report_a = {
                    "camera_id": camera_id,
                    "connection_status": "Reconnecting",
                    "ai_status": "Unresponsive",
                    "measured_fps": 5.0 + attempt,
                    "inference_latency_ms": 90.0 + attempt,
                }
                report_b = {
                    "camera_id": camera_id,
                    "connection_status": "Connected",
                    "ai_status": "Active",
                    "measured_fps": 30.0 + attempt,
                    "inference_latency_ms": 12.0 + attempt,
                }

                barrier = threading.Barrier(2)
                results: dict[str, object] = {}
                errors: list[BaseException] = []

                def send(
                    engine_id,
                    report,
                    barrier=barrier,
                    results=results,
                    errors=errors,
                ):
                    try:
                        barrier.wait(timeout=5)
                        results[engine_id] = client.post(
                            "/api/internal/heartbeat",
                            headers=internal_headers(),
                            json={
                                "engine_id": engine_id,
                                "sent_at": datetime.now(UTC).isoformat(),
                                "cameras": [report],
                            },
                        )
                    except BaseException as exc:  # noqa: BLE001
                        errors.append(exc)

                t_a = threading.Thread(target=send, args=("engine-A", report_a))
                t_b = threading.Thread(target=send, args=("engine-B", report_b))
                t_a.start()
                t_b.start()
                t_a.join(timeout=10)
                t_b.join(timeout=10)

                assert not errors, f"attempt {attempt}: {errors}"
                assert results["engine-A"].status_code == 200
                assert results["engine-B"].status_code == 200

                with Session(client.app.state.engine) as session:
                    db_camera = session.get(Camera, camera_id)
                    observed = (
                        db_camera.connection_status,
                        db_camera.ai_status,
                        db_camera.measured_fps,
                        db_camera.inference_latency_ms,
                    )
                    pure_a = (
                        report_a["connection_status"],
                        report_a["ai_status"],
                        report_a["measured_fps"],
                        report_a["inference_latency_ms"],
                    )
                    pure_b = (
                        report_b["connection_status"],
                        report_b["ai_status"],
                        report_b["measured_fps"],
                        report_b["inference_latency_ms"],
                    )
                    assert observed in (pure_a, pure_b), (
                        attempt,
                        observed,
                        "row is a corrupted mix of both engines' reports",
                    )


class TestConcurrentDuplicateSourceEventId:
    """Edge case 1.6 (be_audit/00_FINDINGS.md F24) — the same
    source_event_id posted twice genuinely concurrently must hit the
    ux_detection_source_event unique-index IntegrityError backstop
    (internal.py's except IntegrityError branch), not just the pre-commit
    SELECT idempotency check, which a sequential test can't tell apart
    from the backstop actually working."""

    def _make_client(self, tmp_path) -> TestClient:
        app_settings = Settings(
            _env_file=None,
            SECRET_KEY="test-secret-key-not-for-production-use",
            INTERNAL_API_KEY="test-internal-api-key-not-for-production",
            DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
            DATABASE_URL=f"sqlite:///{tmp_path / 'duprace.db'}",
            SCHEDULER_ENABLED=False,
            SNAPSHOT_ROOT=tmp_path / "snapshots",
        )
        app = create_app(app_settings)
        return TestClient(app)

    def test_same_source_event_id_posted_by_two_threads_yields_one_row(self, tmp_path):
        with self._make_client(tmp_path) as client:
            for attempt in range(25):
                with Session(client.app.state.engine) as session:
                    camera = make_camera(
                        session,
                        name=f"Dup Race Cam {attempt}",
                        channel_id=3000 + attempt,
                    )
                    camera_id = camera.camera_id

                source_event_id = str(uuid.uuid4())
                payload = {
                    "source_event_id": source_event_id,
                    "camera_id": camera_id,
                    "detected_at": datetime.now(UTC).isoformat(),
                    "snapshot_key": f"duprace/{attempt}.jpg",
                    "confidence_score": 0.9,
                }

                barrier = threading.Barrier(2)
                results: list = []
                errors: list[BaseException] = []
                lock = threading.Lock()

                def send(
                    barrier=barrier,
                    results=results,
                    errors=errors,
                    lock=lock,
                    payload=payload,
                ):
                    try:
                        barrier.wait(timeout=5)
                        resp = client.post(
                            "/api/internal/alert",
                            headers=internal_headers(),
                            json=payload,
                        )
                        with lock:
                            results.append(resp)
                    except BaseException as exc:  # noqa: BLE001
                        errors.append(exc)

                threads = [threading.Thread(target=send) for _ in range(2)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join(timeout=10)

                assert not errors, f"attempt {attempt}: {errors}"
                statuses = sorted(r.status_code for r in results)
                assert statuses == [200, 201], (attempt, statuses)

                with Session(client.app.state.engine) as session:
                    rows = session.exec(
                        select(DetectionLog).where(
                            DetectionLog.source_event_id == source_event_id
                        )
                    ).all()
                    assert len(rows) == 1, (attempt, len(rows))
                    returned_log_ids = {r.json()["log_id"] for r in results}
                    assert returned_log_ids == {rows[0].log_id}
