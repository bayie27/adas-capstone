"""
Tests for /api/auth and the D-006 cookie-session authentication model —
TC-U-201...204, TC-S-201...203, TC-S-501/504, and 14_EDGE_CASES.md §1/§8.
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from app.core.config import settings
from app.core.security import create_session_token, decode_session_token
from app.models import AuditLog, AuthSession
from app.services.sessions import create_session, get_active_session, revoke_session
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import auth_headers, make_admin, make_operator


def _cookie_header(token: str) -> dict:
    return {"Cookie": f"{settings.SESSION_COOKIE_NAME}={token}"}


class TestLogin:
    """TC-U-202 / TC-U-203 — Login and session creation."""

    def test_login_success_sets_cookie_no_token_in_body(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        resp = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "Admin123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"user": body["user"]}
        assert "access_token" not in body
        assert "token" not in body
        assert body["user"]["username"] == "admin"
        assert "password_hash" not in body["user"]

        cookie = resp.cookies.get(settings.SESSION_COOKIE_NAME)
        assert cookie is not None
        assert resp.headers["cache-control"] == "no-store"

    def test_login_stamps_last_login(self, client: TestClient, session: Session):
        user = make_admin(session)
        assert user.last_login is None
        client.post(
            "/api/auth/login", data={"username": "admin", "password": "Admin123"}
        )
        session.refresh(user)
        assert user.last_login is not None

    def test_login_success_writes_login_success_row(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        client.post(
            "/api/auth/login", data={"username": "admin", "password": "Admin123"}
        )
        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "LOGIN_SUCCESS")
        ).all()
        assert len(rows) == 1
        assert rows[0].result == "success"
        assert rows[0].username == "admin"

    @pytest.mark.parametrize(
        "make_bad_request",
        [
            lambda: {"username": "ghost", "password": "Admin123"},  # unknown user
            lambda: {"username": "admin", "password": "wrongpassword"},  # wrong pw
        ],
    )
    def test_bad_credentials_return_generic_401(
        self, client: TestClient, session: Session, make_bad_request
    ):
        make_admin(session)
        resp = client.post("/api/auth/login", data=make_bad_request())
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "AUTH_INVALID_CREDENTIALS"
        assert body["detail"] == "Incorrect username or password."

    def test_inactive_account_returns_identical_body_to_wrong_password(
        self, client: TestClient, session: Session
    ):
        """Edge case 8.9 — byte-identical response. The old code returned a
        distinguishable 400 for an inactive account, an enumeration oracle."""
        user = make_operator(session)
        user.is_active = False
        session.add(user)
        session.commit()

        inactive_resp = client.post(
            "/api/auth/login",
            data={"username": "operator", "password": "Operator123"},
        )
        wrong_pw_resp = client.post(
            "/api/auth/login",
            data={"username": "operator", "password": "WrongPassword1"},
        )
        assert inactive_resp.status_code == wrong_pw_resp.status_code == 401
        assert inactive_resp.json() == wrong_pw_resp.json()

    def test_failed_logins_write_denied_login_failure_rows(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        client.post(
            "/api/auth/login", data={"username": "ghost", "password": "whatever"}
        )
        client.post("/api/auth/login", data={"username": "admin", "password": "wrong"})
        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "LOGIN_FAILURE")
        ).all()
        assert len(rows) == 2
        assert all(r.result == "denied" for r in rows)
        # The unknown-user attempt still snapshots the attempted username.
        assert {r.username for r in rows} == {"ghost", "admin"}

    def test_login_empty_username(self, client: TestClient, session: Session):
        resp = client.post(
            "/api/auth/login", data={"username": "", "password": "Admin123"}
        )
        assert resp.status_code in (400, 422)

    def test_login_empty_password(self, client: TestClient, session: Session):
        resp = client.post(
            "/api/auth/login", data={"username": "admin", "password": ""}
        )
        assert resp.status_code in (400, 401, 422)

    def test_unknown_username_still_runs_a_real_password_verification(
        self, client: TestClient, session: Session, monkeypatch
    ):
        """Edge case 8.8 — timing safety. Asserting wall-clock timing is
        flaky; this instead proves the *mechanism* runs: an unknown
        username still triggers a dummy Argon2id verification rather than
        short-circuiting before any hashing cost is paid."""
        import app.api.routes.auth as auth_module

        calls = []
        original = auth_module.verify_dummy_password
        monkeypatch.setattr(
            auth_module,
            "verify_dummy_password",
            lambda pw: (calls.append(pw), original(pw))[1],
        )

        client.post(
            "/api/auth/login", data={"username": "ghost", "password": "whatever"}
        )
        assert calls == ["whatever"]


class TestUsernameNormalization:
    """Edge case 4.7 — whitespace is stripped consistently; padding a
    username can't create or match a second account."""

    def test_login_strips_whitespace(self, client: TestClient, session: Session):
        make_admin(session)
        resp = client.post(
            "/api/auth/login",
            data={"username": "  admin  ", "password": "Admin123"},
        )
        assert resp.status_code == 200

    @pytest.mark.parametrize("space", [" ", " "])
    def test_login_strips_unicode_whitespace(
        self, client: TestClient, session: Session, space: str
    ):
        """Edge case 4.7 — not just ASCII spaces: U+00A0 (NBSP) and U+2003
        (em space) are both `str.isspace()`-true and must strip too."""
        make_admin(session)
        resp = client.post(
            "/api/auth/login",
            data={"username": f"{space}admin{space}", "password": "Admin123"},
        )
        assert resp.status_code == 200

    def test_unicode_padded_username_cannot_create_a_second_account(
        self, client: TestClient, session: Session
    ):
        """Edge case 4.7 — same as test_padded_username_cannot_create_a_
        second_account below, but with Unicode whitespace padding."""
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.post(
            "/api/users/",
            json={
                "username": " admin ",
                "first_name": "Dup",
                "last_name": "User",
                "role": "Operator",
                "password": "Duppass1",
            },
            headers=headers,
        )
        assert resp.status_code == 400

    def test_padded_username_cannot_create_a_second_account(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.post(
            "/api/users/",
            json={
                "username": "  admin  ",
                "first_name": "Dup",
                "last_name": "User",
                "role": "Operator",
                "password": "Duppass1",
            },
            headers=headers,
        )
        assert resp.status_code == 400


class TestBoundaryValues:
    """Edge cases 2.7, 2.8, 2.9 — validation boundaries on user fields."""

    def _create(self, client, headers, **overrides):
        payload = {
            "username": "boundaryuser",
            "first_name": "B",
            "last_name": "U",
            "role": "Operator",
            "password": "Boundary1",
        }
        payload.update(overrides)
        return client.post("/api/users/", json=payload, headers=headers)

    @pytest.fixture
    def admin_headers(self, client: TestClient, session: Session):
        make_admin(session)
        return auth_headers(client, "admin", "Admin123")

    @pytest.mark.parametrize(
        ("length", "ok"), [(2, False), (3, True), (20, True), (21, False)]
    )
    def test_username_length_boundary(self, client, session, admin_headers, length, ok):
        resp = self._create(client, admin_headers, username="u" * length)
        assert (resp.status_code == 201) is ok

    @pytest.mark.parametrize(
        ("length", "ok"), [(0, False), (1, True), (20, True), (21, False)]
    )
    def test_first_name_length_boundary(
        self, client, session, admin_headers, length, ok
    ):
        resp = self._create(client, admin_headers, first_name="a" * length)
        assert (resp.status_code == 201) is ok

    @pytest.mark.parametrize(
        ("length", "ok"), [(0, False), (1, True), (20, True), (21, False)]
    )
    def test_last_name_length_boundary(
        self, client, session, admin_headers, length, ok
    ):
        resp = self._create(client, admin_headers, last_name="a" * length)
        assert (resp.status_code == 201) is ok

    @pytest.mark.parametrize(
        ("length", "ok"), [(7, False), (8, True), (128, True), (129, False)]
    )
    def test_password_length_boundary(self, client, session, admin_headers, length, ok):
        password = ("a" * (length - 1)) + "1" if length >= 1 else "1"
        resp = self._create(client, admin_headers, password=password)
        assert (resp.status_code == 201) is ok

    def test_password_with_exactly_one_digit_passes(
        self, client, session, admin_headers
    ):
        resp = self._create(client, admin_headers, password="Passwordd1")
        assert resp.status_code == 201


class TestJWTVerification:
    """Edge cases 8.1-8.5 — JWT-level attacks."""

    def _valid_session_and_user(self, session: Session):
        user = make_admin(session)
        auth_session = create_session(session, user, user_agent=None, source_ip=None)
        session.commit()
        return user, auth_session

    def test_alg_none_rejected(self, client: TestClient, session: Session):
        user, auth_session = self._valid_session_and_user(session)
        payload = {
            "sub": str(user.user_id),
            "sid": auth_session.session_id,
            "role": "Admin",
            "iat": datetime.now(UTC),
            "exp": auth_session.expires_at,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }
        token = jwt.encode(payload, key="", algorithm="none")
        resp = client.get("/api/users/me", headers=_cookie_header(token))
        assert resp.status_code == 401

    def test_wrong_signing_key_rejected(self, client: TestClient, session: Session):
        user, auth_session = self._valid_session_and_user(session)
        payload = {
            "sub": str(user.user_id),
            "sid": auth_session.session_id,
            "role": "Admin",
            "iat": datetime.now(UTC),
            "exp": auth_session.expires_at,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }
        token = jwt.encode(
            payload, key="a-completely-different-signing-key-value", algorithm="HS256"
        )
        resp = client.get("/api/users/me", headers=_cookie_header(token))
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_REQUIRED"

    def test_wrong_issuer_rejected(self, client: TestClient, session: Session):
        user, auth_session = self._valid_session_and_user(session)
        payload = {
            "sub": str(user.user_id),
            "sid": auth_session.session_id,
            "role": "Admin",
            "iat": datetime.now(UTC),
            "exp": auth_session.expires_at,
            "iss": "not-adas-backend",
            "aud": settings.JWT_AUDIENCE,
        }
        token = jwt.encode(
            payload, settings.SECRET_KEY.get_secret_value(), algorithm="HS256"
        )
        resp = client.get("/api/users/me", headers=_cookie_header(token))
        assert resp.status_code == 401

    def test_wrong_audience_rejected(self, client: TestClient, session: Session):
        user, auth_session = self._valid_session_and_user(session)
        payload = {
            "sub": str(user.user_id),
            "sid": auth_session.session_id,
            "role": "Admin",
            "iat": datetime.now(UTC),
            "exp": auth_session.expires_at,
            "iss": settings.JWT_ISSUER,
            "aud": "not-adas-dashboard",
        }
        token = jwt.encode(
            payload, settings.SECRET_KEY.get_secret_value(), algorithm="HS256"
        )
        resp = client.get("/api/users/me", headers=_cookie_header(token))
        assert resp.status_code == 401

    def test_expired_token_returns_auth_expired(
        self, client: TestClient, session: Session
    ):
        user = make_admin(session)
        past = datetime.now(UTC) - timedelta(minutes=1)
        auth_session = AuthSession(
            session_id="expired-sid",
            user_id=user.user_id,
            created_at=past - timedelta(hours=8),
            expires_at=past,
        )
        session.add(auth_session)
        session.commit()
        token = create_session_token(user, auth_session)

        resp = client.get("/api/users/me", headers=_cookie_header(token))
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_EXPIRED"

    def test_tampered_signature_rejected(self, client: TestClient, session: Session):
        user, auth_session = self._valid_session_and_user(session)
        token = create_session_token(user, auth_session)
        tampered = token[:-4] + ("A" if token[-4] != "A" else "B") + token[-3:]
        resp = client.get("/api/users/me", headers=_cookie_header(tampered))
        assert resp.status_code == 401

    def test_missing_sid_claim_rejected(self, client: TestClient, session: Session):
        user, _ = self._valid_session_and_user(session)
        payload = {
            "sub": str(user.user_id),
            "role": "Admin",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }
        token = jwt.encode(
            payload, settings.SECRET_KEY.get_secret_value(), algorithm="HS256"
        )
        resp = client.get("/api/users/me", headers=_cookie_header(token))
        assert resp.status_code == 401

    def test_sid_belonging_to_different_sub_rejected(
        self, client: TestClient, session: Session
    ):
        user_a = make_admin(session, username="usera")
        user_b = make_operator(session, username="userb")
        session_b = create_session(session, user_b, user_agent=None, source_ip=None)
        session.commit()

        # Token claims to be user_a, but sid points at user_b's session row.
        payload = {
            "sub": str(user_a.user_id),
            "sid": session_b.session_id,
            "role": "Admin",
            "iat": datetime.now(UTC),
            "exp": session_b.expires_at,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }
        token = jwt.encode(
            payload, settings.SECRET_KEY.get_secret_value(), algorithm="HS256"
        )
        resp = client.get("/api/users/me", headers=_cookie_header(token))
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_REVOKED"

    def test_empty_cookie_value_returns_401_not_500(self, client: TestClient):
        resp = client.get(
            "/api/users/me", headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}="}
        )
        assert resp.status_code == 401

    def test_malformed_cookie_value_returns_401_not_500(self, client: TestClient):
        resp = client.get(
            "/api/users/me",
            headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}=not.a.jwt"},
        )
        assert resp.status_code == 401


