import logging
from datetime import UTC, datetime, timedelta

import pyotp
import pytest
from app.core import redaction
from app.core.errors import AppHTTPException
from app.core.mfa import hash_challenge_token, hash_recovery_code
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import get_password_hash
from app.models import (
    AuditLog,
    AuditResult,
    AuthSession,
    MfaChallenge,
    MfaCredential,
    MfaRecoveryCode,
    User,
    UserRole,
)
from app.schemas.mfa import (
    ChallengeState,
    CompletedEnrollment,
    CompletedLogin,
    CompletedReplacement,
    EnrollmentStartResponse,
    RecoveryCodesResponse,
)
from app.services.mfa import (
    MfaRequestContext,
    begin_enrollment_from_session,
    begin_password_login,
    begin_replacement,
    cancel_challenge,
    confirm_enrollment,
    get_challenge,
    get_enrollment,
    rotate_recovery_codes,
    validate_stored_mfa_secrets,
    verify_challenge,
)
from cryptography.fernet import Fernet
from sqlmodel import Session, select


def _settings(*, dev_tools_enabled=False):
    from app.core.config import Settings

    return Settings(
        _env_file=None,
        SECRET_KEY="test-secret-key-not-for-production-use",
        INTERNAL_API_KEY="test-internal-api-key-not-for-production",
        DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
        MFA_ENCRYPTION_KEY=Fernet.generate_key().decode("ascii"),
        SCHEDULER_ENABLED=False,
        DEV_TOOLS_ENABLED=dev_tools_enabled,
    )


