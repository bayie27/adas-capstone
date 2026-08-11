"""
Tests for /api/users — Use Cases 2 & 3, TC-U-101 through TC-U-107,
TC-I-402, TC-S-201, TC-S-202.
Covers: CRUD, RBAC, last-admin guards, self-service, password rules.
"""

import json

import pytest
from app.models import AuditLog
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import auth_headers, make_admin, make_operator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def admin_headers(client, session):
    make_admin(session)
    return auth_headers(client, "admin", "Admin123")


# ---------------------------------------------------------------------------
# GET /api/users/me — self profile
# ---------------------------------------------------------------------------


class TestGetMyProfile:
    def test_operator_can_get_own_profile(self, client: TestClient, session: Session):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get("/api/users/me", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "operator"
        assert body["role"] == "Operator"
        # password hash must never leak
        assert "password_hash" not in body

    def test_admin_can_get_own_profile(self, client: TestClient, session: Session):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.get("/api/users/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["role"] == "Admin"


# ---------------------------------------------------------------------------
# PATCH /api/users/me — self-service profile update (Use Case 3)
# ---------------------------------------------------------------------------


class TestUpdateMyProfile:
    def test_operator_can_update_own_username(
        self, client: TestClient, session: Session
    ):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.patch(
            "/api/users/me",
            json={"username": "newoperator"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "newoperator"

    def test_operator_cannot_change_own_role(
        self, client: TestClient, session: Session
    ):
        """Operator self-service only allows username/first_name/last_name."""
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.patch(
            "/api/users/me",
            json={"role": "Admin"},
            headers=headers,
        )
        # role field is not in UserOperatorUpdate — should be ignored or 422
        # Either way the role must not change
        if resp.status_code == 200:
            assert resp.json()["role"] == "Operator"

    def test_duplicate_username_rejected(self, client: TestClient, session: Session):
        make_admin(session)  # username: "admin"
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.patch(
            "/api/users/me",
            json={"username": "admin"},  # already taken
            headers=headers,
        )
        assert resp.status_code == 400

    def test_username_strip_whitespace(self, client: TestClient, session: Session):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.patch(
            "/api/users/me",
            json={"username": "  cleanname  "},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "cleanname"

    def test_operator_cannot_change_own_is_active(
        self, client: TestClient, session: Session
    ):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.patch(
            "/api/users/me",
            json={"is_active": False},
            headers=headers,
        )
        if resp.status_code == 200:
            assert resp.json()["is_active"] is True


# ---------------------------------------------------------------------------
# PATCH /api/users/me/password — self-service password change
# ---------------------------------------------------------------------------


class TestChangeMyPassword:
    def test_operator_can_change_own_password(
        self, client: TestClient, session: Session
    ):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.patch(
            "/api/users/me/password",
            json={"old_password": "Operator123", "new_password": "NewPass456"},
            headers=headers,
        )
        assert resp.status_code == 204

        # Verify can now log in with new password
        login = client.post(
            "/api/auth/login",
            data={"username": "operator", "password": "NewPass456"},
        )
        assert login.status_code == 200

    def test_wrong_old_password_rejected(self, client: TestClient, session: Session):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.patch(
            "/api/users/me/password",
            json={"old_password": "WrongOld1", "new_password": "NewPass456"},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_new_password_too_short(self, client: TestClient, session: Session):
        """TC-U-102 — password complexity validation."""
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.patch(
            "/api/users/me/password",
            json={"old_password": "Operator123", "new_password": "short"},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_new_password_no_number_rejected(
        self, client: TestClient, session: Session
    ):
        """Password must contain at least one number."""
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.patch(
            "/api/users/me/password",
            json={"old_password": "Operator123", "new_password": "NoNumbersHere"},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_password_mismatch_scenario(self, client: TestClient, session: Session):
        """TC-U-107 — if old_password matches but new passwords would differ (API layer)."""
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        # API doesn't have confirm_password field — that's validated on the frontend.
        # Backend just needs new_password to be valid.
        resp = client.patch(
            "/api/users/me/password",
            json={"old_password": "Operator123", "new_password": "Valid456"},
            headers=headers,
        )
        assert resp.status_code == 204

    # ---------------------------------------------------------------------------
    # GET /api/users/ — admin user directory
    # ---------------------------------------------------------------------------

    def test_password_changed_at_is_updated(self, client: TestClient, session: Session):
        operator = make_operator(session)
        original_changed_at = operator.password_changed_at
        headers = auth_headers(client, "operator", "Operator123")

        resp = client.patch(
            "/api/users/me/password",
            json={"old_password": "Operator123", "new_password": "NewPass456"},
            headers=headers,
        )

        assert resp.status_code == 204
        session.refresh(operator)
        assert operator.password_changed_at is not None
        assert operator.password_changed_at != original_changed_at


class TestGetAllUsers:
    def test_admin_gets_paginated_list(self, client: TestClient, session: Session):
        make_admin(session)
        make_operator(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.get("/api/users/", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "total_filtered" in body
        assert "users" in body
        assert body["total_filtered"] == 2

    def test_search_by_username(self, client: TestClient, session: Session):
        make_admin(session)
        make_operator(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.get("/api/users/?search=operator", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 1
        assert body["users"][0]["username"] == "operator"

    def test_pagination_limit(self, client: TestClient, session: Session):
        make_admin(session)
        make_operator(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.get("/api/users/?limit=1&offset=0", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()["users"]) == 1

    def test_operator_cannot_list_users(self, client: TestClient, session: Session):
        make_admin(session)
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get("/api/users/", headers=headers)
        assert resp.status_code == 403

    @pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
    def test_pagination_boundary_rejections(
        self, client: TestClient, session: Session, query: str
    ):
        """Edge case 2.1/2.2 (be_audit/00_FINDINGS.md F27)."""
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.get(f"/api/users/?{query}", headers=headers)
        assert resp.status_code == 422

    @pytest.mark.parametrize("query", ["limit=1", "limit=100", "offset=0"])
    def test_pagination_boundary_accepted(
        self, client: TestClient, session: Session, query: str
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.get(f"/api/users/?{query}", headers=headers)
        assert resp.status_code == 200

    def test_offset_beyond_total_returns_empty_page_with_correct_total(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        total = client.get("/api/users/", headers=headers).json()["total_filtered"]

        resp = client.get("/api/users/?offset=100000", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == total
        assert body["users"] == []

    def test_soft_deleted_users_excluded(self, client: TestClient, session: Session):
        make_admin(session)
        op = make_operator(session)
        op.is_active = False
        session.add(op)
        session.commit()

        headers = auth_headers(client, "admin", "Admin123")
        resp = client.get("/api/users/", headers=headers)
        assert resp.json()["total_filtered"] == 1  # only admin


# ---------------------------------------------------------------------------
# POST /api/users/ — admin creates user (TC-I-402)
# ---------------------------------------------------------------------------


class TestCreateUser:
    def test_admin_creates_operator(self, client: TestClient, session: Session):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.post(
            "/api/users/",
            json={
                "username": "newop",
                "first_name": "New",
                "last_name": "Operator",
                "role": "Operator",
                "password": "Newop1234",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["username"] == "newop"
        assert body["role"] == "Operator"
        assert "password_hash" not in body

    def test_duplicate_username_rejected(self, client: TestClient, session: Session):
        """TC-U-101 alt — duplicate username prevention."""
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        # Create once
        client.post(
            "/api/users/",
            json={
                "username": "dupuser",
                "first_name": "A",
                "last_name": "B",
                "role": "Operator",
                "password": "Dupuser1",
            },
            headers=headers,
        )
        # Create again with same username
        resp = client.post(
            "/api/users/",
            json={
                "username": "dupuser",
                "first_name": "C",
                "last_name": "D",
                "role": "Operator",
                "password": "Dupuser1",
            },
            headers=headers,
        )
        assert resp.status_code == 400

    def test_weak_password_rejected(self, client: TestClient, session: Session):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.post(
            "/api/users/",
            json={
                "username": "weakpass",
                "first_name": "A",
                "last_name": "B",
                "role": "Operator",
                "password": "nodigits",
            },
            headers=headers,
        )
        assert resp.status_code == 422

    def test_created_user_can_login(self, client: TestClient, session: Session):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        client.post(
            "/api/users/",
            json={
                "username": "freshuser",
                "first_name": "Fresh",
                "last_name": "User",
                "role": "Operator",
                "password": "Fresh1234",
            },
            headers=headers,
        )
        login = client.post(
            "/api/auth/login",
            data={"username": "freshuser", "password": "Fresh1234"},
        )
        assert login.status_code == 200


# ---------------------------------------------------------------------------
# PATCH /api/users/{user_id} — admin edits user
# ---------------------------------------------------------------------------


class TestUpdateUser:
    def test_admin_can_edit_operator(self, client: TestClient, session: Session):
        make_admin(session)
        op = make_operator(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.patch(
            f"/api/users/{op.user_id}",
            json={"first_name": "Updated"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["first_name"] == "Updated"

    def test_admin_can_promote_operator(self, client: TestClient, session: Session):
        make_admin(session)
        op = make_operator(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.patch(
            f"/api/users/{op.user_id}",
            json={"role": "Admin"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "Admin"

    def test_cannot_demote_last_admin(self, client: TestClient, session: Session):
        """TC-U-105 alt / Use Case 2 — last admin lockout prevention."""
        admin = make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.patch(
            f"/api/users/{admin.user_id}",
            json={"role": "Operator"},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_cannot_deactivate_last_admin(self, client: TestClient, session: Session):
        admin = make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.patch(
            f"/api/users/{admin.user_id}",
            json={"is_active": False},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_cannot_deactivate_last_admin_is_audited_denied(
        self, client: TestClient, session: Session
    ):
        """Edge case 8.16 (be_audit/00_FINDINGS.md F25) — the refusal
        alone was already covered above; this pins the audit trail too, so
        a future change that silently dropped the denied-audit write for
        this guard would fail a test."""
        admin = make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        client.patch(
            f"/api/users/{admin.user_id}",
            json={"is_active": False},
            headers=headers,
        )
        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "USER_DISABLE")
        ).all()
        assert len(rows) == 1
        assert rows[0].result == "denied"
        assert json.loads(rows[0].detail) == {"reason": "last_admin_deactivate"}

    def test_can_demote_admin_when_another_exists(
        self, client: TestClient, session: Session
    ):
        make_admin(session, username="admin1")
        admin2 = make_admin(session, username="admin2")
        headers = auth_headers(client, "admin1", "Admin123")
        resp = client.patch(
            f"/api/users/{admin2.user_id}",
            json={"role": "Operator"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "Operator"

    def test_duplicate_username_on_update_rejected(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        op1 = make_operator(session, username="operator1", password="Operator123")
        op2 = make_operator(session, username="operator2", password="Operator223")
        headers = auth_headers(client, "admin", "Admin123")

        resp = client.patch(
            f"/api/users/{op2.user_id}",
            json={"username": op1.username},
            headers=headers,
        )

        assert resp.status_code == 400

    def test_can_deactivate_admin_when_another_exists(
        self, client: TestClient, session: Session
    ):
        make_admin(session, username="admin1")
        admin2 = make_admin(session, username="admin2")
        headers = auth_headers(client, "admin1", "Admin123")

        resp = client.patch(
            f"/api/users/{admin2.user_id}",
            json={"is_active": False},
            headers=headers,
        )

        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_edit_nonexistent_user_returns_404(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.patch(
            "/api/users/99999", json={"first_name": "Ghost"}, headers=headers
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/users/{user_id}/reset-password — admin force reset
# ---------------------------------------------------------------------------


class TestResetPassword:
    def test_admin_can_reset_operator_password(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        op = make_operator(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.post(
            f"/api/users/{op.user_id}/reset-password",
            json={"new_password": "Resetpass1"},
            headers=headers,
        )
        assert resp.status_code == 204

        # Operator can now login with new password
        login = client.post(
            "/api/auth/login",
            data={"username": "operator", "password": "Resetpass1"},
        )
        assert login.status_code == 200

    def test_reset_password_complexity_enforced(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        op = make_operator(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.post(
            f"/api/users/{op.user_id}/reset-password",
            json={"new_password": "weakpass"},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_operator_cannot_reset_others_password(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        op = make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.post(
            f"/api/users/{op.user_id}/reset-password",
            json={"new_password": "Resetpass1"},
            headers=headers,
        )
        assert resp.status_code == 403

    # ---------------------------------------------------------------------------
    # DELETE /api/users/{user_id} — admin soft delete
    # ---------------------------------------------------------------------------

    def test_reset_password_nonexistent_user_returns_404(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.post(
            "/api/users/99999/reset-password",
            json={"new_password": "Resetpass1"},
            headers=headers,
        )
        assert resp.status_code == 404


class TestDeleteUser:
    def test_admin_can_delete_operator(self, client: TestClient, session: Session):
        make_admin(session)
        op = make_operator(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.delete(f"/api/users/{op.user_id}", headers=headers)
        assert resp.status_code == 204

        # Deleted operator cannot log in
        login = client.post(
            "/api/auth/login",
            data={"username": "operator", "password": "Operator123"},
        )
        # Same generic AUTH_INVALID_CREDENTIALS as unknown user / wrong
        # password (D-006) — a deactivated account no longer gets its own
        # distinguishable status code.
        assert login.status_code == 401

    def test_cannot_delete_last_admin(self, client: TestClient, session: Session):
        """Use Case 2 — last admin lockout guard."""
        admin = make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.delete(f"/api/users/{admin.user_id}", headers=headers)
        assert resp.status_code == 400

    def test_cannot_delete_self(self, client: TestClient, session: Session):
        """Use Case 2 — self-deletion guard."""
        make_admin(session, username="admin1")
        admin2 = make_admin(session, username="admin2")
        headers = auth_headers(client, "admin2", "Admin123")
        resp = client.delete(f"/api/users/{admin2.user_id}", headers=headers)
        assert resp.status_code == 400

    def test_cannot_delete_last_admin_is_audited_denied(
        self, client: TestClient, session: Session
    ):
        """Edge case 8.16 (be_audit/00_FINDINGS.md F25) — pins the audit
        trail for test_cannot_delete_last_admin above (self-targeting, so
        it actually exercises the self_delete guard, not last_admin_delete
        — see the next test for that one)."""
        admin = make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        client.delete(f"/api/users/{admin.user_id}", headers=headers)
        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "USER_DISABLE")
        ).all()
        assert len(rows) == 1
        assert rows[0].result == "denied"
        assert json.loads(rows[0].detail) == {"reason": "self_delete"}

    def test_cannot_delete_last_admin_non_self_is_audited_denied(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """Edge case 8.16's fourth variant — deleting a *different* admin
        who happens to be the last active one. Unreachable through the
        ordinary sequential API: `delete_user`'s self-delete guard runs
        first, and if the caller is a currently-active admin and the
        active-admin count is <= 1, the caller must *be* that one admin, so
        target_id == current_admin.user_id every time — the self-delete
        branch always wins first. The only way to reach the non-self
        last_admin_delete branch is a race (the count going stale between
        this route's read and its guard check) or, as here, isolating the
        guard directly by forcing _get_active_admin_count()'s return value
        — exactly the kind of race F21/F24 showed is worth taking
        seriously rather than dismissing as untestable."""
        import app.api.routes.users as users_module

        make_admin(session, username="admin1")
        admin2 = make_admin(session, username="admin2")
        headers = auth_headers(client, "admin1", "Admin123")
        monkeypatch.setattr(users_module, "_get_active_admin_count", lambda session: 1)

        resp = client.delete(f"/api/users/{admin2.user_id}", headers=headers)

        assert resp.status_code == 400
        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "USER_DISABLE")
        ).all()
        assert len(rows) == 1
        assert rows[0].result == "denied"
        assert json.loads(rows[0].detail) == {"reason": "last_admin_delete"}

    def test_delete_is_soft_not_hard(self, client: TestClient, session: Session):
        """Historical audit trail must be preserved — use Case 2 postcondition."""
        make_admin(session)
        op = make_operator(session)
        op_id = op.user_id
        headers = auth_headers(client, "admin", "Admin123")

        client.delete(f"/api/users/{op_id}", headers=headers)

        # User still exists in DB with is_active=False
        session.refresh(op)
        assert op.is_active is False

    def test_delete_nonexistent_user_returns_404(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.delete("/api/users/99999", headers=headers)
        assert resp.status_code == 404