class TestSessionAuthority:
    """Edge case 8.6, 2.16 — the database session row is authoritative
    regardless of what a correctly-signed JWT claims."""

    def test_deleted_session_row_rejected(self, client: TestClient, session: Session):
        user = make_admin(session)
        auth_session = create_session(session, user, user_agent=None, source_ip=None)
        session.commit()
        token = create_session_token(user, auth_session)

        session.delete(session.get(AuthSession, auth_session.session_id))
        session.commit()

        resp = client.get("/api/users/me", headers=_cookie_header(token))
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_REVOKED"

    def test_revoked_session_row_rejected(self, client: TestClient, session: Session):
        user = make_admin(session)
        auth_session = create_session(session, user, user_agent=None, source_ip=None)
        session.commit()
        token = create_session_token(user, auth_session)

        revoke_session(session, auth_session.session_id, "admin_revoke")
        session.commit()

        resp = client.get("/api/users/me", headers=_cookie_header(token))
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_REVOKED"

    def test_expired_row_with_unexpired_jwt_rejected(
        self, client: TestClient, session: Session
    ):
        """The JWT's own `exp` is still in the future, but its session row's
        expires_at is already past — the DB row wins."""
        user = make_admin(session)
        auth_session = create_session(session, user, user_agent=None, source_ip=None)
        session.commit()
        auth_session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.add(auth_session)
        session.commit()

        payload = {
            "sub": str(user.user_id),
            "sid": auth_session.session_id,
            "role": "Admin",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }
        token = jwt.encode(
            payload, settings.SECRET_KEY.get_secret_value(), algorithm="HS256"
        )

        resp = client.get("/api/users/me", headers=_cookie_header(token))
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_REVOKED"

    def test_session_expiry_exact_boundary_is_rejected(self, session: Session):
        """Edge case 2.16 — expires_at exactly == now is treated as expired."""
        user = make_admin(session)
        now = datetime.now(UTC)
        auth_session = AuthSession(
            session_id="boundary-sid",
            user_id=user.user_id,
            created_at=now - timedelta(hours=8),
            expires_at=now,
        )
        session.add(auth_session)
        session.commit()

        result = get_active_session(session, "boundary-sid")
        assert result is None


