"""
Tests for /api/cameras — 01_CONTRACTS.md §5.9's kpis/breakdowns response
shape, desired-state recomputation on mutation, and presented (staleness-
aware) observed status.
"""

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import settings
from app.models import AIStatus, Camera, ConnectionStatus, DetectionStatus
from app.services.cameras import (
    presented_ai_status_expr,
    presented_connection_status_expr,
    presented_statuses,
)
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import (
    auth_headers,
    make_admin,
    make_camera,
    make_detection,
    make_operator,
)


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

    @pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
    def test_pagination_boundary_rejections(
        self, client: TestClient, session: Session, query: str
    ):
        """Edge case 2.1/2.2 (be_audit/00_FINDINGS.md F29)."""
        headers = _headers(client, session)
        resp = client.get(f"/api/cameras/?{query}", headers=headers)
        assert resp.status_code == 422

    @pytest.mark.parametrize("query", ["limit=1", "limit=100", "offset=0"])
    def test_pagination_boundary_accepted(
        self, client: TestClient, session: Session, query: str
    ):
        headers = _headers(client, session)
        resp = client.get(f"/api/cameras/?{query}", headers=headers)
        assert resp.status_code == 200

    def test_offset_beyond_total_returns_empty_page_with_correct_total(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        make_camera(session, name="Beyond Offset Cam", channel_id=50)

        resp = client.get("/api/cameras/?offset=50", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 1
        assert body["cameras"] == []
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

    def test_kpi_invariants_hold_across_every_combination(
        self, client: TestClient, session: Session
    ):
        """06_PKG_system_health.md Step 5 — configuration, connection, and
        AI state are independent dimensions (D-009). A disabled camera that
        is still reporting Connected/Active must count as Connected/Active
        in the breakdowns, not be silently reclassified as
        Disconnected/Inactive just because it's disabled — nothing may
        infer "disabled" from a connection or AI status."""
        headers = _headers(client, session)
        now = datetime.now(UTC)

        make_camera(
            session,
            name="Enabled Connected",
            channel_id=201,
            connection_status="Connected",
            ai_status="Active",
            last_heartbeat_at=now,
        )
        make_camera(
            session,
            name="Enabled Disconnected",
            channel_id=202,
            connection_status="Disconnected",
            ai_status="Inactive",
            last_heartbeat_at=now,
        )
        make_camera(session, name="Enabled Never HB", channel_id=203)
        make_camera(
            session,
            name="Enabled Stale",
            channel_id=204,
            connection_status="Connected",
            ai_status="Active",
            last_heartbeat_at=now - timedelta(seconds=30),
        )
        # The edge case from the package doc: disabled, but its last
        # observed report was Connected/Active. presented_statuses() never
        # treats a disabled camera as stale, so this must present as
        # Connected/Active — counted there, not under Disconnected/Inactive.
        disabled_but_connected = make_camera(
            session,
            name="Disabled But Connected",
            channel_id=205,
            is_enabled=False,
            connection_status="Connected",
            ai_status="Active",
        )

        resp = client.get("/api/cameras/", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        kpis = body["kpis"]
        conn = body["breakdowns"]["connection"]
        ai = body["breakdowns"]["ai"]

        assert kpis["total"] == 5
        assert kpis["enabled"] == 4
        assert kpis["total"] == kpis["enabled"] + 1  # Disabled is derived
        assert sum(conn.values()) == kpis["total"]
        assert sum(ai.values()) == kpis["total"]

        rows = {c["camera_id"]: c for c in body["cameras"]}
        assert (
            rows[disabled_but_connected.camera_id]["connection_status"] == "Connected"
        )
        assert rows[disabled_but_connected.camera_id]["ai_status"] == "Active"
        assert rows[disabled_but_connected.camera_id]["is_enabled"] is False

        assert conn["connected"] == 2  # enabled_connected + disabled_but_connected
        assert conn["disconnected"] == 1  # enabled_disconnected
        assert conn["reconnecting"] == 1  # enabled_never_heartbeated
        assert conn["unresponsive"] == 1  # enabled_stale
        assert ai["active"] == 2  # enabled_connected + disabled_but_connected
        # enabled_disconnected + enabled_never_heartbeated (never-heartbeated
        # only overrides the presented *connection* status to Reconnecting;
        # ai_status keeps its stored default of Inactive).
        assert ai["inactive"] == 2
        assert ai["unresponsive"] == 1  # enabled_stale

        assert kpis["network_connected"] == conn["connected"]
        assert kpis["active_detection"] == ai["active"]

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


class TestPresentedStatusFilters:
    """P19 §2 — camera status filters must compare *presented*, staleness-
    aware status, the same value the rows and breakdowns show, not the raw
    stored columns."""

    def test_sql_expr_matches_python_across_full_matrix(self, session: Session):
        """The paired test that is the point of this step: for every
        (is_enabled x heartbeat-timing x stored connection_status x stored
        ai_status) combination, the SQL case() expression the filters use
        must agree with presented_statuses(), the function the rows and
        breakdowns are rendered from. Two copies of one rule is exactly how
        the filter/display divergence happened; this is the guard against it
        recurring."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=settings.HEARTBEAT_STALE_SECONDS)
        heartbeat_cases = {
            "never": None,
            "fresh": now - timedelta(seconds=1),
            "exactly_at_cutoff": cutoff,
            "stale": cutoff - timedelta(seconds=1),
        }

        cameras: list[Camera] = []
        channel = 1000
        for is_enabled, hb_value, conn_status, ai_status in itertools.product(
            (True, False),
            heartbeat_cases.values(),
            [s.value for s in ConnectionStatus],
            [s.value for s in AIStatus],
        ):
            channel += 1
            cam = make_camera(
                session,
                name=f"Matrix Cam {channel}",
                channel_id=channel,
                is_enabled=is_enabled,
                connection_status=conn_status,
                ai_status=ai_status,
                last_heartbeat_at=hb_value,
            )
            cameras.append(cam)

        rows = session.exec(
            select(
                Camera.camera_id,
                presented_connection_status_expr(now=now),
                presented_ai_status_expr(now=now),
            )
        ).all()
        sql_by_id = {row[0]: (row[1], row[2]) for row in rows}

        assert len(sql_by_id) == len(cameras)
        for cam in cameras:
            expected = presented_statuses(cam, now=now)
            assert sql_by_id[cam.camera_id] == expected, (
                f"{cam.camera_name}: is_enabled={cam.is_enabled} "
                f"last_heartbeat_at={cam.last_heartbeat_at}"
            )

    def test_filter_by_unresponsive_returns_exactly_what_displays_it(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        now = datetime.now(UTC)
        stale_but_stored_active = make_camera(
            session,
            name="Stale Displays Unresponsive",
            channel_id=301,
            connection_status="Connected",
            ai_status="Active",
            last_heartbeat_at=now - timedelta(seconds=30),
        )
        make_camera(
            session,
            name="Fresh Connected",
            channel_id=302,
            connection_status="Connected",
            ai_status="Active",
            last_heartbeat_at=now,
        )
        # Stored Unresponsive but disabled — the fix must not invent a
        # reason to *exclude* a disabled camera whose stored value already
        # happens to be Unresponsive; disabled cameras keep their stored
        # value verbatim.
        disabled_stored_unresponsive = make_camera(
            session,
            name="Disabled Stored Unresponsive",
            channel_id=303,
            is_enabled=False,
            connection_status="Unresponsive",
            ai_status="Unresponsive",
        )

        resp = client.get(
            "/api/cameras/?connection_status=Unresponsive&ai_status=Unresponsive",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        ids = {c["camera_id"] for c in body["cameras"]}
        assert ids == {
            stale_but_stored_active.camera_id,
            disabled_stored_unresponsive.camera_id,
        }
        assert body["total_filtered"] == 2
        for cam_row in body["cameras"]:
            assert cam_row["connection_status"] == "Unresponsive"
            assert cam_row["ai_status"] == "Unresponsive"

    def test_filtered_total_agrees_with_unfiltered_breakdown_count(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        now = datetime.now(UTC)
        make_camera(
            session,
            name="Stale One",
            channel_id=310,
            connection_status="Connected",
            ai_status="Active",
            last_heartbeat_at=now - timedelta(seconds=30),
        )
        make_camera(
            session,
            name="Stale Two",
            channel_id=311,
            connection_status="Connected",
            ai_status="Active",
            last_heartbeat_at=now - timedelta(seconds=45),
        )
        make_camera(
            session,
            name="Fresh One",
            channel_id=312,
            connection_status="Connected",
            ai_status="Active",
            last_heartbeat_at=now,
        )

        unfiltered = client.get("/api/cameras/", headers=headers).json()
        breakdown_count = unfiltered["breakdowns"]["ai"]["unresponsive"]

        filtered = client.get(
            "/api/cameras/?ai_status=Unresponsive", headers=headers
        ).json()

        assert filtered["total_filtered"] == breakdown_count == 2

    def test_disabled_long_stale_camera_returned_by_stored_status_not_unresponsive(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        cam = make_camera(
            session,
            name="Disabled Long Stale",
            channel_id=320,
            is_enabled=False,
            connection_status="Connected",
            ai_status="Active",
            last_heartbeat_at=datetime.now(UTC) - timedelta(days=1),
        )

        unresponsive = client.get(
            "/api/cameras/?connection_status=Unresponsive", headers=headers
        ).json()
        assert cam.camera_id not in {c["camera_id"] for c in unresponsive["cameras"]}

        connected = client.get(
            "/api/cameras/?connection_status=Connected", headers=headers
        ).json()
        assert cam.camera_id in {c["camera_id"] for c in connected["cameras"]}


class TestGetCameraDetail:
    """01_CONTRACTS.md §5.4/§7.2, P21 Step 1."""

    def test_returns_telemetry_fields_matching_list_presentation(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        cam = make_camera(
            session,
            name="Detail Cam",
            channel_id=200,
            connection_status="Connected",
            ai_status="Active",
            last_heartbeat_at=datetime.now(UTC),
        )
        cam.applied_config_version = 3
        cam.measured_fps = 12.4
        cam.inference_latency_ms = 33.1
        cam.last_error_code = "E1"
        cam.last_error_message = "boom"
        session.add(cam)
        session.commit()

        list_row = next(
            c
            for c in client.get("/api/cameras/", headers=headers).json()["cameras"]
            if c["camera_id"] == cam.camera_id
        )

        resp = client.get(f"/api/cameras/{cam.camera_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["applied_config_version"] == 3
        assert body["measured_fps"] == 12.4
        assert body["inference_latency_ms"] == 33.1
        assert body["last_error_code"] == "E1"
        assert body["last_error_message"] == "boom"
        assert "last_heartbeat_at" in body
        # Staleness-presented identically to the list route — same helper.
        assert body["connection_status"] == list_row["connection_status"]
        assert body["ai_status"] == list_row["ai_status"]

    def test_never_heartbeated_camera_has_null_telemetry_not_zero(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        cam = make_camera(session, name="Fresh Cam", channel_id=205)

        resp = client.get(f"/api/cameras/{cam.camera_id}", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["measured_fps"] is None
        assert body["last_heartbeat_at"] is None

    def test_operator_sees_null_rtsp_admin_sees_masked(
        self, client: TestClient, session: Session
    ):
        op_headers = _headers(client, session)
        make_admin(session)
        admin_headers = auth_headers(client, "admin", "Admin123")
        cam = make_camera(session, name="RTSP Cam", channel_id=201)

        op_resp = client.get(f"/api/cameras/{cam.camera_id}", headers=op_headers)
        assert op_resp.status_code == 200
        assert op_resp.json()["rtsp_url_redacted"] is None

        admin_resp = client.get(f"/api/cameras/{cam.camera_id}", headers=admin_headers)
        assert admin_resp.status_code == 200
        assert admin_resp.json()["rtsp_url_redacted"].startswith("rtsp://")

    def test_redacts_userinfo_credentials_from_response_body(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        from app.core import config as config_module
        from pydantic import SecretStr

        monkeypatch.setattr(
            config_module.settings,
            "RTSP_URL_TEMPLATE",
            "rtsp://{dss_username}:{dss_password}@10.0.0.9:554/ch{channel_id}",
        )
        monkeypatch.setattr(config_module.settings, "DSS_USERNAME", "opuser")
        monkeypatch.setattr(config_module.settings, "DSS_PASS", SecretStr("sekret"))

        make_admin(session)
        admin_headers = auth_headers(client, "admin", "Admin123")
        cam = make_camera(session, name="Leaky Cam", channel_id=202)

        resp = client.get(f"/api/cameras/{cam.camera_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert "opuser" not in resp.text
        assert "sekret" not in resp.text
        assert "***:***@" in resp.json()["rtsp_url_redacted"]

    def test_redacts_credential_appearing_outside_userinfo_position(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """The half a hand-rolled userinfo regex would miss: a template
        putting the password in a query parameter is still covered by
        collect_secret_values() replacing the literal DSS_PASS value."""
        from app.core import config as config_module
        from pydantic import SecretStr

        monkeypatch.setattr(
            config_module.settings,
            "RTSP_URL_TEMPLATE",
            "rtsp://10.0.0.9:554/ch{channel_id}?pwd={dss_password}",
        )
        monkeypatch.setattr(config_module.settings, "DSS_PASS", SecretStr("sekret"))

        make_admin(session)
        admin_headers = auth_headers(client, "admin", "Admin123")
        cam = make_camera(session, name="Query Leak Cam", channel_id=203)

        resp = client.get(f"/api/cameras/{cam.camera_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert "sekret" not in resp.text

    def test_404_on_unknown_camera(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        resp = client.get("/api/cameras/9999", headers=headers)
        assert resp.status_code == 404

    def test_404_on_soft_deleted_camera(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        cam = make_camera(session, name="Gone Cam", channel_id=204)
        client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)

        resp = client.get(f"/api/cameras/{cam.camera_id}", headers=headers)
        assert resp.status_code == 404


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
