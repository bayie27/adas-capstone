"""
Shared fixtures for the ADAS backend test suite.
Uses an in-memory SQLite database so tests are fully isolated
and never touch the real adas.db.
"""

import uuid
from datetime import UTC, datetime

import pyotp
import pytest
from app.core import security as _security
from app.core.config import Settings, settings
from app.core.db import get_engine, get_session, install_sqlite_pragmas
from app.core.mfa import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_recovery_codes,
    generate_totp_secret,
    hash_recovery_code,
    matching_totp_step,
)
from app.core.security import get_password_hash
from app.main import create_app
from app.models import (
    AIStatus,
    AlarmSettings,
    Camera,
    ConnectionStatus,
    DetectionLog,
    DetectionStatus,
    MfaCredential,
    MfaRecoveryCode,
    User,
    UserRole,
)
from app.services import mfa as _mfa_service
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

# ---------------------------------------------------------------------------
# Password hashing — production cost parameters are far too slow for a suite
# ---------------------------------------------------------------------------

# Captured here at conftest import, which happens before any fixture runs —
# so this is genuinely the context app/core/security.py builds at import
# time, not the cheap one installed below. test_security_params.py asserts
# against it; see cheap_password_hashing() for why that matters.
PRODUCTION_PWD_CONTEXT = _security.pwd_context
_TEST_MFA_ENCRYPTION_KEY = Fernet.generate_key().decode("ascii")


@pytest.fixture(autouse=True, scope="session")
def cheap_password_hashing():
    """Argon2id at throwaway cost parameters, for the test suite only.

    Production runs argon2-cffi's RFC 9106 defaults (64 MiB, t=3, p=4) —
    measured at ~400ms per hash and ~180ms per verify on a dev laptop. This
    suite performs roughly 900 of them (every make_admin/make_operator,
    every login/auth_headers, and one per init_db), which was about five
    minutes of pure key derivation.

    These tests assert authentication *behaviour*, not that the KDF is
    expensive — same algorithm, same code paths, ~1ms. The production cost
    parameters are pinned separately by test_security_params.py, so this
    cannot mask a real weakening of app/core/security.py.

    Rebinding the module attribute is enough: nothing imports `pwd_context`
    directly, and get_password_hash/verify_password resolve it as a module
    global at call time.
    """
    _security.pwd_context = CryptContext(
        schemes=["argon2"],
        deprecated="auto",
        argon2__time_cost=1,
        argon2__memory_cost=8,
        argon2__parallelism=1,
    )
    # Recomputed under the cheap context too — otherwise every
    # unknown-username login still pays a full-cost verify (edge case 8.8).
    _security._DUMMY_PASSWORD_HASH = _security.pwd_context.hash(
        "not-a-real-account-used-only-for-timing"
    )


# ---------------------------------------------------------------------------
# Database fixture — fresh in-memory DB per test
# ---------------------------------------------------------------------------


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # F1 — must be registered before anything opens StaticPool's single
    # connection, or the pragmas never apply. Matches production (app.core.db)
    # so tests enforce the same foreign_keys=ON guarantees as the real app.
    install_sqlite_pragmas(engine, settings.SQLITE_BUSY_TIMEOUT_MS)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(scope="session")
def lifespan_db_dir(tmp_path_factory):
    """One migrated throwaway database, shared by every client fixture.

    Session-scoped on purpose. Almost no test reads this database —
    client_fixture overrides get_session/get_engine to the in-memory
    `session` engine — but the lifespan still runs init_db() against it, and
    init_db bootstraps a *fresh* file with a full `alembic upgrade head`
    (37 DDL operations against a synchronous=FULL SQLite file). On a
    per-test tmp_path that fired 352 times, roughly two minutes of the
    suite. Shared, the first client pays for the migration and the rest hit
    the `current_rev == head_rev` fast path in check_schema_revision.

    tmp_path_factory is per-worker under xdist, so this stays one migration
    per worker rather than one shared file racing 16 processes.

    If you add a test that *reads* app.state.engine — counting audit rows
    written by a background job, say — state will leak in from its
    neighbours. Override this fixture in that module to get a fresh
    database per test; test_maintenance.py does exactly that and explains
    why.
    """
    return tmp_path_factory.mktemp("lifespan")


