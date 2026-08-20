"""
Tests for app.services.audit (D-007) and GET /api/audit-logs — TC-S-501...505
and 14_EDGE_CASES.md rows 3.14, 9.2, plus the package doc's "Tests to write"
table for audit coupling, redaction, multi-action, and the viewer.
"""

import csv
from datetime import UTC, datetime
from io import StringIO

import pytest
from alembic import command
from app.core.config import Settings, settings
from app.core.db import create_db_engine
from app.core.migrations import get_alembic_config
from app.core.security import create_session_token
from app.models import AuditLog, AuditResult, Camera
from app.services import audit
from app.services.sessions import create_session
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from .conftest import auth_headers, make_admin, make_camera, make_operator


def _cookie_header_for(session: Session, user) -> dict:
    """Authenticates without going through POST /login, so no LOGIN_SUCCESS
    row is written — needed for tests that assert an exact row count."""
    auth_session = create_session(session, user, user_agent=None, source_ip=None)
    session.commit()
    token = create_session_token(user, auth_session)
    return {"Cookie": f"{settings.SESSION_COOKIE_NAME}={token}"}


class TestAuditCoupling:
    def test_forcing_the_audit_insert_to_fail_rolls_back_the_primary_action(
        self, session: Session
    ):
        camera = Camera(camera_name="RollbackCam", channel_id=987)
        session.add(camera)
        session.flush()
        audit.record(
            session,
            action="NOT_A_REAL_ACTION",
            result=AuditResult.SUCCESS,
            target_type="camera",
            target_ref=str(camera.camera_id),
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        found = session.exec(
            select(Camera).where(Camera.camera_name == "RollbackCam")
        ).first()
        assert found is None

    def test_denied_guard_rejection_still_produces_a_row_after_rollback(
        self, client: TestClient, session: Session
    ):
        """Last-admin-demote guard: nothing is written to the user row, but
        the denied attempt is still audited via a separate transaction."""
        admin = make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.patch(
            f"/api/users/{admin.user_id}",
            json={"role": "Operator"},
            headers=headers,
        )
        assert resp.status_code == 400

        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "USER_ROLE_CHANGE")
        ).all()
        assert len(rows) == 1
        assert rows[0].result == "denied"

    def test_self_delete_guard_is_audited_denied(
        self, client: TestClient, session: Session
    ):
        make_admin(session, username="admin1")
        admin2 = make_admin(session, username="admin2")
        headers = auth_headers(client, "admin2", "Admin123")
        resp = client.delete(f"/api/users/{admin2.user_id}", headers=headers)
        assert resp.status_code == 400

        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "USER_DISABLE")
        ).all()
        assert any(r.result == "denied" for r in rows)


class TestAuditRedaction:
    def test_password_token_apikey_url_and_paths_never_survive(self, session: Session):
        detail = {
            "password": "hunter2",
            "note": (
                "token=abc123 rtsp://admin:hunter2@10.0.5.50:554/cam "
                f"path={settings.SNAPSHOT_ROOT / 'x.jpg'}"
            ),
            "api_key": settings.INTERNAL_API_KEY.get_secret_value(),
        }
        row = audit.record(
            session, action="LOGIN_SUCCESS", result=AuditResult.SUCCESS, detail=detail
        )
        session.commit()
        session.refresh(row)

        assert row.detail is not None
        assert "hunter2" not in row.detail
        assert settings.INTERNAL_API_KEY.get_secret_value() not in row.detail
        assert str(settings.SNAPSHOT_ROOT) not in row.detail
        assert "rtsp://admin:hunter2" not in row.detail
        assert "***REDACTED***" in row.detail

    def test_password_reset_does_not_leak_new_password(
        self, client: TestClient, session: Session
    ):
        """Edge case 8.15."""
        make_admin(session)
        op = make_operator(session)
        headers = auth_headers(client, "admin", "Admin123")
        client.post(
            f"/api/users/{op.user_id}/reset-password",
            json={"new_password": "SuperSecret9"},
            headers=headers,
        )
        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "USER_PASSWORD_RESET")
        ).all()
        assert len(rows) == 1
        assert rows[0].detail is None or "SuperSecret9" not in rows[0].detail