def _next_totp_code(seed: str) -> str:
    now = datetime.now(UTC)
    next_step = int(now.timestamp() // 30) + 1
    return pyotp.TOTP(seed).at(datetime.fromtimestamp(next_step * 30, UTC))


def _enrolled_account(
    session,
    username: str,
    *,
    mfa_limiter: SlidingWindowLimiter | None = None,
    source_ip: str = "192.0.2.21",
):
    user = User(
        username=username,
        first_name="MFA",
        last_name="Account",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash("CorrectHorse9"),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    settings = _settings()
    context = MfaRequestContext(source_ip, "mfa-test-agent")
    password_limiter = SlidingWindowLimiter(10, 300)
    mfa_limiter = mfa_limiter or SlidingWindowLimiter(10, 300)
    challenge = begin_password_login(
        session.get_bind(),
        username=username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    enrollment = get_enrollment(
        session.get_bind(), challenge_token=challenge.challenge_token, settings=settings
    )
    result = confirm_enrollment(
        session.get_bind(),
        challenge_token=challenge.challenge_token,
        code=pyotp.TOTP(enrollment.body.manual_key).now(),
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )
    return (
        user,
        settings,
        context,
        password_limiter,
        mfa_limiter,
        enrollment.body.manual_key,
        result,
    )


def _fail_primary_audit_once(monkeypatch, action: str):
    from app.services import audit

    original = audit.record
    failed = False

    def fail_once(session, **kwargs):
        nonlocal failed
        if (
            not failed
            and kwargs.get("action") == action
            and kwargs.get("result") == AuditResult.SUCCESS
        ):
            failed = True
            raise RuntimeError("forced audit insert failure")
        return original(session, **kwargs)

    monkeypatch.setattr(audit, "record", fail_once)


def test_password_stage_creates_enrollment_challenge_without_authenticating(session):
    user = User(
        username="mfa-operator",
        first_name="MFA",
        last_name="Operator",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash("CorrectHorse9"),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    engine = session.get_bind()

    result = begin_password_login(
        engine,
        username="mfa-operator",
        password="CorrectHorse9",
        context=MfaRequestContext("192.0.2.10", "mfa-test-agent"),
        settings=_settings(),
        password_limiter=SlidingWindowLimiter(10, 300),
        mfa_limiter=SlidingWindowLimiter(10, 300),
    )

    assert isinstance(result.body, ChallengeState)
    assert result.body.model_dump(exclude={"expires_at"}) == {
        "status": "enrollment_required",
        "purpose": "enroll",
    }
    assert result.challenge_token
    assert result.challenge_expires_at == result.body.expires_at

    session.expire_all()
    assert (
        session.exec(
            select(AuthSession).where(AuthSession.user_id == user.user_id)
        ).all()
        == []
    )
    assert session.get(User, user.user_id).last_login is None
    assert (
        session.exec(select(AuditLog).where(AuditLog.action == "LOGIN_SUCCESS")).all()
        == []
    )
    assert (
        session.exec(select(AuditLog).where(AuditLog.action == "MFA_CHALLENGE_START"))
        .one()
        .result
        == "success"
    )
    assert session.get(MfaCredential, user.user_id).state == "unenrolled"
    stored_challenge = session.get(MfaChallenge, user.user_id)
    assert stored_challenge.purpose == "enroll"
    assert stored_challenge.token_hash != result.challenge_token
    assert len(stored_challenge.token_hash) == 64


def test_enrollment_refresh_reuses_encrypted_pending_seed_and_deadline(session):
    user = User(
        username="mfa-refresh",
        first_name="MFA",
        last_name="Refresh",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash("CorrectHorse9"),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    engine = session.get_bind()
    settings = _settings()
    challenge = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=MfaRequestContext("192.0.2.11", "mfa-test-agent"),
        settings=settings,
        password_limiter=SlidingWindowLimiter(10, 300),
        mfa_limiter=SlidingWindowLimiter(10, 300),
    )

    first = get_enrollment(
        engine, challenge_token=challenge.challenge_token, settings=settings
    )
    second = get_enrollment(
        engine, challenge_token=challenge.challenge_token, settings=settings
    )

    assert isinstance(first.body, EnrollmentStartResponse)
    assert second.body == first.body
    assert first.challenge_expires_at == challenge.challenge_expires_at
    assert first.body.issuer == "ADAS"
    assert first.body.account_name == user.username
    assert first.body.provisioning_uri.startswith("otpauth://totp/ADAS:")
    assert first.body.manual_key in first.body.provisioning_uri
    assert first.body.manual_key not in repr(first.body)
    assert first.body.manual_key not in repr(first)
    assert session.get(MfaChallenge, user.user_id).pending_secret_ciphertext != (
        first.body.manual_key
    )


def test_enrollment_confirmation_commits_factor_codes_session_and_audits(session):
    user = User(
        username="mfa-confirm",
        first_name="MFA",
        last_name="Confirm",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash("CorrectHorse9"),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    engine = session.get_bind()
    settings = _settings()
    context = MfaRequestContext("192.0.2.12", "mfa-test-agent")
    challenge = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=SlidingWindowLimiter(10, 300),
        mfa_limiter=SlidingWindowLimiter(10, 300),
    )
    enrollment = get_enrollment(
        engine, challenge_token=challenge.challenge_token, settings=settings
    )
    code = pyotp.TOTP(enrollment.body.manual_key).now()

    result = confirm_enrollment(
        engine,
        challenge_token=challenge.challenge_token,
        code=code,
        context=context,
        settings=settings,
        mfa_limiter=SlidingWindowLimiter(10, 300),
    )

    assert isinstance(result.body, CompletedEnrollment)
    assert result.body.status == "authenticated"
    assert result.body.user.user_id == user.user_id
    assert len(result.body.recovery_codes) == 10
    assert len(set(result.body.recovery_codes)) == 10
    assert result.session_token
    assert result.clear_challenge is True
    assert result.close_user_id == user.user_id
    assert result.close_reason == "mfa_enrollment"

    session.expire_all()
    credential = session.get(MfaCredential, user.user_id)
    assert credential.state == "enrolled"
    assert credential.active_secret_ciphertext != enrollment.body.manual_key
    assert credential.last_accepted_step is not None
    assert credential.recovery_generation == 1
    assert session.get(MfaChallenge, user.user_id) is None
    codes = session.exec(
        select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.user_id)
    ).all()
    assert len(codes) == 10
    assert all(row.code_hash not in result.body.recovery_codes for row in codes)
    auth_session = session.exec(
        select(AuthSession).where(AuthSession.user_id == user.user_id)
    ).one()
    assert auth_session.auth_method == "totp"
    assert auth_session.mfa_credential_version == credential.credential_version
    assert session.get(User, user.user_id).last_login is not None
    actions = session.exec(
        select(AuditLog.action).where(AuditLog.user_id == user.user_id)
    ).all()
    assert "MFA_ENROLL" in actions
    assert "LOGIN_SUCCESS" in actions


def test_totp_login_accepts_a_new_step_and_creates_only_a_totp_session(session):
    user = User(
        username="mfa-login",
        first_name="MFA",
        last_name="Login",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash("CorrectHorse9"),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    engine = session.get_bind()
    settings = _settings()
    context = MfaRequestContext("192.0.2.13", "mfa-test-agent")
    password_limiter = SlidingWindowLimiter(10, 300)
    mfa_limiter = SlidingWindowLimiter(10, 300)
    enrollment_challenge = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    enrollment = get_enrollment(
        engine,
        challenge_token=enrollment_challenge.challenge_token,
        settings=settings,
    )
    enrollment_code = pyotp.TOTP(enrollment.body.manual_key).now()
    confirm_enrollment(
        engine,
        challenge_token=enrollment_challenge.challenge_token,
        code=enrollment_code,
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )

    login_challenge = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    next_code = _next_totp_code(enrollment.body.manual_key)
    result = verify_challenge(
        engine,
        challenge_token=login_challenge.challenge_token,
        method="totp",
        code=next_code,
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )

    assert isinstance(result.body, CompletedLogin)
    assert result.body.status == "authenticated"
    assert result.body.user.user_id == user.user_id
    assert result.session_token
    assert result.clear_challenge is True
    assert result.body.user.last_login is not None
    session.expire_all()
    credential = session.get(MfaCredential, user.user_id)
    sessions = session.exec(
        select(AuthSession).where(AuthSession.user_id == user.user_id)
    ).all()
    assert len(sessions) == 2
    assert all(row.auth_method == "totp" for row in sessions)
    assert all(
        row.mfa_credential_version == credential.credential_version for row in sessions
    )
    assert session.get(MfaChallenge, user.user_id) is None
    assert session.exec(
        select(AuditLog).where(
            AuditLog.user_id == user.user_id,
            AuditLog.action == "LOGIN_SUCCESS",
        )
    ).all()


def test_enrollment_confirmation_consumes_its_totp_step_globally(session, monkeypatch):
    import app.services.mfa as mfa_service

    user = User(
        username="mfa-global-replay",
        first_name="MFA",
        last_name="Replay",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash("CorrectHorse9"),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    engine = session.get_bind()
    settings = _settings()
    context = MfaRequestContext("192.0.2.35", "mfa-test-agent")
    password_limiter = SlidingWindowLimiter(10, 300)
    mfa_limiter = SlidingWindowLimiter(10, 300)
    fixed_now = datetime.now(UTC)
    monkeypatch.setattr(mfa_service, "_now", lambda: fixed_now)
    enrollment_challenge = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    enrollment = get_enrollment(
        engine,
        challenge_token=enrollment_challenge.challenge_token,
        settings=settings,
    )
    code = pyotp.TOTP(enrollment.body.manual_key).at(fixed_now)
    confirm_enrollment(
        engine,
        challenge_token=enrollment_challenge.challenge_token,
        code=code,
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )
    login_challenge = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )

    with pytest.raises(AppHTTPException) as replay:
        verify_challenge(
            engine,
            challenge_token=login_challenge.challenge_token,
            method="totp",
            code=code,
            context=context,
            settings=settings,
            mfa_limiter=mfa_limiter,
        )

    assert replay.value.code == "MFA_INVALID_CODE"
    session.expire_all()
    assert session.get(MfaCredential, user.user_id).last_accepted_step is not None
    assert session.get(MfaChallenge, user.user_id).purpose == "login"
    assert (
        len(
            session.exec(
                select(AuthSession).where(AuthSession.user_id == user.user_id)
            ).all()
        )
        == 1
    )


def test_interrupted_recovery_requires_another_unused_code(session):
    user, settings, context, password_limiter, mfa_limiter, _seed, enrolled = (
        _enrolled_account(session, "mfa-recovery")
    )
    first_code, second_code = enrolled.body.recovery_codes[:2]
    engine = session.get_bind()
    first_login = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )

    recovery = verify_challenge(
        engine,
        challenge_token=first_login.challenge_token,
        method="recovery",
        code=first_code,
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )

    assert isinstance(recovery.body, ChallengeState)
    assert recovery.body.purpose == "recovery_enroll"
    assert recovery.body.status == "enrollment_required"
    assert recovery.challenge_token
    assert recovery.close_user_id == user.user_id
    assert recovery.close_reason == "mfa_recovery"
    session.expire_all()
    credential = session.get(MfaCredential, user.user_id)
    assert credential.state == "recovery_pending"
    assert credential.active_secret_ciphertext is None
    assert credential.credential_version == 2
    assert session.get(MfaChallenge, user.user_id).purpose == "recovery_enroll"
    recovery_rows = session.exec(
        select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.user_id)
    ).all()
    assert sum(row.consumed_at is not None for row in recovery_rows) == 1
    assert len(recovery_rows) == 10
    assert all(
        row.revoked_at is not None
        for row in session.exec(
            select(AuthSession).where(AuthSession.user_id == user.user_id)
        ).all()
    )

    cancel_challenge(
        engine,
        challenge_token=recovery.challenge_token,
        context=context,
        settings=settings,
    )
    restarted = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    assert restarted.body.purpose == "recovery_verify"
    with pytest.raises(Exception) as seed_error:
        get_enrollment(
            engine,
            challenge_token=restarted.challenge_token,
            settings=settings,
        )
    assert getattr(seed_error.value, "code", None) == "MFA_CHALLENGE_INVALID"

    continued = verify_challenge(
        engine,
        challenge_token=restarted.challenge_token,
        method="recovery",
        code=second_code,
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )
    assert continued.body.purpose == "recovery_enroll"
    assert continued.challenge_token
    assert continued.challenge_token != recovery.challenge_token
    session.expire_all()
    recovery_rows = session.exec(
        select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.user_id)
    ).all()
    assert sum(row.consumed_at is not None for row in recovery_rows) == 2
    assert session.exec(
        select(AuditLog).where(
            AuditLog.user_id == user.user_id,
            AuditLog.action == "MFA_RECOVERY_USE",
        )
    ).all()


def test_recovery_enrollment_replaces_old_batch_and_creates_totp_session(session):
    user, settings, context, password_limiter, mfa_limiter, _seed, enrolled = (
        _enrolled_account(session, "mfa-recovery-done")
    )
    engine = session.get_bind()
    old_codes = set(enrolled.body.recovery_codes)
    login = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    recovery = verify_challenge(
        engine,
        challenge_token=login.challenge_token,
        method="recovery",
        code=next(iter(old_codes)),
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )
    pending = get_enrollment(
        engine, challenge_token=recovery.challenge_token, settings=settings
    )
    result = confirm_enrollment(
        engine,
        challenge_token=recovery.challenge_token,
        code=pyotp.TOTP(pending.body.manual_key).now(),
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )

    assert isinstance(result.body, CompletedEnrollment)
    new_codes = set(result.body.recovery_codes)
    assert len(new_codes) == 10
    assert old_codes.isdisjoint(new_codes)
    assert result.session_token
    session.expire_all()
    credential = session.get(MfaCredential, user.user_id)
    assert credential.state == "enrolled"
    assert credential.credential_version == 3
    assert credential.last_accepted_step is not None
    assert credential.recovery_generation == 2
    assert session.get(MfaChallenge, user.user_id) is None
    current_rows = session.exec(
        select(MfaRecoveryCode).where(
            MfaRecoveryCode.user_id == user.user_id,
            MfaRecoveryCode.generation == 2,
        )
    ).all()
    assert len(current_rows) == 10
    assert (
        len(
            session.exec(
                select(MfaRecoveryCode).where(
                    MfaRecoveryCode.user_id == user.user_id,
                    MfaRecoveryCode.generation == 1,
                )
            ).all()
        )
        == 0
    )
    sessions = session.exec(
        select(AuthSession).where(AuthSession.user_id == user.user_id)
    ).all()
    assert sum(row.revoked_at is None for row in sessions) == 1
    active = next(row for row in sessions if row.revoked_at is None)
    assert active.auth_method == "totp"
    assert active.mfa_credential_version == credential.credential_version
    assert (
        session.exec(
            select(AuditLog).where(
                AuditLog.user_id == user.user_id,
                AuditLog.action == "MFA_ENROLL",
                AuditLog.detail.like('%"source": "recovery"%'),
            )
        ).first()
        is not None
    )


def test_recovery_rotation_requires_fresh_proofs_and_preserves_sessions(session):
    user, settings, context, password_limiter, mfa_limiter, seed, enrolled = (
        _enrolled_account(session, "mfa-rotate")
    )
    engine = session.get_bind()
    first_codes = enrolled.body.recovery_codes
    auth_session = session.exec(
        select(AuthSession).where(AuthSession.user_id == user.user_id)
    ).one()
    session.expire_all()
    previous_login = session.get(User, user.user_id).last_login
    previous_version = session.get(MfaCredential, user.user_id).credential_version
    outstanding = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )

    result = rotate_recovery_codes(
        engine,
        session_id=auth_session.session_id,
        user_id=user.user_id,
        password="CorrectHorse9",
        code=_next_totp_code(seed),
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )

    assert isinstance(result.body, RecoveryCodesResponse)
    new_codes = result.body.recovery_codes
    assert len(new_codes) == 10
    assert len(set(new_codes)) == 10
    assert set(first_codes).isdisjoint(new_codes)
    assert result.clear_challenge is True
    session.expire_all()
    credential = session.get(MfaCredential, user.user_id)
    assert credential.credential_version == previous_version
    assert session.get(User, user.user_id).last_login == previous_login
    assert session.get(AuthSession, auth_session.session_id).revoked_at is None
    assert session.get(MfaChallenge, user.user_id) is None
    rows = session.exec(
        select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.user_id)
    ).all()
    assert len(rows) == 10
    assert all(row.generation == credential.recovery_generation for row in rows)
    with pytest.raises(Exception) as invalidated:
        verify_challenge(
            engine,
            challenge_token=outstanding.challenge_token,
            method="recovery",
            code=first_codes[0],
            context=context,
            settings=settings,
            mfa_limiter=mfa_limiter,
        )
    assert getattr(invalidated.value, "code", None) == "MFA_CHALLENGE_INVALID"