def _build_test_settings(lifespan_dir) -> Settings:
    """A disposable Settings instance, decoupled from the real .env, whose
    engine (built inside create_app()) never touches the repo-root adas.db —
    that engine is unused anyway once get_session/get_engine are overridden
    below, but lifespan still runs init_db() against it on TestClient
    startup, and that must land somewhere harmless."""
    return Settings(
        _env_file=None,
        SECRET_KEY="test-secret-key-not-for-production-use",
        INTERNAL_API_KEY="test-internal-api-key-not-for-production",
        DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
        MFA_ENCRYPTION_KEY=_TEST_MFA_ENCRYPTION_KEY,
        DATABASE_URL=f"sqlite:///{lifespan_dir / 'lifespan-only.db'}",
        SCHEDULER_ENABLED=False,
        # F7 — tests drive export jobs directly via process_export_job(),
        # not through the worker pool; a live pool would race those calls.
        EXPORT_JOB_WORKERS=0,
        # F25 — lifespan now mkdir()s SNAPSHOT_ROOT at startup; without this
        # override every test booting the app via the `client` fixture would
        # create the real repo's ai_engine/snapshots/ directory as a side
        # effect, same class of leak test_client_fixture_never_touches_the_
        # real_repo_root_db guards against for DATABASE_URL.
        SNAPSHOT_ROOT=lifespan_dir / "snapshots",
    )


@pytest.fixture(name="client")
def client_fixture(session: Session, lifespan_db_dir, monkeypatch):
    app_settings = _build_test_settings(lifespan_db_dir)
    app = create_app(app_settings)

    # Session validation intentionally reads the process-global settings
    # singleton. Keep it aligned with this isolated application instance.
    for field in (
        "SECRET_KEY",
        "ALGORITHM",
        "JWT_ISSUER",
        "JWT_AUDIENCE",
        "SESSION_COOKIE_NAME",
        "SESSION_LIFETIME_MINUTES",
        "SESSION_COOKIE_SECURE",
        "DEV_TOOLS_ENABLED",
    ):
        monkeypatch.setattr(settings, field, getattr(app_settings, field))

    def get_session_override():
        yield session

    def get_engine_override():
        return session.get_bind()

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_engine] = get_engine_override
    with TestClient(app, base_url="https://testserver") as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers — reusable across test modules
# ---------------------------------------------------------------------------


