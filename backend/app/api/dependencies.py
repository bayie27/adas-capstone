import secrets

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlmodel import Session

from app.core.config import settings
from app.core.db import get_session
from app.core.errors import AppHTTPException
from app.core.security import decode_session_token
from app.models import AuditResult, AuthSession, User, UserRole
from app.services.audit import record_out_of_band
from app.services.realtime import RealtimeManager
from app.services.sessions import get_active_session


def verify_internal_api_key(x_api_key: str | None = Header(default=None)) -> str:
    if x_api_key is None or not secrets.compare_digest(
        x_api_key, settings.INTERNAL_API_KEY.get_secret_value()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Internal API Key"
        )
    return x_api_key


def _auth_required() -> AppHTTPException:
    return AppHTTPException(
        status.HTTP_401_UNAUTHORIZED, "Not authenticated.", code="AUTH_REQUIRED"
    )


def _auth_revoked() -> AppHTTPException:
    return AppHTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Session was revoked or has expired.",
        code="AUTH_REVOKED",
    )


def authenticate_session_token(
    token: str, session: Session
) -> tuple[User, AuthSession]:
    """D-006 request authentication, in order: (1) verify the JWT signature,
    issuer, audience, and expiry; (2) load the auth_session by `sid` and
    require it active; (3) load the User by `sub` and require it active;
    (4) the caller authorizes using the *current* database role, never the
    JWT's `role` claim.

    Shared by `get_current_user` (reads the token from the cookie on an HTTP
    `Request`) and the `/ws/alerts` handshake (04_PKG_realtime.md Step 4,
    reads it from `WebSocket.cookies`) — a browser cannot set an
    `Authorization` header on a WebSocket, so both paths authenticate off
    the same session cookie, just plucked from a different object.
    """
    try:
        payload = decode_session_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise AppHTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Session expired. Please log in again.",
            code="AUTH_EXPIRED",
        ) from exc
    except jwt.InvalidTokenError as exc:
        # Covers a malformed/empty cookie value, a bad signature, an
        # alg:none token (algorithms= is explicit in decode_session_token),
        # and a wrong iss/aud — all collapse to the same generic code so
        # the response never distinguishes *why* the token was rejected.
        raise _auth_required() from exc

    sid = payload.get("sid")
    sub = payload.get("sub")
    if not sid or not sub:
        raise _auth_required()

    try:
        sub_user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise _auth_required() from exc

    auth_session = get_active_session(session, sid)
    if auth_session is None:
        raise _auth_revoked()

    # A `sid` whose session row belongs to a different user than the
    # token's `sub` claims (edge case 8.5) — reject rather than trust `sub`.
    if auth_session.user_id != sub_user_id:
        raise _auth_revoked()

    user = session.get(User, sub_user_id)
    if user is None or not user.is_active:
        raise _auth_revoked()

    return user, auth_session


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    """The cookie is the only place the token is read from — there is no
    bearer-token fallback."""
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        raise _auth_required()

    user, _auth_session = authenticate_session_token(token, session)
    return user


def require_admin(action: str | None = None):
    """Like a plain admin guard, but when `action` names a catalog action
    (01_CONTRACTS.md §8), a 403 rejection is also audited as a denied
    attempt at that action — Step 10's "every 403 from get_current_admin"
    requirement, applied per-route since `action` is a CHECK-constrained
    enum and there's no generic "forbidden" catalog entry to fall back to.
    Routes with no corresponding catalog action (the users list, the audit
    viewer — "viewing is not audited") use `get_current_admin` below, which
    is just `require_admin(None)`, instead."""

    def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        session: Session = Depends(get_session),
    ) -> User:
        if current_user.role != UserRole.ADMIN:
            if action is not None:
                record_out_of_band(
                    session.get_bind(),
                    action=action,
                    result=AuditResult.DENIED,
                    actor=current_user,
                    source_ip=request.client.host if request.client else None,
                )
            raise AppHTTPException(
                status.HTTP_403_FORBIDDEN,
                "Admin privileges required.",
                code="FORBIDDEN",
            )
        return current_user

    return dependency


get_current_admin = require_admin(None)


def get_realtime_manager(request: Request) -> RealtimeManager:
    """Routes that broadcast (alerts, internal) or that revoke sessions and
    must close the matching sockets (auth, users) depend on this instead of
    importing a module-level singleton — see app.services.realtime."""
    return request.app.state.realtime_manager
