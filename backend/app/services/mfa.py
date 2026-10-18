"""Transactional MFA services used by the integrated authentication API."""

import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import pyotp
from pydantic import BaseModel
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, delete, select

from app.core.config import Settings
from app.core.errors import AppHTTPException
from app.core.mfa import (
    canonicalize_recovery_code,
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_recovery_codes,
    generate_totp_secret,
    hash_challenge_token,
    hash_recovery_code,
    matching_totp_step,
)
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import (
    create_session_token,
    verify_dummy_password,
    verify_password,
)
from app.models import (
    AuditResult,
    AuthSession,
    MfaChallenge,
    MfaCredential,
    MfaRecoveryCode,
    User,
)
from app.schemas.mfa import (
    ChallengeState,
    CompletedEnrollment,
    CompletedLogin,
    CompletedReplacement,
    EnrollmentStartResponse,
    MfaStatusResponse,
    RecoveryCodesResponse,
)
from app.schemas.user import UserRead
from app.services import audit
from app.services.sessions import create_session, revoke_all_for_user


@dataclass(frozen=True)
class MfaRequestContext:
    source_ip: str | None
    user_agent: str | None


@dataclass(frozen=True, repr=False)
class MfaServiceResult:
    body: BaseModel | None
    challenge_token: str | None = None
    challenge_expires_at: datetime | None = None
    clear_challenge: bool = False
    session_token: str | None = None
    clear_session: bool = False
    close_user_id: int | None = None
    close_reason: str | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _begin_write(session: Session) -> None:
    """Reserve SQLite's single writer before reading one-use state."""
    if session.get_bind().dialect.name == "sqlite":
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    else:
        session.begin()


def _mfa_key(settings: Settings) -> str:
    if settings.MFA_ENCRYPTION_KEY is None:
        raise AppHTTPException(
            503,
            "The service is temporarily unavailable.",
            code="TEMPORARILY_UNAVAILABLE",
        )
    return settings.MFA_ENCRYPTION_KEY.get_secret_value()


def _password_keys(username: str, source_ip: str | None) -> tuple[str, str]:
    return f"ip:{source_ip}", f"user:{username.lower()}"


def _mfa_keys(user_id: int, source_ip: str | None) -> tuple[str, str]:
    return f"user:{user_id}", f"ip:{source_ip}"


def _check_mfa_limiter(
    engine: Engine,
    limiter: SlidingWindowLimiter,
    *,
    user_id: int,
    username: str,
    source_ip: str | None,
    action: str,
    stage: str,
) -> None:
    account_key, ip_key = _mfa_keys(user_id, source_ip)
    account_allowed, account_retry = limiter.check(account_key)
    ip_allowed, ip_retry = limiter.check(ip_key)
    if account_allowed and ip_allowed:
        return
    audit.record_out_of_band(
        engine,
        action=action,
        result=AuditResult.DENIED,
        actor_username=username,
        source_ip=source_ip,
        target_type="mfa",
        target_ref=str(user_id),
        detail={"stage": stage, "reason": "rate_limited"},
    )
    raise AppHTTPException(
        429,
        "Too many authentication attempts. Please try again later.",
        code="AUTH_RATE_LIMITED",
        headers={"Retry-After": str(max(account_retry, ip_retry))},
    )


def _record_mfa_failure(
    engine: Engine,
    limiter: SlidingWindowLimiter,
    *,
    user_id: int,
    username: str,
    source_ip: str | None,
    action: str,
    stage: str,
    reason: str,
) -> None:
    for key in _mfa_keys(user_id, source_ip):
        limiter.record_failure(key)
    audit.record_out_of_band(
        engine,
        action=action,
        result=AuditResult.DENIED,
        actor_username=username,
        source_ip=source_ip,
        target_type="mfa",
        target_ref=str(user_id),
        detail={"stage": stage, "reason": reason},
    )


def _reset_mfa_account(limiter: SlidingWindowLimiter, user_id: int) -> None:
    limiter.reset(_mfa_keys(user_id, None)[0])


def _challenge_owner(engine: Engine, challenge_token: str) -> int | None:
    with Session(engine) as session:
        return session.exec(
            select(MfaChallenge.user_id).where(
                MfaChallenge.token_hash == hash_challenge_token(challenge_token)
            )
        ).first()


def _challenge_purpose(engine: Engine, challenge_token: str) -> str | None:
    with Session(engine) as session:
        return session.exec(
            select(MfaChallenge.purpose).where(
                MfaChallenge.token_hash == hash_challenge_token(challenge_token)
            )
        ).first()


def _invalid_code() -> AppHTTPException:
    return AppHTTPException(
        401,
        "The verification code is invalid or has already been used.",
        code="MFA_INVALID_CODE",
    )


def _challenge_invalid() -> AppHTTPException:
    return AppHTTPException(
        401,
        "This authentication step has expired. Please sign in again.",
        code="MFA_CHALLENGE_INVALID",
    )


def _matching_recovery_code(
    session: Session,
    *,
    user_id: int,
    generation: int,
    code: str,
) -> MfaRecoveryCode | None:
    try:
        expected = hash_recovery_code(
            user_id, generation, canonicalize_recovery_code(code)
        )
    except (TypeError, ValueError):
        return None
    candidates = session.exec(
        select(MfaRecoveryCode).where(
            MfaRecoveryCode.user_id == user_id,
            MfaRecoveryCode.generation == generation,
            MfaRecoveryCode.consumed_at.is_(None),
        )
    ).all()
    for candidate in candidates:
        if hmac.compare_digest(candidate.code_hash, expected):
            return candidate
    return None


def _transaction_failed(
    engine: Engine,
    *,
    action: str,
    actor_username: str | None,
    target_user_id: int | None,
    source_ip: str | None,
    phase: str,
) -> None:
    actor = None
    if target_user_id is not None:
        with Session(engine) as session:
            persisted_user = session.get(User, target_user_id)
            if persisted_user is not None:
                actor = User.model_construct(
                    user_id=persisted_user.user_id,
                    username=persisted_user.username,
                    role=persisted_user.role,
                )
    audit.record_out_of_band(
        engine,
        action=action,
        result=AuditResult.FAILURE,
        actor=actor,
        actor_username=actor_username if actor is None else None,
        target_type="mfa",
        target_ref=str(target_user_id) if target_user_id is not None else None,
        detail={"phase": phase, "reason": "transaction_failed"},
        source_ip=source_ip,
    )