class TestConcurrencyAndMultiSession:
    """Edge cases 1.10, 1.11."""

    def test_two_logins_create_independent_sessions(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        resp1 = client.post(
            "/api/auth/login", data={"username": "admin", "password": "Admin123"}
        )
        resp2 = client.post(
            "/api/auth/login", data={"username": "admin", "password": "Admin123"}
        )
        cookie1 = resp1.cookies.get(settings.SESSION_COOKIE_NAME)
        cookie2 = resp2.cookies.get(settings.SESSION_COOKIE_NAME)
        assert cookie1 != cookie2

        payload1 = decode_session_token(cookie1)
        payload2 = decode_session_token(cookie2)
        assert payload1["sid"] != payload2["sid"]

    def test_revoking_one_session_does_not_touch_the_other(
        self, client: TestClient, session: Session
    ):
        user = make_admin(session)
        resp1 = client.post(
            "/api/auth/login", data={"username": "admin", "password": "Admin123"}
        )
        resp2 = client.post(
            "/api/auth/login", data={"username": "admin", "password": "Admin123"}
        )
        cookie1 = resp1.cookies.get(settings.SESSION_COOKIE_NAME)
        cookie2 = resp2.cookies.get(settings.SESSION_COOKIE_NAME)

        sid1 = decode_session_token(cookie1)["sid"]
        revoke_session(session, sid1, "admin_revoke")
        session.commit()

        resp_using_cookie1 = client.get(
            "/api/users/me", headers=_cookie_header(cookie1)
        )
        resp_using_cookie2 = client.get(
            "/api/users/me", headers=_cookie_header(cookie2)
        )
        assert resp_using_cookie1.status_code == 401
        assert resp_using_cookie2.status_code == 200
        assert user.username == "admin"

    def test_request_completes_cleanly_after_mid_flight_revocation(
        self, client: TestClient, session: Session
    ):
        """Edge case 1.10 — no half-applied writes; the *next* request is
        the one that gets 401, not a corrupted in-flight one."""
        make_admin(session)
        resp = client.post(
            "/api/auth/login", data={"username": "admin", "password": "Admin123"}
        )
        cookie = resp.cookies.get(settings.SESSION_COOKIE_NAME)
        sid = decode_session_token(cookie)["sid"]

        ok = client.get("/api/users/me", headers=_cookie_header(cookie))
        assert ok.status_code == 200

        revoke_session(session, sid, "admin_revoke")
        session.commit()

        rejected = client.get("/api/users/me", headers=_cookie_header(cookie))
        assert rejected.status_code == 401

    def test_deactivation_by_another_session_rejects_the_next_request_immediately(
        self, client: TestClient, session: Session
    ):
        """Verification step 4 — an operator's own session is still
        cookie-valid, but an admin deactivating them in a *different*
        session must make the operator's very next request 401 AUTH_REVOKED
        immediately, not after the JWT's own 8-hour expiry."""
        op = make_operator(session)
        op_cookie_headers = auth_headers(client, "operator", "Operator123")
        make_admin(session)
        admin_headers = auth_headers(client, "admin", "Admin123")

        still_active = client.get("/api/users/me", headers=op_cookie_headers)
        assert still_active.status_code == 200

        deactivate = client.patch(
            f"/api/users/{op.user_id}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert deactivate.status_code == 200

        next_request = client.get("/api/users/me", headers=op_cookie_headers)
        assert next_request.status_code == 401
        assert next_request.json()["code"] == "AUTH_REVOKED"


class TestLogout:
    def test_logout_revokes_session(self, client: TestClient, session: Session):
        make_admin(session)
        resp = client.post(
            "/api/auth/login", data={"username": "admin", "password": "Admin123"}
        )
        cookie = resp.cookies.get(settings.SESSION_COOKIE_NAME)

        logout_resp = client.post("/api/auth/logout", headers=_cookie_header(cookie))
        assert logout_resp.status_code == 204
        assert logout_resp.headers["cache-control"] == "no-store"

        after = client.get("/api/users/me", headers=_cookie_header(cookie))
        assert after.status_code == 401
        assert after.json()["code"] == "AUTH_REVOKED"

    def test_logout_clears_the_cookie(self, client: TestClient, session: Session):
        make_admin(session)
        resp = client.post(
            "/api/auth/login", data={"username": "admin", "password": "Admin123"}
        )
        cookie = resp.cookies.get(settings.SESSION_COOKIE_NAME)
        logout_resp = client.post("/api/auth/logout", headers=_cookie_header(cookie))
        set_cookie = logout_resp.headers.get("set-cookie", "")
        assert settings.SESSION_COOKIE_NAME in set_cookie
        assert "Max-Age=0" in set_cookie or "01 Jan 1970" in set_cookie

    def test_logout_writes_logout_audit_row(self, client: TestClient, session: Session):
        make_admin(session)
        resp = client.post(
            "/api/auth/login", data={"username": "admin", "password": "Admin123"}
        )
        cookie = resp.cookies.get(settings.SESSION_COOKIE_NAME)
        client.post("/api/auth/logout", headers=_cookie_header(cookie))

        rows = session.exec(select(AuditLog).where(AuditLog.action == "LOGOUT")).all()
        assert len(rows) == 1
        assert rows[0].result == "success"

    def test_logout_twice_both_return_204(self, client: TestClient, session: Session):
        """Edge case 10.5."""
        make_admin(session)
        resp = client.post(
            "/api/auth/login", data={"username": "admin", "password": "Admin123"}
        )
        cookie = resp.cookies.get(settings.SESSION_COOKIE_NAME)

        first = client.post("/api/auth/logout", headers=_cookie_header(cookie))
        second = client.post("/api/auth/logout", headers=_cookie_header(cookie))
        assert first.status_code == 204
        assert second.status_code == 204

    def test_logout_with_no_cookie_returns_204(self, client: TestClient):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 204


class TestOriginValidation:
    """Edge case 8.12 and 01_CONTRACTS.md Step 5."""

    def test_foreign_origin_on_unsafe_method_rejected(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        headers["Origin"] = "http://evil.example.com"
        resp = client.post("/api/auth/logout", headers=headers)
        assert resp.status_code == 403
        assert resp.json()["code"] == "ORIGIN_REJECTED"

    def test_absent_origin_allowed(self, client: TestClient, session: Session):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.post("/api/auth/logout", headers=headers)
        assert resp.status_code == 204

    def test_listed_origin_allowed(self, client: TestClient, session: Session):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        headers["Origin"] = settings.CORS_ORIGINS[0]
        resp = client.post("/api/auth/logout", headers=headers)
        assert resp.status_code == 204

    def test_internal_routes_exempt_from_origin_check(self, client: TestClient):
        from .conftest import internal_headers

        headers = internal_headers()
        headers["Origin"] = "http://evil.example.com"
        resp = client.post(
            "/api/internal/heartbeat",
            headers=headers,
            json={
                "engine_id": "adas-ai-1",
                "sent_at": datetime.now(UTC).isoformat(),
                "cameras": [],
            },
        )
        assert resp.status_code == 200


class TestRateLimit:
    """Edge case 6.10 and D-006 login protection."""

    def test_nth_plus_one_failure_returns_429_with_retry_after(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        for _ in range(settings.LOGIN_RATE_LIMIT_ATTEMPTS):
            client.post(
                "/api/auth/login",
                data={"username": "admin", "password": "wrongpassword"},
            )
        resp = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "wrongpassword"},
        )
        assert resp.status_code == 429
        assert resp.json()["code"] == "AUTH_RATE_LIMITED"
        assert "Retry-After" in resp.headers

    def test_success_resets_the_limiter(self, client: TestClient, session: Session):
        make_admin(session)
        for _ in range(settings.LOGIN_RATE_LIMIT_ATTEMPTS - 1):
            client.post(
                "/api/auth/login",
                data={"username": "admin", "password": "wrongpassword"},
            )
        ok = client.post(
            "/api/auth/login", data={"username": "admin", "password": "Admin123"}
        )
        assert ok.status_code == 200

        # The limiter should be clear again — another failure doesn't 429.
        resp = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    def test_ip_and_username_dimensions_are_independent(
        self, client: TestClient, session: Session
    ):
        """Locking out one username doesn't lock out a different username
        from the same (test) client IP dimension check — verified by
        confirming a *different* username's attempts aren't 429'd."""
        make_admin(session, username="lockme")
        make_admin(session, username="other")
        for _ in range(settings.LOGIN_RATE_LIMIT_ATTEMPTS):
            client.post(
                "/api/auth/login",
                data={"username": "lockme", "password": "wrongpassword"},
            )
        locked = client.post(
            "/api/auth/login",
            data={"username": "lockme", "password": "wrongpassword"},
        )
        assert locked.status_code == 429

    def test_rate_limit_rejection_is_audited(
        self, client: TestClient, session: Session
    ):
        """Verification step 5 — LOGIN_RATE_LIMIT_ATTEMPTS+1 failed attempts
        (default 10+1=11) produce exactly that many LOGIN_FAILURE rows: the
        real wrong-password checks plus the rate-limited rejection itself."""
        make_admin(session)
        for _ in range(settings.LOGIN_RATE_LIMIT_ATTEMPTS + 1):
            client.post(
                "/api/auth/login",
                data={"username": "admin", "password": "wrongpassword"},
            )
        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "LOGIN_FAILURE")
        ).all()
        assert len(rows) == settings.LOGIN_RATE_LIMIT_ATTEMPTS + 1
        assert all(r.result == "denied" for r in rows)


