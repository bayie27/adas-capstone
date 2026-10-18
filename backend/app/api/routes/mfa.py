"""Thin API adapter for the transactional MFA services."""

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.engine import Engine
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.dependencies import authenticate_session_token, get_realtime_manager
from app.core.config import Settings
from app.core.db import get_engine
from app.core.errors import AppHTTPException
from app.core.rate_limit import (
    SlidingWindowLimiter,
    get_mfa_rate_limiter,
    get_rate_limiter,
)
from app.core.security import clear_session_cookie, set_session_cookie
from app.schemas.common import ApiError
from app.schemas.mfa import (
    ChallengeState,
    CompletedEnrollment,
    CompletedLogin,
    CompletedReplacement,
    EnrollmentConfirmRequest,
    EnrollmentFromSessionRequest,
    EnrollmentStartRequest,
    EnrollmentStartResponse,
    MfaStatusResponse,
    RecoveryCodeRotationRequest,
    RecoveryCodesResponse,
    ReplacementStartRequest,
    VerifyChallengeRequest,
)
from app.services.mfa import (
    MfaRequestContext,
    MfaServiceResult,
    begin_enrollment_from_session,
    begin_password_login,
    begin_replacement,
    cancel_challenge,
    confirm_enrollment,
    get_challenge,
    get_enrollment,
    get_mfa_status,
    rotate_recovery_codes,
    verify_challenge,
)
from app.services.realtime import RealtimeManager

router = APIRouter(prefix="/api/auth/mfa", tags=["Multi-factor authentication"])


@dataclass(frozen=True)
class MfaIdentity:
    session_id: str
    user_id: int


