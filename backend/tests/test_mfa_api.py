import tempfile
from pathlib import Path

import pyotp
import pytest
from app.api.routes import mfa as mfa_api
from app.core.config import Settings
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import get_password_hash
from app.main import http_exception_handler, make_origin_validation_middleware
from app.models import User, UserRole
from app.schemas.mfa import ChallengeState
from app.services.realtime import RealtimeManager
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def lifespan_db_dir():
    repo_tmp = Path(__file__).resolve().parents[2] / "var" / "tmp"
    repo_tmp.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="mfa-api-lifespan-", dir=repo_tmp))


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        SECRET_KEY="test-secret-key-not-for-production-use",
        INTERNAL_API_KEY="test-internal-api-key-not-for-production",
        DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
        MFA_ENCRYPTION_KEY=Fernet.generate_key().decode("ascii"),
        SESSION_COOKIE_SECURE=True,
        CORS_ORIGINS=["https://ui.test"],
        SCHEDULER_ENABLED=False,
    )


@pytest.fixture
def isolated_mfa_client(session):
    settings = _settings()
    engine = session.get_bind()
    app = FastAPI()
    app.state.settings = settings
    app.state.engine = engine
    app.state.rate_limiter = SlidingWindowLimiter(10, 300)
    app.state.mfa_rate_limiter = SlidingWindowLimiter(10, 300)
    app.state.realtime_manager = RealtimeManager(
        queue_maxsize=4, send_timeout_seconds=1
    )
    app.include_router(mfa_api.router)
    app.add_api_route(
        "/api/auth/login",
        mfa_api.password_login,
        methods=["POST"],
        response_model=ChallengeState,
    )
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.middleware("http")(make_origin_validation_middleware(settings.CORS_ORIGINS))
    mfa_api.install_auth_no_store(app)
    with TestClient(app, base_url="https://testserver") as client:
        yield client


