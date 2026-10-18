import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyotp
import pytest
from app.core.config import Settings
from app.core.db import install_sqlite_pragmas
from app.core.errors import AppHTTPException
from app.core.mfa import (
    encrypt_totp_secret,
    generate_recovery_codes,
    hash_challenge_token,
    hash_recovery_code,
)
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import get_password_hash
from app.models import (
    AuditLog,
    AuthSession,
    MfaChallenge,
    MfaCredential,
    MfaRecoveryCode,
    User,
    UserRole,
)
from app.services.mfa import (
    MfaRequestContext,
    confirm_enrollment,
    verify_challenge,
)
from cryptography.fernet import Fernet
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        SECRET_KEY="test-secret-key-not-for-production-use",
        INTERNAL_API_KEY="test-internal-api-key-not-for-production",
        DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
        MFA_ENCRYPTION_KEY=Fernet.generate_key().decode("ascii"),
        SQLITE_BUSY_TIMEOUT_MS=5000,
        SCHEDULER_ENABLED=False,
    )


def _file_engine(*, busy_timeout_ms: int = 5000):
    repository_tmp = Path(__file__).resolve().parents[2] / "var" / "tmp"
    repository_tmp.mkdir(parents=True, exist_ok=True)
    directory = tempfile.TemporaryDirectory(
        prefix="mfa-concurrency-", dir=repository_tmp
    )
    path = Path(directory.name) / "mfa.db"
    engine = create_engine(
        f"sqlite:///{path.as_posix()}",
        connect_args={"check_same_thread": False},
        pool_size=6,
        max_overflow=0,
    )
    install_sqlite_pragmas(engine, busy_timeout_ms)
    SQLModel.metadata.create_all(engine)
    return engine, directory


def _user(session: Session, username: str) -> User:
    user = User(
        username=username,
        first_name="Race",
        last_name="Test",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash("CorrectHorse9"),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _race_two(engine, operation):
    barrier = threading.Barrier(2)
    writer_connections: list[int] = []
    guard = threading.Lock()

    def capture_write(connection, _cursor, statement, _parameters, _context, _many):
        if statement.strip().upper() == "BEGIN IMMEDIATE":
            with guard:
                writer_connections.append(id(connection.connection.driver_connection))

    event.listen(engine, "before_cursor_execute", capture_write)

    def run_one():
        # Hold two distinct pooled connections through the barrier so service
        # work cannot collapse onto StaticPool's one shared connection.
        with engine.connect():
            barrier.wait(timeout=10)
            try:
                return operation()
            except Exception as exc:  # return safe error codes, never proof data
                return getattr(exc, "code", type(exc).__name__)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: run_one(), range(2)))
    finally:
        event.remove(engine, "before_cursor_execute", capture_write)
    assert len(set(writer_connections)) >= 2
    return results


