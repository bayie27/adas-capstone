from datetime import UTC, datetime

import jwt
from fastapi import Response
from passlib.context import CryptContext

from app.core.config import settings
from app.models import AuthSession, User

# Argon2id per 01_CONTRACTS.md §3.1 / D-005 password handling. No bcrypt->argon2
# migration path is needed — the dev DB is disposable and gets reset with this
# package's schema change (be_decisions_review.md, Password Handling).
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# A fixed hash verified on the unknown-username login path (edge case 8.8, D-006
# "Login Protection and Auditing") so a real Argon2id verification always runs
# and failure timing cannot be used to enumerate valid usernames.
_DUMMY_PASSWORD_HASH = pwd_context.hash("not-a-real-account-used-only-for-timing")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def verify_dummy_password(plain_password: str) -> None:
    """Burns the same Argon2id verification cost as a real check without a
    matching user row. Return value is intentionally discarded — this call
    exists only for its timing, never to authenticate."""
    pwd_context.verify(plain_password, _DUMMY_PASSWORD_HASH)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_session_token(user: User, auth_session: AuthSession) -> str:
    """D-006 claims. `sub` is the immutable user_id, never the mutable
    username. `role` supports frontend initialization only — every request
    re-authorizes from the current database role, never this claim."""
    to_encode = {
        "sub": str(user.user_id),
        "sid": auth_session.session_id,
        "role": str(user.role),
        "iat": datetime.now(UTC),
        "exp": auth_session.expires_at,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    return jwt.encode(
        to_encode, settings.SECRET_KEY.get_secret_value(), algorithm=settings.ALGORITHM
    )


def decode_session_token(token: str) -> dict:
    """Verifies signature, issuer, audience, and expiration, restricted to
    the configured algorithm (rejects `alg: none` and any other algorithm —
    edge case 8.1). Passing `issuer=`/`audience=` is what actually makes
    `jwt.decode` check those claims; writing them without passing these
    kwargs would silently skip verification (edge case 8.3)."""
    return jwt.decode(
        token,
        settings.SECRET_KEY.get_secret_value(),
        algorithms=[settings.ALGORITHM],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
    )


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.SESSION_LIFETIME_MINUTES * 60,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