def test_replacement_confirmation_swaps_factor_and_revokes_every_session(session):
    user, settings, context, _password_limiter, mfa_limiter, seed, enrolled = (
        _enrolled_account(session, "mfa-replace")
    )
    engine = session.get_bind()
    old_codes = enrolled.body.recovery_codes
    existing_session = session.exec(
        select(AuthSession).where(AuthSession.user_id == user.user_id)
    ).one()
    old_credential = session.get(MfaCredential, user.user_id)
    old_ciphertext = old_credential.active_secret_ciphertext
    old_version = old_credential.credential_version
    login_successes = len(
        session.exec(
            select(AuditLog).where(
                AuditLog.user_id == user.user_id,
                AuditLog.action == "LOGIN_SUCCESS",
            )
        ).all()
    )

    replacement = begin_replacement(
        engine,
        session_id=existing_session.session_id,
        user_id=user.user_id,
        password="CorrectHorse9",
        code=_next_totp_code(seed),
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )
    pending = get_enrollment(
        engine,
        challenge_token=replacement.challenge_token,
        settings=settings,
    )

    assert replacement.body.purpose == "replace"
    assert replacement.body.status == "enrollment_required"
    assert pending.body.manual_key != seed
    session.expire_all()
    assert session.get(MfaCredential, user.user_id).active_secret_ciphertext == (
        old_ciphertext
    )
    assert session.get(MfaCredential, user.user_id).credential_version == old_version
    assert session.get(AuthSession, existing_session.session_id).revoked_at is None

    result = confirm_enrollment(
        engine,
        challenge_token=replacement.challenge_token,
        code=pyotp.TOTP(pending.body.manual_key).now(),
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )

    assert isinstance(result.body, CompletedReplacement)
    assert result.body.status == "reauthentication_required"
    assert set(result.body.recovery_codes).isdisjoint(old_codes)
    assert result.session_token is None
    assert result.clear_challenge is True
    assert result.clear_session is True
    assert result.close_user_id == user.user_id
    assert result.close_reason == "mfa_replacement"
    session.expire_all()
    credential = session.get(MfaCredential, user.user_id)
    assert credential.active_secret_ciphertext != old_ciphertext
    assert credential.credential_version == old_version + 1
    assert session.get(MfaChallenge, user.user_id) is None
    assert all(
        row.revoked_at is not None
        for row in session.exec(
            select(AuthSession).where(AuthSession.user_id == user.user_id)
        ).all()
    )
    assert (
        len(
            session.exec(
                select(AuditLog).where(
                    AuditLog.user_id == user.user_id,
                    AuditLog.action == "LOGIN_SUCCESS",
                )
            ).all()
        )
        == login_successes
    )


