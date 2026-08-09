from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.api.dependencies import get_realtime_manager
from app.core.config import settings
from app.core.db import get_session
from app.core.errors import AppHTTPException
from app.core.rate_limit import SlidingWindowLimiter, get_rate_limiter
from app.core.security import (
    clear_session_cookie,
    create_session_token,
    decode_session_token,
    set_session_cookie,
    verify_dummy_password,
    verify_password,
)
from app.models import AuditResult, User
from app.schemas import LoginResponse, UserRead
from app.services import audit
from app.services.realtime import RealtimeManager
from app.services.sessions import create_session, revoke_session

# The Swagger "Authorize" button no longer works once auth moves to an
# HttpOnly cookie — OAuth2PasswordRequestForm is kept here purely as a form
# parser for `username`/`password`, not as a bearer-token scheme. There is
# no OAuth2PasswordBearer anywhere in this codebase anymore; see
# app/api/dependencies.py.
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login", response_model=LoginResponse)
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
    limiter: SlidingWindowLimiter = Depends(get_rate_limiter),
) -> LoginResponse:
    response.headers["Cache-Control"] = "no-store"

    source_ip = _client_ip(request)
    attempted_username = form_data.username.strip()
    ip_key = f"ip:{source_ip}"
    username_key = f"user:{attempted_username.lower()}"

    ip_allowed, ip_retry_after = limiter.check(ip_key)
    username_allowed, username_retry_after = limiter.check(username_key)
    if not ip_allowed or not username_allowed:
        retry_after = max(ip_retry_after, username_retry_after)
        audit.record_out_of_band(
            session.get_bind(),
            action="LOGIN_FAILURE",
            result=AuditResult.DENIED,
            actor_username=attempted_username,
            source_ip=source_ip,
            detail={"reason": "rate_limited"},
        )
        raise AppHTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many login attempts. Please try again later.",
            code="AUTH_RATE_LIMITED",
            headers={"Retry-After": str(retry_after)},
        )

    user = session.exec(select(User).where(User.username == attempted_username)).first()

    def _reject(reason: str) -> None:
        limiter.record_failure(ip_key)
        limiter.record_failure(username_key)
        audit.record_out_of_band(
            session.get_bind(),
            action="LOGIN_FAILURE",
            result=AuditResult.DENIED,
            actor=user,
            actor_username=attempted_username,
            source_ip=source_ip,
            detail={"reason": reason},
        )
        # Byte-identical for unknown username, wrong password, and inactive
        # account (edge cases 8.8/8.9, D-006) — never a distinguishable 400.
        raise AppHTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect username or password.",
            code="AUTH_INVALID_CREDENTIALS",
        )

    if user is None:
        # A real Argon2id verification always runs, even for an unknown
        # username, so failure timing can't be used to enumerate accounts.
        verify_dummy_password(form_data.password)
        _reject("unknown_user")

    if not verify_password(form_data.password, user.password_hash):
        _reject("wrong_password")

    if not user.is_active:
        _reject("inactive_account")

    auth_session = create_session(
        session,
        user,
        user_agent=request.headers.get("user-agent"),
        source_ip=source_ip,
    )
    user.last_login = datetime.now(UTC)
    session.add(user)

    audit.record(
        session,
        action="LOGIN_SUCCESS",
        result=AuditResult.SUCCESS,
        actor=user,
        target_type="session",
        target_ref=auth_session.session_id,
        source_ip=source_ip,
    )
    session.commit()
    session.refresh(user)

    limiter.reset(ip_key)
    limiter.reset(username_key)

    token = create_session_token(user, auth_session)
    set_session_cookie(response, token)

    return LoginResponse(user=UserRead.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    manager: RealtimeManager = Depends(get_realtime_manager),
) -> None:
    """Idempotent: an already-revoked, expired, or missing session cookie
    still clears the cookie and returns 204 (edge case 10.5, D-006) — logout
    never asks "were you still logged in?", only "make sure I'm logged out."
    """
    response.headers["Cache-Control"] = "no-store"

    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    sid = None
    if token:
        try:
            payload = decode_session_token(token)
        except jwt.InvalidTokenError:
            payload = None

        if payload:
            sid = payload.get("sid")
            sub = payload.get("sub")
            if sid:
                revoke_session(session, sid, reason="logout")
                actor = None
                try:
                    actor = session.get(User, int(sub)) if sub else None
                except (TypeError, ValueError):
                    actor = None
                if actor is not None:
                    audit.record(
                        session,
                        action="LOGOUT",
                        result=AuditResult.SUCCESS,
                        actor=actor,
                        target_type="session",
                        target_ref=sid,
                        source_ip=_client_ip(request),
                    )
                session.commit()

    clear_session_cookie(response)

    # After the commit, in the route (04_PKG_realtime.md Step 5) — closing a
    # socket for a rollback that never happened is worse than a late close.
    # Idempotent: a second logout for an already-revoked sid closes nothing.
    if sid:
        await manager.close_session(sid, reason="logout")

    return None
