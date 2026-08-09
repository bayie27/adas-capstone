import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, col, select

from app.api.dependencies import authenticate_session_token
from app.api.routes import (
    alerts,
    analytics,
    audit,
    auth,
    cameras,
    events,
    help,
    internal,
    maintenance,
    settings,
    system,
    users,
)
from app.core.config import Settings
from app.core.config import settings as default_settings
from app.core.db import create_db_engine, get_engine, init_db
from app.core.errors import AppHTTPException
from app.core.logging import configure_logging, request_id_ctx
from app.core.rate_limit import SlidingWindowLimiter
from app.core.scheduler import add_job, create_scheduler
from app.models import AIStatus, Camera, ConnectionStatus
from app.schemas import ApiError, default_error_code
from app.schemas.events import ConnectionReadyData, EventType, make_event
from app.services.cameras import (
    reconcile_camera_desired_states,
    schedule_pending_cooldowns,
    sweep_expired_cooldowns,
)
from app.services.realtime import CloseCode, RealtimeManager
from app.services.realtime_revalidation import ws_session_revalidation
from app.services.sessions import expire_stale_sessions
from app.services.snoozes import (
    reconcile_snoozes,
    schedule_pending_snoozes,
    sweep_expired_snoozes,
)

configure_logging(default_settings.LOG_LEVEL)
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_settings: Settings = app.state.settings
    engine = app.state.engine

    logger.info("Initializing database...")
    init_db(engine, app_settings)
    app.state.db_initialized = True

    # On every server start, reset all enabled cameras to Disconnected/Inactive.
    # This is a single bulk UPDATE — not taxing even for 400 cameras.
    # The AI engine is responsible for updating statuses as it connects to each feed.
    logger.info("Resetting camera statuses to Disconnected/Inactive...")
    with Session(engine) as session:
        cameras_to_reset = session.exec(
            select(Camera).where(
                col(Camera.is_active).is_(True),
                col(Camera.is_enabled).is_(True),
            )
        ).all()

        for camera in cameras_to_reset:
            camera.connection_status = ConnectionStatus.DISCONNECTED.value
            camera.ai_status = AIStatus.INACTIVE.value
            session.add(camera)

        session.commit()
        logger.info(
            "Reset %d camera(s) to Disconnected/Inactive.", len(cameras_to_reset)
        )

    # Desired state is *recomputed*, not reset — unlike observed state,
    # which genuinely has no reporter until the AI engine reconnects. This
    # is what makes the dismiss cooldown durable across a restart: without
    # it, a restart inside the 60s window used to strand the camera Paused
    # forever, since the cooldown was only a discarded asyncio.create_task.
    logger.info("Recomputing camera desired states...")
    pending_cooldowns = reconcile_camera_desired_states(engine)

    # Atomically clears expired Unverified snoozes so those incidents become
    # alarm-active again; returns the still-pending ones so they can be
    # rescheduled once the scheduler exists below (D-004).
    logger.info("Reconciling incident snoozes...")
    pending_snoozes = reconcile_snoozes(engine)

    # Guarded by SCHEDULER_ENABLED (defaulted False in tests) — otherwise
    # background jobs race the test suite's short-lived engines/sessions.
    if app_settings.SCHEDULER_ENABLED:
        scheduler = create_scheduler()
        schedule_pending_cooldowns(
            scheduler, engine, pending_cooldowns, app.state.realtime_manager
        )
        add_job(
            scheduler,
            lambda: sweep_expired_cooldowns(engine, app.state.realtime_manager),
            job_id="cooldown_sweep",
            trigger="interval",
            seconds=30,
        )
        schedule_pending_snoozes(
            scheduler, engine, pending_snoozes, app.state.realtime_manager
        )
        add_job(
            scheduler,
            lambda: sweep_expired_snoozes(engine, app.state.realtime_manager),
            job_id="snooze_sweep",
            trigger="interval",
            seconds=30,
        )
        add_job(
            scheduler,
            lambda: expire_stale_sessions(engine),
            job_id="expired_session_cleanup",
            trigger="interval",
            hours=1,
        )

        # A plain `lambda` here would NOT be awaited by APScheduler's
        # AsyncIOExecutor: it dispatches based on
        # `inspect.iscoroutinefunction(job.func)`, and a lambda wrapping a
        # coroutine call is itself a sync function, so the returned
        # coroutine gets silently dropped ("coroutine was never awaited").
        # An `async def` closure keeps the coroutine-function check true.
        async def run_ws_session_revalidation() -> None:
            await ws_session_revalidation(engine, app.state.realtime_manager)

        add_job(
            scheduler,
            run_ws_session_revalidation,
            job_id="ws_session_revalidation",
            trigger="interval",
            seconds=60,
        )
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("Scheduler started.")
    else:
        app.state.scheduler = None

    yield
    # Anything here runs when the server shuts down
    if app.state.scheduler is not None:
        app.state.scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down.")
    logger.info("Server shutting down...")