def test_replacement_cancellation_keeps_the_old_factor_and_session(session):
    user, settings, context, _password_limiter, mfa_limiter, seed, _enrolled = (
        _enrolled_account(session, "mfa-replace-cancel")
    )
    engine = session.get_bind()
    auth_session = session.exec(
        select(AuthSession).where(AuthSession.user_id == user.user_id)
    ).one()
    session.expire_all()
    old_ciphertext = session.get(MfaCredential, user.user_id).active_secret_ciphertext
    replacement = begin_replacement(
        engine,
        session_id=auth_session.session_id,
        user_id=user.user_id,
        password="CorrectHorse9",
        code=_next_totp_code(seed),
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )

    cancelled = cancel_challenge(
        engine,
        challenge_token=replacement.challenge_token,
        context=context,
        settings=settings,
    )

    assert cancelled.clear_challenge is True
    session.expire_all()
    assert session.get(MfaChallenge, user.user_id) is None
    assert session.get(MfaCredential, user.user_id).active_secret_ciphertext == (
        old_ciphertext
    )
    assert session.get(AuthSession, auth_session.session_id).revoked_at is None


def test_expired_replacement_challenge_leaves_old_factor_intact(session):
    user, settings, context, _password_limiter, mfa_limiter, seed, _enrolled = (
        _enrolled_account(session, "mfa-replace-expiry")
    )
    engine = session.get_bind()
    auth_session = session.exec(
        select(AuthSession).where(AuthSession.user_id == user.user_id)
    ).one()
    session.expire_all()
    old_ciphertext = session.get(MfaCredential, user.user_id).active_secret_ciphertext
    replacement = begin_replacement(
        engine,
        session_id=auth_session.session_id,
        user_id=user.user_id,
        password="CorrectHorse9",
        code=_next_totp_code(seed),
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )
    with Session(engine) as update_session:
        challenge = update_session.get(MfaChallenge, user.user_id)
        challenge.expires_at = datetime.now(UTC) - timedelta(microseconds=1)
        update_session.add(challenge)
        update_session.commit()

    cancelled = cancel_challenge(
        engine,
        challenge_token=replacement.challenge_token,
        context=context,
        settings=settings,
    )

    assert cancelled.clear_challenge is True
    session.expire_all()
    assert session.get(MfaChallenge, user.user_id) is None
    assert session.get(MfaCredential, user.user_id).active_secret_ciphertext == (
        old_ciphertext
    )
    assert session.get(AuthSession, auth_session.session_id).revoked_at is None


def test_demo_enrollment_requires_password_then_new_factor_proof(session):
    user = User(
        username="mfa-demo-enroll",
        first_name="MFA",
        last_name="Demo",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash("CorrectHorse9"),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    settings = _settings(dev_tools_enabled=True)
    now = datetime.now(UTC)
    demo_session = AuthSession(
        session_id="demo-session-enroll",
        user_id=user.user_id,
        created_at=now,
        expires_at=now + timedelta(hours=1),
        auth_method="demo_impersonation",
    )
    session.add(demo_session)
    session.commit()
    engine = session.get_bind()
    context = MfaRequestContext("192.0.2.22", "mfa-test-agent")
    password_limiter = SlidingWindowLimiter(10, 300)
    mfa_limiter = SlidingWindowLimiter(10, 300)

    challenge = begin_enrollment_from_session(
        engine,
        session_id=demo_session.session_id,
        user_id=user.user_id,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )

    assert challenge.body.purpose == "enroll"
    assert challenge.challenge_token
    session.expire_all()
    assert session.get(MfaCredential, user.user_id).state == "unenrolled"
    assert session.get(AuthSession, demo_session.session_id).revoked_at is None
    enrollment = get_enrollment(
        engine, challenge_token=challenge.challenge_token, settings=settings
    )
    result = confirm_enrollment(
        engine,
        challenge_token=challenge.challenge_token,
        code=pyotp.TOTP(enrollment.body.manual_key).now(),
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )

    assert isinstance(result.body, CompletedEnrollment)
    session.expire_all()
    assert session.get(AuthSession, demo_session.session_id).revocation_reason == (
        "mfa_enrollment"
    )
    active = session.exec(
        select(AuthSession).where(
            AuthSession.user_id == user.user_id,
            AuthSession.revoked_at.is_(None),
        )
    ).one()
    assert active.auth_method == "totp"
    assert (
        session.exec(
            select(AuditLog.detail).where(
                AuditLog.user_id == user.user_id,
                AuditLog.action == "MFA_ENROLL",
            )
        )
        .one()
        .find('"source": "demo"')
        >= 0
    )


def test_exhausted_last_recovery_code_leaves_no_password_only_restart(session):
    user, settings, context, password_limiter, mfa_limiter, _seed, enrolled = (
        _enrolled_account(session, "mfa-exhausted")
    )
    engine = session.get_bind()
    last_challenge = None
    for code in enrolled.body.recovery_codes:
        login = begin_password_login(
            engine,
            username=user.username,
            password="CorrectHorse9",
            context=context,
            settings=settings,
            password_limiter=password_limiter,
            mfa_limiter=mfa_limiter,
        )
        recovery = verify_challenge(
            engine,
            challenge_token=login.challenge_token,
            method="recovery",
            code=code,
            context=context,
            settings=settings,
            mfa_limiter=mfa_limiter,
        )
        last_challenge = recovery.challenge_token
        if code != enrolled.body.recovery_codes[-1]:
            cancel_challenge(
                engine,
                challenge_token=last_challenge,
                context=context,
                settings=settings,
            )

    assert last_challenge
    cancel_challenge(
        engine,
        challenge_token=last_challenge,
        context=context,
        settings=settings,
    )
    restart = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    assert restart.body.purpose == "recovery_verify"
    with pytest.raises(Exception) as no_seed:
        get_enrollment(
            engine, challenge_token=restart.challenge_token, settings=settings
        )
    assert getattr(no_seed.value, "code", None) == "MFA_CHALLENGE_INVALID"
    with pytest.raises(Exception) as exhausted:
        verify_challenge(
            engine,
            challenge_token=restart.challenge_token,
            method="recovery",
            code=enrolled.body.recovery_codes[-1],
            context=context,
            settings=settings,
            mfa_limiter=mfa_limiter,
        )
    assert getattr(exhausted.value, "code", None) == "MFA_INVALID_CODE"
    session.expire_all()
    assert session.get(MfaCredential, user.user_id).state == "recovery_pending"
    assert all(
        row.consumed_at is not None
        for row in session.exec(
            select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.user_id)
        ).all()
    )
    assert (
        session.exec(select(MfaChallenge).where(MfaChallenge.user_id == user.user_id))
        .one()
        .purpose
        == "recovery_verify"
    )


