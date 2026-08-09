"""
Tests for /api/cameras — 01_CONTRACTS.md §5.9's kpis/breakdowns response
shape, desired-state recomputation on mutation, and presented (staleness-
aware) observed status.
"""

from datetime import UTC, datetime, timedelta

from app.models import DetectionStatus
from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import auth_headers, make_camera, make_detection, make_operator


def _headers(client: TestClient, session: Session) -> dict:
    make_operator(session, username="camop", password="Operator123")
    return auth_headers(client, "camop", "Operator123")


class TestGetAllCameras:
    def test_response_shape_and_population_invariants(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        make_camera(session, name="A", channel_id=1)
        disabled = make_camera(session, name="B", channel_id=2, is_enabled=False)
        disabled.connection_status = "Disconnected"
        disabled.ai_status = "Inactive"
        session.add(disabled)
        session.commit()

        resp = client.get("/api/cameras/", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == {"kpis", "breakdowns", "total_filtered", "cameras"}

        kpis = body["kpis"]
        conn = body["breakdowns"]["connection"]
        ai = body["breakdowns"]["ai"]
        assert kpis["total"] == 2
        assert kpis["enabled"] == 1
        # Population invariants (01_CONTRACTS.md §5.9): every breakdown sums
        # to the same total, and disabled is derived (total - enabled), not
        # returned separately.
        assert sum(conn.values()) == kpis["total"]
        assert sum(ai.values()) == kpis["total"]
        assert "disabled" not in kpis

    def test_zero_cameras_kpis_all_zero(self, client: TestClient, session: Session):
        """Edge case 3.6 — KPI invariants still hold with all counts 0."""
        headers = _headers(client, session)
        resp = client.get("/api/cameras/", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["kpis"] == {
            "total": 0,
            "enabled": 0,
            "network_connected": 0,
            "active_detection": 0,
        }
        assert body["total_filtered"] == 0
        assert body["cameras"] == []

    def test_soft_deleted_camera_excluded_from_kpis(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        cam = make_camera(session, name="To Delete", channel_id=5)
        client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)

        resp = client.get("/api/cameras/", headers=headers)
        assert resp.json()["kpis"]["total"] == 0

    def test_presented_unresponsive_after_stale_heartbeat(
        self, client: TestClient, session: Session
    ):
        """Step 2 — never written to the row, only presented at read time."""
        headers = _headers(client, session)
        cam = make_camera(
            session,
            name="Stale Cam",
            channel_id=90,
            connection_status="Connected",
            ai_status="Active",
        )
        cam.last_heartbeat_at = datetime.now(UTC) - timedelta(seconds=30)
        session.add(cam)
        session.commit()

        resp = client.get("/api/cameras/", headers=headers)
        row = next(c for c in resp.json()["cameras"] if c["camera_id"] == cam.camera_id)
        assert row["connection_status"] == "Unresponsive"
        assert row["ai_status"] == "Unresponsive"
        assert resp.json()["breakdowns"]["connection"]["unresponsive"] == 1
        assert resp.json()["breakdowns"]["ai"]["unresponsive"] == 1

        session.refresh(cam)
        assert cam.connection_status == "Connected"
        assert cam.ai_status == "Active"

    def test_heartbeat_staleness_boundary(self, client: TestClient, session: Session):
        """Edge case 2.18 — exactly HEARTBEAT_STALE_SECONDS (10s) old is
        Unresponsive; 9.9s old is still fresh."""
        headers = _headers(client, session)
        now = datetime.now(UTC)
        fresh = make_camera(
            session,
            name="Just Fresh Cam",
            channel_id=93,
            connection_status="Connected",
            ai_status="Active",
            last_heartbeat_at=now - timedelta(seconds=9.9),
        )
        stale = make_camera(
            session,
            name="Just Stale Cam",
            channel_id=94,
            connection_status="Connected",
            ai_status="Active",
            last_heartbeat_at=now - timedelta(seconds=10),
        )

        resp = client.get("/api/cameras/", headers=headers)
        rows = {c["camera_id"]: c for c in resp.json()["cameras"]}
        assert rows[fresh.camera_id]["connection_status"] == "Connected"
        assert rows[stale.camera_id]["connection_status"] == "Unresponsive"

    def test_never_heartbeated_presented_as_reconnecting(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        cam = make_camera(session, name="Never HB Cam", channel_id=91)
        assert cam.last_heartbeat_at is None

        resp = client.get("/api/cameras/", headers=headers)
        row = next(c for c in resp.json()["cameras"] if c["camera_id"] == cam.camera_id)
        assert row["connection_status"] == "Reconnecting"

    def test_disabled_camera_never_presented_as_unresponsive(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        cam = make_camera(
            session, name="Disabled Stale Cam", channel_id=92, is_enabled=False
        )
        cam.last_heartbeat_at = datetime.now(UTC) - timedelta(hours=1)
        session.add(cam)
        session.commit()

        resp = client.get("/api/cameras/", headers=headers)
        row = next(c for c in resp.json()["cameras"] if c["camera_id"] == cam.camera_id)
        assert row["connection_status"] != "Unresponsive"

    def test_filter_by_is_enabled(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        make_camera(session, name="Enabled Cam", channel_id=6, is_enabled=True)
        make_camera(session, name="Disabled Cam", channel_id=7, is_enabled=False)

        resp = client.get("/api/cameras/?is_enabled=false", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 1
        assert body["cameras"][0]["camera_name"] == "Disabled Cam"


class TestCreateCamera:
    def test_create_sets_desired_active(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        resp = client.post(
            "/api/cameras/",
            headers=headers,
            json={"camera_name": "New Cam", "channel_id": 99},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["desired_ai_state"] == "Active"
        assert body["desired_state_reason"] is None
        assert body["config_version"] == 1
        assert body["connection_status"] == "Reconnecting"

    def test_duplicate_active_name_is_409(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        make_camera(session, name="Dup Cam", channel_id=50)
        resp = client.post(
            "/api/cameras/",
            headers=headers,
            json={"camera_name": "Dup Cam", "channel_id": 51},
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == "CONFLICT_DUPLICATE"

    def test_duplicate_active_channel_id_is_409(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        make_camera(session, name="Chan Cam", channel_id=55)
        resp = client.post(
            "/api/cameras/",
            headers=headers,
            json={"camera_name": "Other Name", "channel_id": 55},
        )
        assert resp.status_code == 409

    def test_reuses_soft_deleted_camera_name(
        self, client: TestClient, session: Session
    ):
        """Edge case 9.3 — reusing a soft-deleted camera's name must
        succeed, not raise an unhandled 500."""
        headers = _headers(client, session)
        cam = make_camera(session, name="Recycled", channel_id=60)
        client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)

        resp = client.post(
            "/api/cameras/",
            headers=headers,
            json={"camera_name": "Recycled", "channel_id": 61},
        )
        assert resp.status_code == 201, resp.text

    def test_reuses_soft_deleted_camera_channel_id(
        self, client: TestClient, session: Session
    ):
        """Edge case 9.4 — same for channel_id."""
        headers = _headers(client, session)
        cam = make_camera(session, name="Chan Recycled", channel_id=65)
        client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)

        resp = client.post(
            "/api/cameras/",
            headers=headers,
            json={"camera_name": "Different Name", "channel_id": 65},
        )
        assert resp.status_code == 201, resp.text


class TestUpdateCamera:
    def test_rename_does_not_bump_config_version(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        # desired_ai_state="Active" matches what the real create route
        # would have already derived — otherwise recompute-everywhere
        # (Step 2) would itself count as a first-time change here.
        cam = make_camera(
            session, name="Rename Cam", channel_id=69, desired_ai_state="Active"
        )
        old_version = cam.config_version

        resp = client.patch(
            f"/api/cameras/{cam.camera_id}",
            headers=headers,
            json={"camera_name": "Renamed"},
        )
        assert resp.status_code == 200
        assert resp.json()["config_version"] == old_version

    def test_disable_sets_inactive_and_bumps_version(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        cam = make_camera(session, name="Disable Cam", channel_id=70)
        old_version = cam.config_version

        resp = client.patch(
            f"/api/cameras/{cam.camera_id}", headers=headers, json={"is_enabled": False}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["desired_ai_state"] == "Inactive"
        assert body["desired_state_reason"] == "disabled"
        assert body["config_version"] == old_version + 1

    def test_missing_camera_404(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        resp = client.patch(
            "/api/cameras/99999", headers=headers, json={"camera_name": "X"}
        )
        assert resp.status_code == 404

    def test_rename_to_duplicate_active_name_is_409(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        make_camera(session, name="Taken Name", channel_id=72)
        other = make_camera(session, name="Other Cam", channel_id=73)

        resp = client.patch(
            f"/api/cameras/{other.camera_id}",
            headers=headers,
            json={"camera_name": "Taken Name"},
        )
        assert resp.status_code == 409


class TestDeleteCamera:
    def test_refuses_with_open_incident(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        cam = make_camera(session, name="Open Incident Cam", channel_id=80)
        make_detection(session, cam, status=DetectionStatus.UNVERIFIED)

        resp = client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)
        assert resp.status_code == 400, resp.text
        assert resp.json()["code"] == "PRECONDITION_FAILED"

        session.refresh(cam)
        assert cam.is_active is True

    def test_succeeds_without_open_incident_sets_inactive(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        cam = make_camera(session, name="Deletable Cam", channel_id=81)

        resp = client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)
        assert resp.status_code == 204, resp.text

        session.refresh(cam)
        assert cam.is_active is False
        assert cam.desired_ai_state == "Inactive"
        assert cam.desired_state_reason == "disabled"

    def test_succeeds_with_a_closed_incident(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        cam = make_camera(session, name="Closed Incident Cam", channel_id=82)
        make_detection(session, cam, status=DetectionStatus.RESOLVED)

        resp = client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)
        assert resp.status_code == 204

    def test_missing_camera_404(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        resp = client.delete("/api/cameras/99999", headers=headers)
        assert resp.status_code == 404
