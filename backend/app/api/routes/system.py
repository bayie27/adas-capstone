"""
Unauthenticated health probes — nothing else. routes/system_health.py (P5)
and routes/maintenance.py (P7) are deliberately separate modules so those
packages can be built in parallel without editing this file.
"""

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text
from sqlmodel import Session

router = APIRouter(tags=["System"])


@router.get("/healthz/live")
def liveness() -> dict[str, str]:
    """The process responds. No DB touch, no telemetry, no configuration."""
    return {"status": "ok"}


@router.get("/healthz/ready")
def readiness(request: Request) -> dict[str, object]:
    """DB reachable + startup initialization complete.

    P7 gates the restore restart on this endpoint, so it must genuinely
    verify database access rather than always returning 200.
    """
    checks: dict[str, str] = {}

    if not getattr(request.app.state, "db_initialized", False):
        checks["initialization"] = "pending"
        raise HTTPException(
            status_code=503, detail="Database initialization is not complete."
        )
    checks["initialization"] = "ok"

    try:
        with Session(request.app.state.engine) as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        checks["database"] = "unreachable"
        raise HTTPException(status_code=503, detail="Database is unreachable.") from exc
    checks["database"] = "ok"

    return {"status": "ready", "checks": checks}
