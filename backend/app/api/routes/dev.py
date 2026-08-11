"""Development-only routes (dev_plan/02_PKG_dev_api.md).

This router is registered by create_app() **only** when the resolved
DEV_TOOLS_ENABLED is true. When it is off the routes do not exist at all —
GET /api/dev/status 404s, and the frontend's probe reads that as "no dev
tools here" rather than needing a separate flag of its own.

DT-3 allows the flag to be on outside development (the LAN demo box runs a
production build), so nothing here may become an authentication bypass:
everything except GET /status is gated, and POST /login-as requires an
existing session because it is an account *switcher*.
"""

from fastapi import APIRouter, Request

from app.core.config import Settings
from app.dev import PROFILES
from app.schemas.dev import DevProfileInfo, DevStatusResponse

router = APIRouter(prefix="/api/dev", tags=["Dev Tools"])


@router.get("/status", response_model=DevStatusResponse)
def dev_status(request: Request) -> DevStatusResponse:
    """Unauthenticated on purpose, and safe to be: it returns only whether
    the router exists and the profile names it can seed. No usernames, no
    camera list, nothing an anonymous caller could act on. The frontend
    needs it before login to decide whether to render the trigger at all.
    """
    app_settings: Settings = request.app.state.settings
    return DevStatusResponse(
        enabled=bool(app_settings.DEV_TOOLS_ENABLED),
        profiles=[
            DevProfileInfo(name=name, description=profile.description)
            for name, profile in PROFILES.items()
        ],
    )