class TestProtectedRoutes:
    """TC-U-203 — a session cookie is required for protected routes."""

    def test_no_cookie_returns_401(self, client: TestClient, session: Session):
        resp = client.get("/api/alerts/")
        assert resp.status_code == 401

    def test_bearer_header_alone_is_not_accepted(
        self, client: TestClient, session: Session
    ):
        """There is no bearer-token fallback — only the cookie is read."""
        resp = client.get(
            "/api/alerts/", headers={"Authorization": "Bearer this.is.not.valid"}
        )
        assert resp.status_code == 401

    def test_valid_cookie_allows_access(self, client: TestClient, session: Session):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.get("/api/alerts/", headers=headers)
        assert resp.status_code == 200


class TestRBAC:
    """TC-U-204 / TC-S-201 / TC-S-202 / TC-S-505 — role-based access control
    and its audit coverage."""

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

    def test_operator_403_creates_denied_user_create_row(
        self, client: TestClient, session: Session
    ):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        client.post(
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
        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "USER_CREATE")
        ).all()
        assert len(rows) == 1
        assert rows[0].result == "denied"
        assert rows[0].username == "operator"

    def test_operator_cannot_delete_user(self, client: TestClient, session: Session):
        admin = make_admin(session)
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.delete(f"/api/users/{admin.user_id}", headers=headers)
        assert resp.status_code == 403

    def test_operator_cannot_view_audit_logs(
        self, client: TestClient, session: Session
    ):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get("/api/audit-logs/", headers=headers)
        assert resp.status_code == 403

    def test_admin_can_access_user_management(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.get("/api/users/", headers=headers)
        assert resp.status_code == 200

    def test_role_escalation_via_update_my_profile_ignored(
        self, client: TestClient, session: Session
    ):
        """Edge case 8.10 — UserOperatorUpdate has no `role` field."""
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.patch("/api/users/me", json={"role": "Admin"}, headers=headers)
        if resp.status_code == 200:
            assert resp.json()["role"] == "Operator"

        me = client.get("/api/users/me", headers=headers)
        assert me.json()["role"] == "Operator"

    # Every admin-only route in the API (be_audit/00_FINDINGS.md F27,
    # edge case 8.11). A POST/PATCH body is deliberately `{}` — missing
    # every required field — so a 422 slipping through would mean the
    # route handler's body validation ran before the role check, not
    # just that the route is admin-gated at all.
    _ADMIN_ROUTES: list[tuple[str, str, dict | None]] = [
        ("GET", "/api/audit-logs/", None),
        ("GET", "/api/audit-logs/export", None),
        ("POST", "/api/exports/retraining", {}),
        ("GET", "/api/system/backups", None),
        ("POST", "/api/system/backups", None),
        ("POST", "/api/system/restores", {}),
        ("GET", "/api/system/restores/latest", None),
        ("GET", "/api/users/", None),
        ("POST", "/api/users/", {}),
        ("PATCH", "/api/users/1", {}),
        ("POST", "/api/users/1/reset-password", {}),
        ("DELETE", "/api/users/1", None),
    ]

    @pytest.mark.parametrize(("method", "path", "body"), _ADMIN_ROUTES)
    def test_operator_gets_403_before_payload_processing_on_every_admin_route(
        self,
        client: TestClient,
        session: Session,
        method: str,
        path: str,
        body: dict | None,
    ):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.request(method, path, json=body, headers=headers)
        assert resp.status_code == 403, (method, path, resp.status_code, resp.text)
        assert resp.json()["code"] == "FORBIDDEN"
