from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import os
from app.core.db import init_db
from app.ws_manager import manager
from app.api.routes import internal, auth, cameras, alerts



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
