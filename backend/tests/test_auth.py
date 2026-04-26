"""
Tests for /api/auth — TC-U-201, TC-U-202, TC-U-203
Covers: login success, bad credentials, inactive account, JWT generation.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import make_admin, make_operator, get_token, auth_headers


class TestLogin:
    """TC-U-202 / TC-U-203 — Login and JWT generation."""

    def test_login_success_admin(self, client: TestClient, session: Session):
        make_admin(session)
        resp = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "Admin123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_login_success_operator(self, client: TestClient, session: Session):
        make_operator(session)
        resp = client.post(
            "/api/auth/login",
            data={"username": "operator", "password": "Operator123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client: TestClient, session: Session):
        make_admin(session)
        resp = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    def test_login_wrong_username(self, client: TestClient, session: Session):
        resp = client.post(
            "/api/auth/login",
            data={"username": "ghost", "password": "Admin123"},
        )
        assert resp.status_code == 401

    def test_login_inactive_account(self, client: TestClient, session: Session):
        """TC-U-101 alt — soft-deleted account cannot log in."""
        user = make_operator(session)
        user.is_active = False
        session.add(user)
        session.commit()

        resp = client.post(
            "/api/auth/login",
            data={"username": "operator", "password": "Operator123"},
        )
        assert resp.status_code == 400

    def test_login_empty_username(self, client: TestClient, session: Session):
        resp = client.post(
            "/api/auth/login",
            data={"username": "", "password": "Admin123"},
        )
        # FastAPI's OAuth2PasswordRequestForm requires username
        assert resp.status_code in (400, 422)

    def test_login_empty_password(self, client: TestClient, session: Session):
        resp = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": ""},
        )
        assert resp.status_code in (400, 401, 422)


class TestProtectedRoutes:
    """TC-U-203 — Token required for protected routes."""

    def test_no_token_returns_401(self, client: TestClient, session: Session):
        resp = client.get("/api/alerts/")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client: TestClient, session: Session):
        resp = client.get(
            "/api/alerts/",
            headers={"Authorization": "Bearer this.is.not.valid"},
        )
        assert resp.status_code == 401

    def test_valid_token_allows_access(self, client: TestClient, session: Session):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.get("/api/alerts/", headers=headers)
        assert resp.status_code == 200


class TestRBAC:
    """TC-U-204 / TC-S-201 / TC-S-202 — Role-based access control."""

    def test_operator_cannot_access_user_management(
        self, client: TestClient, session: Session
    ):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get("/api/users/", headers=headers)
        assert resp.status_code == 403

    def test_operator_cannot_create_user(self, client: TestClient, session: Session):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.post(
            "/api/users/",
            json={
                "username": "newuser",
                "first_name": "New",
                "last_name": "User",
                "role": "Operator",
                "password": "Newuser123",
            },
            headers=headers,
        )
        assert resp.status_code == 403

    def test_operator_cannot_delete_user(self, client: TestClient, session: Session):
        admin = make_admin(session)
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.delete(f"/api/users/{admin.user_id}", headers=headers)
        assert resp.status_code == 403

    def test_admin_can_access_user_management(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.get("/api/users/", headers=headers)
        assert resp.status_code == 200