def test_mfa_secrets_are_redacted_from_record_reprs_and_nested_audit_details(
    session, monkeypatch
):
    from app.services import audit
    from app.services.mfa import MfaServiceResult

    settings = _settings()
    monkeypatch.setattr(redaction, "settings", settings)
    key = settings.MFA_ENCRYPTION_KEY.get_secret_value()
    assert key not in redaction.redact_text(f"MFA_ENCRYPTION_KEY={key}")

    sentinel = "RECOVERY-SENTINEL-DO-NOT-LOG"
    response = EnrollmentStartResponse(
        provisioning_uri=f"otpauth://totp/ADAS?secret={sentinel}",
        manual_key=sentinel,
        account_name="mfa-redact",
        expires_at=datetime.now(UTC),
    )
    result = MfaServiceResult(
        body=response,
        challenge_token=sentinel,
        session_token=sentinel,
    )
    assert sentinel not in repr(response)
    assert sentinel not in repr(result)

    user = User(
        username="mfa-redact",
        first_name="MFA",
        last_name="Redact",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash("CorrectHorse9"),
    )
    session.add(user)
    session.commit()
    audit.record(
        session,
        action="MFA_CHALLENGE_CANCEL",
        actor=user,
        detail={
            "phase": "cancelled",
            "mfa_code": sentinel,
            "nested": {
                "manual_key": sentinel,
                "challenge_token": sentinel,
                "pending_secret_ciphertext": sentinel,
            },
        },
    )
    session.commit()
    row = session.exec(
        select(AuditLog).where(
            AuditLog.user_id == user.user_id,
            AuditLog.action == "MFA_CHALLENGE_CANCEL",
        )
    ).one()
    assert sentinel not in row.detail
    assert row.detail.count("***REDACTED***") == 4


def test_failed_code_does_not_leak_code_token_or_seed_to_logs(session, caplog):
    user, settings, context, password_limiter, mfa_limiter, seed, _enrolled = (
        _enrolled_account(session, "mfa-log-check")
    )
    engine = session.get_bind()
    challenge = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    proof_sentinel = "AUTH-CODE-LOG-SENTINEL"

    with caplog.at_level(logging.DEBUG), pytest.raises(AppHTTPException):
        verify_challenge(
            engine,
            challenge_token=challenge.challenge_token,
            method="totp",
            code=proof_sentinel,
            context=context,
            settings=settings,
            mfa_limiter=mfa_limiter,
        )

    assert proof_sentinel not in caplog.text
    assert challenge.challenge_token not in caplog.text
    assert seed not in caplog.text


def test_stored_seed_validator_checks_active_and_pending_ciphertext_without_echoing(
    session,
):
    user, settings, context, _password_limiter, mfa_limiter, seed, _enrolled = (
        _enrolled_account(session, "mfa-key-check")
    )
    engine = session.get_bind()
    key = settings.MFA_ENCRYPTION_KEY.get_secret_value()
    validate_stored_mfa_secrets(engine, key)
    begin_replacement(
        engine,
        session_id=session.exec(
            select(AuthSession).where(AuthSession.user_id == user.user_id)
        )
        .one()
        .session_id,
        user_id=user.user_id,
        password="CorrectHorse9",
        code=_next_totp_code(seed),
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )
    validate_stored_mfa_secrets(engine, key)

    wrong_key = Fernet.generate_key().decode("ascii")
    with pytest.raises(ValueError) as wrong_key_error:
        validate_stored_mfa_secrets(engine, wrong_key)
    assert wrong_key not in str(wrong_key_error.value)
    assert seed not in str(wrong_key_error.value)

    with Session(engine) as write_session:
        credential = write_session.get(MfaCredential, user.user_id)
        credential.active_secret_ciphertext = "corrupt-mfa-ciphertext-sentinel"
        write_session.add(credential)
        write_session.commit()
    with pytest.raises(ValueError) as ciphertext_error:
        validate_stored_mfa_secrets(engine, key)
    assert "corrupt-mfa-ciphertext-sentinel" not in str(ciphertext_error.value)


def test_demo_replacement_requires_enabled_demo_mode_password_and_totp(session):
    user, settings, context, _password_limiter, mfa_limiter, seed, _enrolled = (
        _enrolled_account(session, "mfa-demo-replace")
    )
    engine = session.get_bind()
    with Session(engine) as write_session:
        auth_session = write_session.exec(
            select(AuthSession).where(AuthSession.user_id == user.user_id)
        ).one()
        auth_session.auth_method = "demo_impersonation"
        auth_session.mfa_credential_version = None
        write_session.add(auth_session)
        write_session.commit()
        session_id = auth_session.session_id

    with pytest.raises(AppHTTPException) as disabled:
        begin_replacement(
            engine,
            session_id=session_id,
            user_id=user.user_id,
            password="CorrectHorse9",
            code=_next_totp_code(seed),
            context=context,
            settings=settings,
            mfa_limiter=mfa_limiter,
        )
    assert disabled.value.code == "AUTH_REVOKED"
    assert session.get(MfaChallenge, user.user_id) is None

    enabled_settings = settings.model_copy(update={"DEV_TOOLS_ENABLED": True})
    result = begin_replacement(
        engine,
        session_id=session_id,
        user_id=user.user_id,
        password="CorrectHorse9",
        code=_next_totp_code(seed),
        context=context,
        settings=enabled_settings,
        mfa_limiter=mfa_limiter,
    )
    assert result.body.purpose == "replace"
    session.expire_all()
    assert session.get(AuthSession, session_id).revoked_at is None


def test_demo_rotation_requires_current_password_and_active_totp(session):
    user, settings, context, _password_limiter, mfa_limiter, seed, enrolled = (
        _enrolled_account(session, "mfa-demo-rotate")
    )
    engine = session.get_bind()
    auth_session = session.exec(
        select(AuthSession).where(AuthSession.user_id == user.user_id)
    ).one()
    with Session(engine) as write_session:
        demo_session = write_session.get(AuthSession, auth_session.session_id)
        demo_session.auth_method = "demo_impersonation"
        demo_session.mfa_credential_version = None
        write_session.add(demo_session)
        write_session.commit()

    result = rotate_recovery_codes(
        engine,
        session_id=auth_session.session_id,
        user_id=user.user_id,
        password="CorrectHorse9",
        code=_next_totp_code(seed),
        context=context,
        settings=settings.model_copy(update={"DEV_TOOLS_ENABLED": True}),
        mfa_limiter=mfa_limiter,
    )

    assert isinstance(result.body, RecoveryCodesResponse)
    assert set(result.body.recovery_codes).isdisjoint(enrolled.body.recovery_codes)
    session.expire_all()
    assert session.get(AuthSession, auth_session.session_id).revoked_at is None
    assert session.get(AuthSession, auth_session.session_id).auth_method == (
        "demo_impersonation"
    )