def _add_recovery_batch(
    session: Session,
    *,
    user_id: int,
    credential: MfaCredential,
    codes: list[str],
    now: datetime,
) -> int:
    generation = credential.recovery_generation + 1
    session.exec(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id))
    for code in codes:
        session.add(
            MfaRecoveryCode(
                user_id=user_id,
                generation=generation,
                code_hash=hash_recovery_code(user_id, generation, code),
                created_at=now,
            )
        )
    credential.recovery_generation = generation
    return generation


def _load_management_actor(
    session: Session,
    *,
    session_id: str,
    user_id: int,
    settings: Settings,
    now: datetime,
) -> tuple[User, AuthSession, MfaCredential | None]:
    auth_session = session.get(AuthSession, session_id)
    if (
        auth_session is None
        or auth_session.user_id != user_id
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= now
    ):
        raise AppHTTPException(
            401, "Session was revoked or has expired.", code="AUTH_REVOKED"
        )
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise AppHTTPException(
            401, "Session was revoked or has expired.", code="AUTH_REVOKED"
        )
    credential = session.get(MfaCredential, user_id)
    if auth_session.auth_method == "demo_impersonation":
        if not settings.DEV_TOOLS_ENABLED:
            raise AppHTTPException(
                401, "Session was revoked or has expired.", code="AUTH_REVOKED"
            )
    elif auth_session.auth_method == "totp":
        if (
            credential is None
            or credential.state != "enrolled"
            or auth_session.mfa_credential_version != credential.credential_version
        ):
            raise AppHTTPException(
                401, "Session was revoked or has expired.", code="AUTH_REVOKED"
            )
    else:
        raise AppHTTPException(
            401, "Session was revoked or has expired.", code="AUTH_REVOKED"
        )
    return user, auth_session, credential


def _state_conflict() -> AppHTTPException:
    return AppHTTPException(
        409,
        "This account is not in a state that supports this MFA action.",
        code="MFA_STATE_CONFLICT",
    )


def _management_denial(
    engine: Engine,
    *,
    action: str,
    user_id: int,
    username: str | None,
    source_ip: str | None,
    reason: str,
) -> None:
    audit.record_out_of_band(
        engine,
        action=action,
        result=AuditResult.DENIED,
        actor_username=username,
        source_ip=source_ip,
        target_type="mfa",
        target_ref=str(user_id),
        detail={"reason": reason},
    )


def _session_user_snapshot(
    engine: Engine,
    *,
    session_id: str,
    user_id: int,
    settings: Settings,
) -> tuple[str, str, int | None]:
    with Session(engine) as session:
        user, _auth_session, credential = _load_management_actor(
            session,
            session_id=session_id,
            user_id=user_id,
            settings=settings,
            now=_now(),
        )
        return (
            user.username,
            user.password_hash,
            credential.credential_version if credential is not None else None,
        )


def invalidate_user_challenge(session: Session, user_id: int) -> None:
    """Invalidate a user's pending challenge inside the caller's transaction."""
    session.exec(delete(MfaChallenge).where(MfaChallenge.user_id == user_id))


def validate_stored_mfa_secrets(engine: Engine, key: str) -> None:
    """Fail closed if the supplied key cannot decrypt every stored MFA seed."""
    from app.core.mfa import validate_encryption_key

    try:
        validate_encryption_key(key)
        with Session(engine) as session:
            ciphertexts = [
                value
                for value in session.exec(
                    select(MfaCredential.active_secret_ciphertext).where(
                        MfaCredential.active_secret_ciphertext.is_not(None)
                    )
                ).all()
            ]
            ciphertexts.extend(
                value
                for value in session.exec(
                    select(MfaChallenge.pending_secret_ciphertext).where(
                        MfaChallenge.pending_secret_ciphertext.is_not(None)
                    )
                ).all()
            )
            for ciphertext in ciphertexts:
                decrypt_totp_secret(ciphertext, key)
    except Exception:
        raise ValueError(
            "Stored MFA secrets cannot be validated with MFA_ENCRYPTION_KEY."
        ) from None


def get_mfa_status(
    engine: Engine,
    *,
    session_id: str,
    user_id: int,
    settings: Settings,
) -> MfaServiceResult:
    """Return safe MFA status for a current TOTP or enabled demo session."""
    with Session(engine) as session:
        _user, auth_session, credential = _load_management_actor(
            session,
            session_id=session_id,
            user_id=user_id,
            settings=settings,
            now=_now(),
        )
        if credential is None:
            state = "unenrolled"
            enrolled_at = None
            remaining = 0
        else:
            state = credential.state
            enrolled_at = credential.enrolled_at
            remaining = len(
                session.exec(
                    select(MfaRecoveryCode.recovery_code_id).where(
                        MfaRecoveryCode.user_id == user_id,
                        MfaRecoveryCode.generation == credential.recovery_generation,
                        MfaRecoveryCode.consumed_at.is_(None),
                    )
                ).all()
            )
        return MfaServiceResult(
            body=MfaStatusResponse(
                state=state,
                recovery_codes_remaining=remaining,
                enrolled_at=enrolled_at,
                auth_method=auth_session.auth_method,
            )
        )