async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    token = request_id_ctx.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response


_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def make_origin_validation_middleware(allowed_origins: list[str]):
    """01_CONTRACTS.md §5 Step 5 — defense in depth alongside SameSite=Strict.
    Every unsafe cookie-authenticated method must present an `Origin` that's
    either absent (same-origin non-browser callers like curl/TestClient) or
    in CORS_ORIGINS. /api/internal/* is exempt: it authenticates with
    x-api-key from a non-browser client and never sends Origin."""
    allowed = set(allowed_origins)

    async def origin_validation_middleware(request: Request, call_next):
        if request.method in _UNSAFE_METHODS and not request.url.path.startswith(
            "/api/internal/"
        ):
            origin = request.headers.get("origin")
            if origin is not None and origin not in allowed:
                return JSONResponse(
                    status_code=403,
                    content=ApiError(
                        detail="Request Origin is not allowed.",
                        code="ORIGIN_REJECTED",
                    ).model_dump(),
                )
        return await call_next(request)

    return origin_validation_middleware


async def http_exception_handler(request: Request, exc: HTTPException):
    code = getattr(exc, "code", None) or default_error_code(exc.status_code)
    content = ApiError(detail=str(exc.detail), code=code).model_dump()
    if isinstance(exc, AppHTTPException):
        content.update(exc.extra)
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=exc.headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = json.loads(json.dumps(exc.errors(), default=str))
    return JSONResponse(
        status_code=422,
        content=ApiError(
            detail="Validation failed",
            code="VALIDATION_ERROR",
            errors=errors,
        ).model_dump(),
    )


async def operational_error_handler(request: Request, exc: OperationalError):
    if "database is locked" not in str(exc).lower():
        # Not the lock-timeout case D-005 calls out — treat like any other
        # unhandled exception rather than claiming a specific cause.
        logger.exception(
            "Unhandled OperationalError on %s %s", request.method, request.url
        )
        return JSONResponse(
            status_code=500,
            content=ApiError(
                detail="An internal server error occurred.",
                code="INTERNAL_SERVER_ERROR",
            ).model_dump(),
        )

    logger.error(
        "SQLite busy-timeout exceeded on %s %s [request_id=%s]",
        request.method,
        request.url,
        request_id_ctx.get(),
    )
    return JSONResponse(
        status_code=503,
        content=ApiError(
            detail="The service is temporarily unavailable. Please retry shortly.",
            code="TEMPORARILY_UNAVAILABLE",
        ).model_dump(),
    )


async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "Unhandled exception on %s %s [request_id=%s]",
        request.method,
        request.url,
        request_id_ctx.get(),
    )
    return JSONResponse(
        status_code=500,
        content=ApiError(
            detail="An internal server error occurred.",
            code="INTERNAL_SERVER_ERROR",
        ).model_dump(),
    )


