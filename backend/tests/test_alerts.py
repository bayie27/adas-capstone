"""
Tests for /api/alerts.
Covers: list/filtering, CSV export, detail view, alert state transitions,
snooze, and authenticated snapshot retrieval.
"""

import csv
import uuid
from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from app.core.scheduler import create_scheduler
from app.models import DetectionLog, DetectionStatus
from app.schemas.events import EventEnvelope
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


def make_alert(
    session: Session,
    camera,
    *,
    detected_at: datetime | None = None,
    status: DetectionStatus = DetectionStatus.UNVERIFIED,
    confidence_score: float = 0.95,
    snapshot_key: str | None = None,
    verified_by_id: int | None = None,
    verified_at: datetime | None = None,
    closed_by_id: int | None = None,
    closed_at: datetime | None = None,
    snoozed_at: datetime | None = None,
    snoozed_until: datetime | None = None,
    snoozed_by_id: int | None = None,
) -> DetectionLog:
    assert camera.camera_id is not None
    detected_at = detected_at or datetime.now(UTC)
    log = DetectionLog(
        camera_id=camera.camera_id,
        detected_at=detected_at,
        snapshot_key=snapshot_key
        or f"cam_{camera.camera_id}_{int(detected_at.timestamp())}.jpg",
        confidence_score=confidence_score,
        detection_status=status.value,
        verified_by_id=verified_by_id,
        verified_at=verified_at,
        closed_by_id=closed_by_id,
        closed_at=closed_at,
        snoozed_at=snoozed_at,
        snoozed_until=snoozed_until,
        snoozed_by_id=snoozed_by_id,
        source_event_id=str(uuid.uuid4()),
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
        # Terminal status: a camera may only have one *open* (Unverified/
        # Ongoing) incident at a time (ux_detection_open_camera).
        second_log = make_alert(
            session,
            camera,
            status=DetectionStatus.RESOLVED,
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
        # A different camera: only one open (Unverified/Ongoing) incident is
        # allowed per camera at a time (ux_detection_open_camera), and
        # `verified_log` above already holds that slot on `camera`.
        other_camera = make_camera(session, name="Other User Filter Cam", channel_id=2)
        make_alert(
            session,
            other_camera,
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
        # Only one open (Unverified/Ongoing) incident is allowed per camera
        # at a time (ux_detection_open_camera) — `middle` stays open, the
        # other two are terminal so all three can coexist on one camera.
        make_alert(session, camera, status=DetectionStatus.RESOLVED, detected_at=early)
        target_log = make_alert(session, camera, detected_at=middle)
        make_alert(session, camera, status=DetectionStatus.RESOLVED, detected_at=late)

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
        # Only one open (Unverified/Ongoing) incident is allowed per camera
        # at a time (ux_detection_open_camera) — `middle` stays open, the
        # other two are terminal so all three can coexist on one camera.
        oldest = make_alert(
            session,
            camera,
            status=DetectionStatus.RESOLVED,
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
            status=DetectionStatus.RESOLVED,
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
        # Terminal status: target_log above already holds target_camera's one
        # open-incident slot (ux_detection_open_camera). Status Dismissed
        # also keeps this row excluded from the `status=Ongoing` filter below.
        make_alert(
            session,
            target_camera,
            status=DetectionStatus.DISMISSED,
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
            snapshot_key="exports/test_snapshot.jpg",
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
        # Step 9 — never a filesystem path, only the authorized API route.
        assert "snapshot_key" not in body
        assert body["snapshot_url"] == f"/api/alerts/{log.log_id}/snapshot"
        assert body["created_at"] is not None
        assert body["updated_at"] is not None

    def test_get_alert_details_404(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)

        resp = client.get("/api/alerts/99999", headers=headers)

        assert resp.status_code == 404


class TestAlertSnapshotRoute:
    def test_snapshot_requires_auth(self, client: TestClient):
        resp = client.get("/api/alerts/1/snapshot")
        assert resp.status_code == 401

    def test_snapshot_404_when_log_missing(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)
        resp = client.get("/api/alerts/99999/snapshot", headers=headers)
        assert resp.status_code == 404

    def test_snapshot_404_when_file_missing(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Missing File Cam", channel_id=1)
        log = make_alert(session, camera, snapshot_key="does/not/exist.jpg")

        resp = client.get(f"/api/alerts/{log.log_id}/snapshot", headers=headers)
        assert resp.status_code == 404

    def test_public_snapshots_mount_is_gone(self, client: TestClient):
        resp = client.get("/snapshots/whatever.jpg")
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
        assert body["closed_by_id"] is None

        session.refresh(log)
        assert log.detection_status == DetectionStatus.ONGOING
        assert log.verified_by_id == operator.user_id
        assert log.verified_at is not None
        assert log.closed_by_id is None

    def test_confirm_rejects_non_unverified_alert(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Reject Confirm Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.ONGOING)

        resp = client.post(f"/api/alerts/{log.log_id}/confirm", headers=headers)

        assert resp.status_code == 409
        assert resp.json()["code"] == "CONFLICT_STATE"

    def test_confirm_missing_alert_returns_404(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session)

        resp = client.post("/api/alerts/99999/confirm", headers=headers)

        assert resp.status_code == 404

    def test_dismiss_unverified_alert_stamps_verification_not_closure(
        self, client: TestClient, session: Session
    ):
        """D-002: an immediate dismiss stamps *verification* fields; closure
        fields stay empty. The old code got this backwards."""
        operator, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Dismiss Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)

        resp = client.post(f"/api/alerts/{log.log_id}/dismiss", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["detection_status"] == "Dismissed"
        assert body["verified_by_id"] == operator.user_id
        assert body["verified_by_name"] == "Test Operator"
        assert body["verified_at"] is not None
        assert body["closed_by_id"] is None
        assert body["closed_by_name"] is None
        assert body["closed_at"] is None

        session.refresh(log)
        assert log.detection_status == DetectionStatus.DISMISSED
        assert log.verified_by_id == operator.user_id
        assert log.closed_by_id is None

    def test_dismiss_ongoing_alert_retains_verifier_stamps_closer(
        self, client: TestClient, session: Session
    ):
        verifier = make_operator(session, username="verifier", password="Operator123")
        corrector, headers = operator_with_headers(
            client, session, username="corrector"
        )
        camera = make_camera(session, name="Dismiss Ongoing Cam", channel_id=1)
        log = make_alert(
            session,
            camera,
            status=DetectionStatus.ONGOING,
            verified_by_id=verifier.user_id,
            verified_at=datetime.now(UTC),
        )

        resp = client.post(f"/api/alerts/{log.log_id}/dismiss", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["detection_status"] == "Dismissed"
        assert body["verified_by_id"] == verifier.user_id
        assert body["closed_by_id"] == corrector.user_id

        session.refresh(log)
        assert log.detection_status == DetectionStatus.DISMISSED
        assert log.verified_by_id == verifier.user_id
        assert log.closed_by_id == corrector.user_id

    def test_dismiss_rejects_resolved_alert(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Reject Dismiss Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.RESOLVED)

        resp = client.post(f"/api/alerts/{log.log_id}/dismiss", headers=headers)

        assert resp.status_code == 409
        assert resp.json()["code"] == "CONFLICT_STATE"

    def test_dismiss_missing_alert_returns_404(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session)

        resp = client.post("/api/alerts/99999/dismiss", headers=headers)

        assert resp.status_code == 404

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
        assert body["verified_by_id"] == operator.user_id

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

        assert resp.status_code == 409
        assert resp.json()["code"] == "CONFLICT_STATE"

    def test_resolve_missing_alert_returns_404(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session)

        resp = client.post("/api/alerts/99999/resolve", headers=headers)

        assert resp.status_code == 404

    def test_conflict_body_names_the_winner(self, client: TestClient, session: Session):
        """01_CONTRACTS.md §5.3 — the exact 409 shape the frontend's
        already-handled modal depends on."""
        winner = make_operator(session, username="winner", password="Operator123")
        _, headers = operator_with_headers(client, session, username="loser")
        camera = make_camera(session, name="Conflict Body Cam", channel_id=1)
        log = make_alert(
            session,
            camera,
            status=DetectionStatus.ONGOING,
            verified_by_id=winner.user_id,
            verified_at=datetime.now(UTC),
        )

        resp = client.post(f"/api/alerts/{log.log_id}/confirm", headers=headers)

        assert resp.status_code == 409
        body = resp.json()
        assert body["code"] == "CONFLICT_STATE"
        assert body["current_status"] == "Ongoing"
        assert body["handled_action"] == "ALERT_CONFIRM"
        assert body["handled_by"] == "Test Operator"
        assert body["handled_at"] is not None


class TestStateMachineExhaustiveness:
    """14_EDGE_CASES.md §7 — four statuses, sixteen ordered pairs, four
    legal. Parametrized over every illegal pair including self-transitions."""

    ROUTES = {
        "confirm": DetectionStatus.ONGOING,
        "dismiss": DetectionStatus.DISMISSED,
        "resolve": DetectionStatus.RESOLVED,
    }

    @pytest.mark.parametrize(
        ("route", "starting_status"),
        [
            ("confirm", DetectionStatus.ONGOING),
            ("confirm", DetectionStatus.DISMISSED),
            ("confirm", DetectionStatus.RESOLVED),
            ("dismiss", DetectionStatus.DISMISSED),
            ("dismiss", DetectionStatus.RESOLVED),
            ("resolve", DetectionStatus.UNVERIFIED),
            ("resolve", DetectionStatus.DISMISSED),
            ("resolve", DetectionStatus.RESOLVED),
        ],
    )
    def test_illegal_transition_rejected(
        self,
        client: TestClient,
        session: Session,
        route: str,
        starting_status: DetectionStatus,
    ):
        username = f"sm{route[:3]}{starting_status.value[:3]}".lower()
        _, headers = operator_with_headers(client, session, username=username)
        camera = make_camera(
            session, name=f"SM Cam {route} {starting_status.value}", channel_id=1
        )
        log = make_alert(session, camera, status=starting_status)

        resp = client.post(f"/api/alerts/{log.log_id}/{route}", headers=headers)

        assert resp.status_code == 409
        assert resp.json()["code"] == "CONFLICT_STATE"
        session.refresh(log)
        assert log.detection_status == starting_status.value

    def test_no_route_can_reopen_a_terminal_incident_to_unverified(
        self, client: TestClient
    ):
        """The remaining four illegal pairs (*, Unverified) have no route
        to even attempt them — D-002: terminal states have no reopen path
        and no general-purpose edit or delete API. The absence of a route
        is a requirement, not an omission."""
        openapi = client.get("/openapi.json").json()
        alert_paths = {
            path: methods
            for path, methods in openapi["paths"].items()
            if path.startswith("/api/alerts/{log_id}")
        }
        for path, methods in alert_paths.items():
            for method in methods:
                if method.lower() != "post":
                    continue
                assert path.rsplit("/", 1)[-1] in {
                    "confirm",
                    "dismiss",
                    "resolve",
                    "snooze",
                }, f"unexpected POST route {path} could reopen an incident"


class TestAlertCameraStatusSideEffects:
    def test_confirm_keeps_camera_paused_no_camera_broadcast(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        payloads = _capture_broadcasts(client, monkeypatch)
        _, headers = operator_with_headers(client, session, username="pausecheck")
        camera = make_camera(
            session,
            name="Paused Confirm Cam",
            channel_id=101,
            desired_ai_state="Paused",
            desired_state_reason="incident",
        )
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)

        resp = client.post(f"/api/alerts/{log.log_id}/confirm", headers=headers)

        assert resp.status_code == 200
        session.refresh(camera)
        assert camera.desired_ai_state == "Paused"
        assert camera.desired_state_reason == "incident"
        assert [p["type"] for p in payloads] == ["ALERT_STATUS_UPDATE"]

    def test_dismiss_unverified_starts_cooldown_and_schedules_job(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        payloads = _capture_broadcasts(client, monkeypatch)
        scheduler = create_scheduler()
        monkeypatch.setattr(client.app.state, "scheduler", scheduler)

        _, headers = operator_with_headers(client, session, username="dismissu")
        camera = make_camera(
            session,
            name="Cooldown Dispatch Cam",
            channel_id=102,
            desired_ai_state="Paused",
            desired_state_reason="incident",
        )
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)

        resp = client.post(f"/api/alerts/{log.log_id}/dismiss", headers=headers)

        assert resp.status_code == 200
        session.refresh(camera)
        assert camera.desired_ai_state == "Paused"
        assert camera.desired_state_reason == "cooldown"
        assert camera.cooldown_until is not None

        # Broadcast ordering from Unverified: alert leads, camera follows.
        assert [p["type"] for p in payloads] == [
            "ALERT_STATUS_UPDATE",
            "CAMERA_STATUS_UPDATE",
        ]

        job_ids = {job.id for job in scheduler.get_jobs()}
        assert f"cooldown:{camera.camera_id}" in job_ids

    def test_dismiss_ongoing_reactivates_enabled_camera_and_broadcasts(
        self,
        client: TestClient,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        payloads = _capture_broadcasts(client, monkeypatch)

        operator, headers = operator_with_headers(client, session, username="dismisso")
        camera = make_camera(
            session,
            name="Dismiss Ongoing Status Cam",
            channel_id=103,
            desired_ai_state="Paused",
            desired_state_reason="incident",
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
        assert camera.desired_ai_state == "Active"
        assert camera.desired_state_reason is None
        # Broadcast ordering from Ongoing: camera leads, alert follows.
        assert [p["type"] for p in payloads] == [
            "CAMERA_STATUS_UPDATE",
            "ALERT_STATUS_UPDATE",
        ]
        assert payloads[1]["data"]["log_id"] == log.log_id
        assert (
            payloads[1]["data"]["detection_status"] == DetectionStatus.DISMISSED.value
        )
        assert payloads[1]["data"]["action"] == "ALERT_CORRECTION"

    def test_dismiss_ongoing_does_not_reactivate_disabled_camera(
        self,
        client: TestClient,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        payloads = _capture_broadcasts(client, monkeypatch)

        operator, headers = operator_with_headers(
            client, session, username="dismissdisabled"
        )
        camera = make_camera(
            session,
            name="Disabled Dismiss Cam",
            channel_id=104,
            is_enabled=False,
            desired_ai_state="Inactive",
            desired_state_reason="disabled",
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
        assert camera.desired_ai_state == "Inactive"
        assert camera.desired_state_reason == "disabled"
        assert [p["type"] for p in payloads] == ["ALERT_STATUS_UPDATE"]

    def test_resolve_ongoing_reactivates_enabled_camera_and_broadcasts(
        self,
        client: TestClient,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        payloads = _capture_broadcasts(client, monkeypatch)

        operator, headers = operator_with_headers(
            client, session, username="resolveactive"
        )
        camera = make_camera(
            session,
            name="Resolve Status Cam",
            channel_id=105,
            desired_ai_state="Paused",
            desired_state_reason="incident",
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
        assert camera.desired_ai_state == "Active"
        assert [p["type"] for p in payloads] == [
            "CAMERA_STATUS_UPDATE",
            "ALERT_STATUS_UPDATE",
        ]
        assert payloads[1]["data"]["log_id"] == log.log_id
        assert payloads[1]["data"]["detection_status"] == DetectionStatus.RESOLVED.value
        assert payloads[1]["data"]["action"] == "ALERT_RESOLVE"

    def test_resolve_ongoing_does_not_reactivate_disabled_camera(
        self,
        client: TestClient,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        payloads = _capture_broadcasts(client, monkeypatch)

        operator, headers = operator_with_headers(
            client, session, username="resolvedisabled"
        )
        camera = make_camera(
            session,
            name="Disabled Resolve Cam",
            channel_id=106,
            is_enabled=False,
            desired_ai_state="Inactive",
            desired_state_reason="disabled",
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
        assert camera.desired_ai_state == "Inactive"
        assert [p["type"] for p in payloads] == ["ALERT_STATUS_UPDATE"]
        assert payloads[0]["data"]["log_id"] == log.log_id
        assert payloads[0]["data"]["detection_status"] == DetectionStatus.RESOLVED.value
        assert payloads[0]["data"]["action"] == "ALERT_RESOLVE"


class TestSnooze:
    def test_snooze_unverified_alert(self, client: TestClient, session: Session):
        operator, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Snooze Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)

        resp = client.post(f"/api/alerts/{log.log_id}/snooze", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["snoozed_by_id"] == operator.user_id
        assert body["snoozed_until"] is not None

        session.refresh(log)
        assert log.snoozed_by_id == operator.user_id
        assert log.snoozed_until is not None

    def test_snooze_uses_actor_saved_duration(
        self, client: TestClient, session: Session
    ):
        operator, headers = operator_with_headers(client, session)
        operator.alarm_settings.snooze_duration = 45
        session.add(operator.alarm_settings)
        session.commit()
        camera = make_camera(session, name="Duration Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)
        before = datetime.now(UTC)

        resp = client.post(f"/api/alerts/{log.log_id}/snooze", headers=headers)

        assert resp.status_code == 200
        snoozed_until = datetime.fromisoformat(resp.json()["snoozed_until"])
        delta = (snoozed_until - before).total_seconds()
        assert 44 <= delta <= 46

    def test_snooze_rejects_a_client_supplied_duration(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Body Reject Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)

        resp = client.post(
            f"/api/alerts/{log.log_id}/snooze",
            headers=headers,
            json={"snooze_duration": 45},
        )

        assert resp.status_code == 422

    def test_snooze_non_unverified_is_precondition_failed(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Precondition Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.RESOLVED)

        resp = client.post(f"/api/alerts/{log.log_id}/snooze", headers=headers)

        assert resp.status_code == 400
        assert resp.json()["code"] == "PRECONDITION_FAILED"

    def test_snooze_missing_alert_returns_404(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session)

        resp = client.post("/api/alerts/99999/snooze", headers=headers)

        assert resp.status_code == 404

    def test_re_snooze_overwrites_deadline(self, client: TestClient, session: Session):
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Re-snooze Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)

        first = client.post(f"/api/alerts/{log.log_id}/snooze", headers=headers)
        first_until = first.json()["snoozed_until"]

        second = client.post(f"/api/alerts/{log.log_id}/snooze", headers=headers)
        second_until = second.json()["snoozed_until"]

        assert second.status_code == 200
        assert second_until >= first_until

    def test_snooze_broadcasts_snooze_activated(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        payloads = _capture_broadcasts(client, monkeypatch)
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Broadcast Snooze Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)

        resp = client.post(f"/api/alerts/{log.log_id}/snooze", headers=headers)

        assert resp.status_code == 200
        assert [p["type"] for p in payloads] == ["SNOOZE_ACTIVATED"]
        assert payloads[0]["data"]["log_id"] == log.log_id


class TestConcurrency:
    """14_EDGE_CASES.md §1 — exactly one side of a race wins; the loser gets
    a clean 409/400, never a corrupted or double-applied state."""

    def test_two_confirms_race_exactly_one_wins(
        self, client: TestClient, session: Session
    ):
        """Edge case 1.1 — both operators attempt the same transition
        (Unverified -> Ongoing); only the first commit can win."""
        _, headers_a = operator_with_headers(client, session, username="race_a")
        _, headers_b = operator_with_headers(client, session, username="race_b")
        camera = make_camera(session, name="Race Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)

        resp_a = client.post(f"/api/alerts/{log.log_id}/confirm", headers=headers_a)
        resp_b = client.post(f"/api/alerts/{log.log_id}/confirm", headers=headers_b)

        assert {resp_a.status_code, resp_b.status_code} == {200, 409}

        session.refresh(log)
        assert log.detection_status == DetectionStatus.ONGOING.value

    def test_two_resolves_race_exactly_one_wins(
        self, client: TestClient, session: Session
    ):
        operator, headers_a = operator_with_headers(
            client, session, username="resolve_a"
        )
        _, headers_b = operator_with_headers(client, session, username="resolve_b")
        camera = make_camera(session, name="Resolve Race Cam", channel_id=1)
        log = make_alert(
            session,
            camera,
            status=DetectionStatus.ONGOING,
            verified_by_id=operator.user_id,
            verified_at=datetime.now(UTC),
        )

        resp_a = client.post(f"/api/alerts/{log.log_id}/resolve", headers=headers_a)
        resp_b = client.post(f"/api/alerts/{log.log_id}/resolve", headers=headers_b)

        assert {resp_a.status_code, resp_b.status_code} == {200, 409}

    def test_snooze_already_handled_before_request_is_precondition_failed(
        self, client: TestClient, session: Session
    ):
        """A snooze request arriving after the incident was already
        confirmed (no overlap in time) is a plain business-rule rejection,
        not a race — 400, per 01_CONTRACTS.md §1.3's explicit "snooze on a
        non-Unverified incident" case."""
        operator, headers_confirm = operator_with_headers(
            client, session, username="snoozebiz1"
        )
        _, headers_snooze = operator_with_headers(
            client, session, username="snoozebiz2"
        )
        camera = make_camera(session, name="Snooze Business Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)

        confirm_resp = client.post(
            f"/api/alerts/{log.log_id}/confirm", headers=headers_confirm
        )
        assert confirm_resp.status_code == 200

        snooze_resp = client.post(
            f"/api/alerts/{log.log_id}/snooze", headers=headers_snooze
        )
        assert snooze_resp.status_code == 400
        assert snooze_resp.json()["code"] == "PRECONDITION_FAILED"

        session.refresh(log)
        assert log.detection_status == DetectionStatus.ONGOING.value
        assert log.snoozed_until is None

    def test_snooze_loses_to_a_confirm_landing_mid_flight(
        self, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """Edge case 1.3 — a genuine race: snooze's peek sees Unverified,
        but a Confirm commits before snooze's own atomic UPDATE fires. The
        atomic UPDATE (not the peek) is what must decide this, so it comes
        back as ConflictState (409), never a silently-applied snooze on an
        Ongoing incident."""
        from app.services.incidents import ConflictState, transition
        from app.services.snoozes import snooze_incident

        engine = session.get_bind()
        camera = make_camera(session, name="Mid-flight Race Cam", channel_id=1)
        log = make_alert(session, camera, status=DetectionStatus.UNVERIFIED)
        confirmer = make_operator(
            session, username="midflightc", password="Operator123"
        )
        snoozer = make_operator(session, username="midflights", password="Operator123")

        real_get = Session.get
        state = {"landed": False}

        def landing_get(self, entity, ident, *args, **kwargs):
            result = real_get(self, entity, ident, *args, **kwargs)
            if entity is DetectionLog and not state["landed"]:
                state["landed"] = True
                with Session(engine) as other_session:
                    transition(
                        other_session,
                        log_id=log.log_id,
                        expected=DetectionStatus.UNVERIFIED,
                        new=DetectionStatus.ONGOING,
                        actor=confirmer,
                    )
                    other_session.commit()
            return result

        monkeypatch.setattr(Session, "get", landing_get)

        with pytest.raises(ConflictState) as exc_info:
            snooze_incident(session, log_id=log.log_id, actor=snoozer)

        assert exc_info.value.current_status == DetectionStatus.ONGOING.value
        assert exc_info.value.handled_action == "ALERT_CONFIRM"