class MfaNoStoreMiddleware(BaseHTTPMiddleware):
    """Keep auth success and error responses out of browser/proxy caches."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/auth"):
            response.headers["Cache-Control"] = "no-store"
        return response


def install_auth_no_store(app: FastAPI) -> None:
    """Install the P4 auth cache policy without activating any MFA route."""
    app.add_middleware(MfaNoStoreMiddleware)
    app.add_exception_handler(RequestValidationError, mfa_validation_exception_handler)


async def mfa_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    is_auth = request.url.path.startswith("/api/auth")
    if not is_auth:
        # Preserve the application's existing validation contract on other
        # routes; only auth validation needs the stricter input/context scrub.
        errors = json.loads(json.dumps(exc.errors(), default=str))
        for error in errors:
            locations = [str(part).lower() for part in error.get("loc", [])]
            if any("password" in part for part in locations):
                error.pop("input", None)
        return JSONResponse(
            status_code=422,
            content=ApiError(
                detail="Validation failed",
                code="VALIDATION_ERROR",
                errors=errors,
            ).model_dump(),
        )

    errors = []
    for error in exc.errors():
        safe_error = {
            key: value for key, value in error.items() if key not in {"input", "ctx"}
        }
        errors.append(safe_error)
    return JSONResponse(
        status_code=422,
        content=ApiError(
            detail="Validation failed",
            code="VALIDATION_ERROR",
            errors=errors,
        ).model_dump(),
        headers={"Cache-Control": "no-store"},
    )


def _context(request: Request) -> MfaRequestContext:
    return MfaRequestContext(
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _challenge_cookie_name() -> str:
    return "adas_mfa_challenge"


def _set_challenge_cookie(
    response: Response,
    *,
    token: str,
    expires_at: datetime,
    settings: Settings,
) -> None:
    max_age = max(0, math.ceil((expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        key=_challenge_cookie_name(),
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="strict",
        path="/api/auth",
    )


def clear_challenge_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=_challenge_cookie_name(),
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="strict",
        path="/api/auth",
    )


def _apply_result(
    response: Response,
    result: MfaServiceResult,
    settings: Settings,
) -> None:
    response.headers["Cache-Control"] = "no-store"
    if result.challenge_token and result.challenge_expires_at:
        _set_challenge_cookie(
            response,
            token=result.challenge_token,
            expires_at=result.challenge_expires_at,
            settings=settings,
        )
    elif result.clear_challenge:
        clear_challenge_cookie(response, settings)
    if result.session_token:
        set_session_cookie(response, result.session_token, settings)
    elif result.clear_session:
        clear_session_cookie(response, settings)


def _reset_password_limiter_after_authentication(
    result: MfaServiceResult,
    limiter: SlidingWindowLimiter,
    source_ip: str | None,
) -> None:
    if isinstance(result.body, CompletedLogin):
        limiter.reset(f"ip:{source_ip}")
        limiter.reset(f"user:{result.body.user.username.lower()}")


def _call_challenge(
    response: Response,
    settings: Settings,
    operation: Callable[[], MfaServiceResult],
) -> MfaServiceResult:
    try:
        return operation()
    except AppHTTPException as exc:
        if getattr(exc, "code", None) == "MFA_CHALLENGE_INVALID":
            clear_response = Response()
            clear_challenge_cookie(clear_response, settings)
            headers = dict(exc.headers or {})
            headers["Set-Cookie"] = clear_response.headers["set-cookie"]
            exc.headers = headers
        raise


def _current_identity(
    request: Request,
    engine: Engine,
) -> MfaIdentity:
    settings = _settings(request)
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        raise AppHTTPException(401, "Not authenticated.", code="AUTH_REQUIRED")
    with Session(engine) as session:
        user, auth_session = authenticate_session_token(token, session, settings)
        if user.user_id is None:
            raise AppHTTPException(
                401, "Session was revoked or has expired.", code="AUTH_REVOKED"
            )
        return MfaIdentity(
            session_id=auth_session.session_id,
            user_id=user.user_id,
        )


def _current_identity_dependency(
    request: Request,
    engine: Engine = Depends(get_engine),
) -> MfaIdentity:
    return _current_identity(request, engine)


def password_login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    engine: Engine = Depends(get_engine),
    password_limiter: SlidingWindowLimiter = Depends(get_rate_limiter),
    mfa_limiter: SlidingWindowLimiter = Depends(get_mfa_rate_limiter),
) -> ChallengeState:
    """P4's thin POST /login handler; P2 keeps it outside normal routing."""
    settings = _settings(request)
    response.headers["Cache-Control"] = "no-store"
    result = begin_password_login(
        engine,
        username=form_data.username,
        password=form_data.password,
        context=_context(request),
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    _apply_result(response, result, settings)
    if isinstance(result.body, ChallengeState):
        return result.body
    raise RuntimeError("Password stage returned an invalid service response.")


@router.get("/challenge", response_model=ChallengeState)
def challenge_status(
    request: Request,
    response: Response,
    engine: Engine = Depends(get_engine),
) -> ChallengeState:
    settings = _settings(request)
    response.headers["Cache-Control"] = "no-store"
    result = _call_challenge(
        response,
        settings,
        lambda: get_challenge(
            engine,
            challenge_token=request.cookies.get(_challenge_cookie_name(), ""),
            settings=settings,
        ),
    )
    _apply_result(response, result, settings)
    return result.body


@router.delete("/challenge", status_code=status.HTTP_204_NO_CONTENT)
def challenge_cancel(
    request: Request,
    response: Response,
    engine: Engine = Depends(get_engine),
) -> None:
    settings = _settings(request)
    result = cancel_challenge(
        engine,
        challenge_token=request.cookies.get(_challenge_cookie_name()),
        context=_context(request),
        settings=settings,
    )
    _apply_result(response, result, settings)


@router.post("/enrollment/start", response_model=EnrollmentStartResponse)
def enrollment_start(
    request: Request,
    response: Response,
    _body: EnrollmentStartRequest,
    engine: Engine = Depends(get_engine),
) -> EnrollmentStartResponse:
    settings = _settings(request)
    result = _call_challenge(
        response,
        settings,
        lambda: get_enrollment(
            engine,
            challenge_token=request.cookies.get(_challenge_cookie_name(), ""),
            settings=settings,
        ),
    )
    _apply_result(response, result, settings)
    return result.body


@router.post(
    "/enrollment/confirm",
    response_model=CompletedEnrollment | CompletedReplacement,
)
async def enrollment_confirm(
    payload: EnrollmentConfirmRequest,
    request: Request,
    response: Response,
    engine: Engine = Depends(get_engine),
    password_limiter: SlidingWindowLimiter = Depends(get_rate_limiter),
    mfa_limiter: SlidingWindowLimiter = Depends(get_mfa_rate_limiter),
    manager: RealtimeManager = Depends(get_realtime_manager),
) -> CompletedEnrollment | CompletedReplacement:
    settings = _settings(request)
    result = await run_in_threadpool(
        _call_challenge,
        response,
        settings,
        lambda: confirm_enrollment(
            engine,
            challenge_token=request.cookies.get(_challenge_cookie_name(), ""),
            code=payload.code,
            context=_context(request),
            settings=settings,
            mfa_limiter=mfa_limiter,
        ),
    )
    _reset_password_limiter_after_authentication(
        result, password_limiter, _context(request).source_ip
    )
    _apply_result(response, result, settings)
    if result.close_user_id is not None:
        await manager.close_user(
            result.close_user_id,
            reason=result.close_reason or "mfa_enrollment",
        )
    return result.body


@router.post("/verify", response_model=CompletedLogin | ChallengeState)
async def challenge_verify(
    payload: VerifyChallengeRequest,
    request: Request,
    response: Response,
    engine: Engine = Depends(get_engine),
    password_limiter: SlidingWindowLimiter = Depends(get_rate_limiter),
    mfa_limiter: SlidingWindowLimiter = Depends(get_mfa_rate_limiter),
    manager: RealtimeManager = Depends(get_realtime_manager),
) -> CompletedLogin | ChallengeState:
    settings = _settings(request)
    result = await run_in_threadpool(
        _call_challenge,
        response,
        settings,
        lambda: verify_challenge(
            engine,
            challenge_token=request.cookies.get(_challenge_cookie_name(), ""),
            method=payload.method,
            code=payload.code,
            context=_context(request),
            settings=settings,
            mfa_limiter=mfa_limiter,
        ),
    )
    _reset_password_limiter_after_authentication(
        result, password_limiter, _context(request).source_ip
    )
    _apply_result(response, result, settings)
    if result.close_user_id is not None:
        await manager.close_user(
            result.close_user_id,
            reason=result.close_reason or "mfa_recovery",
        )
    return result.body


@router.get("/status", response_model=MfaStatusResponse)
def mfa_status(
    request: Request,
    identity: MfaIdentity = Depends(_current_identity_dependency),
    engine: Engine = Depends(get_engine),
) -> MfaStatusResponse:
    result = get_mfa_status(
        engine,
        session_id=identity.session_id,
        user_id=identity.user_id,
        settings=_settings(request),
    )
    return result.body


@router.post("/recovery-codes/rotate", response_model=RecoveryCodesResponse)
def recovery_codes_rotate(
    payload: RecoveryCodeRotationRequest,
    request: Request,
    response: Response,
    identity: MfaIdentity = Depends(_current_identity_dependency),
    engine: Engine = Depends(get_engine),
    mfa_limiter: SlidingWindowLimiter = Depends(get_mfa_rate_limiter),
) -> RecoveryCodesResponse:
    settings = _settings(request)
    result = rotate_recovery_codes(
        engine,
        session_id=identity.session_id,
        user_id=identity.user_id,
        password=payload.password,
        code=payload.code,
        context=_context(request),
        settings=settings,
        mfa_limiter=mfa_limiter,
    )
    _apply_result(response, result, settings)
    return result.body


@router.post("/replacement/start", response_model=ChallengeState)
def replacement_start(
    payload: ReplacementStartRequest,
    request: Request,
    response: Response,
    identity: MfaIdentity = Depends(_current_identity_dependency),
    engine: Engine = Depends(get_engine),
    mfa_limiter: SlidingWindowLimiter = Depends(get_mfa_rate_limiter),
) -> ChallengeState:
    settings = _settings(request)
    result = begin_replacement(
        engine,
        session_id=identity.session_id,
        user_id=identity.user_id,
        password=payload.password,
        code=payload.code,
        context=_context(request),
        settings=settings,
        mfa_limiter=mfa_limiter,
    )
    _apply_result(response, result, settings)
    return result.body


@router.post(
    "/enrollment/from-session",
    response_model=ChallengeState,
)
def enrollment_from_session(
    payload: EnrollmentFromSessionRequest,
    request: Request,
    response: Response,
    identity: MfaIdentity = Depends(_current_identity_dependency),
    engine: Engine = Depends(get_engine),
    password_limiter: SlidingWindowLimiter = Depends(get_rate_limiter),
    mfa_limiter: SlidingWindowLimiter = Depends(get_mfa_rate_limiter),
) -> ChallengeState:
    settings = _settings(request)
    result = begin_enrollment_from_session(
        engine,
        session_id=identity.session_id,
        user_id=identity.user_id,
        password=payload.password,
        context=_context(request),
        settings=settings,
        password_limiter=password_limiter,
        mfa_limiter=mfa_limiter,
    )
    _apply_result(response, result, settings)
    return result.body