def begin_replacement(
    engine: Engine,
    *,
    session_id: str,
    user_id: int,
    password: str,
    code: str,
    context: MfaRequestContext,
    settings: Settings,
    mfa_limiter: SlidingWindowLimiter,
) -> MfaServiceResult:
    """Start two-phase replacement while leaving the old factor usable."""
    action = "MFA_REPLACE"
    username, initial_password_hash = _verify_management_password(
        engine,
        session_id=session_id,
        user_id=user_id,
        password=password,
        source_ip=context.source_ip,
        settings=settings,
        mfa_limiter=mfa_limiter,
        action=action,
        stage="replacement_start",
    )
    try:
        with Session(engine) as session:
            _begin_write(session)
            user, _auth_session, credential = _load_management_actor(
                session,
                session_id=session_id,
                user_id=user_id,
                settings=settings,
                now=_now(),
            )
            if user.password_hash != initial_password_hash:
                raise AppHTTPException(
                    401,
                    "Incorrect username or password.",
                    code="AUTH_INVALID_CREDENTIALS",
                )
            if credential is None or credential.state != "enrolled":
                raise _state_conflict()
            if credential.active_secret_ciphertext is None:
                raise _state_conflict()
            now = _now()
            try:
                current_secret = decrypt_totp_secret(
                    credential.active_secret_ciphertext, _mfa_key(settings)
                )
            except Exception:
                raise _temporarily_unavailable() from None
            accepted_step = matching_totp_step(current_secret, code, now)
            if (
                accepted_step is None
                or credential.last_accepted_step is None
                or accepted_step <= credential.last_accepted_step
            ):
                session.rollback()
                _record_mfa_failure(
                    engine,
                    mfa_limiter,
                    user_id=user_id,
                    username=user.username,
                    source_ip=context.source_ip,
                    action=action,
                    stage="replacement_start",
                    reason="invalid_code",
                )
                raise _invalid_code()

            pending_ciphertext = encrypt_totp_secret(
                generate_totp_secret(), _mfa_key(settings)
            )
            expires_at = now + timedelta(minutes=15)
            challenge_token = secrets.token_urlsafe(32)
            credential.last_accepted_step = accepted_step
            credential.updated_at = now
            invalidate_user_challenge(session, user_id)
            session.add(
                MfaChallenge(
                    user_id=user_id,
                    token_hash=hash_challenge_token(challenge_token),
                    purpose="replace",
                    credential_version=credential.credential_version,
                    password_changed_at=user.password_changed_at,
                    pending_secret_ciphertext=pending_ciphertext,
                    created_at=now,
                    expires_at=expires_at,
                )
            )
            audit.record(
                session,
                action=action,
                result=AuditResult.SUCCESS,
                actor=user,
                target_type="mfa_challenge",
                target_ref=str(user_id),
                detail={"phase": "started"},
                source_ip=context.source_ip,
            )
            session.commit()
    except AppHTTPException as exc:
        if getattr(exc, "code", None) in {
            "AUTH_INVALID_CREDENTIALS",
            "AUTH_REVOKED",
            "MFA_STATE_CONFLICT",
        }:
            _management_denial(
                engine,
                action=action,
                user_id=user_id,
                username=username,
                source_ip=context.source_ip,
                reason=getattr(exc, "code", "denied").lower(),
            )
        raise
    except OperationalError:
        raise _temporarily_unavailable() from None
    except Exception:
        _transaction_failed(
            engine,
            action=action,
            actor_username=username,
            target_user_id=user_id,
            source_ip=context.source_ip,
            phase="replacement_start",
        )
        raise _temporarily_unavailable() from None

    _reset_mfa_account(mfa_limiter, user_id)
    return MfaServiceResult(
        body=ChallengeState(
            status="enrollment_required",
            purpose="replace",
            expires_at=expires_at,
        ),
        challenge_token=challenge_token,
        challenge_expires_at=expires_at,
    )


def begin_enrollment_from_session(
    engine: Engine,
    *,
    session_id: str,
    user_id: int,
    password: str,
    context: MfaRequestContext,
    settings: Settings,
    password_limiter: SlidingWindowLimiter,
    mfa_limiter: SlidingWindowLimiter,
) -> MfaServiceResult:
    """Start enrollment only from an enabled demo session after fresh password proof."""
    action = "MFA_ENROLL"
    username, stored_hash, _credential_version = _session_user_snapshot(
        engine,
        session_id=session_id,
        user_id=user_id,
        settings=settings,
    )
    ip_key, user_key = _password_keys(username, context.source_ip)
    ip_allowed, ip_retry = password_limiter.check(ip_key)
    user_allowed, user_retry = password_limiter.check(user_key)
    if not ip_allowed or not user_allowed:
        retry_after = max(ip_retry, user_retry)
        _management_denial(
            engine,
            action=action,
            user_id=user_id,
            username=username,
            source_ip=context.source_ip,
            reason="password_rate_limited",
        )
        raise AppHTTPException(
            429,
            "Too many authentication attempts. Please try again later.",
            code="AUTH_RATE_LIMITED",
            headers={"Retry-After": str(retry_after)},
        )
    _check_mfa_limiter(
        engine,
        mfa_limiter,
        user_id=user_id,
        username=username,
        source_ip=context.source_ip,
        action=action,
        stage="demo_enrollment_start",
    )
    if not verify_password(password, stored_hash):
        for key in (ip_key, user_key):
            password_limiter.record_failure(key)
        _management_denial(
            engine,
            action=action,
            user_id=user_id,
            username=username,
            source_ip=context.source_ip,
            reason="invalid_password",
        )
        raise AppHTTPException(
            401,
            "Incorrect username or password.",
            code="AUTH_INVALID_CREDENTIALS",
        )

    try:
        with Session(engine) as session:
            _begin_write(session)
            user, auth_session, credential = _load_management_actor(
                session,
                session_id=session_id,
                user_id=user_id,
                settings=settings,
                now=_now(),
            )
            if user.password_hash != stored_hash:
                raise AppHTTPException(
                    401,
                    "Incorrect username or password.",
                    code="AUTH_INVALID_CREDENTIALS",
                )
            if auth_session.auth_method != "demo_impersonation":
                raise _state_conflict()
            if credential is None:
                credential = MfaCredential(user_id=user_id)
                session.add(credential)
                session.flush()
            if credential.state != "unenrolled":
                raise _state_conflict()
            now = _now()
            pending_ciphertext = encrypt_totp_secret(
                generate_totp_secret(), _mfa_key(settings)
            )
            expires_at = now + timedelta(minutes=15)
            challenge_token = secrets.token_urlsafe(32)
            invalidate_user_challenge(session, user_id)
            session.add(
                MfaChallenge(
                    user_id=user_id,
                    token_hash=hash_challenge_token(challenge_token),
                    purpose="enroll",
                    credential_version=credential.credential_version,
                    password_changed_at=user.password_changed_at,
                    pending_secret_ciphertext=pending_ciphertext,
                    created_at=now,
                    expires_at=expires_at,
                )
            )
            audit.record(
                session,
                action="MFA_CHALLENGE_START",
                result=AuditResult.SUCCESS,
                actor=user,
                target_type="mfa_challenge",
                target_ref=str(user_id),
                detail={"phase": "demo_enrollment", "purpose": "enroll"},
                source_ip=context.source_ip,
            )
            session.commit()
    except AppHTTPException as exc:
        if getattr(exc, "code", None) in {
            "AUTH_INVALID_CREDENTIALS",
            "AUTH_REVOKED",
            "MFA_STATE_CONFLICT",
        }:
            _management_denial(
                engine,
                action=action,
                user_id=user_id,
                username=username,
                source_ip=context.source_ip,
                reason=getattr(exc, "code", "denied").lower(),
            )
        raise
    except OperationalError:
        raise _temporarily_unavailable() from None
    except Exception:
        _transaction_failed(
            engine,
            action="MFA_CHALLENGE_START",
            actor_username=username,
            target_user_id=user_id,
            source_ip=context.source_ip,
            phase="demo_enrollment_start",
        )
        raise _temporarily_unavailable() from None

    return MfaServiceResult(
        body=ChallengeState(
            status="enrollment_required",
            purpose="enroll",
            expires_at=expires_at,
        ),
        challenge_token=challenge_token,
        challenge_expires_at=expires_at,
    )