class TestMultiAction:
    def test_camera_rename_and_disable_writes_exactly_two_rows(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        camera = make_camera(session, name="Old Name", channel_id=42)

        resp = client.patch(
            f"/api/cameras/{camera.camera_id}",
            json={"camera_name": "New Name", "is_enabled": False},
            headers=headers,
        )
        assert resp.status_code == 200

        rows = session.exec(
            select(AuditLog).where(
                AuditLog.target_type == "camera",
                AuditLog.target_ref == str(camera.camera_id),
            )
        ).all()
        assert len(rows) == 2
        assert {r.action for r in rows} == {"CAMERA_UPDATE", "CAMERA_DISABLE"}

    def test_disabling_alone_writes_only_camera_disable(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        camera = make_camera(session, name="Solo Cam", channel_id=43)

        resp = client.patch(
            f"/api/cameras/{camera.camera_id}",
            json={"is_enabled": False},
            headers=headers,
        )
        assert resp.status_code == 200

        rows = session.exec(
            select(AuditLog).where(
                AuditLog.target_type == "camera",
                AuditLog.target_ref == str(camera.camera_id),
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].action == "CAMERA_DISABLE"

    def test_user_update_base_action_plus_role_change(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        op = make_operator(session)
        headers = auth_headers(client, "admin", "Admin123")

        resp = client.patch(
            f"/api/users/{op.user_id}",
            json={"first_name": "Renamed", "role": "Admin"},
            headers=headers,
        )
        assert resp.status_code == 200

        rows = session.exec(
            select(AuditLog).where(
                AuditLog.target_type == "user",
                AuditLog.target_ref == str(op.user_id),
            )
        ).all()
        assert {r.action for r in rows} == {"USER_UPDATE", "USER_ROLE_CHANGE"}


class TestSinceRenamedUserSnapshot:
    def test_audit_row_keeps_the_username_at_time_of_action(
        self, client: TestClient, session: Session
    ):
        """Edge case 9.2."""
        make_admin(session)
        op = make_operator(session, username="original_name")
        admin_headers = auth_headers(client, "admin", "Admin123")
        op_headers = auth_headers(client, "original_name", "Operator123")

        client.patch(
            "/api/users/me", json={"username": "renamed_now"}, headers=op_headers
        )

        row = session.exec(
            select(AuditLog).where(AuditLog.action == "USER_PROFILE_UPDATE")
        ).first()
        assert row is not None
        assert row.username == "original_name"

        session.refresh(op)
        assert op.username == "renamed_now"
        assert admin_headers  # keeps the admin fixture alive/used


class TestAuditViewer:
    def test_fresh_database_returns_empty_page(
        self, client: TestClient, session: Session
    ):
        """Edge case 3.14 — empty page, correct total_filtered, no crash.
        Authenticates without POST /login so no LOGIN_SUCCESS row exists."""
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)
        assert session.exec(select(AuditLog)).all() == []

        resp = client.get("/api/audit-logs/", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"total_filtered": 0, "items": []}

    @pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
    def test_pagination_boundary_rejections(
        self, client: TestClient, session: Session, query: str
    ):
        """Edge case 2.1/2.2 (be_audit/00_FINDINGS.md F29)."""
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)
        resp = client.get(f"/api/audit-logs/?{query}", headers=headers)
        assert resp.status_code == 422

    @pytest.mark.parametrize("query", ["limit=1", "limit=100", "offset=0"])
    def test_pagination_boundary_accepted(
        self, client: TestClient, session: Session, query: str
    ):
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)
        resp = client.get(f"/api/audit-logs/?{query}", headers=headers)
        assert resp.status_code == 200

    def test_offset_beyond_total_returns_empty_page_with_correct_total(
        self, client: TestClient, session: Session
    ):
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)
        # make_admin itself commits a couple of rows via its own setup;
        # what matters is total_filtered agreeing with an empty items list.
        total = client.get("/api/audit-logs/", headers=headers).json()["total_filtered"]

        resp = client.get("/api/audit-logs/?offset=100000", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == total
        assert body["items"] == []

    def test_viewer_stable_pagination_no_duplicates_or_gaps(
        self, client: TestClient, session: Session
    ):
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)

        # Five rows sharing the exact same created_at — only audit_id can
        # break the tie, proving the (created_at DESC, audit_id DESC) order
        # is what keeps pagination stable.
        from datetime import UTC, datetime

        same_instant = datetime.now(UTC)
        for _ in range(5):
            row = AuditLog(
                actor_type="system",
                action="LOGIN_SUCCESS",
                result="success",
                created_at=same_instant,
            )
            session.add(row)
        session.commit()

        page1 = client.get("/api/audit-logs/?limit=2&offset=0", headers=headers).json()
        page2 = client.get("/api/audit-logs/?limit=2&offset=2", headers=headers).json()
        page3 = client.get("/api/audit-logs/?limit=2&offset=4", headers=headers).json()

        assert page1["total_filtered"] == 5
        all_ids = (
            [i["audit_id"] for i in page1["items"]]
            + [i["audit_id"] for i in page2["items"]]
            + [i["audit_id"] for i in page3["items"]]
        )
        assert len(all_ids) == len(set(all_ids)) == 5
        assert all_ids == sorted(all_ids, reverse=True)

    def test_filter_by_action(self, client: TestClient, session: Session):
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)
        session.add(AuditLog(actor_type="system", action="LOGOUT", result="success"))
        session.add(
            AuditLog(actor_type="system", action="CAMERA_DELETE", result="success")
        )
        session.commit()

        resp = client.get("/api/audit-logs/?action=LOGOUT", headers=headers)
        body = resp.json()
        assert body["total_filtered"] == 1
        assert body["items"][0]["action"] == "LOGOUT"

    def test_filter_by_invalid_action_is_422(
        self, client: TestClient, session: Session
    ):
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)
        resp = client.get("/api/audit-logs/?action=NOT_REAL", headers=headers)
        assert resp.status_code == 422

    def test_filter_by_result(self, client: TestClient, session: Session):
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)
        session.add(AuditLog(actor_type="system", action="LOGOUT", result="denied"))
        session.add(AuditLog(actor_type="system", action="LOGOUT", result="success"))
        session.commit()

        resp = client.get("/api/audit-logs/?result=denied", headers=headers)
        body = resp.json()
        assert body["total_filtered"] == 1
        assert body["items"][0]["result"] == "denied"

    def test_filter_by_user_id(self, client: TestClient, session: Session):
        admin = make_admin(session)
        op = make_operator(session)
        headers = _cookie_header_for(session, admin)
        session.add(
            AuditLog(
                actor_type="user",
                user_id=op.user_id,
                username=op.username,
                action="LOGOUT",
                result="success",
            )
        )
        session.commit()

        resp = client.get(f"/api/audit-logs/?user_id={op.user_id}", headers=headers)
        assert resp.json()["total_filtered"] == 1

    def test_filter_by_target_type_and_ref(self, client: TestClient, session: Session):
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)
        session.add(
            AuditLog(
                actor_type="system",
                action="CAMERA_DELETE",
                result="success",
                target_type="camera",
                target_ref="7",
            )
        )
        session.commit()

        resp = client.get(
            "/api/audit-logs/?target_type=camera&target_ref=7", headers=headers
        )
        assert resp.json()["total_filtered"] == 1

    def test_filter_by_date_range(self, client: TestClient, session: Session):
        from datetime import UTC, datetime, timedelta

        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)
        old = AuditLog(
            actor_type="system",
            action="LOGOUT",
            result="success",
            created_at=datetime.now(UTC) - timedelta(days=10),
        )
        session.add(old)
        session.commit()

        start = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        resp = client.get(
            "/api/audit-logs/", params={"start_date": start}, headers=headers
        )
        assert resp.status_code == 200
        assert old.audit_id not in [i["audit_id"] for i in resp.json()["items"]]

    def test_date_range_start_after_end_is_422(
        self, client: TestClient, session: Session
    ):
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)
        resp = client.get(
            "/api/audit-logs/?start_date=2026-06-02T00:00:00Z"
            "&end_date=2026-06-01T00:00:00Z",
            headers=headers,
        )
        assert resp.status_code == 422

    def test_search_matches_username(self, client: TestClient, session: Session):
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)
        session.add(
            AuditLog(
                actor_type="user",
                username="findme_special",
                action="LOGOUT",
                result="success",
            )
        )
        session.commit()

        resp = client.get("/api/audit-logs/?search=findme_special", headers=headers)
        assert resp.json()["total_filtered"] == 1

    def test_no_update_or_delete_route_exists(
        self, client: TestClient, session: Session
    ):
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)
        row = AuditLog(actor_type="system", action="LOGOUT", result="success")
        session.add(row)
        session.commit()

        patch_resp = client.patch(
            f"/api/audit-logs/{row.audit_id}",
            json={"result": "denied"},
            headers=headers,
        )
        delete_resp = client.delete(f"/api/audit-logs/{row.audit_id}", headers=headers)
        assert patch_resp.status_code in (404, 405)
        assert delete_resp.status_code in (404, 405)


