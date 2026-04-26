from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging
from fastapi.staticfiles import StaticFiles
import os
from app.core.db import init_db
from app.ws_manager import manager
from app.api.routes import internal, auth, cameras, alerts, users
from app.models import ApiError

@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs exactly once when the server boots up
    print("Initializing Database...")
    init_db()
    yield
    # Anything here runs when the server shuts down
    print("Server shutting down...")


app = FastAPI(
    title="A.D.A.S. Backend API",
    description="Intelligent Real-Time Road Accident Detection & Alert System",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount the static snapshots directory so FE can display the images
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_DIR = os.path.join(BASE_DIR, "..", "..", "ai_engine", "snapshots")
app.mount("/snapshots", StaticFiles(directory=SNAPSHOT_DIR), name="snapshots")


app.include_router(internal.router)
app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(alerts.router)
app.include_router(users.router)

logger = logging.getLogger("uvicorn.error")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiError(
            detail=str(exc.detail),
            code=f"HTTP_{exc.status_code}",
        ).model_dump(),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=ApiError(
            detail="Validation failed",
            code="VALIDATION_ERROR",
            errors=list(exc.errors()),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.method} {request.url}")
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
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "A.D.A.S. Backend is running securely"}
