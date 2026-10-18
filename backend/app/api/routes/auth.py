import jwt
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app.api.dependencies import get_realtime_manager
from app.api.routes.mfa import (
    clear_challenge_cookie,
)
from app.api.routes.mfa import (
    password_login as mfa_password_login,
)
from app.core.db import get_engine, get_session
from app.core.rate_limit import (
    SlidingWindowLimiter,
    get_mfa_rate_limiter,
    get_rate_limiter,
)
from app.core.security import (
    clear_session_cookie,
    decode_session_token,
)
from app.models import AuditResult, User
from app.schemas.mfa import ChallengeState
from app.services import audit
from app.services.mfa import MfaRequestContext, cancel_challenge
from app.services.realtime import RealtimeManager
from app.services.sessions import revoke_session

# The Swagger "Authorize" button no longer works once auth moves to an
# HttpOnly cookie — OAuth2PasswordRequestForm is kept here purely as a form
# parser for `username`/`password`, not as a bearer-token scheme. There is
# no OAuth2PasswordBearer anywhere in this codebase anymore; see
# app/api/dependencies.py.
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login", response_model=ChallengeState)
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    engine=Depends(get_engine),
    password_limiter: SlidingWindowLimiter = Depends(get_rate_limiter),
    mfa_limiter: SlidingWindowLimiter = Depends(get_mfa_rate_limiter),
) -> ChallengeState:
    """The P2 password-stage adapter; a password never creates a session."""
    return mfa_password_login(
        request,
        response,
        form_data,
        engine,
        password_limiter,
        mfa_limiter,
    )


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
    app_settings = request.app.state.settings
    response.headers["Cache-Control"] = "no-store"

    challenge_token = request.cookies.get("adas_mfa_challenge")
    if challenge_token is not None and challenge_token.isascii():
        cancel_challenge(
            session.get_bind(),
            challenge_token=challenge_token,
            context=MfaRequestContext(
                source_ip=_client_ip(request),
                user_agent=request.headers.get("user-agent"),
            ),
            settings=app_settings,
        )
    clear_challenge_cookie(response, app_settings)

    token = request.cookies.get(app_settings.SESSION_COOKIE_NAME)
    sid = None
    if token:
        try:
            payload = decode_session_token(token, app_settings)
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

    clear_session_cookie(response, app_settings)

    # After the commit, in the route (04_PKG_realtime.md Step 5) — closing a
    # socket for a rollback that never happened is worse than a late close.
    # Idempotent: a second logout for an already-revoked sid closes nothing.
    if sid:
        await manager.close_session(sid, reason="logout")

    return None
