import logging
from datetime import UTC, datetime

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.models import AuthSession

logger = logging.getLogger("uvicorn.error")


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