def _verify_management_password(
    engine: Engine,
    *,
    session_id: str,
    user_id: int,
    password: str,
    source_ip: str | None,
    settings: Settings,
    mfa_limiter: SlidingWindowLimiter,
    action: str,
    stage: str,
) -> tuple[str, str]:
    username, stored_hash, _credential_version = _session_user_snapshot(
        engine,
        session_id=session_id,
        user_id=user_id,
        settings=settings,
    )
    _check_mfa_limiter(
        engine,
        mfa_limiter,
        user_id=user_id,
        username=username,
        source_ip=source_ip,
        action=action,
        stage=stage,
    )
    if not verify_password(password, stored_hash):
        _record_mfa_failure(
            engine,
            mfa_limiter,
            user_id=user_id,
            username=username,
            source_ip=source_ip,
            action=action,
            stage=stage,
            reason="invalid_password",
        )
        raise AppHTTPException(
            401,
            "Incorrect username or password.",
            code="AUTH_INVALID_CREDENTIALS",
        )
    return username, stored_hash


def rotate_recovery_codes(
    engine: Engine,
    *,
    session_id: str,
    user_id: int,
    password: str,
    code: str,
    context: MfaRequestContext,
    settings: Settings,
    mfa_limiter: SlidingWindowLimiter,
) -> MfaServiceResult:
    """Replace the recovery batch after fresh password and TOTP proofs."""
    action = "MFA_RECOVERY_ROTATE"
    username, initial_password_hash = _verify_management_password(
        engine,
        session_id=session_id,
        user_id=user_id,
        password=password,
        source_ip=context.source_ip,
        settings=settings,
        mfa_limiter=mfa_limiter,
        action=action,
        stage="rotation",
    )
    try:
        with Session(engine) as session:
            _begin_write(session)
            user, _auth_session, credential = _load_management_actor(
                session,
                session_id=session_id,
                user_id=user_id,
                settings=settings,
                now=_now(),
            )
            if user.password_hash != initial_password_hash:
                raise AppHTTPException(
                    401,
                    "Incorrect username or password.",
                    code="AUTH_INVALID_CREDENTIALS",
                )
            if credential is None or credential.state != "enrolled":
                raise _state_conflict()
            if credential.active_secret_ciphertext is None:
                raise _state_conflict()
            now = _now()
            try:
                secret = decrypt_totp_secret(
                    credential.active_secret_ciphertext, _mfa_key(settings)
                )
            except Exception:
                raise _temporarily_unavailable() from None
            accepted_step = matching_totp_step(secret, code, now)
            if (
                accepted_step is None
                or credential.last_accepted_step is None
                or accepted_step <= credential.last_accepted_step
            ):
                session.rollback()
                _record_mfa_failure(
                    engine,
                    mfa_limiter,
                    user_id=user_id,
                    username=user.username,
                    source_ip=context.source_ip,
                    action=action,
                    stage="rotation",
                    reason="invalid_code",
                )
                raise _invalid_code()

            codes = generate_recovery_codes()
            credential.last_accepted_step = accepted_step
            credential.updated_at = now
            generation = _add_recovery_batch(
                session,
                user_id=user_id,
                credential=credential,
                codes=codes,
                now=now,
            )
            invalidate_user_challenge(session, user_id)
            audit.record(
                session,
                action=action,
                result=AuditResult.SUCCESS,
                actor=user,
                target_type="mfa_recovery_codes",
                target_ref=str(user_id),
                detail={
                    "phase": "rotated",
                    "generation": generation,
                    "count": len(codes),
                },
                source_ip=context.source_ip,
            )
            session.commit()
    except AppHTTPException as exc:
        if getattr(exc, "code", None) in {
            "AUTH_INVALID_CREDENTIALS",
            "AUTH_REVOKED",
            "MFA_STATE_CONFLICT",
        }:
            _management_denial(
                engine,
                action=action,
                user_id=user_id,
                username=username,
                source_ip=context.source_ip,
                reason=getattr(exc, "code", "denied").lower(),
            )
        raise
    except OperationalError:
        raise _temporarily_unavailable() from None
    except Exception:
        _transaction_failed(
            engine,
            action=action,
            actor_username=username,
            target_user_id=user_id,
            source_ip=context.source_ip,
            phase="rotation",
        )
        raise _temporarily_unavailable() from None

    _reset_mfa_account(mfa_limiter, user_id)
    return MfaServiceResult(
        body=RecoveryCodesResponse(recovery_codes=codes),
        clear_challenge=True,
    )