def test_challenge_deadline_is_inclusive_and_new_password_flow_supersedes_old(
    session, monkeypatch
):
    import app.services.mfa as mfa_service

    user = User(
        username="mfa-deadline",
        first_name="MFA",
        last_name="Deadline",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash("CorrectHorse9"),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    engine = session.get_bind()
    settings = _settings()
    context = MfaRequestContext("192.0.2.32", "mfa-test-agent")
    password_limiter = SlidingWindowLimiter(10, 300)
    mfa_limiter = SlidingWindowLimiter(10, 300)
    first = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    original_now = mfa_service._now
    deadline = first.challenge_expires_at
    monkeypatch.setattr(mfa_service, "_now", lambda: deadline)

    assert (
        get_challenge(
            engine, challenge_token=first.challenge_token, settings=settings
        ).body.expires_at
        == deadline
    )

    monkeypatch.setattr(
        mfa_service,
        "_now",
        lambda: deadline + timedelta(microseconds=1),
    )
    with pytest.raises(AppHTTPException) as expired:
        get_challenge(engine, challenge_token=first.challenge_token, settings=settings)
    assert expired.value.code == "MFA_CHALLENGE_INVALID"

    monkeypatch.setattr(mfa_service, "_now", original_now)
    second = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    assert second.challenge_token != first.challenge_token
    with pytest.raises(AppHTTPException) as superseded:
        get_challenge(engine, challenge_token=first.challenge_token, settings=settings)
    assert superseded.value.code == "MFA_CHALLENGE_INVALID"


def test_password_failures_are_generic_and_password_limiter_success_is_deferred(
    session,
):
    user = User(
        username="mfa-pass-limit",
        first_name="MFA",
        last_name="Limiter",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash("CorrectHorse9"),
    )
    session.add(user)
    inactive_user = User(
        username="mfa-inactive-user",
        first_name="MFA",
        last_name="Inactive",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash("CorrectHorse9"),
        is_active=False,
    )
    session.add(inactive_user)
    session.commit()
    engine = session.get_bind()
    settings = _settings()
    limiter = SlidingWindowLimiter(2, 300)
    mfa_limiter = SlidingWindowLimiter(2, 300)
    context = MfaRequestContext("192.0.2.33", "mfa-test-agent")

    with pytest.raises(AppHTTPException) as wrong_password:
        begin_password_login(
            engine,
            username=user.username,
            password="WrongPass9",
            context=context,
            settings=settings,
            password_limiter=limiter,
            mfa_limiter=mfa_limiter,
        )
    with pytest.raises(AppHTTPException) as unknown_user:
        begin_password_login(
            engine,
            username="unknown-mfa-user",
            password="WrongPass9",
            context=MfaRequestContext("192.0.2.34", "mfa-test-agent"),
            settings=settings,
            password_limiter=SlidingWindowLimiter(2, 300),
            mfa_limiter=mfa_limiter,
        )
    with pytest.raises(AppHTTPException) as inactive_account:
        begin_password_login(
            engine,
            username=inactive_user.username,
            password="CorrectHorse9",
            context=MfaRequestContext("192.0.2.35", "mfa-test-agent"),
            settings=settings,
            password_limiter=SlidingWindowLimiter(2, 300),
            mfa_limiter=mfa_limiter,
        )
    assert (
        wrong_password.value.status_code,
        wrong_password.value.detail,
        wrong_password.value.code,
    ) == (
        unknown_user.value.status_code,
        unknown_user.value.detail,
        unknown_user.value.code,
    )
    assert (
        inactive_account.value.status_code,
        inactive_account.value.detail,
        inactive_account.value.code,
    ) == (
        unknown_user.value.status_code,
        unknown_user.value.detail,
        unknown_user.value.code,
    )

    challenge = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=limiter,
        mfa_limiter=mfa_limiter,
    )
    assert challenge.body.purpose == "enroll"
    with pytest.raises(AppHTTPException) as second_failure:
        begin_password_login(
            engine,
            username=user.username,
            password="WrongPass9",
            context=context,
            settings=settings,
            password_limiter=limiter,
            mfa_limiter=mfa_limiter,
        )
    assert second_failure.value.code == "AUTH_INVALID_CREDENTIALS"
    with pytest.raises(AppHTTPException) as rate_limited:
        begin_password_login(
            engine,
            username=user.username,
            password="CorrectHorse9",
            context=context,
            settings=settings,
            password_limiter=limiter,
            mfa_limiter=mfa_limiter,
        )
    assert rate_limited.value.status_code == 429
    assert rate_limited.value.code == "AUTH_RATE_LIMITED"
    assert int(rate_limited.value.headers["Retry-After"]) >= 1
    session.expire_all()
    assert (
        session.exec(
            select(AuthSession).where(AuthSession.user_id == user.user_id)
        ).all()
        == []
    )


def test_mfa_limits_isolate_accounts_and_ips_and_password_restart_cannot_clear_them(
    session,
):
    shared_limiter = SlidingWindowLimiter(1, 300)
    first = _enrolled_account(
        session,
        "mfa-limit-first",
        mfa_limiter=shared_limiter,
        source_ip="192.0.2.41",
    )
    other_ip = _enrolled_account(
        session,
        "mfa-limit-other-ip",
        mfa_limiter=shared_limiter,
        source_ip="192.0.2.42",
    )
    same_ip = _enrolled_account(
        session,
        "mfa-limit-same-ip",
        mfa_limiter=shared_limiter,
        source_ip="192.0.2.41",
    )
    first_user, settings, context, password_limiter, _, first_seed, _ = first
    first_challenge = begin_password_login(
        session.get_bind(),
        username=first_user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=shared_limiter,
    )
    with pytest.raises(AppHTTPException) as wrong_code:
        verify_challenge(
            session.get_bind(),
            challenge_token=first_challenge.challenge_token,
            method="totp",
            code="not-a-totp-code",
            context=context,
            settings=settings,
            mfa_limiter=shared_limiter,
        )
    assert wrong_code.value.code == "MFA_INVALID_CODE"

    restarted = begin_password_login(
        session.get_bind(),
        username=first_user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=shared_limiter,
    )
    with pytest.raises(AppHTTPException) as account_limited:
        verify_challenge(
            session.get_bind(),
            challenge_token=restarted.challenge_token,
            method="totp",
            code=_next_totp_code(first_seed),
            context=context,
            settings=settings,
            mfa_limiter=shared_limiter,
        )
    assert account_limited.value.code == "AUTH_RATE_LIMITED"
    assert int(account_limited.value.headers["Retry-After"]) >= 1

    (
        other_user,
        other_settings,
        other_context,
        other_password_limiter,
        _,
        other_seed,
        _,
    ) = other_ip
    other_challenge = begin_password_login(
        session.get_bind(),
        username=other_user.username,
        password="CorrectHorse9",
        context=other_context,
        settings=other_settings,
        password_limiter=other_password_limiter,
        mfa_limiter=shared_limiter,
    )
    other_login = verify_challenge(
        session.get_bind(),
        challenge_token=other_challenge.challenge_token,
        method="totp",
        code=_next_totp_code(other_seed),
        context=other_context,
        settings=other_settings,
        mfa_limiter=shared_limiter,
    )
    assert isinstance(other_login.body, CompletedLogin)

    (
        same_ip_user,
        same_ip_settings,
        same_ip_context,
        same_ip_password_limiter,
        _,
        same_ip_seed,
        _,
    ) = same_ip
    same_ip_challenge = begin_password_login(
        session.get_bind(),
        username=same_ip_user.username,
        password="CorrectHorse9",
        context=same_ip_context,
        settings=same_ip_settings,
        password_limiter=same_ip_password_limiter,
        mfa_limiter=shared_limiter,
    )
    with pytest.raises(AppHTTPException) as ip_limited:
        verify_challenge(
            session.get_bind(),
            challenge_token=same_ip_challenge.challenge_token,
            method="totp",
            code=_next_totp_code(same_ip_seed),
            context=same_ip_context,
            settings=same_ip_settings,
            mfa_limiter=shared_limiter,
        )
    assert ip_limited.value.code == "AUTH_RATE_LIMITED"
    assert int(ip_limited.value.headers["Retry-After"]) >= 1


