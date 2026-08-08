import json
import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, col, select

from app.api.routes import alerts, analytics, auth, cameras, internal, users
from app.core.config import settings
from app.core.db import engine, init_db
from app.core.logging import configure_logging, request_id_ctx
from app.models import AIStatus, Camera, ConnectionStatus
from app.schemas import ApiError, default_error_code
from app.ws_manager import manager

configure_logging(settings.LOG_LEVEL)
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs exactly once when the server boots up
    logger.info("Initializing database...")
    init_db()

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
    yield
    # Anything here runs when the server shuts down
    logger.info("Server shutting down...")


app = FastAPI(
    title="A.D.A.S. Backend API",
    description="Intelligent Real-Time Road Accident Detection & Alert System",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    token = request_id_ctx.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the static snapshots directory so FE can display the images
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_DIR = os.path.join(BASE_DIR, "..", "..", "ai_engine", "snapshots")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)
app.mount("/snapshots", StaticFiles(directory=SNAPSHOT_DIR), name="snapshots")

app.include_router(internal.router)
app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(alerts.router)
app.include_router(users.router)
app.include_router(analytics.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiError(
            detail=str(exc.detail),
            code=default_error_code(exc.status_code),
        ).model_dump(),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
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


@app.exception_handler(OperationalError)
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


@app.exception_handler(Exception)
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


@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Received messages are unused — this just blocks until the client
            # disconnects (or sends a ping/keepalive), since alerts are only
            # ever pushed server -> client.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "A.D.A.S. Backend is running securely"}