def _seed_test_factor(session: Session, user: User) -> str:
    assert user.user_id is not None
    secret = generate_totp_secret()
    now = datetime.now(UTC)
    credential = MfaCredential(
        user_id=user.user_id,
        state="enrolled",
        active_secret_ciphertext=encrypt_totp_secret(secret, _TEST_MFA_ENCRYPTION_KEY),
        credential_version=1,
        last_accepted_step=int(now.timestamp() // 30),
        enrolled_at=now,
        recovery_generation=1,
    )
    session.add(credential)
    session.add_all(
        MfaRecoveryCode(
            user_id=user.user_id,
            generation=1,
            code_hash=hash_recovery_code(user.user_id, 1, code),
        )
        for code in generate_recovery_codes()
    )
    session.commit()
    return secret


def make_admin(
    session: Session,
    username="admin",
    password="Admin123",
    *,
    enrolled: bool = True,
) -> User:
    user = User(
        username=username,
        first_name="System",
        last_name="Admin",
        role=UserRole.ADMIN,
        password_hash=get_password_hash(password),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.add(AlarmSettings(user_id=user.user_id))
    session.commit()
    if enrolled:
        _seed_test_factor(session, user)
    return user


def make_operator(
    session: Session,
    username="operator",
    password="Operator123",
    *,
    enrolled: bool = True,
) -> User:
    user = User(
        username=username,
        first_name="Test",
        last_name="Operator",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash(password),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.add(AlarmSettings(user_id=user.user_id))
    session.commit()
    if enrolled:
        _seed_test_factor(session, user)
    return user


def make_camera(
    session: Session,
    name="Test Camera",
    channel_id=1,
    *,
    connection_status: str = ConnectionStatus.DISCONNECTED.value,
    ai_status: str = AIStatus.INACTIVE.value,
    is_enabled: bool = True,
    is_active: bool = True,
    desired_ai_state: str | None = None,
    desired_state_reason: str | None = None,
    cooldown_until=None,
    last_heartbeat_at=None,
) -> Camera:
    camera = Camera(
        camera_name=name,
        channel_id=channel_id,
        connection_status=connection_status,
        ai_status=ai_status,
        is_enabled=is_enabled,
        is_active=is_active,
        last_heartbeat_at=last_heartbeat_at,
    )
    if desired_ai_state is not None:
        camera.desired_ai_state = desired_ai_state
    if desired_state_reason is not None:
        camera.desired_state_reason = desired_state_reason
    if cooldown_until is not None:
        camera.cooldown_until = cooldown_until
    session.add(camera)
    session.commit()
    session.refresh(camera)
    return camera


def make_detection(
    session: Session,
    camera: Camera,
    status: DetectionStatus = DetectionStatus.UNVERIFIED,
    confidence: float = 0.95,
) -> DetectionLog:
    assert camera.camera_id is not None
    log = DetectionLog(
        camera_id=camera.camera_id,
        detected_at=datetime.now(UTC),
        snapshot_key="cam1_20260426_120000.jpg",
        confidence_score=confidence,
        detection_status=status.value,
        source_event_id=str(uuid.uuid4()),
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


# ---------------------------------------------------------------------------
# Auth helper — completes the same password, challenge, and TOTP endpoints
# ---------------------------------------------------------------------------


def _test_factor(client: TestClient, username: str) -> tuple[str, int | None]:
    session_override = client.app.dependency_overrides.get(get_session)
    if session_override is None:
        session = Session(client.app.state.engine)
        close_session = True
    else:
        generator = session_override()
        session = next(generator)
        close_session = False
    try:
        session.expire_all()
        user = session.exec(select(User).where(User.username == username)).first()
        assert user is not None and user.user_id is not None
        credential = session.get(MfaCredential, user.user_id)
        assert credential is not None and credential.active_secret_ciphertext
        secret = decrypt_totp_secret(
            credential.active_secret_ciphertext,
            client.app.state.settings.MFA_ENCRYPTION_KEY.get_secret_value(),
        )
        return secret, credential.last_accepted_step
    finally:
        if close_session:
            session.close()
        elif session_override is not None:
            generator.close()


def _complete_mfa_login(client: TestClient, username: str, password: str) -> dict:
    now = datetime.now(UTC)
    target_step = int(now.timestamp() // 30) + 1
    if client.app.dependency_overrides.get(get_session) is not None:
        try:
            _secret, last_accepted_step = _test_factor(client, username)
        except AssertionError:
            last_accepted_step = None
        if last_accepted_step is not None:
            target_step = max(target_step, last_accepted_step + 1)
    service_time = datetime.fromtimestamp(target_step * 30 + 5, UTC)
    original_clock = _mfa_service._now
    _mfa_service._now = lambda: service_time
    try:
        response = client.post(
            "/api/auth/login",
            data={"username": username, "password": password},
        )
        assert response.status_code == 200, "Password stage did not return a challenge."
        challenge = response.json()
        if challenge.get("status") == "enrollment_required":
            enrollment = client.post("/api/auth/mfa/enrollment/start", json={})
            assert enrollment.status_code == 200, "Enrollment setup was not available."
            secret = enrollment.json()["manual_key"]
            code = pyotp.TOTP(secret).at(service_time)
            assert matching_totp_step(secret, code, service_time) is not None
            completed = client.post(
                "/api/auth/mfa/enrollment/confirm", json={"code": code}
            )
        elif challenge.get("status") == "mfa_required":
            secret, _last_step = _test_factor(client, username)
            code = pyotp.TOTP(secret).at(service_time)
            assert matching_totp_step(secret, code, service_time) is not None
            completed = client.post(
                "/api/auth/mfa/verify",
                json={"method": "totp", "code": code},
            )
        else:
            raise AssertionError("Password stage returned no MFA challenge.")
        assert completed.status_code == 200, (
            "MFA proof did not complete authentication: "
            f"{completed.status_code} {completed.json().get('code')}"
        )
        body = completed.json()
        assert body.get("status") == "authenticated", (
            "MFA proof did not return a session."
        )
        session_cookie = completed.cookies.get(
            client.app.state.settings.SESSION_COOKIE_NAME
        )
        assert session_cookie, "Completed MFA did not set the session cookie."
        return {"body": body, "session_cookie": session_cookie}
    finally:
        _mfa_service._now = original_clock


def login(client: TestClient, username: str, password: str) -> dict:
    """Completes the real login endpoints and returns the user response."""
    return _complete_mfa_login(client, username, password)["body"]["user"]


def auth_headers(client: TestClient, username: str, password: str) -> dict:
    """Returns a session cookie after completing the live TOTP flow."""
    result = _complete_mfa_login(client, username, password)
    cookie_name = client.app.state.settings.SESSION_COOKIE_NAME
    return {"Cookie": f"{cookie_name}={result['session_cookie']}"}


def internal_headers() -> dict:
    return {"x-api-key": settings.INTERNAL_API_KEY.get_secret_value()}