def test_password_hash_is_rechecked_after_hash_verification_before_challenge_write(
    session, monkeypatch
):
    import app.services.mfa as mfa_service

    user = User(
        username="mfa-password-race",
        first_name="MFA",
        last_name="Race",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash("CorrectHorse9"),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    engine = session.get_bind()
    settings = _settings()
    limiter = SlidingWindowLimiter(10, 300)
    old_begin_write = mfa_service._begin_write
    original_hash = user.password_hash

    def change_password_before_reservation(write_session):
        current_user = write_session.get(User, user.user_id)
        current_user.password_hash = get_password_hash("ChangedPass9")
        current_user.password_changed_at = datetime.now(UTC)
        write_session.add(current_user)
        write_session.commit()
        old_begin_write(write_session)

    monkeypatch.setattr(mfa_service, "_begin_write", change_password_before_reservation)
    with pytest.raises(AppHTTPException) as stale_password:
        begin_password_login(
            engine,
            username=user.username,
            password="CorrectHorse9",
            context=MfaRequestContext("192.0.2.43", "mfa-test-agent"),
            settings=settings,
            password_limiter=limiter,
            mfa_limiter=SlidingWindowLimiter(10, 300),
        )

    assert stale_password.value.code == "AUTH_INVALID_CREDENTIALS"
    session.expire_all()
    assert session.get(User, user.user_id).password_hash != original_hash
    assert session.get(MfaCredential, user.user_id) is None
    assert session.get(MfaChallenge, user.user_id) is None
    assert (
        session.exec(
            select(AuthSession).where(AuthSession.user_id == user.user_id)
        ).all()
        == []
    )


def test_challenge_expiry_is_rechecked_inside_the_writer_transaction(
    session, monkeypatch
):
    import app.services.mfa as mfa_service

    user, settings, context, password_limiter, mfa_limiter, seed, _enrolled = (
        _enrolled_account(session, "mfa-expiry-race")
    )
    engine = session.get_bind()
    challenge = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    previous_step = session.get(MfaCredential, user.user_id).last_accepted_step
    session.expire_all()
    old_begin_write = mfa_service._begin_write

    def expire_before_reservation(write_session):
        stored = write_session.get(MfaChallenge, user.user_id)
        stored.expires_at = datetime.now(UTC) - timedelta(microseconds=1)
        write_session.add(stored)
        write_session.commit()
        old_begin_write(write_session)

    monkeypatch.setattr(mfa_service, "_begin_write", expire_before_reservation)
    with pytest.raises(AppHTTPException) as stale_challenge:
        verify_challenge(
            engine,
            challenge_token=challenge.challenge_token,
            method="totp",
            code=_next_totp_code(seed),
            context=context,
            settings=settings,
            mfa_limiter=mfa_limiter,
        )

    assert stale_challenge.value.code == "MFA_CHALLENGE_INVALID"
    session.expire_all()
    assert session.get(MfaChallenge, user.user_id).expires_at < datetime.now(UTC)
    assert session.get(MfaCredential, user.user_id).last_accepted_step == previous_step
    assert (
        len(
            session.exec(
                select(AuthSession).where(AuthSession.user_id == user.user_id)
            ).all()
        )
        == 1
    )


def test_credential_version_is_rechecked_inside_the_writer_transaction(
    session, monkeypatch
):
    import app.services.mfa as mfa_service

    user, settings, context, password_limiter, mfa_limiter, seed, _enrolled = (
        _enrolled_account(session, "mfa-version-race")
    )
    engine = session.get_bind()
    challenge = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    old_begin_write = mfa_service._begin_write

    def bump_version_before_reservation(write_session):
        credential = write_session.get(MfaCredential, user.user_id)
        credential.credential_version += 1
        write_session.add(credential)
        write_session.commit()
        old_begin_write(write_session)

    monkeypatch.setattr(mfa_service, "_begin_write", bump_version_before_reservation)
    with pytest.raises(AppHTTPException) as stale_version:
        verify_challenge(
            engine,
            challenge_token=challenge.challenge_token,
            method="totp",
            code=_next_totp_code(seed),
            context=context,
            settings=settings,
            mfa_limiter=mfa_limiter,
        )

    assert stale_version.value.code == "MFA_CHALLENGE_INVALID"
    session.expire_all()
    assert session.get(MfaChallenge, user.user_id).credential_version == 1
    assert session.get(MfaCredential, user.user_id).credential_version == 2
    assert (
        len(
            session.exec(
                select(AuthSession).where(AuthSession.user_id == user.user_id)
            ).all()
        )
        == 1
    )


def test_login_audit_failure_rolls_back_accepted_totp_and_new_session(
    session, monkeypatch
):
    user, settings, context, password_limiter, mfa_limiter, seed, _enrolled = (
        _enrolled_account(session, "mfa-login-rollback")
    )
    engine = session.get_bind()
    challenge = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    session.expire_all()
    previous_step = session.get(MfaCredential, user.user_id).last_accepted_step
    previous_last_login = session.get(User, user.user_id).last_login
    session_count = len(
        session.exec(
            select(AuthSession).where(AuthSession.user_id == user.user_id)
        ).all()
    )
    _fail_primary_audit_once(monkeypatch, "LOGIN_SUCCESS")

    with pytest.raises(AppHTTPException) as failure:
        verify_challenge(
            engine,
            challenge_token=challenge.challenge_token,
            method="totp",
            code=_next_totp_code(seed),
            context=context,
            settings=settings,
            mfa_limiter=mfa_limiter,
        )

    assert failure.value.code == "TEMPORARILY_UNAVAILABLE"
    session.expire_all()
    assert session.get(MfaChallenge, user.user_id) is not None
    assert session.get(MfaCredential, user.user_id).last_accepted_step == previous_step
    assert session.get(User, user.user_id).last_login == previous_last_login
    assert (
        len(
            session.exec(
                select(AuthSession).where(AuthSession.user_id == user.user_id)
            ).all()
        )
        == session_count
    )
    assert (
        session.exec(
            select(AuditLog).where(
                AuditLog.user_id == user.user_id,
                AuditLog.action == "LOGIN_FAILURE",
                AuditLog.result == "failure",
            )
        ).first()
        is not None
    )


def test_recovery_audit_failure_preserves_code_factor_session_and_challenge(
    session, monkeypatch
):
    user, settings, context, password_limiter, mfa_limiter, _seed, enrolled = (
        _enrolled_account(session, "mfa-rec-rollback")
    )
    engine = session.get_bind()
    challenge = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    original_ciphertext = session.get(
        MfaCredential, user.user_id
    ).active_secret_ciphertext
    sessions = session.exec(
        select(AuthSession).where(AuthSession.user_id == user.user_id)
    ).all()
    _fail_primary_audit_once(monkeypatch, "MFA_RECOVERY_USE")

    with pytest.raises(AppHTTPException) as failure:
        verify_challenge(
            engine,
            challenge_token=challenge.challenge_token,
            method="recovery",
            code=enrolled.body.recovery_codes[0],
            context=context,
            settings=settings,
            mfa_limiter=mfa_limiter,
        )

    assert failure.value.code == "TEMPORARILY_UNAVAILABLE"
    session.expire_all()
    credential = session.get(MfaCredential, user.user_id)
    assert credential.state == "enrolled"
    assert credential.active_secret_ciphertext == original_ciphertext
    assert session.get(MfaChallenge, user.user_id).purpose == "login"
    assert all(
        session.get(AuthSession, row.session_id).revoked_at is None for row in sessions
    )
    recovery_row = session.exec(
        select(MfaRecoveryCode).where(
            MfaRecoveryCode.user_id == user.user_id,
            MfaRecoveryCode.generation == credential.recovery_generation,
        )
    ).all()
    assert all(row.consumed_at is None for row in recovery_row)
    assert (
        session.exec(
            select(AuditLog).where(
                AuditLog.user_id == user.user_id,
                AuditLog.action == "MFA_RECOVERY_USE",
                AuditLog.result == "failure",
            )
        ).first()
        is not None
    )


def test_enrollment_audit_failure_rolls_back_factor_batch_and_session(
    session, monkeypatch
):
    user = User(
        username="mfa-enroll-rollback",
        first_name="MFA",
        last_name="Rollback",
        role=UserRole.OPERATOR,
        password_hash=get_password_hash("CorrectHorse9"),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    engine = session.get_bind()
    settings = _settings()
    context = MfaRequestContext("192.0.2.31", "mfa-test-agent")
    challenge = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=SlidingWindowLimiter(10, 300),
        mfa_limiter=SlidingWindowLimiter(10, 300),
    )
    enrollment = get_enrollment(
        engine, challenge_token=challenge.challenge_token, settings=settings
    )
    _fail_primary_audit_once(monkeypatch, "MFA_ENROLL")

    with pytest.raises(AppHTTPException) as failure:
        confirm_enrollment(
            engine,
            challenge_token=challenge.challenge_token,
            code=pyotp.TOTP(enrollment.body.manual_key).now(),
            context=context,
            settings=settings,
            mfa_limiter=SlidingWindowLimiter(10, 300),
        )

    assert failure.value.code == "TEMPORARILY_UNAVAILABLE"
    session.expire_all()
    assert session.get(MfaCredential, user.user_id).state == "unenrolled"
    assert session.get(MfaChallenge, user.user_id).purpose == "enroll"
    assert (
        session.exec(
            select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.user_id)
        ).all()
        == []
    )
    assert (
        session.exec(
            select(AuthSession).where(AuthSession.user_id == user.user_id)
        ).all()
        == []
    )
    assert (
        session.exec(
            select(AuditLog).where(
                AuditLog.action == "MFA_ENROLL",
                AuditLog.result == "failure",
                AuditLog.target_ref == str(user.user_id),
            )
        ).first()
        is not None
    )


