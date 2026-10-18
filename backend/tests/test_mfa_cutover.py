"""P4 activation, rollout migration, and startup fail-closed evidence."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from alembic import command
from app.core.config import Settings, settings
from app.core.db import create_db_engine
from app.core.mfa import encrypt_totp_secret, generate_totp_secret
from app.core.migrations import (
    get_alembic_config,
    get_database_revision,
)
from app.core.security import create_session_token
from app.main import create_app
from app.models import (
    AuthSession,
    Camera,
    ConnectionStatus,
    MfaCredential,
    User,
    UserRole,
)
from app.services.sessions import create_session
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError
from sqlmodel import Session, select
from starlette.websockets import WebSocketDisconnect

from .conftest import make_admin, make_operator

_FOUNDATION_REVISION = "5b87b6564753"
_NOW = "2026-10-18 12:00:00.000000"


def _migration_settings(db_path) -> Settings:
    return Settings(
        _env_file=None,
        SECRET_KEY="mfa-cutover-migration-test-secret-1234567890",
        INTERNAL_API_KEY="mfa-cutover-migration-test-internal-key",
        DEFAULT_ADMIN_PASSWORD="MfaCutoverTest123!",
        DATABASE_URL=f"sqlite:///{db_path}",
    )


def _seed_foundation_database(settings: Settings) -> None:
    command.upgrade(get_alembic_config(settings), _FOUNDATION_REVISION)
    engine = create_db_engine(settings)
    with engine.begin() as connection:
        for user_id in (1, 2):
            connection.execute(
                text(
                    "INSERT INTO user (user_id, username, first_name, last_name, "
                    "role, password_hash, is_active, created_at, updated_at) "
                    "VALUES (:id, :username, 'MFA', 'Cutover', 'Operator', 'hash', "
                    "1, :now, :now)"
                ),
                {"id": user_id, "username": f"cutover-{user_id}", "now": _NOW},
            )
        sessions = (
            ("legacy-password", 1, None, None, "password", None),
            ("demo-session", 1, None, None, "demo_impersonation", None),
            ("totp-session", 2, None, None, "totp", 4),
            (
                "already-revoked",
                2,
                _NOW,
                "admin_revoke",
                "password",
                None,
            ),
        )
        for session_id, user_id, revoked_at, reason, method, version in sessions:
            connection.execute(
                text(
                    "INSERT INTO auth_session (session_id, user_id, created_at, "
                    "expires_at, revoked_at, revocation_reason, auth_method, "
                    "mfa_credential_version, user_agent, source_ip) VALUES "
                    "(:sid, :uid, :now, '2026-10-19 12:00:00.000000', :revoked, "
                    ":reason, :method, :version, 'migration-test', '127.0.0.1')"
                ),
                {
                    "sid": session_id,
                    "uid": user_id,
                    "now": _NOW,
                    "revoked": revoked_at,
                    "reason": reason,
                    "method": method,
                    "version": version,
                },
            )
        for user_id, digest in ((1, "a" * 64), (2, "b" * 64)):
            connection.execute(
                text(
                    "INSERT INTO mfa_challenge (user_id, token_hash, purpose, "
                    "credential_version, created_at, expires_at) VALUES "
                    "(:uid, :digest, 'login', 0, :now, '2026-10-18 12:05:00.000000')"
                ),
                {"uid": user_id, "digest": digest, "now": _NOW},
            )
        connection.execute(
            text(
                "INSERT INTO audit_log (audit_id, actor_type, user_id, username, "
                "role, action, target_type, target_ref, result, detail, request_id, "
                "source_ip, created_at) VALUES (17, 'user', 1, 'cutover-1', "
                "'Operator', 'LOGIN_SUCCESS', 'session', 'historical-session', "
                "'success', '{\"source\":\"before-cutover\"}', 'before-p4', "
                "'127.0.0.1', :now)"
            ),
            {"now": _NOW},
        )
    engine.dispose()


def test_cutover_migration_revokes_legacy_sessions_once_and_preserves_history(tmp_path):
    settings = _migration_settings(tmp_path / "cutover.db")
    _seed_foundation_database(settings)

    command.upgrade(get_alembic_config(settings), "head")
    engine = create_db_engine(settings)
    try:
        with engine.connect() as connection:
            sessions = {
                row.session_id: (row.revoked_at, row.revocation_reason)
                for row in connection.execute(
                    text(
                        "SELECT session_id, revoked_at, revocation_reason "
                        "FROM auth_session"
                    )
                )
            }
            assert all(sessions[key][0] is not None for key in sessions)
            assert sessions["legacy-password"][1] == "mfa_rollout"
            assert sessions["demo-session"][1] == "mfa_rollout"
            assert sessions["totp-session"][1] == "mfa_rollout"
            assert sessions["already-revoked"] == (_NOW, "admin_revoke")
            assert (
                connection.execute(
                    text("SELECT count(*) FROM mfa_challenge")
                ).scalar_one()
                == 0
            )
            assert (
                connection.execute(text("SELECT count(*) FROM user")).scalar_one() == 2
            )
            audit = connection.execute(
                text(
                    "SELECT audit_id, actor_type, action, target_type, target_ref, "
                    "result, detail FROM audit_log ORDER BY audit_id"
                )
            ).all()
            assert len(audit) == 2
            assert audit[0].audit_id == 17
            assert audit[0].detail == '{"source":"before-cutover"}'
            assert audit[1].actor_type == "system"
            assert audit[1].action == "MFA_ROLLOUT"
            assert audit[1].target_ref == "p4-mandatory-mfa-cutover"
            assert '"revoked_sessions":3' in audit[1].detail
            assert '"cleared_challenges":2' in audit[1].detail
            default = (
                connection.execute(text("PRAGMA table_info(auth_session)"))
                .mappings()
                .all()
            )
            auth_method = next(row for row in default if row["name"] == "auth_method")
            assert auth_method["dflt_value"] is None

        with pytest.raises(DatabaseError), engine.begin() as connection:
            connection.execute(
                text("UPDATE audit_log SET detail='rewritten' WHERE audit_id=17")
            )
        with pytest.raises(DatabaseError), engine.begin() as connection:
            connection.execute(text("DELETE FROM audit_log WHERE audit_id=17"))

        command.upgrade(get_alembic_config(settings), "head")
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT count(*) FROM audit_log WHERE action='MFA_ROLLOUT'")
                ).scalar_one()
                == 1
            )
    finally:
        engine.dispose()


def test_cutover_migration_failure_rolls_back_session_challenge_and_audit_changes(
    tmp_path,
):
    settings = _migration_settings(tmp_path / "cutover-failure.db")
    _seed_foundation_database(settings)
    engine = create_db_engine(settings)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TRIGGER fail_mfa_rollout BEFORE INSERT ON audit_log "
                "WHEN NEW.action='MFA_ROLLOUT' BEGIN "
                "SELECT RAISE(ABORT, 'injected rollout audit failure'); END"
            )
        )
    engine.dispose()

    with pytest.raises(DatabaseError):
        command.upgrade(get_alembic_config(settings), "head")

    engine = create_db_engine(settings)
    try:
        assert get_database_revision(engine) == _FOUNDATION_REVISION
        with engine.connect() as connection:
            auth_method = next(
                row
                for row in connection.execute(
                    text("PRAGMA table_info(auth_session)")
                ).mappings()
                if row["name"] == "auth_method"
            )
            assert auth_method["dflt_value"] == "'password'"
            assert (
                connection.execute(
                    text(
                        "SELECT revoked_at FROM auth_session WHERE session_id='legacy-password'"
                    )
                ).scalar_one()
                is None
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM mfa_challenge")
                ).scalar_one()
                == 2
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM audit_log WHERE action='MFA_ROLLOUT'")
                ).scalar_one()
                == 0
            )
    finally:
        engine.dispose()


def test_populated_cutover_downgrade_refuses_without_rewinding_data(tmp_path):
    settings = _migration_settings(tmp_path / "cutover-downgrade.db")
    _seed_foundation_database(settings)
    command.upgrade(get_alembic_config(settings), "head")
    engine = create_db_engine(settings)
    try:
        with engine.connect() as connection:
            before_sessions = connection.execute(
                text(
                    "SELECT session_id, revoked_at, revocation_reason "
                    "FROM auth_session ORDER BY session_id"
                )
            ).all()
            before_challenges = connection.execute(
                text("SELECT count(*) FROM mfa_challenge")
            ).scalar_one()
            before_audit = connection.execute(
                text("SELECT audit_id, action, detail FROM audit_log ORDER BY audit_id")
            ).all()
        with pytest.raises(RuntimeError, match="Refusing MFA cutover downgrade"):
            command.downgrade(get_alembic_config(settings), _FOUNDATION_REVISION)
        assert get_database_revision(engine) == "8d4e7a2c9f10"
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text(
                        "SELECT session_id, revoked_at, revocation_reason "
                        "FROM auth_session ORDER BY session_id"
                    )
                ).all()
                == before_sessions
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM mfa_challenge")
                ).scalar_one()
                == before_challenges
            )
            assert (
                connection.execute(
                    text(
                        "SELECT audit_id, action, detail FROM audit_log ORDER BY audit_id"
                    )
                ).all()
                == before_audit
            )
            auth_method = next(
                row
                for row in connection.execute(
                    text("PRAGMA table_info(auth_session)")
                ).mappings()
                if row["name"] == "auth_method"
            )
            assert auth_method["dflt_value"] is None
    finally:
        engine.dispose()


def _startup_settings(
    db_path,
    snapshot_root,
    *,
    key: str | None,
    environment: str = "production",
) -> Settings:
    return Settings(
        _env_file=None,
        ENVIRONMENT=environment,
        SECRET_KEY="startup-mfa-test-secret-key-1234567890",
        INTERNAL_API_KEY="startup-mfa-test-internal-key",
        DEFAULT_ADMIN_PASSWORD="StartupMfaTest123!",
        MFA_ENCRYPTION_KEY=key,
        DATABASE_URL=f"sqlite:///{db_path}",
        SNAPSHOT_ROOT=snapshot_root,
        SCHEDULER_ENABLED=False,
        DEV_TOOLS_ENABLED=False,
    )


def test_startup_rejects_missing_key_before_database_or_runtime_writes(tmp_path):
    db_path = tmp_path / "missing-key.db"
    snapshot_root = tmp_path / "snapshots"
    app = create_app(_startup_settings(db_path, snapshot_root, key=None))

    with (
        pytest.raises(RuntimeError, match="MFA_ENCRYPTION_KEY is required"),
        TestClient(app),
    ):
        pass

    assert not db_path.exists()
    assert not snapshot_root.exists()


@pytest.mark.parametrize("failure", ["wrong-key", "corrupt-ciphertext"])
def test_startup_rejects_bad_stored_secrets_before_camera_reset(tmp_path, failure):
    stable_key = Fernet.generate_key().decode("ascii")
    configured_key = (
        Fernet.generate_key().decode("ascii") if failure == "wrong-key" else stable_key
    )
    db_path = tmp_path / f"{failure}.db"
    base_settings = _startup_settings(
        db_path, tmp_path / f"snapshots-{failure}", key=stable_key
    )
    command.upgrade(get_alembic_config(base_settings), "head")
    engine = create_db_engine(base_settings)
    now = datetime.now(UTC)
    user = User(
        username="startup-user",
        first_name="Startup",
        last_name="MFA",
        role=UserRole.OPERATOR,
        password_hash="test-hash",
        is_active=True,
    )
    camera = Camera(
        camera_name="Before key check",
        channel_id=1,
        is_active=True,
        is_enabled=True,
        connection_status=ConnectionStatus.CONNECTED.value,
        ai_status="Active",
    )
    secret = generate_totp_secret()
    ciphertext = (
        "not-a-valid-fernet-token"
        if failure == "corrupt-ciphertext"
        else encrypt_totp_secret(secret, stable_key)
    )
    with Session(engine) as session:
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.user_id is not None
        session.add(
            MfaCredential(
                user_id=user.user_id,
                state="enrolled",
                active_secret_ciphertext=ciphertext,
                credential_version=1,
                last_accepted_step=int(now.timestamp() // 30),
                enrolled_at=now,
                recovery_generation=1,
            )
        )
        session.add(camera)
        session.commit()
        camera_id = camera.camera_id
    engine.dispose()

    app_settings = _startup_settings(
        db_path,
        tmp_path / f"snapshots-{failure}",
        key=configured_key,
    )
    app = create_app(app_settings)
    with (
        pytest.raises(RuntimeError, match="Stored MFA secrets cannot be validated"),
        TestClient(app),
    ):
        pass

    engine = create_db_engine(app_settings)
    try:
        with Session(engine) as session:
            unchanged = session.get(Camera, camera_id)
            assert unchanged is not None
            assert unchanged.connection_status == ConnectionStatus.CONNECTED.value
            assert unchanged.ai_status == "Active"
    finally:
        engine.dispose()


def test_main_app_password_stage_only_creates_challenge_and_no_store_error_responses(
    client: TestClient, session: Session
):
    user = make_operator(session, enrolled=False)
    response = client.post(
        "/api/auth/login",
        data={"username": user.username, "password": "Operator123"},
    )
    assert response.status_code == 200
    assert set(response.json()) == {"status", "purpose", "expires_at"}
    assert response.json()["status"] == "enrollment_required"
    assert response.json()["purpose"] == "enroll"
    assert response.cookies.get(settings.SESSION_COOKIE_NAME) is None
    assert response.cookies.get("adas_mfa_challenge")
    assert response.headers["cache-control"] == "no-store"
    session.refresh(user)
    assert user.last_login is None
    assert not session.exec(
        select(AuthSession).where(AuthSession.user_id == user.user_id)
    ).all()

    challenge = client.get("/api/auth/mfa/challenge")
    assert challenge.status_code == 200
    assert challenge.json()["purpose"] == "enroll"

    copied = response.cookies.get("adas_mfa_challenge")
    protected = client.get(
        "/api/users/me",
        headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={copied}"},
    )
    assert protected.status_code == 401
    assert protected.json()["code"] == "AUTH_REQUIRED"

    sentinel = "sensitive-validation-sentinel-" + ("x" * 70)
    invalid = client.post(
        "/api/auth/mfa/verify",
        json={"method": "totp", "code": sentinel},
    )
    assert invalid.status_code == 422
    assert invalid.headers["cache-control"] == "no-store"
    assert sentinel not in invalid.text

    origin_rejection = client.post(
        "/api/auth/logout", headers={"Origin": "https://unlisted.invalid"}
    )
    assert origin_rejection.status_code == 403
    assert origin_rejection.headers["cache-control"] == "no-store"


def test_legacy_password_session_is_rejected_by_protected_rest_and_websocket(
    client: TestClient, session: Session
):
    user = make_admin(session)
    legacy_session = create_session(
        session,
        user,
        user_agent=None,
        source_ip=None,
        auth_method="password",
    )
    session.commit()
    token = create_session_token(user, legacy_session, client.app.state.settings)
    cookie = {"Cookie": f"{settings.SESSION_COOKIE_NAME}={token}"}

    response = client.get("/api/users/me", headers=cookie)
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REVOKED"

    with (
        pytest.raises(WebSocketDisconnect) as disconnected,
        client.websocket_connect("/ws/alerts", headers=cookie),
    ):
        pass
    assert disconnected.value.code == 4001
