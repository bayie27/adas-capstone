"""
Tests for /api/cameras — 01_CONTRACTS.md §5.9's kpis/breakdowns response
shape, desired-state recomputation on mutation, and presented (staleness-
aware) observed status.
"""

import itertools
import json
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import settings
from app.models import AIStatus, AuditLog, Camera, ConnectionStatus, DetectionStatus
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


class TestPresentedStatuses:
    """The staleness rule itself, asserted against presented_statuses() with
    an explicit `now` — the same shape as the sibling boundary test in
    test_system_health.py, and for the same reason.

    Deliberately not a route test: GET /api/cameras/ reads its own
    datetime.now(UTC) at request time (routes/cameras.py), so a camera
    parked a fraction of a second inside the window crosses the boundary
    while the request is in flight. That gave the route-level version of
    this test a ~100ms real-time budget and made it flaky under
    `pytest -n auto`. Route-level staleness presentation is covered by
    TestGetAllCameras with margins wide enough not to care.
    """

    def test_heartbeat_staleness_boundary(self, session: Session):
        """Edge case 2.18 — exactly HEARTBEAT_STALE_SECONDS (10s) old is
        Unresponsive on both dimensions; a hair under is still fresh."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=settings.HEARTBEAT_STALE_SECONDS)
        fresh = make_camera(
            session,
            name="Just Fresh Cam",
            channel_id=93,
            connection_status="Connected",
            ai_status="Active",
            last_heartbeat_at=cutoff + timedelta(milliseconds=100),
        )
        stale = make_camera(
            session,
            name="Just Stale Cam",
            channel_id=94,
            connection_status="Connected",
            ai_status="Active",
            last_heartbeat_at=cutoff,
        )

        assert presented_statuses(fresh, now=now) == ("Connected", "Active")
        assert presented_statuses(stale, now=now) == ("Unresponsive", "Unresponsive")


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

    def test_rename_records_camera_name_and_previous_camera_name(
        self, client: TestClient, session: Session
    ):
        """P25 Step 3's rename trap: by the time CAMERA_UPDATE is written,
        db_camera.camera_name is already the *new* name, so the old one
        must be captured before the mutation loop runs."""
        headers = _headers(client, session)
        cam = make_camera(session, name="Old Name", channel_id=74)

        resp = client.patch(
            f"/api/cameras/{cam.camera_id}",
            headers=headers,
            json={"camera_name": "New Name"},
        )
        assert resp.status_code == 200

        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "CAMERA_UPDATE")
        ).all()
        assert len(rows) == 1
        detail = json.loads(rows[0].detail)
        assert detail["camera_name"] == "New Name"
        assert detail["previous_camera_name"] == "Old Name"

    def test_non_rename_update_records_no_previous_camera_name(
        self, client: TestClient, session: Session
    ):
        """A CAMERA_UPDATE row for a field other than camera_name must not
        gain a previous_camera_name key — that field never changed."""
        headers = _headers(client, session)
        cam = make_camera(session, name="Stable Name", channel_id=75)

        resp = client.patch(
            f"/api/cameras/{cam.camera_id}",
            headers=headers,
            json={"channel_id": 999},
        )
        assert resp.status_code == 200

        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "CAMERA_UPDATE")
        ).all()
        assert len(rows) == 1
        detail = json.loads(rows[0].detail)
        assert detail["camera_name"] == "Stable Name"
        assert "previous_camera_name" not in detail

    def test_enable_disable_detail_carries_camera_name(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        cam = make_camera(session, name="Toggle Cam", channel_id=76)

        client.patch(
            f"/api/cameras/{cam.camera_id}",
            headers=headers,
            json={"is_enabled": False},
        )
        client.patch(
            f"/api/cameras/{cam.camera_id}",
            headers=headers,
            json={"is_enabled": True},
        )

        disable_row = session.exec(
            select(AuditLog).where(AuditLog.action == "CAMERA_DISABLE")
        ).one()
        enable_row = session.exec(
            select(AuditLog).where(AuditLog.action == "CAMERA_ENABLE")
        ).one()
        assert json.loads(disable_row.detail) == {"camera_name": "Toggle Cam"}
        assert json.loads(enable_row.detail) == {"camera_name": "Toggle Cam"}


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
        make_detection(session, cam, status=DetectionStatus.CLEARED)

        resp = client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)
        assert resp.status_code == 204

    def test_missing_camera_404(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        resp = client.delete("/api/cameras/99999", headers=headers)
        assert resp.status_code == 404

    def test_delete_detail_carries_camera_name(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        cam = make_camera(session, name="Named Delete Cam", channel_id=83)

        resp = client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)
        assert resp.status_code == 204

        row = session.exec(
            select(AuditLog).where(AuditLog.action == "CAMERA_DELETE")
        ).one()
        assert json.loads(row.detail) == {"camera_name": "Named Delete Cam"}


class TestGetAllCamerasIsActiveFilter:
    """P23 — mirrors P19 §3's is_active tri-state for Users. Camera
    soft-delete had no reactivation path (PR #126) because there was no way
    to even list, let alone restore, a deleted row."""

    def test_default_omits_soft_deleted_cameras(
        self, client: TestClient, session: Session
    ):
        """Pins today's behaviour: a caller that passes nothing must see
        exactly what it saw before this change."""
        headers = _headers(client, session)
        cam = make_camera(session, name="Keep Me", channel_id=400)
        deleted = make_camera(session, name="Delete Me", channel_id=401)
        client.delete(f"/api/cameras/{deleted.camera_id}", headers=headers)

        resp = client.get("/api/cameras/", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 1
        assert body["cameras"][0]["camera_id"] == cam.camera_id

    def test_is_active_false_returns_only_soft_deleted(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        make_camera(session, name="Keep Me 2", channel_id=402)
        deleted = make_camera(session, name="Delete Me 2", channel_id=403)
        client.delete(f"/api/cameras/{deleted.camera_id}", headers=headers)

        resp = client.get("/api/cameras/?is_active=false", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 1
        assert body["cameras"][0]["camera_id"] == deleted.camera_id
        assert body["cameras"][0]["is_active"] is False

    def test_is_active_null_returns_both(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        make_camera(session, name="Keep Me 3", channel_id=404)
        deleted = make_camera(session, name="Delete Me 3", channel_id=405)
        client.delete(f"/api/cameras/{deleted.camera_id}", headers=headers)

        resp = client.get("/api/cameras/?is_active=null", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total_filtered"] == 2

    def test_invalid_is_active_value_is_422(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        resp = client.get("/api/cameras/?is_active=maybe", headers=headers)
        assert resp.status_code == 422

    def test_kpis_and_breakdowns_unaffected_by_is_active_filter(
        self, client: TestClient, session: Session
    ):
        """01_CONTRACTS.md §5.9 — kpis/breakdowns deliberately stay the
        unfiltered is_active=1 population no matter what the list filter
        shows; a soft-deleted camera is not part of the fleet being
        monitored."""
        headers = _headers(client, session)
        make_camera(session, name="Keep Me 4", channel_id=406)
        deleted = make_camera(session, name="Delete Me 4", channel_id=407)
        client.delete(f"/api/cameras/{deleted.camera_id}", headers=headers)

        default_body = client.get("/api/cameras/", headers=headers).json()
        deleted_body = client.get(
            "/api/cameras/?is_active=false", headers=headers
        ).json()
        both_body = client.get("/api/cameras/?is_active=null", headers=headers).json()

        assert default_body["kpis"] == deleted_body["kpis"] == both_body["kpis"]
        assert (
            default_body["breakdowns"]
            == deleted_body["breakdowns"]
            == both_body["breakdowns"]
        )
        assert default_body["kpis"]["total"] == 1


class TestCameraRestore:
    """P23 — the reactivation path DELETE never had (PR #126)."""

    def test_restore_detail_carries_camera_name(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        cam = make_camera(session, name="Named Restore Cam", channel_id=409)
        client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)

        resp = client.patch(
            f"/api/cameras/{cam.camera_id}",
            headers=headers,
            json={"is_active": True},
        )
        assert resp.status_code == 200

        row = session.exec(
            select(AuditLog).where(AuditLog.action == "CAMERA_RESTORE")
        ).one()
        assert json.loads(row.detail) == {"camera_name": "Named Restore Cam"}

    def test_round_trip_restore(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        cam = make_camera(
            session, name="Round Trip Cam", channel_id=410, desired_ai_state="Active"
        )
        client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)
        deleted_version = session.exec(
            select(Camera.config_version).where(Camera.camera_id == cam.camera_id)
        ).one()

        listed = client.get("/api/cameras/?is_active=false", headers=headers).json()
        assert cam.camera_id in {c["camera_id"] for c in listed["cameras"]}

        with client.websocket_connect("/ws/alerts", headers=headers) as websocket:
            websocket.receive_json()  # CONNECTION_READY

            resp = client.patch(
                f"/api/cameras/{cam.camera_id}",
                headers=headers,
                json={"is_active": True},
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["is_active"] is True
            assert body["config_version"] == deleted_version + 1
            assert body["desired_ai_state"] == "Active"

            envelope = websocket.receive_json()
            assert envelope["type"] == "CAMERA_STATUS_UPDATE"
            assert envelope["data"]["camera_id"] == cam.camera_id

        actions = session.exec(
            select(AuditLog.action).where(AuditLog.target_ref == str(cam.camera_id))
        ).all()
        assert actions.count("CAMERA_RESTORE") == 1

    def test_restore_collision_on_taken_name_is_409(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        make_camera(session, name="Taken Restore Name", channel_id=411)
        deleted = make_camera(session, name="Old Name", channel_id=412)
        client.delete(f"/api/cameras/{deleted.camera_id}", headers=headers)

        resp = client.patch(
            f"/api/cameras/{deleted.camera_id}",
            headers=headers,
            json={"is_active": True, "camera_name": "Taken Restore Name"},
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == "CONFLICT_DUPLICATE"

    def test_restore_collision_on_taken_name_case_insensitive_is_409(
        self, client: TestClient, session: Session
    ):
        """The unique index is on lower(camera_name) — "Case Cam" and
        "case cam" collide even though neither string matches exactly.
        The soft-deleted camera is seeded directly with is_active=False
        (rather than created-then-deleted) — creating it active first would
        itself collide with the live "Case Cam" at insert time, since the
        partial index only exempts rows that are already inactive."""
        headers = _headers(client, session)
        make_camera(session, name="Case Cam", channel_id=413)
        deleted = make_camera(session, name="case cam", channel_id=414, is_active=False)

        resp = client.patch(
            f"/api/cameras/{deleted.camera_id}",
            headers=headers,
            json={"is_active": True},
        )
        assert resp.status_code == 409, resp.text

    def test_restore_collision_on_taken_channel_id_is_409(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        make_camera(session, name="Chan Holder", channel_id=415)
        deleted = make_camera(session, name="Chan Deleted", channel_id=416)
        client.delete(f"/api/cameras/{deleted.camera_id}", headers=headers)

        resp = client.patch(
            f"/api/cameras/{deleted.camera_id}",
            headers=headers,
            json={"is_active": True, "channel_id": 415},
        )
        assert resp.status_code == 409, resp.text

    def test_patch_cannot_deactivate_an_active_camera(
        self, client: TestClient, session: Session
    ):
        """PATCH's is_active is one-directional (restore only) — the
        True -> False transition stays DELETE's job, since only DELETE
        checks for an open incident first."""
        headers = _headers(client, session)
        cam = make_camera(session, name="Guard Cam", channel_id=417)

        resp = client.patch(
            f"/api/cameras/{cam.camera_id}",
            headers=headers,
            json={"is_active": False},
        )
        assert resp.status_code == 400, resp.text

        session.refresh(cam)
        assert cam.is_active is True

    def test_delete_still_404s_on_an_already_soft_deleted_camera(
        self, client: TestClient, session: Session
    ):
        """Lookup split — DELETE stays on the active-only lookup; only
        PATCH can reach a soft-deleted row."""
        headers = _headers(client, session)
        cam = make_camera(session, name="Double Delete Cam", channel_id=418)
        client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)

        resp = client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)
        assert resp.status_code == 404

    def test_only_patch_reaches_a_soft_deleted_camera(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        cam = make_camera(session, name="Reach Cam", channel_id=419)
        client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)

        get_resp = client.get(f"/api/cameras/{cam.camera_id}", headers=headers)
        assert get_resp.status_code == 404

        patch_resp = client.patch(
            f"/api/cameras/{cam.camera_id}",
            headers=headers,
            json={"is_active": True},
        )
        assert patch_resp.status_code == 200, patch_resp.text

    def test_restored_cameras_detections_stay_linked(
        self, client: TestClient, session: Session
    ):
        """The whole point of a soft delete — a restored camera's incident
        history was never orphaned."""
        headers = _headers(client, session)
        cam = make_camera(session, name="Detections Cam", channel_id=420)
        detection = make_detection(session, cam, status=DetectionStatus.CLEARED)
        client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)

        resp = client.patch(
            f"/api/cameras/{cam.camera_id}",
            headers=headers,
            json={"is_active": True},
        )
        assert resp.status_code == 200, resp.text

        session.refresh(detection)
        assert detection.camera_id == cam.camera_id

    def test_restore_and_rename_in_same_request_produces_both_actions(
        self, client: TestClient, session: Session
    ):
        """D-007 multi-action semantics — restoring and renaming together
        produce both CAMERA_RESTORE and CAMERA_UPDATE, same transaction."""
        headers = _headers(client, session)
        cam = make_camera(session, name="Combo Cam", channel_id=421)
        client.delete(f"/api/cameras/{cam.camera_id}", headers=headers)

        resp = client.patch(
            f"/api/cameras/{cam.camera_id}",
            headers=headers,
            json={"is_active": True, "camera_name": "Combo Cam Renamed"},
        )
        assert resp.status_code == 200, resp.text

        actions = session.exec(
            select(AuditLog.action).where(AuditLog.target_ref == str(cam.camera_id))
        ).all()
        assert actions.count("CAMERA_RESTORE") == 1
        assert actions.count("CAMERA_UPDATE") == 1

    def test_is_active_true_on_an_already_active_camera_is_not_audited_as_restore(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        cam = make_camera(session, name="Already Active Cam", channel_id=422)

        resp = client.patch(
            f"/api/cameras/{cam.camera_id}",
            headers=headers,
            json={"is_active": True},
        )
        assert resp.status_code == 200, resp.text

        actions = session.exec(
            select(AuditLog.action).where(AuditLog.target_ref == str(cam.camera_id))
        ).all()
        assert "CAMERA_RESTORE" not in actions