def _record_password_failure(
    engine: Engine,
    limiter: SlidingWindowLimiter,
    *,
    username: str,
    source_ip: str | None,
    reason: str,
) -> None:
    for key in _password_keys(username, source_ip):
        limiter.record_failure(key)
    audit.record_out_of_band(
        engine,
        action="LOGIN_FAILURE",
        result=AuditResult.DENIED,
        actor_username=username,
        source_ip=source_ip,
        detail={"stage": "password", "reason": reason},
    )


def _invalid_credentials() -> AppHTTPException:
    return AppHTTPException(
        401,
        "Incorrect username or password.",
        code="AUTH_INVALID_CREDENTIALS",
    )


def _temporarily_unavailable() -> AppHTTPException:
    return AppHTTPException(
        503,
        "The service is temporarily unavailable. Please retry shortly.",
        code="TEMPORARILY_UNAVAILABLE",
    )


def begin_password_login(
    engine: Engine,
    *,
    username: str,
    password: str,
    context: MfaRequestContext,
    settings: Settings,
    password_limiter: SlidingWindowLimiter,
    mfa_limiter: SlidingWindowLimiter,
) -> MfaServiceResult:
    """Verify a password and issue a restricted, single-account challenge."""
    del mfa_limiter  # Password validation never clears or consumes MFA failures.
    attempted_username = username.strip()
    ip_key, user_key = _password_keys(attempted_username, context.source_ip)
    ip_allowed, ip_retry = password_limiter.check(ip_key)
    user_allowed, user_retry = password_limiter.check(user_key)
    if not ip_allowed or not user_allowed:
        retry_after = max(ip_retry, user_retry)
        audit.record_out_of_band(
            engine,
            action="LOGIN_FAILURE",
            result=AuditResult.DENIED,
            actor_username=attempted_username,
            source_ip=context.source_ip,
            detail={"stage": "password", "reason": "rate_limited"},
        )
        raise AppHTTPException(
            429,
            "Too many login attempts. Please try again later.",
            code="AUTH_RATE_LIMITED",
            headers={"Retry-After": str(retry_after)},
        )

    with Session(engine) as read_session:
        candidate = read_session.exec(
            select(User).where(User.username == attempted_username)
        ).first()
        if candidate is None:
            verify_dummy_password(password)
            _record_password_failure(
                engine,
                password_limiter,
                username=attempted_username,
                source_ip=context.source_ip,
                reason="unknown_user",
            )
            raise _invalid_credentials()
        user_id = candidate.user_id
        initial_password_hash = candidate.password_hash
        valid_password = verify_password(password, initial_password_hash)
        is_active = candidate.is_active
        candidate_username = candidate.username

    if not valid_password:
        _record_password_failure(
            engine,
            password_limiter,
            username=attempted_username,
            source_ip=context.source_ip,
            reason="wrong_password",
        )
        raise _invalid_credentials()
    if not is_active or user_id is None:
        _record_password_failure(
            engine,
            password_limiter,
            username=attempted_username,
            source_ip=context.source_ip,
            reason="inactive_account",
        )
        raise _invalid_credentials()

    try:
        with Session(engine) as session:
            _begin_write(session)
            user = session.get(User, user_id)
            if (
                user is None
                or not user.is_active
                or user.password_hash != initial_password_hash
            ):
                session.rollback()
                _record_password_failure(
                    engine,
                    password_limiter,
                    username=attempted_username,
                    source_ip=context.source_ip,
                    reason="credentials_changed",
                )
                raise _invalid_credentials()

            credential = session.get(MfaCredential, user_id)
            if credential is None:
                credential = MfaCredential(user_id=user_id)
                session.add(credential)
                session.flush()

            if credential.state == "unenrolled":
                purpose = "enroll"
                secret = generate_totp_secret()
                pending_ciphertext = encrypt_totp_secret(secret, _mfa_key(settings))
            elif credential.state == "enrolled":
                purpose = "login"
                pending_ciphertext = None
            elif credential.state == "recovery_pending":
                purpose = "recovery_verify"
                pending_ciphertext = None
            else:
                raise _temporarily_unavailable()

            now = _now()
            lifetime = timedelta(minutes=15 if purpose == "enroll" else 5)
            expires_at = now + lifetime
            challenge_token = secrets.token_urlsafe(32)
            session.exec(delete(MfaChallenge).where(MfaChallenge.user_id == user_id))
            session.add(
                MfaChallenge(
                    user_id=user_id,
                    token_hash=hash_challenge_token(challenge_token),
                    purpose=purpose,
                    credential_version=credential.credential_version,
                    password_changed_at=user.password_changed_at,
                    pending_secret_ciphertext=pending_ciphertext,
                    created_at=now,
                    expires_at=expires_at,
                )
            )
            audit.record(
                session,
                action="MFA_CHALLENGE_START",
                result=AuditResult.SUCCESS,
                actor=user,
                target_type="mfa_challenge",
                target_ref=str(user_id),
                detail={"phase": "password", "purpose": purpose},
                source_ip=context.source_ip,
            )
            session.commit()
    except AppHTTPException:
        raise
    except OperationalError:
        raise _temporarily_unavailable() from None
    except Exception:
        audit.record_out_of_band(
            engine,
            action="MFA_CHALLENGE_START",
            result=AuditResult.FAILURE,
            actor_username=candidate_username,
            target_type="mfa_challenge",
            target_ref=str(user_id),
            detail={"phase": "password", "reason": "transaction_failed"},
            source_ip=context.source_ip,
        )
        raise _temporarily_unavailable() from None

    status_value = "enrollment_required" if purpose == "enroll" else "mfa_required"
    body = ChallengeState(status=status_value, purpose=purpose, expires_at=expires_at)
    return MfaServiceResult(
        body=body,
        challenge_token=challenge_token,
        challenge_expires_at=expires_at,
    )


def _challenge_state(challenge: MfaChallenge) -> ChallengeState:
    status_value = (
        "mfa_required"
        if challenge.purpose in {"login", "recovery_verify"}
        else "enrollment_required"
    )
    return ChallengeState(
        status=status_value,
        purpose=challenge.purpose,
        expires_at=challenge.expires_at,
    )


