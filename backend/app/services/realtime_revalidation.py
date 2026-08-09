"""04_PKG_realtime.md Step 5 — the `ws_session_revalidation` scheduler job.

The handshake only authenticates once, at connect time. Without this job, a
session revoked (logout elsewhere, password change, admin disable) while its
socket stays open would keep receiving alerts until the socket happens to
fail for some other reason. Runs every 60s per app/main.py's scheduler
wiring; TC-I-404's "closes immediately" case is handled separately, by
`close_session`/`close_user` being called directly from the routes that
revoke — this job is the catch-all for revocation that happens out of band
(directly in the DB, or by a process other than this one).

Takes an explicit engine and opens its own short-lived Session rather than
reusing a request session, per D-005's scheduler-job policy (see
`app.services.sessions.expire_stale_sessions` for the same pattern).
"""

from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.models import User
from app.services.realtime import CloseCode, RealtimeManager
from app.services.sessions import get_active_session


async def ws_session_revalidation(engine: Engine, manager: RealtimeManager) -> None:
    with Session(engine) as session:
        for conn in manager.snapshot_connections():
            auth_session = get_active_session(session, conn.session_id)
            if auth_session is None:
                await manager.disconnect(
                    conn.connection_id,
                    code=CloseCode.SESSION_REVOKED,
                    reason="session revoked or expired",
                )
                continue

            user = session.get(User, conn.user_id)
            if user is None or not user.is_active:
                await manager.disconnect(
                    conn.connection_id,
                    code=CloseCode.SESSION_REVOKED,
                    reason="user deactivated",
                )
