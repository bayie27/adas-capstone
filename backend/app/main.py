from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from app.core.db import init_db
from app.ws_manager import manager
from app.api.routes import internal, auth



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
import os
os.makedirs("snapshots", exist_ok=True) # Ensure the folder exists
app.mount("/snapshots", StaticFiles(directory="snapshots"), name="snapshots")


app.include_router(internal.router)
app.include_router(auth.router)

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