def _load_challenge(
    session: Session,
    *,
    challenge_token: str,
    now: datetime,
    allowed_purposes: set[str] | None = None,
) -> tuple[MfaChallenge, User, MfaCredential]:
    challenge = session.exec(
        select(MfaChallenge).where(
            MfaChallenge.token_hash == hash_challenge_token(challenge_token)
        )
    ).first()
    if challenge is None or now > challenge.expires_at:
        raise AppHTTPException(
            401,
            "This authentication step has expired. Please sign in again.",
            code="MFA_CHALLENGE_INVALID",
        )
    user = session.get(User, challenge.user_id)
    credential = session.get(MfaCredential, challenge.user_id)
    if user is None or not user.is_active or credential is None:
        raise AppHTTPException(
            401,
            "This authentication step has expired. Please sign in again.",
            code="MFA_CHALLENGE_INVALID",
        )
    if (
        user.password_changed_at != challenge.password_changed_at
        or credential.credential_version != challenge.credential_version
        or (allowed_purposes is not None and challenge.purpose not in allowed_purposes)
    ):
        raise AppHTTPException(
            401,
            "This authentication step has expired. Please sign in again.",
            code="MFA_CHALLENGE_INVALID",
        )
    required_state = {
        "login": "enrolled",
        "enroll": "unenrolled",
        "recovery_verify": "recovery_pending",
        "recovery_enroll": "recovery_pending",
        "replace": "enrolled",
    }.get(challenge.purpose)
    if required_state is None or credential.state != required_state:
        raise AppHTTPException(
            401,
            "This authentication step has expired. Please sign in again.",
            code="MFA_CHALLENGE_INVALID",
        )
    return challenge, user, credential


def get_challenge(
    engine: Engine,
    *,
    challenge_token: str,
    settings: Settings,
) -> MfaServiceResult:
    """Return current challenge state without extending its deadline."""
    del settings
    with Session(engine) as session:
        challenge, _user, _credential = _load_challenge(
            session, challenge_token=challenge_token, now=_now()
        )
        body = _challenge_state(challenge)
        return MfaServiceResult(
            body=body,
            challenge_expires_at=challenge.expires_at,
        )


def cancel_challenge(
    engine: Engine,
    *,
    challenge_token: str | None,
    context: MfaRequestContext,
    settings: Settings,
) -> MfaServiceResult:
    """Cancel one challenge without changing recovery-pending or active factors."""
    del settings
    if not challenge_token:
        return MfaServiceResult(body=None, clear_challenge=True)
    user_id: int | None = None
    username: str | None = None
    try:
        with Session(engine) as session:
            _begin_write(session)
            challenge = session.exec(
                select(MfaChallenge).where(
                    MfaChallenge.token_hash == hash_challenge_token(challenge_token)
                )
            ).first()
            if challenge is None:
                session.rollback()
                return MfaServiceResult(body=None, clear_challenge=True)
            user_id = challenge.user_id
            user = session.get(User, user_id)
            username = user.username if user is not None else None
            expired = _now() > challenge.expires_at
            session.delete(challenge)
            if not expired and user is not None:
                audit.record(
                    session,
                    action="MFA_CHALLENGE_CANCEL",
                    result=AuditResult.SUCCESS,
                    actor=user,
                    target_type="mfa_challenge",
                    target_ref=str(user_id),
                    detail={"purpose": challenge.purpose},
                    source_ip=context.source_ip,
                )
            session.commit()
    except OperationalError:
        raise _temporarily_unavailable() from None
    except Exception:
        _transaction_failed(
            engine,
            action="MFA_CHALLENGE_CANCEL",
            actor_username=username,
            target_user_id=user_id,
            source_ip=context.source_ip,
            phase="cancel",
        )
        raise _temporarily_unavailable() from None
    return MfaServiceResult(body=None, clear_challenge=True)


def get_enrollment(
    engine: Engine,
    *,
    challenge_token: str,
    settings: Settings,
) -> MfaServiceResult:
    """Reveal the same pending seed while its enrollment challenge is valid."""
    with Session(engine) as session:
        challenge, user, _credential = _load_challenge(
            session,
            challenge_token=challenge_token,
            now=_now(),
            allowed_purposes={"enroll", "recovery_enroll", "replace"},
        )
        if challenge.pending_secret_ciphertext is None:
            raise AppHTTPException(
                401,
                "This authentication step has expired. Please sign in again.",
                code="MFA_CHALLENGE_INVALID",
            )
        try:
            plaintext_seed = decrypt_totp_secret(
                challenge.pending_secret_ciphertext, _mfa_key(settings)
            )
        except Exception:
            raise _temporarily_unavailable() from None
        body = EnrollmentStartResponse(
            provisioning_uri=pyotp.TOTP(plaintext_seed).provisioning_uri(
                name=user.username, issuer_name="ADAS"
            ),
            manual_key=plaintext_seed,
            issuer="ADAS",
            account_name=user.username,
            expires_at=challenge.expires_at,
        )
        return MfaServiceResult(body=body, challenge_expires_at=challenge.expires_at)


