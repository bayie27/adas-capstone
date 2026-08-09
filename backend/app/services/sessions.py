import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.core.config import settings
from app.models import AuthSession, User

logger = logging.getLogger("uvicorn.error")


def create_session(
    session: Session,
    user: User,
    *,
    user_agent: str | None = None,
    source_ip: str | None = None,
) -> AuthSession:
    """D-006 — creates the server-side session record that the JWT `sid`
    claim points at. Added to the caller's session; the caller commits
    together with the rest of the login transaction."""
    assert user.user_id is not None
    now = datetime.now(UTC)
    auth_session = AuthSession(
        session_id=str(uuid.uuid4()),
        user_id=user.user_id,
        created_at=now,
        expires_at=now + timedelta(minutes=settings.SESSION_LIFETIME_MINUTES),
        user_agent=user_agent[:256] if user_agent else None,
        source_ip=source_ip,
    )
    session.add(auth_session)
    return auth_session


def get_active_session(session: Session, session_id: str) -> AuthSession | None:
    """Not revoked, not expired. Per D-006 the database session record is
    authoritative — a correctly signed JWT whose row is missing, revoked, or
    past `expires_at` (inclusive) is rejected."""
    auth_session = session.get(AuthSession, session_id)
    if auth_session is None:
        return None
    if auth_session.revoked_at is not None:
        return None
    if auth_session.expires_at <= datetime.now(UTC):
        return None
    return auth_session


def revoke_session(session: Session, session_id: str, reason: str) -> None:
    """Idempotent: revoking an already-revoked or nonexistent session is a
    no-op so `POST /api/auth/logout` can be called twice safely."""
    auth_session = session.get(AuthSession, session_id)
    if auth_session is None or auth_session.revoked_at is not None:
        return
    auth_session.revoked_at = datetime.now(UTC)
    auth_session.revocation_reason = reason
    session.add(auth_session)


def revoke_all_for_user(session: Session, user_id: int, reason: str) -> list[str]:
    """Returns the revoked session ids so the caller can close the matching
    WebSockets — P3 wires that up; here it is just a return value."""
    now = datetime.now(UTC)
    sessions_to_revoke = session.exec(
        select(AuthSession).where(
            col(AuthSession.user_id) == user_id,
            col(AuthSession.revoked_at).is_(None),
        )
    ).all()

    revoked_ids: list[str] = []
    for auth_session in sessions_to_revoke:
        auth_session.revoked_at = now
        auth_session.revocation_reason = reason
        session.add(auth_session)
        revoked_ids.append(auth_session.session_id)
    return revoked_ids


def expire_stale_sessions(engine: Engine) -> int:
    """D-006 — mark auth_session rows past expires_at as revoked.

    Takes an explicit engine and opens its own short-lived Session rather
    than reusing a request session, per D-005's scheduler-job policy. Never
    imports FastAPI, so it stays callable from a plain scheduler job.
    """
    now = datetime.now(UTC)
    with Session(engine) as session:
        stale_sessions = session.exec(
            select(AuthSession).where(
                col(AuthSession.expires_at) < now,
                col(AuthSession.revoked_at).is_(None),
            )
        ).all()

        for auth_session in stale_sessions:
            auth_session.revoked_at = now
            auth_session.revocation_reason = "expired_cleanup"
            session.add(auth_session)

        session.commit()

    if stale_sessions:
        logger.info("Revoked %d expired auth_session row(s).", len(stale_sessions))
    return len(stale_sessions)