class TestAuditExport:
    def test_export_csv_does_not_contain_its_own_audit_export_row(
        self, client: TestClient, session: Session
    ):
        """07_PKG_reports.md Step 4 / the audit recursion trap: an
        AUDIT_EXPORT written by this very call must never appear in the
        file it produces."""
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)
        session.add(AuditLog(actor_type="system", action="LOGOUT", result="success"))
        session.commit()

        resp = client.get("/api/audit-logs/export", headers=headers)

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        rows = list(csv.DictReader(StringIO(resp.text[1:])))
        assert all(row["Action"] != "AUDIT_EXPORT" for row in rows)

        # But the attempt itself was audited, after the snapshot was taken.
        export_rows = session.exec(
            select(AuditLog).where(AuditLog.action == "AUDIT_EXPORT")
        ).all()
        assert len(export_rows) == 1
        assert export_rows[0].result == "success"

    def test_export_pdf(self, client: TestClient, session: Session):
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)
        session.add(AuditLog(actor_type="system", action="LOGOUT", result="success"))
        session.commit()

        resp = client.get("/api/audit-logs/export?format=pdf", headers=headers)

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "adas_audit_export.pdf" in resp.headers["content-disposition"]
        assert resp.content.startswith(b"%PDF")

    def test_export_forbidden_for_operator(self, client: TestClient, session: Session):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")

        resp = client.get("/api/audit-logs/export", headers=headers)

        assert resp.status_code == 403

    def test_export_rejects_invalid_sort_by(self, client: TestClient, session: Session):
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)

        resp = client.get("/api/audit-logs/export?sort_by=detail", headers=headers)

        assert resp.status_code == 422

    def test_export_filters_match_the_list_endpoint(
        self, client: TestClient, session: Session
    ):
        admin = make_admin(session)
        headers = _cookie_header_for(session, admin)
        session.add(AuditLog(actor_type="system", action="LOGOUT", result="success"))
        session.add(
            AuditLog(actor_type="system", action="CAMERA_DELETE", result="success")
        )
        session.commit()

        list_resp = client.get("/api/audit-logs/?action=LOGOUT", headers=headers)
        export_resp = client.get(
            "/api/audit-logs/export?action=LOGOUT", headers=headers
        )

        list_ids = [i["audit_id"] for i in list_resp.json()["items"]]
        rows = list(csv.DictReader(StringIO(export_resp.text[1:])))
        export_ids = [int(row["Audit ID"]) for row in rows]
        assert list_ids == export_ids