def test_replacement_audit_failure_preserves_old_factor_and_sessions(
    session, monkeypatch
):
    user, settings, context, _password_limiter, mfa_limiter, seed, _enrolled = (
        _enrolled_account(session, "mfa-replace-rollback")
    )
    engine = session.get_bind()
    auth_session = session.exec(
        select(AuthSession).where(AuthSession.user_id == user.user_id)
    ).one()
    previous = session.get(MfaCredential, user.user_id)
    old_ciphertext = previous.active_secret_ciphertext
    old_version = previous.credential_version
    replacement = begin_replacement(
        engine,
        session_id=auth_session.session_id,
        user_id=user.user_id,
        password="CorrectHorse9",
        code=_next_totp_code(seed),
        context=context,
        settings=settings,
        mfa_limiter=mfa_limiter,
    )
    enrollment = get_enrollment(
        engine, challenge_token=replacement.challenge_token, settings=settings
    )
    _fail_primary_audit_once(monkeypatch, "MFA_REPLACE")

    with pytest.raises(AppHTTPException) as failure:
        confirm_enrollment(
            engine,
            challenge_token=replacement.challenge_token,
            code=pyotp.TOTP(enrollment.body.manual_key).now(),
            context=context,
            settings=settings,
            mfa_limiter=mfa_limiter,
        )

    assert failure.value.code == "TEMPORARILY_UNAVAILABLE"
    session.expire_all()
    assert session.get(MfaCredential, user.user_id).active_secret_ciphertext == (
        old_ciphertext
    )
    assert session.get(MfaCredential, user.user_id).credential_version == old_version
    assert session.get(MfaChallenge, user.user_id).purpose == "replace"
    assert session.get(AuthSession, auth_session.session_id).revoked_at is None
    assert (
        session.exec(
            select(AuditLog).where(
                AuditLog.action == "MFA_REPLACE",
                AuditLog.result == "failure",
                AuditLog.target_ref == str(user.user_id),
            )
        ).first()
        is not None
    )


def test_rotation_audit_failure_preserves_old_codes_step_session_and_challenge(
    session, monkeypatch
):
    user, settings, context, password_limiter, mfa_limiter, seed, enrolled = (
        _enrolled_account(session, "mfa-rotate-rollback")
    )
    engine = session.get_bind()
    auth_session = session.exec(
        select(AuthSession).where(AuthSession.user_id == user.user_id)
    ).one()
    old_codes = set(enrolled.body.recovery_codes)
    previous_step = session.get(MfaCredential, user.user_id).last_accepted_step
    outstanding = begin_password_login(
        engine,
        username=user.username,
        password="CorrectHorse9",
        context=context,
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    _fail_primary_audit_once(monkeypatch, "MFA_RECOVERY_ROTATE")

    with pytest.raises(AppHTTPException) as failure:
        rotate_recovery_codes(
            engine,
            session_id=auth_session.session_id,
            user_id=user.user_id,
            password="CorrectHorse9",
            code=_next_totp_code(seed),
            context=context,
            settings=settings,
            mfa_limiter=mfa_limiter,
        )

    assert failure.value.code == "TEMPORARILY_UNAVAILABLE"
    session.expire_all()
    assert session.get(MfaChallenge, user.user_id).token_hash == hash_challenge_token(
        outstanding.challenge_token
    )
    assert session.get(MfaCredential, user.user_id).last_accepted_step == previous_step
    assert session.get(AuthSession, auth_session.session_id).revoked_at is None
    rows = session.exec(
        select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.user_id)
    ).all()
    stored_hashes = {row.code_hash for row in rows}
    expected_hashes = {hash_recovery_code(user.user_id, 1, code) for code in old_codes}
    assert stored_hashes == expected_hashes
    assert len(rows) == 10
    assert (
        session.exec(
            select(AuditLog).where(
                AuditLog.action == "MFA_RECOVERY_ROTATE",
                AuditLog.result == "failure",
                AuditLog.target_ref == str(user.user_id),
            )
        ).first()
        is not None
    )
