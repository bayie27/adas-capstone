"""
Tests for /api/alerts.
Covers: list/filtering, CSV export, detail view, and alert state transitions.
"""

import asyncio
import csv
from datetime import UTC, datetime, timedelta
from io import StringIO

import app.api.routes.alerts as alert_routes
import app.core.db as db_module
import pytest
from app.models import AIStatus, DetectionLog, DetectionStatus
from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import auth_headers, make_camera, make_operator


def operator_with_headers(
    client: TestClient,
    session: Session,
    *,
    username: str = "operator",
    password: str = "Operator123",
):
    operator = make_operator(session, username=username, password=password)
    headers = auth_headers(client, username, password)
    return operator, headers


def make_alert(
    session: Session,
    camera,
    *,
    detected_at: datetime | None = None,
    status: DetectionStatus = DetectionStatus.UNVERIFIED,
    confidence_score: float = 0.95,
    snapshot_path: str | None = None,
    verified_by_id: int | None = None,
    verified_at: datetime | None = None,
    closed_by_id: int | None = None,
    closed_at: datetime | None = None,
) -> DetectionLog:
    assert camera.camera_id is not None
    detected_at = detected_at or datetime.now(UTC)
    log = DetectionLog(
        camera_id=camera.camera_id,
        detected_at=detected_at,
        snapshot_path=snapshot_path
        or f"cam_{camera.camera_id}_{int(detected_at.timestamp())}.jpg",
        confidence_score=confidence_score,
        detection_status=status.value,
        verified_by_id=verified_by_id,
        verified_at=verified_at,
        closed_by_id=closed_by_id,
        closed_at=closed_at,
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


class TestGetAlerts:
    def test_operator_gets_paginated_alert_list(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="North Gate", channel_id=1)
        log = make_alert(session, camera)

        resp = client.get("/api/alerts/", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 1
        assert len(body["logs"]) == 1
        assert body["logs"][0]["log_id"] == log.log_id
        assert body["logs"][0]["camera_name"] == "North Gate"
        assert body["logs"][0]["detection_status"] == "Unverified"

    def test_search_by_camera_name(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)
        target_camera = make_camera(session, name="North Gate", channel_id=1)
        other_camera = make_camera(session, name="South Gate", channel_id=2)
        target_log = make_alert(session, target_camera)
        make_alert(session, other_camera)

        resp = client.get("/api/alerts/?search=North", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 1
        assert body["logs"][0]["log_id"] == target_log.log_id
        assert body["logs"][0]["camera_name"] == "North Gate"

    def test_search_by_log_id(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="North Gate", channel_id=1)
        first_log = make_alert(session, camera)
        second_log = make_alert(
            session,
            camera,
            detected_at=datetime.now(UTC) + timedelta(minutes=1),
        )

        resp = client.get(f"/api/alerts/?search={first_log.log_id}", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 1
        assert body["logs"][0]["log_id"] == first_log.log_id
        assert body["logs"][0]["log_id"] != second_log.log_id

    def test_filter_by_status(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Status Cam", channel_id=1)
        make_alert(session, camera, status=DetectionStatus.UNVERIFIED)
        resolved_log = make_alert(
            session,
            camera,
            status=DetectionStatus.RESOLVED,
            detected_at=datetime.now(UTC) + timedelta(minutes=1),
        )

        resp = client.get("/api/alerts/?status=Resolved", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 1
        assert body["logs"][0]["log_id"] == resolved_log.log_id
        assert body["logs"][0]["detection_status"] == "Resolved"

    def test_filter_by_camera_id(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)
        target_camera = make_camera(session, name="Target Cam", channel_id=1)
        other_camera = make_camera(session, name="Other Cam", channel_id=2)
        target_log = make_alert(session, target_camera)
        make_alert(session, other_camera)

        resp = client.get(
            f"/api/alerts/?camera_id={target_camera.camera_id}",
            headers=headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 1
        assert body["logs"][0]["log_id"] == target_log.log_id

    def test_filter_by_user_id_matches_verified_or_closed_by(
        self, client: TestClient, session: Session
    ):
        actor, headers = operator_with_headers(client, session)
        other_operator = make_operator(
            session, username="operator2", password="Operator223"
        )
        camera = make_camera(session, name="User Filter Cam", channel_id=1)

        verified_log = make_alert(
            session,
            camera,
            status=DetectionStatus.ONGOING,
            verified_by_id=actor.user_id,
            verified_at=datetime.now(UTC),
        )
        closed_log = make_alert(
            session,
            camera,
            status=DetectionStatus.DISMISSED,
            detected_at=datetime.now(UTC) + timedelta(minutes=1),
            closed_by_id=actor.user_id,
            closed_at=datetime.now(UTC),
        )
        make_alert(
            session,
            camera,
            status=DetectionStatus.ONGOING,
            detected_at=datetime.now(UTC) + timedelta(minutes=2),
            verified_by_id=other_operator.user_id,
            verified_at=datetime.now(UTC),
        )

        resp = client.get(f"/api/alerts/?user_id={actor.user_id}", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        logs_by_id = {log["log_id"]: log for log in body["logs"]}
        assert body["total_filtered"] == 2
        assert set(logs_by_id) == {verified_log.log_id, closed_log.log_id}
        assert logs_by_id[verified_log.log_id]["verified_by_name"] == "Test Operator"
        assert logs_by_id[closed_log.log_id]["closed_by_name"] == "Test Operator"

    def test_filter_by_date_range(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Date Cam", channel_id=1)
        early = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        middle = datetime(2026, 1, 2, 9, 0, tzinfo=UTC)
        late = datetime(2026, 1, 3, 9, 0, tzinfo=UTC)
        make_alert(session, camera, detected_at=early)
        target_log = make_alert(session, camera, detected_at=middle)
        make_alert(session, camera, detected_at=late)

        resp = client.get(
            "/api/alerts/?start_date=2026-01-02T00:00:00Z&end_date=2026-01-02T23:59:59Z",
            headers=headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 1
        assert body["logs"][0]["log_id"] == target_log.log_id

    def test_pagination_limit_and_offset(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Paginate Cam", channel_id=1)
        oldest = make_alert(
            session,
            camera,
            detected_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        )
        middle = make_alert(
            session,
            camera,
            detected_at=datetime(2026, 1, 2, 9, 0, tzinfo=UTC),
        )
        newest = make_alert(
            session,
            camera,
            detected_at=datetime(2026, 1, 3, 9, 0, tzinfo=UTC),
        )

        resp = client.get("/api/alerts/?limit=1&offset=1", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 3
        assert len(body["logs"]) == 1
        assert body["logs"][0]["log_id"] == middle.log_id
        assert body["logs"][0]["log_id"] not in {newest.log_id, oldest.log_id}

    def test_invalid_date_range_returns_422(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)

        resp = client.get(
            "/api/alerts/?start_date=2026-01-03T00:00:00Z&end_date=2026-01-02T00:00:00Z",
            headers=headers,
        )

        assert resp.status_code == 422

    def test_invalid_camera_id_returns_422(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)

        resp = client.get("/api/alerts/?camera_id=0", headers=headers)

        assert resp.status_code == 422

    def test_invalid_user_id_returns_422(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)

        resp = client.get("/api/alerts/?user_id=0", headers=headers)

        assert resp.status_code == 422

    def test_combined_filters_narrow_results(
        self, client: TestClient, session: Session
    ):
        actor, headers = operator_with_headers(client, session)
        target_camera = make_camera(session, name="North Gate", channel_id=1)
        other_camera = make_camera(session, name="South Gate", channel_id=2)

        target_log = make_alert(
            session,
            target_camera,
            status=DetectionStatus.ONGOING,
            verified_by_id=actor.user_id,
            verified_at=datetime.now(UTC),
        )
        make_alert(
            session,
            target_camera,
            status=DetectionStatus.UNVERIFIED,
            detected_at=datetime.now(UTC) + timedelta(minutes=1),
        )
        make_alert(
            session,
            other_camera,
            status=DetectionStatus.ONGOING,
            detected_at=datetime.now(UTC) + timedelta(minutes=2),
            verified_by_id=actor.user_id,
            verified_at=datetime.now(UTC),
        )

        resp = client.get(
            f"/api/alerts/?search=North&status=Ongoing&user_id={actor.user_id}",
            headers=headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 1
        assert body["logs"][0]["log_id"] == target_log.log_id


class TestExportAlerts:
    def test_export_alerts_csv(self, client: TestClient, session: Session):
        operator, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="CSV Cam", channel_id=1)
        log = make_alert(
            session,
            camera,
            status=DetectionStatus.UNVERIFIED,
            confidence_score=0.87,
            snapshot_path="exports/test_snapshot.jpg",
            verified_by_id=operator.user_id,
            verified_at=datetime(2026, 7, 1, 8, 5, tzinfo=UTC),
            closed_by_id=operator.user_id,
            closed_at=datetime(2026, 7, 1, 8, 10, tzinfo=UTC),
        )

        resp = client.get("/api/alerts/export?status=Unverified", headers=headers)

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "adas_incident_export.csv" in resp.headers["content-disposition"]

        rows = list(csv.reader(StringIO(resp.text)))
        assert rows[0] == [
            "Log ID",
            "Detected At",
            "Camera ID",
            "Camera Name",
            "Status",
            "Confidence",
            "Snapshot URL",
            "Verified By ID",
            "Verified By Name",
            "Verified At",
            "Closed By ID",
            "Closed By Name",
            "Closed At",
        ]
        assert rows[1][0] == str(log.log_id)
        assert rows[1][3] == "CSV Cam"
        assert rows[1][4] == "Unverified"
        assert rows[1][5] == "87.0%"
        assert rows[1][6] == "http://testserver/snapshots/exports/test_snapshot.jpg"
        assert rows[1][7] == str(operator.user_id)
        assert rows[1][8] == "Test Operator"
        assert rows[1][10] == str(operator.user_id)
        assert rows[1][11] == "Test Operator"


class TestGetAlertDetails:
    def test_get_alert_details_success(self, client: TestClient, session: Session):
        operator, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Detail Cam", channel_id=1)
        log = make_alert(
            session,
            camera,
            status=DetectionStatus.RESOLVED,
            verified_by_id=operator.user_id,
            verified_at=datetime(2026, 7, 2, 8, 5, tzinfo=UTC),
            closed_by_id=operator.user_id,
            closed_at=datetime(2026, 7, 2, 8, 10, tzinfo=UTC),
        )

        resp = client.get(f"/api/alerts/{log.log_id}", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["log_id"] == log.log_id
        assert body["camera_name"] == "Detail Cam"
        assert body["verified_by_name"] == "Test Operator"
        assert body["closed_by_name"] == "Test Operator"
        assert body["snapshot_path"] == log.snapshot_path

    def test_get_alert_details_404(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)

        resp = client.get("/api/alerts/99999", headers=headers)

        assert resp.status_code == 404


class TestAlertTransitions:
    def test_confirm_unverified_alert(self, client: TestClient, session: Session):
        operator, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Confirm Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)

        resp = client.post(f"/api/alerts/{log.log_id}/confirm", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["detection_status"] == "Ongoing"
        assert body["verified_by_id"] == operator.user_id
        assert body["verified_by_name"] == "Test Operator"
        assert body["verified_at"] is not None

        session.refresh(log)
        assert log.detection_status == DetectionStatus.ONGOING
        assert log.verified_by_id == operator.user_id
        assert log.verified_at is not None

    def test_confirm_rejects_non_unverified_alert(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Reject Confirm Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.ONGOING)

        resp = client.post(f"/api/alerts/{log.log_id}/confirm", headers=headers)

        assert resp.status_code == 400

    def test_confirm_missing_alert_returns_400(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session)

        resp = client.post("/api/alerts/99999/confirm", headers=headers)

        assert resp.status_code == 400

    def test_dismiss_unverified_alert(self, client: TestClient, session: Session):
        operator, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Dismiss Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)

        resp = client.post(f"/api/alerts/{log.log_id}/dismiss", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["detection_status"] == "Dismissed"
        assert body["closed_by_id"] == operator.user_id
        assert body["closed_by_name"] == "Test Operator"
        assert body["closed_at"] is not None

        session.refresh(log)
        assert log.detection_status == DetectionStatus.DISMISSED
        assert log.closed_by_id == operator.user_id
        assert log.closed_at is not None

    def test_dismiss_ongoing_alert(self, client: TestClient, session: Session):
        operator, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Dismiss Ongoing Cam", channel_id=1)
        log = make_alert(
            session,
            camera,
            status=DetectionStatus.ONGOING,
            verified_by_id=operator.user_id,
            verified_at=datetime.now(UTC),
        )

        resp = client.post(f"/api/alerts/{log.log_id}/dismiss", headers=headers)

        assert resp.status_code == 200
        assert resp.json()["detection_status"] == "Dismissed"

        session.refresh(log)
        assert log.detection_status == DetectionStatus.DISMISSED

    def test_dismiss_rejects_resolved_alert(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Reject Dismiss Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.RESOLVED)

        resp = client.post(f"/api/alerts/{log.log_id}/dismiss", headers=headers)

        assert resp.status_code == 400

    def test_dismiss_missing_alert_returns_400(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session)

        resp = client.post("/api/alerts/99999/dismiss", headers=headers)

        assert resp.status_code == 400

    def test_resolve_ongoing_alert(self, client: TestClient, session: Session):
        operator, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Resolve Cam", channel_id=1)
        log = make_alert(
            session,
            camera,
            status=DetectionStatus.ONGOING,
            verified_by_id=operator.user_id,
            verified_at=datetime.now(UTC),
        )

        resp = client.post(f"/api/alerts/{log.log_id}/resolve", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["detection_status"] == "Resolved"
        assert body["closed_by_id"] == operator.user_id
        assert body["closed_by_name"] == "Test Operator"
        assert body["closed_at"] is not None

        session.refresh(log)
        assert log.detection_status == DetectionStatus.RESOLVED
        assert log.closed_by_id == operator.user_id
        assert log.closed_at is not None

    def test_resolve_rejects_non_ongoing_alert(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Reject Resolve Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)

        resp = client.post(f"/api/alerts/{log.log_id}/resolve", headers=headers)

        assert resp.status_code == 400

    def test_resolve_missing_alert_returns_400(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session)

        resp = client.post("/api/alerts/99999/resolve", headers=headers)

        assert resp.status_code == 400


class TestAlertCameraStatusSideEffects:
    def test_confirm_keeps_camera_paused(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session, username="pausecheck")
        camera = make_camera(
            session,
            name="Paused Confirm Cam",
            channel_id=101,
            ai_status=AIStatus.PAUSED.value,
        )
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)

        resp = client.post(f"/api/alerts/{log.log_id}/confirm", headers=headers)

        assert resp.status_code == 200
        session.refresh(camera)
        assert camera.ai_status == AIStatus.PAUSED.value

    def test_dismiss_unverified_keeps_camera_paused_and_schedules_cooldown(
        self,
        client: TestClient,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        scheduled: list[str] = []

        def fake_create_task(coro):
            scheduled.append(coro.cr_code.co_name)
            coro.close()
            return object()

        monkeypatch.setattr(alert_routes.asyncio, "create_task", fake_create_task)

        _, headers = operator_with_headers(client, session, username="dismissu")
        camera = make_camera(
            session,
            name="Cooldown Dispatch Cam",
            channel_id=102,
            ai_status=AIStatus.PAUSED.value,
        )
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)

        resp = client.post(f"/api/alerts/{log.log_id}/dismiss", headers=headers)

        assert resp.status_code == 200
        session.refresh(camera)
        assert camera.ai_status == AIStatus.PAUSED.value
        assert scheduled == ["_resume_camera_after_cooldown"]

    def test_dismiss_ongoing_reactivates_enabled_camera_and_broadcasts(
        self,
        client: TestClient,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        payloads: list[dict] = []

        async def fake_broadcast(payload: dict) -> None:
            payloads.append(payload)

        monkeypatch.setattr(alert_routes.manager, "broadcast_alert", fake_broadcast)

        operator, headers = operator_with_headers(client, session, username="dismisso")
        camera = make_camera(
            session,
            name="Dismiss Ongoing Status Cam",
            channel_id=103,
            ai_status=AIStatus.PAUSED.value,
        )
        log = make_alert(
            session,
            camera,
            status=DetectionStatus.ONGOING,
            verified_by_id=operator.user_id,
            verified_at=datetime.now(UTC),
        )

        resp = client.post(f"/api/alerts/{log.log_id}/dismiss", headers=headers)

        assert resp.status_code == 200
        session.refresh(camera)
        assert camera.ai_status == AIStatus.ACTIVE.value
        assert payloads == [
            {
                "type": "CAMERA_STATUS_UPDATE",
                "camera_id": camera.camera_id,
                "connection_status": camera.connection_status,
                "ai_status": AIStatus.ACTIVE.value,
            },
            {
                "type": "ALERT_STATUS_UPDATE",
                "log_id": log.log_id,
                "detection_status": DetectionStatus.DISMISSED.value,
            },
        ]

    def test_dismiss_ongoing_does_not_reactivate_disabled_camera(
        self,
        client: TestClient,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        payloads: list[dict] = []

        async def fake_broadcast(payload: dict) -> None:
            payloads.append(payload)

        monkeypatch.setattr(alert_routes.manager, "broadcast_alert", fake_broadcast)

        operator, headers = operator_with_headers(
            client, session, username="dismissdisabled"
        )
        camera = make_camera(
            session,
            name="Disabled Dismiss Cam",
            channel_id=104,
            ai_status=AIStatus.PAUSED.value,
            is_enabled=False,
        )
        log = make_alert(
            session,
            camera,
            status=DetectionStatus.ONGOING,
            verified_by_id=operator.user_id,
            verified_at=datetime.now(UTC),
        )

        resp = client.post(f"/api/alerts/{log.log_id}/dismiss", headers=headers)

        assert resp.status_code == 200
        session.refresh(camera)
        assert camera.ai_status == AIStatus.PAUSED.value
        assert payloads == [
            {
                "type": "ALERT_STATUS_UPDATE",
                "log_id": log.log_id,
                "detection_status": DetectionStatus.DISMISSED.value,
            },
        ]

    def test_resolve_ongoing_reactivates_enabled_camera_and_broadcasts(
        self,
        client: TestClient,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        payloads: list[dict] = []

        async def fake_broadcast(payload: dict) -> None:
            payloads.append(payload)

        monkeypatch.setattr(alert_routes.manager, "broadcast_alert", fake_broadcast)

        operator, headers = operator_with_headers(
            client, session, username="resolveactive"
        )
        camera = make_camera(
            session,
            name="Resolve Status Cam",
            channel_id=105,
            ai_status=AIStatus.PAUSED.value,
        )
        log = make_alert(
            session,
            camera,
            status=DetectionStatus.ONGOING,
            verified_by_id=operator.user_id,
            verified_at=datetime.now(UTC),
        )

        resp = client.post(f"/api/alerts/{log.log_id}/resolve", headers=headers)

        assert resp.status_code == 200
        session.refresh(camera)
        assert camera.ai_status == AIStatus.ACTIVE.value
        assert payloads == [
            {
                "type": "CAMERA_STATUS_UPDATE",
                "camera_id": camera.camera_id,
                "connection_status": camera.connection_status,
                "ai_status": AIStatus.ACTIVE.value,
            },
            {
                "type": "ALERT_STATUS_UPDATE",
                "log_id": log.log_id,
                "detection_status": DetectionStatus.RESOLVED.value,
            },
        ]

    def test_resolve_ongoing_does_not_reactivate_disabled_camera(
        self,
        client: TestClient,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        payloads: list[dict] = []

        async def fake_broadcast(payload: dict) -> None:
            payloads.append(payload)

        monkeypatch.setattr(alert_routes.manager, "broadcast_alert", fake_broadcast)

        operator, headers = operator_with_headers(
            client, session, username="resolvedisabled"
        )
        camera = make_camera(
            session,
            name="Disabled Resolve Cam",
            channel_id=106,
            ai_status=AIStatus.PAUSED.value,
            is_enabled=False,
        )
        log = make_alert(
            session,
            camera,
            status=DetectionStatus.ONGOING,
            verified_by_id=operator.user_id,
            verified_at=datetime.now(UTC),
        )

        resp = client.post(f"/api/alerts/{log.log_id}/resolve", headers=headers)

        assert resp.status_code == 200
        session.refresh(camera)
        assert camera.ai_status == AIStatus.PAUSED.value
        assert payloads == [
            {
                "type": "ALERT_STATUS_UPDATE",
                "log_id": log.log_id,
                "detection_status": DetectionStatus.RESOLVED.value,
            },
        ]

    def test_resume_camera_after_cooldown_reactivates_and_broadcasts(
        self,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        slept: list[int] = []
        broadcasted: list[tuple[int, str]] = []

        async def fake_sleep(seconds: int) -> None:
            slept.append(seconds)

        async def fake_broadcast(camera) -> None:
            broadcasted.append((camera.camera_id, camera.ai_status))

        monkeypatch.setattr(db_module, "engine", session.get_bind())
        monkeypatch.setattr(alert_routes.asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(alert_routes, "_broadcast_camera_status", fake_broadcast)

        camera = make_camera(
            session,
            name="Resume Helper Cam",
            channel_id=107,
            ai_status=AIStatus.PAUSED.value,
        )

        asyncio.run(alert_routes._resume_camera_after_cooldown(camera.camera_id))

        session.refresh(camera)
        assert slept == [60]
        assert camera.ai_status == AIStatus.ACTIVE.value
        assert broadcasted == [(camera.camera_id, AIStatus.ACTIVE.value)]

    @pytest.mark.parametrize(
        ("is_enabled", "is_active"),
        [
            (False, True),
            (True, False),
        ],
    )
    def test_resume_camera_after_cooldown_skips_unavailable_camera(
        self,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
        is_enabled: bool,
        is_active: bool,
    ):
        slept: list[int] = []
        broadcasted: list[tuple[int, str]] = []

        async def fake_sleep(seconds: int) -> None:
            slept.append(seconds)

        async def fake_broadcast(camera) -> None:
            broadcasted.append((camera.camera_id, camera.ai_status))

        monkeypatch.setattr(db_module, "engine", session.get_bind())
        monkeypatch.setattr(alert_routes.asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(alert_routes, "_broadcast_camera_status", fake_broadcast)

        camera = make_camera(
            session,
            name=f"Skipped Resume Cam {is_enabled}-{is_active}",
            channel_id=108 if is_enabled else 109,
            ai_status=AIStatus.PAUSED.value,
            is_enabled=is_enabled,
            is_active=is_active,
        )

        asyncio.run(alert_routes._resume_camera_after_cooldown(camera.camera_id))

        session.refresh(camera)
        assert slept == [60]
        assert camera.ai_status == AIStatus.PAUSED.value
        assert broadcasted == []