def test_two_file_connections_accept_one_totp_step_once():
    engine, directory = _file_engine()
    try:
        settings = _settings()
        context = MfaRequestContext("192.0.2.60", "mfa-race")
        token = f"race-{uuid.uuid4().hex}"
        secret = pyotp.random_base32(length=32)
        now = datetime.now(UTC)
        with Session(engine) as session:
            user = _user(session, "mfa-race-totp")
            credential = MfaCredential(
                user_id=user.user_id,
                state="enrolled",
                active_secret_ciphertext=encrypt_totp_secret(
                    secret, settings.MFA_ENCRYPTION_KEY.get_secret_value()
                ),
                credential_version=1,
                last_accepted_step=int(now.timestamp() // 30) - 1,
                enrolled_at=now,
                recovery_generation=1,
            )
            session.add(credential)
            session.add(
                MfaChallenge(
                    user_id=user.user_id,
                    token_hash=hash_challenge_token(token),
                    purpose="login",
                    credential_version=1,
                    password_changed_at=None,
                    expires_at=now + timedelta(minutes=5),
                )
            )
            session.commit()
            user_id = user.user_id

        limiter = SlidingWindowLimiter(10, 300)
        code = pyotp.TOTP(secret).now()
        results = _race_two(
            engine,
            lambda: verify_challenge(
                engine,
                challenge_token=token,
                method="totp",
                code=code,
                context=context,
                settings=settings,
                mfa_limiter=limiter,
            ),
        )

        assert (
            sum(
                getattr(result, "session_token", None) is not None for result in results
            )
            == 1
        )
        assert sum(result == "MFA_CHALLENGE_INVALID" for result in results) == 1
        with Session(engine) as session:
            sessions = session.exec(
                select(AuthSession).where(AuthSession.user_id == user_id)
            ).all()
            assert len(sessions) == 1
            assert sessions[0].auth_method == "totp"
            assert (
                len(
                    session.exec(
                        select(AuditLog).where(
                            AuditLog.user_id == user_id,
                            AuditLog.action == "LOGIN_SUCCESS",
                        )
                    ).all()
                )
                == 1
            )
    finally:
        engine.dispose()
        directory.cleanup()


def test_two_file_connections_consume_one_recovery_code_once():
    engine, directory = _file_engine()
    try:
        settings = _settings()
        context = MfaRequestContext("192.0.2.61", "mfa-race")
        token = f"race-{uuid.uuid4().hex}"
        secret = pyotp.random_base32(length=32)
        codes = generate_recovery_codes()
        now = datetime.now(UTC)
        with Session(engine) as session:
            user = _user(session, "mfa-race-recovery")
            credential = MfaCredential(
                user_id=user.user_id,
                state="enrolled",
                active_secret_ciphertext=encrypt_totp_secret(
                    secret, settings.MFA_ENCRYPTION_KEY.get_secret_value()
                ),
                credential_version=1,
                last_accepted_step=int(now.timestamp() // 30) - 1,
                enrolled_at=now,
                recovery_generation=1,
            )
            session.add(credential)
            session.add(
                AuthSession(
                    session_id=f"race-session-{uuid.uuid4().hex}",
                    user_id=user.user_id,
                    created_at=now,
                    expires_at=now + timedelta(hours=1),
                    auth_method="totp",
                    mfa_credential_version=1,
                )
            )
            session.add(
                MfaChallenge(
                    user_id=user.user_id,
                    token_hash=hash_challenge_token(token),
                    purpose="login",
                    credential_version=1,
                    password_changed_at=None,
                    expires_at=now + timedelta(minutes=5),
                )
            )
            for code in codes:
                session.add(
                    MfaRecoveryCode(
                        user_id=user.user_id,
                        generation=1,
                        code_hash=hash_recovery_code(user.user_id, 1, code),
                        created_at=now,
                    )
                )
            session.commit()
            user_id = user.user_id

        limiter = SlidingWindowLimiter(10, 300)
        results = _race_two(
            engine,
            lambda: verify_challenge(
                engine,
                challenge_token=token,
                method="recovery",
                code=codes[0],
                context=context,
                settings=settings,
                mfa_limiter=limiter,
            ),
        )

        assert (
            sum(
                getattr(result, "challenge_token", None) is not None
                for result in results
            )
            == 1
        )
        assert sum(result == "MFA_CHALLENGE_INVALID" for result in results) == 1
        with Session(engine) as session:
            credential = session.get(MfaCredential, user_id)
            assert credential.state == "recovery_pending"
            rows = session.exec(
                select(MfaRecoveryCode).where(
                    MfaRecoveryCode.user_id == user_id,
                    MfaRecoveryCode.generation == 1,
                )
            ).all()
            assert sum(row.consumed_at is not None for row in rows) == 1
            assert (
                len(
                    session.exec(
                        select(AuditLog).where(
                            AuditLog.user_id == user_id,
                            AuditLog.action == "MFA_RECOVERY_USE",
                            AuditLog.result == "success",
                        )
                    ).all()
                )
                == 1
            )
    finally:
        engine.dispose()
        directory.cleanup()


def test_two_file_connections_confirm_enrollment_once():
    engine, directory = _file_engine()
    try:
        settings = _settings()
        context = MfaRequestContext("192.0.2.62", "mfa-race")
        token = f"race-{uuid.uuid4().hex}"
        pending_secret = pyotp.random_base32(length=32)
        now = datetime.now(UTC)
        with Session(engine) as session:
            user = _user(session, "mfa-race-enroll")
            session.add(MfaCredential(user_id=user.user_id, state="unenrolled"))
            session.add(
                MfaChallenge(
                    user_id=user.user_id,
                    token_hash=hash_challenge_token(token),
                    purpose="enroll",
                    credential_version=0,
                    password_changed_at=None,
                    pending_secret_ciphertext=encrypt_totp_secret(
                        pending_secret,
                        settings.MFA_ENCRYPTION_KEY.get_secret_value(),
                    ),
                    expires_at=now + timedelta(minutes=15),
                )
            )
            session.commit()
            user_id = user.user_id

        limiter = SlidingWindowLimiter(10, 300)
        code = pyotp.TOTP(pending_secret).now()
        results = _race_two(
            engine,
            lambda: confirm_enrollment(
                engine,
                challenge_token=token,
                code=code,
                context=context,
                settings=settings,
                mfa_limiter=limiter,
            ),
        )

        winners = [
            result for result in results if getattr(result, "session_token", None)
        ]
        assert len(winners) == 1
        assert len(winners[0].body.recovery_codes) == 10
        assert sum(result == "MFA_CHALLENGE_INVALID" for result in results) == 1
        with Session(engine) as session:
            credential = session.get(MfaCredential, user_id)
            assert credential.state == "enrolled"
            assert (
                len(
                    session.exec(
                        select(MfaRecoveryCode).where(
                            MfaRecoveryCode.user_id == user_id,
                            MfaRecoveryCode.generation
                            == credential.recovery_generation,
                        )
                    ).all()
                )
                == 10
            )
            assert (
                len(
                    session.exec(
                        select(AuthSession).where(AuthSession.user_id == user_id)
                    ).all()
                )
                == 1
            )
            assert (
                len(
                    session.exec(
                        select(AuditLog).where(
                            AuditLog.user_id == user_id,
                            AuditLog.action == "MFA_ENROLL",
                            AuditLog.result == "success",
                        )
                    ).all()
                )
                == 1
            )
    finally:
        engine.dispose()
        directory.cleanup()


def test_sqlite_writer_busy_returns_503_without_partial_mfa_acceptance():
    engine, directory = _file_engine(busy_timeout_ms=50)
    try:
        settings = _settings()
        context = MfaRequestContext("192.0.2.63", "mfa-busy")
        token = f"busy-{uuid.uuid4().hex}"
        secret = pyotp.random_base32(length=32)
        now = datetime.now(UTC)
        with Session(engine) as session:
            user = _user(session, "mfa-race-busy")
            credential = MfaCredential(
                user_id=user.user_id,
                state="enrolled",
                active_secret_ciphertext=encrypt_totp_secret(
                    secret, settings.MFA_ENCRYPTION_KEY.get_secret_value()
                ),
                credential_version=1,
                last_accepted_step=int(now.timestamp() // 30) - 1,
                enrolled_at=now,
                recovery_generation=1,
            )
            session.add(credential)
            session.add(
                MfaChallenge(
                    user_id=user.user_id,
                    token_hash=hash_challenge_token(token),
                    purpose="login",
                    credential_version=1,
                    expires_at=now + timedelta(minutes=5),
                )
            )
            session.commit()
            user_id = user.user_id
            accepted_step = credential.last_accepted_step

        limiter = SlidingWindowLimiter(10, 300)
        with engine.connect() as blocker:
            blocker.exec_driver_sql("BEGIN IMMEDIATE")
            with pytest.raises(AppHTTPException) as busy:
                verify_challenge(
                    engine,
                    challenge_token=token,
                    method="totp",
                    code=pyotp.TOTP(secret).now(),
                    context=context,
                    settings=settings,
                    mfa_limiter=limiter,
                )
            blocker.rollback()

        assert busy.value.code == "TEMPORARILY_UNAVAILABLE"
        with Session(engine) as session:
            assert session.get(MfaChallenge, user_id).purpose == "login"
            assert (
                session.get(MfaCredential, user_id).last_accepted_step == accepted_step
            )
            assert (
                session.exec(
                    select(AuthSession).where(AuthSession.user_id == user_id)
                ).all()
                == []
            )
            assert (
                session.exec(
                    select(AuditLog).where(
                        AuditLog.user_id == user_id,
                        AuditLog.action == "LOGIN_SUCCESS",
                    )
                ).all()
                == []
            )
    finally:
        engine.dispose()
        directory.cleanup()
