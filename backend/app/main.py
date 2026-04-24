from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing Database...")
    init_db()
    yield

    print("Server shutting down...")


app = FastAPI(
    title="A.D.A.S. Backend API",
    description="Intelligent Real-Time Road Accident Detection & Alert System",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "A.D.A.S. Backend is running securely"}