def confirm_enrollment(
    engine: Engine,
    *,
    challenge_token: str,
    code: str,
    context: MfaRequestContext,
    settings: Settings,
    mfa_limiter: SlidingWindowLimiter,
) -> MfaServiceResult:
    """Confirm an enrollment or replacement with an atomic factor transition."""
    user_id = _challenge_owner(engine, challenge_token)
    if user_id is None:
        audit.record_out_of_band(
            engine,
            action="LOGIN_FAILURE",
            result=AuditResult.DENIED,
            source_ip=context.source_ip,
            target_type="mfa_challenge",
            detail={"stage": "enrollment_confirmation", "reason": "invalid_challenge"},
        )
        raise _challenge_invalid()
    with Session(engine) as read_session:
        read_user = read_session.get(User, user_id)
        if read_user is None:
            audit.record_out_of_band(
                engine,
                action="LOGIN_FAILURE",
                result=AuditResult.DENIED,
                source_ip=context.source_ip,
                target_type="mfa_challenge",
                target_ref=str(user_id),
                detail={
                    "stage": "enrollment_confirmation",
                    "reason": "invalid_challenge",
                },
            )
            raise _challenge_invalid()
        username = read_user.username
    challenge_purpose = _challenge_purpose(engine, challenge_token)
    action = "MFA_REPLACE" if challenge_purpose == "replace" else "MFA_ENROLL"
    proof_action = "MFA_REPLACE" if challenge_purpose == "replace" else "LOGIN_FAILURE"
    _check_mfa_limiter(
        engine,
        mfa_limiter,
        user_id=user_id,
        username=username,
        source_ip=context.source_ip,
        action=proof_action,
        stage="enrollment_confirmation",
    )

    session_token: str | None = None
    clear_session = False
    result_body: BaseModel
    close_reason = "mfa_enrollment"
    try:
        with Session(engine) as session:
            _begin_write(session)
            challenge, user, credential = _load_challenge(
                session,
                challenge_token=challenge_token,
                now=_now(),
                allowed_purposes={"enroll", "recovery_enroll", "replace"},
            )
            if challenge.pending_secret_ciphertext is None:
                raise _challenge_invalid()
            now = _now()
            try:
                pending_secret = decrypt_totp_secret(
                    challenge.pending_secret_ciphertext, _mfa_key(settings)
                )
            except Exception:
                raise _temporarily_unavailable() from None
            accepted_step = matching_totp_step(pending_secret, code, now)
            if accepted_step is None:
                session.rollback()
                _record_mfa_failure(
                    engine,
                    mfa_limiter,
                    user_id=user_id,
                    username=user.username,
                    source_ip=context.source_ip,
                    action=proof_action,
                    stage="enrollment_confirmation",
                    reason="invalid_code",
                )
                raise _invalid_code()

            codes = generate_recovery_codes()
            if challenge.purpose == "replace":
                action = "MFA_REPLACE"
                close_reason = "mfa_replacement"
                credential.active_secret_ciphertext = (
                    challenge.pending_secret_ciphertext
                )
                credential.credential_version += 1
                credential.last_accepted_step = accepted_step
                credential.enrolled_at = now
                credential.recovery_started_at = None
                credential.updated_at = now
                _add_recovery_batch(
                    session,
                    user_id=user_id,
                    credential=credential,
                    codes=codes,
                    now=now,
                )
                session.delete(challenge)
                revoke_all_for_user(session, user_id, "mfa_replacement")
                audit.record(
                    session,
                    action=action,
                    result=AuditResult.SUCCESS,
                    actor=user,
                    target_type="mfa_credential",
                    target_ref=str(user_id),
                    detail={"phase": "confirmed"},
                    source_ip=context.source_ip,
                )
                result_body = CompletedReplacement(recovery_codes=codes)
                clear_session = True
            else:
                action = "MFA_ENROLL"
                enrollment_source = (
                    "recovery" if challenge.purpose == "recovery_enroll" else "initial"
                )
                if (
                    enrollment_source == "initial"
                    and session.exec(
                        select(AuthSession).where(
                            AuthSession.user_id == user_id,
                            AuthSession.auth_method == "demo_impersonation",
                            AuthSession.revoked_at.is_(None),
                            AuthSession.expires_at > now,
                        )
                    ).first()
                ):
                    enrollment_source = "demo"

                credential.state = "enrolled"
                credential.active_secret_ciphertext = (
                    challenge.pending_secret_ciphertext
                )
                credential.credential_version += 1
                credential.last_accepted_step = accepted_step
                credential.enrolled_at = now
                credential.recovery_started_at = None
                credential.updated_at = now
                _add_recovery_batch(
                    session,
                    user_id=user_id,
                    credential=credential,
                    codes=codes,
                    now=now,
                )
                session.delete(challenge)
                revoke_all_for_user(session, user_id, "mfa_enrollment")
                user.last_login = now
                session.add(user)
                auth_session = create_session(
                    session,
                    user,
                    user_agent=context.user_agent,
                    source_ip=context.source_ip,
                    auth_method="totp",
                    mfa_credential_version=credential.credential_version,
                    app_settings=settings,
                )
                user_response = UserRead.model_validate(user)
                session_token = create_session_token(user, auth_session, settings)
                audit.record(
                    session,
                    action=action,
                    result=AuditResult.SUCCESS,
                    actor=user,
                    target_type="mfa_credential",
                    target_ref=str(user_id),
                    detail={"phase": "confirmed", "source": enrollment_source},
                    source_ip=context.source_ip,
                )
                audit.record(
                    session,
                    action="LOGIN_SUCCESS",
                    result=AuditResult.SUCCESS,
                    actor=user,
                    target_type="session",
                    target_ref=auth_session.session_id,
                    detail={"auth_method": "totp"},
                    source_ip=context.source_ip,
                )
                result_body = CompletedEnrollment(
                    user=user_response, recovery_codes=codes
                )

            session.commit()
    except AppHTTPException as exc:
        if getattr(exc, "code", None) == "MFA_CHALLENGE_INVALID":
            audit.record_out_of_band(
                engine,
                action=proof_action,
                result=AuditResult.DENIED,
                actor_username=username,
                source_ip=context.source_ip,
                target_type="mfa_challenge",
                target_ref=str(user_id),
                detail={
                    "stage": "enrollment_confirmation",
                    "reason": "invalid_challenge",
                },
            )
        raise
    except OperationalError:
        raise _temporarily_unavailable() from None
    except Exception:
        _transaction_failed(
            engine,
            action=action,
            actor_username=username,
            target_user_id=user_id,
            source_ip=context.source_ip,
            phase="confirmation",
        )
        raise _temporarily_unavailable() from None

    _reset_mfa_account(mfa_limiter, user_id)
    return MfaServiceResult(
        body=result_body,
        clear_challenge=True,
        session_token=session_token,
        clear_session=clear_session,
        close_user_id=user_id,
        close_reason=close_reason,
    )