def _user(session, username: str = "mfa-api-user") -> User:
    user = User(
        username=username,
        first_name="API",
        last_name="Test",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash("CorrectHorse9"),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_isolated_adapter_keeps_password_stage_as_challenge_and_sets_safe_cookie(
    session, isolated_mfa_client
):
    user = _user(session)
    response = isolated_mfa_client.post(
        "/api/auth/login",
        data={"username": user.username, "password": "CorrectHorse9"},
        headers={"Origin": "https://ui.test"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "enrollment_required"
    assert body["purpose"] == "enroll"
    assert "user" not in body
    assert "session_token" not in body
    assert response.headers["cache-control"] == "no-store"
    challenge_cookie = response.headers["set-cookie"].split(";", 1)[0]
    assert challenge_cookie.startswith("adas_mfa_challenge=")
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]
    assert "Path=/api/auth" in response.headers["set-cookie"]
    assert "Domain=" not in response.headers["set-cookie"]
    assert response.cookies.get("adas_session") is None

    state = isolated_mfa_client.get("/api/auth/mfa/challenge")
    assert state.status_code == 200
    assert state.json()["purpose"] == "enroll"
    assert state.headers["cache-control"] == "no-store"
    refreshed = isolated_mfa_client.post(
        "/api/auth/mfa/enrollment/start",
        json={},
        headers={"Origin": "https://ui.test"},
    )
    assert refreshed.status_code == 200
    assert refreshed.headers["cache-control"] == "no-store"
    assert refreshed.json()["issuer"] == "ADAS"


def test_adapter_completes_totp_enrollment_and_status_without_secret_fields(
    session, isolated_mfa_client
):
    user = _user(session, "mfa-api-complete")
    login = isolated_mfa_client.post(
        "/api/auth/login",
        data={"username": user.username, "password": "CorrectHorse9"},
    )
    enrollment = isolated_mfa_client.post("/api/auth/mfa/enrollment/start", json={})
    code = pyotp.TOTP(enrollment.json()["manual_key"]).now()

    confirmed = isolated_mfa_client.post(
        "/api/auth/mfa/enrollment/confirm", json={"code": code}
    )

    assert confirmed.status_code == 200
    response_body = confirmed.json()
    assert response_body["status"] == "authenticated"
    assert response_body["user"]["user_id"] == user.user_id
    assert len(response_body["recovery_codes"]) == 10
    assert confirmed.headers["cache-control"] == "no-store"
    assert "adas_session=" in confirmed.headers["set-cookie"]
    assert "Path=/;" in confirmed.headers["set-cookie"]
    assert "adas_mfa_challenge=" in confirmed.headers["set-cookie"]

    status_response = isolated_mfa_client.get("/api/auth/mfa/status")
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["state"] == "enrolled"
    assert status_body["recovery_codes_remaining"] == 10
    assert status_body["auth_method"] == "totp"
    assert not ({"active_secret", "manual_key", "recovery_codes"} & status_body.keys())

    full_session_in_challenge_route = isolated_mfa_client.post(
        "/api/auth/mfa/enrollment/start", json={}
    )
    assert full_session_in_challenge_route.status_code == 401
    assert full_session_in_challenge_route.json()["code"] == "MFA_CHALLENGE_INVALID"
    assert "Path=/api/auth" in full_session_in_challenge_route.headers["set-cookie"]

    challenge_only = login.cookies.get("adas_mfa_challenge")
    confused = isolated_mfa_client.get(
        "/api/auth/mfa/status",
        cookies={"adas_session": challenge_only},
    )
    assert confused.status_code == 401
    assert confused.headers["cache-control"] == "no-store"


def test_validation_errors_do_not_echo_proofs_and_have_no_store(isolated_mfa_client):
    sentinel = "012345secret-otp-value"
    response = isolated_mfa_client.post(
        "/api/auth/mfa/enrollment/confirm", json={"code": sentinel}
    )

    assert response.status_code == 422
    assert sentinel not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_missing_challenge_is_rejected_and_cookie_is_cleared(isolated_mfa_client):
    response = isolated_mfa_client.get("/api/auth/mfa/challenge")

    assert response.status_code == 401
    assert response.json()["code"] == "MFA_CHALLENGE_INVALID"
    assert response.headers["cache-control"] == "no-store"
    assert "adas_mfa_challenge=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert "Path=/api/auth" in response.headers["set-cookie"]

    malformed = isolated_mfa_client.get(
        "/api/auth/mfa/challenge",
        cookies={"adas_mfa_challenge": "not-a-valid-challenge-token"},
    )
    assert malformed.status_code == 401
    assert malformed.json()["code"] == "MFA_CHALLENGE_INVALID"
    assert "adas_mfa_challenge=" in malformed.headers["set-cookie"]
    assert "Max-Age=0" in malformed.headers["set-cookie"]


def test_password_limiter_resets_only_after_full_mfa_authentication(
    session, isolated_mfa_client
):
    user = _user(session, "mfa-api-limit")
    isolated_mfa_client.app.state.rate_limiter = SlidingWindowLimiter(2, 300)

    first_failure = isolated_mfa_client.post(
        "/api/auth/login",
        data={"username": user.username, "password": "WrongPass9"},
    )
    challenge = isolated_mfa_client.post(
        "/api/auth/login",
        data={"username": user.username, "password": "CorrectHorse9"},
    )
    second_failure = isolated_mfa_client.post(
        "/api/auth/login",
        data={"username": user.username, "password": "WrongPass9"},
    )
    blocked = isolated_mfa_client.post(
        "/api/auth/login",
        data={"username": user.username, "password": "WrongPass9"},
    )

    assert first_failure.status_code == 401
    assert challenge.status_code == 200
    assert second_failure.status_code == 401
    assert blocked.status_code == 429

    enrollment = isolated_mfa_client.post("/api/auth/mfa/enrollment/start", json={})
    confirmed = isolated_mfa_client.post(
        "/api/auth/mfa/enrollment/confirm",
        json={"code": pyotp.TOTP(enrollment.json()["manual_key"]).now()},
    )
    assert confirmed.status_code == 200

    after_completion = [
        isolated_mfa_client.post(
            "/api/auth/login",
            data={"username": user.username, "password": "WrongPass9"},
        )
        for _ in range(3)
    ]
    assert [response.status_code for response in after_completion] == [401, 401, 429]


def test_invalid_origin_is_rejected_without_cacheable_auth_response(
    isolated_mfa_client,
):
    response = isolated_mfa_client.post(
        "/api/auth/mfa/challenge", headers={"Origin": "https://attacker.test"}
    )

    assert response.status_code == 403
    assert response.json()["code"] == "ORIGIN_REJECTED"
    assert response.headers["cache-control"] == "no-store"


def test_ordinary_application_registers_mfa_and_password_only_issues_challenge(
    session, client
):
    user = _user(session, "mfa-staged-user")

    challenge_status = client.get("/api/auth/mfa/challenge")
    login = client.post(
        "/api/auth/login",
        data={"username": user.username, "password": "CorrectHorse9"},
    )

    assert challenge_status.status_code == 401
    assert login.status_code == 200
    assert set(login.json()) == {"status", "purpose", "expires_at"}
    assert login.json()["status"] == "enrollment_required"
    assert login.json()["purpose"] == "enroll"
    assert login.cookies.get("adas_session") is None
    assert login.cookies.get("adas_mfa_challenge")
    assert login.headers["cache-control"] == "no-store"