async def websocket_alerts(
    websocket: WebSocket, engine: Engine = Depends(get_engine)
) -> None:
    """01_CONTRACTS.md §9 / 04_PKG_realtime.md Step 4. Order matters: Origin
    is rejected before any DB work, and the socket is only `accept()`-ed once
    authentication and the connection limits both pass — a browser cannot
    set an `Authorization` header on a WebSocket, so the session cookie
    (sent automatically on the handshake) is the only credential, same as
    D-006 chose for REST.

    `engine` comes through `Depends(get_engine)` rather than reading
    `websocket.app.state.engine` directly, so the test suite's dependency
    override (a throwaway in-memory engine) actually takes effect here too.
    """
    app_settings: Settings = websocket.app.state.settings
    manager: RealtimeManager = websocket.app.state.realtime_manager

    origin = websocket.headers.get("origin")
    if origin is not None and origin not in set(app_settings.CORS_ORIGINS):
        await websocket.close(code=CloseCode.ORIGIN_REJECTED)
        return

    token = websocket.cookies.get(app_settings.SESSION_COOKIE_NAME)
    if not token:
        await websocket.close(code=CloseCode.AUTH_FAILED)
        return

    with Session(engine) as session:
        try:
            user, auth_session = authenticate_session_token(token, session)
        except AppHTTPException:
            await websocket.close(code=CloseCode.AUTH_FAILED)
            return

        assert user.user_id is not None
        if (
            manager.connection_count_for_user(user.user_id)
            >= app_settings.WS_MAX_CONNECTIONS_PER_USER
            or manager.total_connection_count() >= app_settings.WS_MAX_CONNECTIONS_TOTAL
        ):
            # Reject the new connection; never displace an established
            # operational dashboard.
            await websocket.close(code=CloseCode.CONNECTION_LIMIT)
            return

        await websocket.accept()
        conn = await manager.connect(
            websocket,
            user_id=user.user_id,
            session_id=auth_session.session_id,
            role=user.role,
        )
        user_id, role = user.user_id, user.role

    ready_event = make_event(
        EventType.CONNECTION_READY,
        ConnectionReadyData(
            connection_id=conn.connection_id,
            server_time=datetime.now(UTC),
            user_id=user_id,
            role=role,
        ),
    )
    conn.queue.put_nowait(ready_event.model_dump(mode="json"))

    try:
        while True:
            # Received messages are unused — clients never mutate state over
            # the socket (D-008). This just blocks until the client
            # disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        # The old implementation only deregistered on WebSocketDisconnect,
        # leaking the connection on any other exception. Every exit path
        # goes through the `finally` below now.
        logger.exception(
            "Unexpected error in /ws/alerts read loop for connection %s",
            conn.connection_id,
        )
    finally:
        await manager.disconnect(conn.connection_id, code=1000, reason="closed")


def health_check() -> dict[str, str]:
    return {"status": "A.D.A.S. Backend is running securely"}


def create_app(app_settings: Settings | None = None) -> FastAPI:
    """App factory. `app_settings` lets tests bind a throwaway engine and
    disposable settings without touching the real repo-root DB — see
    backend/tests/conftest.py."""
    resolved_settings = app_settings if app_settings is not None else default_settings

    application = FastAPI(
        title="A.D.A.S. Backend API",
        description="Intelligent Real-Time Road Accident Detection & Alert System",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.engine = create_db_engine(resolved_settings)
    application.state.db_initialized = False
    application.state.rate_limiter = SlidingWindowLimiter(
        resolved_settings.LOGIN_RATE_LIMIT_ATTEMPTS,
        resolved_settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )
    # On app.state, not a module global, so tests get a clean instance per
    # app (04_PKG_realtime.md Step 2).
    application.state.realtime_manager = RealtimeManager(
        queue_maxsize=resolved_settings.WS_QUEUE_MAXSIZE,
        send_timeout_seconds=resolved_settings.WS_SEND_TIMEOUT_SECONDS,
    )

    application.middleware("http")(request_id_middleware)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.middleware("http")(
        make_origin_validation_middleware(resolved_settings.CORS_ORIGINS)
    )

    application.include_router(internal.router)
    application.include_router(auth.router)
    application.include_router(cameras.router)
    application.include_router(alerts.router)
    application.include_router(users.router)
    application.include_router(analytics.router)
    application.include_router(system.router)
    application.include_router(audit.router)
    application.include_router(maintenance.router)
    application.include_router(events.router)
    application.include_router(help.router)
    application.include_router(settings.router)

    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(
        RequestValidationError, validation_exception_handler
    )
    application.add_exception_handler(OperationalError, operational_error_handler)
    application.add_exception_handler(Exception, global_exception_handler)

    application.add_api_websocket_route("/ws/alerts", websocket_alerts)
    application.add_api_route("/", health_check, methods=["GET"])

    return application


# The FastAPI CLI entrypoint (`uv run fastapi dev backend/app/main.py`) still
# imports this module-level `app` unchanged.
app = create_app()