def verify_challenge(
    engine: Engine,
    *,
    challenge_token: str,
    method: Literal["totp", "recovery"],
    code: str,
    context: MfaRequestContext,
    settings: Settings,
    mfa_limiter: SlidingWindowLimiter,
) -> MfaServiceResult:
    """Accept one login TOTP or recovery code in a single-writer transaction."""
    user_id = _challenge_owner(engine, challenge_token)
    if user_id is None:
        audit.record_out_of_band(
            engine,
            action="LOGIN_FAILURE",
            result=AuditResult.DENIED,
            source_ip=context.source_ip,
            target_type="mfa_challenge",
            detail={"stage": "challenge", "reason": "invalid_challenge"},
        )
        raise _challenge_invalid()
    with Session(engine) as read_session:
        read_user = read_session.get(User, user_id)
        if read_user is None:
            raise _challenge_invalid()
        username = read_user.username
    _check_mfa_limiter(
        engine,
        mfa_limiter,
        user_id=user_id,
        username=username,
        source_ip=context.source_ip,
        action="LOGIN_FAILURE",
        stage="challenge_verification",
    )

    failure_action = "LOGIN_FAILURE"
    failure_phase = "totp_login"
    try:
        with Session(engine) as session:
            _begin_write(session)
            challenge, user, credential = _load_challenge(
                session,
                challenge_token=challenge_token,
                now=_now(),
                allowed_purposes={"login", "recovery_verify"},
            )
            now = _now()
            if challenge.purpose == "recovery_verify" and method != "recovery":
                raise _challenge_invalid()

            if method == "totp":
                failure_action = "LOGIN_FAILURE"
                failure_phase = "totp_login"
                if (
                    challenge.purpose != "login"
                    or credential.active_secret_ciphertext is None
                ):
                    raise _challenge_invalid()
                try:
                    secret = decrypt_totp_secret(
                        credential.active_secret_ciphertext, _mfa_key(settings)
                    )
                except Exception:
                    raise _temporarily_unavailable() from None
                accepted_step = matching_totp_step(secret, code, now)
                if (
                    accepted_step is None
                    or credential.last_accepted_step is None
                    or accepted_step <= credential.last_accepted_step
                ):
                    session.rollback()
                    _record_mfa_failure(
                        engine,
                        mfa_limiter,
                        user_id=user_id,
                        username=user.username,
                        source_ip=context.source_ip,
                        action="LOGIN_FAILURE",
                        stage="challenge_verification",
                        reason="invalid_code",
                    )
                    raise _invalid_code()

                credential.last_accepted_step = accepted_step
                credential.updated_at = now
                session.delete(challenge)
                user.last_login = now
                session.add(user)
                auth_session = create_session(
                    session,
                    user,
                    user_agent=context.user_agent,
                    source_ip=context.source_ip,
                    auth_method="totp",
                    mfa_credential_version=credential.credential_version,
                    app_settings=settings,
                )
                user_response = UserRead.model_validate(user)
                session_token = create_session_token(user, auth_session, settings)
                audit.record(
                    session,
                    action="LOGIN_SUCCESS",
                    result=AuditResult.SUCCESS,
                    actor=user,
                    target_type="session",
                    target_ref=auth_session.session_id,
                    detail={"auth_method": "totp"},
                    source_ip=context.source_ip,
                )
                session.commit()
                mfa_result = MfaServiceResult(
                    body=CompletedLogin(user=user_response),
                    clear_challenge=True,
                    session_token=session_token,
                )
            else:
                failure_action = "MFA_RECOVERY_USE"
                failure_phase = "recovery_acceptance"
                if challenge.purpose not in {"login", "recovery_verify"}:
                    raise _challenge_invalid()
                recovery_code = _matching_recovery_code(
                    session,
                    user_id=user_id,
                    generation=credential.recovery_generation,
                    code=code,
                )
                if recovery_code is None:
                    session.rollback()
                    _record_mfa_failure(
                        engine,
                        mfa_limiter,
                        user_id=user_id,
                        username=user.username,
                        source_ip=context.source_ip,
                        action="LOGIN_FAILURE",
                        stage="recovery_verification",
                        reason="invalid_code",
                    )
                    raise _invalid_code()

                recovery_code.consumed_at = now
                credential.state = "recovery_pending"
                credential.active_secret_ciphertext = None
                credential.last_accepted_step = None
                credential.credential_version += 1
                credential.enrolled_at = None
                credential.recovery_started_at = now
                credential.updated_at = now
                pending_secret = generate_totp_secret()
                pending_ciphertext = encrypt_totp_secret(
                    pending_secret, _mfa_key(settings)
                )
                expires_at = now + timedelta(minutes=15)
                next_token = secrets.token_urlsafe(32)
                session.exec(
                    delete(MfaChallenge).where(MfaChallenge.user_id == user_id)
                )
                recovery_challenge = MfaChallenge(
                    user_id=user_id,
                    token_hash=hash_challenge_token(next_token),
                    purpose="recovery_enroll",
                    credential_version=credential.credential_version,
                    password_changed_at=user.password_changed_at,
                    pending_secret_ciphertext=pending_ciphertext,
                    created_at=now,
                    expires_at=expires_at,
                )
                session.add(recovery_challenge)
                revoke_all_for_user(session, user_id, "mfa_recovery")
                audit.record(
                    session,
                    action="MFA_RECOVERY_USE",
                    result=AuditResult.SUCCESS,
                    actor=user,
                    target_type="mfa_credential",
                    target_ref=str(user_id),
                    detail={"phase": "accepted"},
                    source_ip=context.source_ip,
                )
                session.commit()
                mfa_result = MfaServiceResult(
                    body=_challenge_state(recovery_challenge),
                    challenge_token=next_token,
                    challenge_expires_at=expires_at,
                    close_user_id=user_id,
                    close_reason="mfa_recovery",
                )
    except AppHTTPException as exc:
        if getattr(exc, "code", None) == "MFA_CHALLENGE_INVALID":
            audit.record_out_of_band(
                engine,
                action="LOGIN_FAILURE",
                result=AuditResult.DENIED,
                actor_username=username,
                source_ip=context.source_ip,
                target_type="mfa_challenge",
                target_ref=str(user_id),
                detail={"stage": "challenge", "reason": "invalid_challenge"},
            )
        raise
    except OperationalError:
        raise _temporarily_unavailable() from None
    except Exception:
        _transaction_failed(
            engine,
            action=failure_action,
            actor_username=username,
            target_user_id=user_id,
            source_ip=context.source_ip,
            phase=failure_phase,
        )
        raise _temporarily_unavailable() from None

    _reset_mfa_account(mfa_limiter, user_id)
    return mfa_result