class TestMigratedAuditLogImmutability:
    """P23 Step 1 — adding CAMERA_RESTORE to ck_audit_action_valid needs a
    SQLite batch_alter_table move-and-copy rebuild of audit_log, which
    means trg_audit_log_no_update/trg_audit_log_no_delete get dropped and
    recreated around it. Every other test in this file runs against the
    create_all() fixture (conftest.py's `session`), which builds straight
    from the current models and would pass even if the migration itself
    forgot to recreate a trigger or silently dropped an index — only
    replaying the actual Alembic migration chain proves the rebuild left
    the trail intact."""

    @pytest.fixture()
    def migrated_engine(self, tmp_path):
        db_path = tmp_path / "p23-migrated.db"
        migration_settings = Settings(
            _env_file=None,
            SECRET_KEY="test-migration-secret",
            INTERNAL_API_KEY="test-migration-key",
            DEFAULT_ADMIN_PASSWORD="test-migration-pw",
            DATABASE_URL=f"sqlite:///{db_path}",
        )
        command.upgrade(get_alembic_config(migration_settings), "head")
        engine = create_db_engine(migration_settings)
        yield engine
        engine.dispose()

    @staticmethod
    def _insert_row(engine, action: str) -> None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO audit_log (actor_type, action, result, created_at) "
                    "VALUES ('system', :action, 'success', :created_at)"
                ),
                {"action": action, "created_at": datetime.now(UTC).isoformat()},
            )

    def test_update_raises_after_migration(self, migrated_engine):
        self._insert_row(migrated_engine, "LOGIN_SUCCESS")
        with (
            pytest.raises(Exception, match="audit_log is append-only"),
            migrated_engine.begin() as conn,
        ):
            conn.execute(text("UPDATE audit_log SET action = 'LOGOUT'"))

    def test_delete_raises_after_migration(self, migrated_engine):
        self._insert_row(migrated_engine, "LOGIN_SUCCESS")
        with (
            pytest.raises(Exception, match="audit_log is append-only"),
            migrated_engine.begin() as conn,
        ):
            conn.execute(text("DELETE FROM audit_log"))

    def test_camera_restore_is_accepted_after_migration(self, migrated_engine):
        self._insert_row(migrated_engine, "CAMERA_RESTORE")  # must not raise

    def test_unknown_action_still_rejected_after_migration(self, migrated_engine):
        with pytest.raises(Exception):  # noqa: B017 — raw IntegrityError from SQLite
            self._insert_row(migrated_engine, "NOT_A_REAL_ACTION")

    def test_all_four_audit_indexes_survive_the_rebuild(self, migrated_engine):
        with migrated_engine.connect() as conn:
            names = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'index' AND tbl_name = 'audit_log'"
                    )
                ).fetchall()
            }
        assert names == {
            "ix_audit_created_at",
            "ix_audit_action_created_at",
            "ix_audit_user_created_at",
            "ix_audit_target",
        }
