"""Development-only routes (dev_plan/02_PKG_dev_api.md).

This router is registered by create_app() **only** when the resolved
DEV_TOOLS_ENABLED is true. When it is off the routes do not exist at all —
GET /api/dev/status 404s, and the frontend's probe reads that as "no dev
tools here" rather than needing a separate flag of its own.

DT-3 allows the flag to be on outside development (the LAN demo box runs a
production build), so nothing here may become an authentication bypass:
everything except GET /status is gated, and POST /login-as requires an
existing session because it is an account *switcher*, not a way in.

get_current_admin is require_admin(None) — the variant that does NOT write
a denied audit row, which is correct here: none of the 26 AUDIT_ACTIONS
covers a dev action, and this module writes no audit rows at all
(see app/dev/service.py's docstring for why that is deliberate).
"""

import random
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session, col, select

from app.api.dependencies import (
    authenticate_session_token,
    get_current_user,
    get_realtime_manager,
    get_scheduler,
    require_admin,
)
from app.core.config import Settings
from app.core.db import get_session
from app.core.errors import AppHTTPException
from app.core.security import create_session_token, set_session_cookie
from app.dev import PROFILES, write_snapshot
from app.dev.seed import seed_health_history
from app.dev.service import (
    UatProfileRequired,
    reset_uat_session,
)
from app.dev.service import (
    reseed as reseed_service,
)
from app.models import Camera, DetectionLog, DetectionStatus, User
from app.schemas import DetectionLogCreateV2
from app.schemas.dev import (
    DevCameraStateRequest,
    DevDetectionRequest,
    DevHealthHistoryRequest,
    DevHealthHistoryResponse,
    DevLoginAsRequest,
    DevLoginAsResponse,
    DevProfileInfo,
    DevReseedRequest,
    DevReseedResponse,
    DevSessionUser,
    DevStatusResponse,
    DevUatResetRequest,
    DevUatResetResponse,
)
from app.services.cameras import ObservedReport, apply_observed
from app.services.events import camera_status_update_event, new_detection_event
from app.services.incidents import (
    CameraUnavailableForIngest,
    OpenIncidentConflict,
    ingest_detection,
)
from app.services.realtime import RealtimeManager
from app.services.sessions import create_session, revoke_session

router = APIRouter(prefix="/api/dev", tags=["Dev Tools"])

get_current_admin = require_admin(None)

_OPEN_STATUSES = (DetectionStatus.UNVERIFIED.value, DetectionStatus.ONGOING.value)


def _app_settings(request: Request) -> Settings:
    return request.app.state.settings


def _mint_session(
    request: Request,
    response: Response,
    session: Session,
    user: User,
) -> DevSessionUser:
    """Exactly what routes/auth.py:107-132 does. No hand-rolled Set-Cookie:
    SESSION_COOKIE_NAME, HttpOnly, SameSite and SESSION_COOKIE_SECURE must
    stay identical to a real login, or this silently diverges on the LAN TLS
    demo where SESSION_COOKIE_SECURE actually matters."""
    auth_session = create_session(
        session,
        user,
        user_agent=request.headers.get("user-agent"),
        source_ip=request.client.host if request.client else None,
    )
    session.commit()
    session.refresh(user)
    set_session_cookie(response, create_session_token(user, auth_session))
    return DevSessionUser(user_id=user.user_id, username=user.username, role=user.role)


@router.get("/status", response_model=DevStatusResponse)
def dev_status(request: Request) -> DevStatusResponse:
    """Unauthenticated on purpose, and safe to be: it returns only whether
    the router exists and the profile names it can seed. No usernames, no
    camera list, nothing an anonymous caller could act on. The frontend
    needs it before login to decide whether to render the trigger at all.
    """
    app_settings = _app_settings(request)
    return DevStatusResponse(
        enabled=bool(app_settings.DEV_TOOLS_ENABLED),
        profiles=[
            DevProfileInfo(name=name, description=profile.description)
            for name, profile in PROFILES.items()
        ],
    )


@router.post("/reseed", response_model=DevReseedResponse)
async def dev_reseed(
    body: DevReseedRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
    manager: RealtimeManager = Depends(get_realtime_manager),
    scheduler=Depends(get_scheduler),
) -> DevReseedResponse:
    """The only endpoint that mints a cookie, and only because it just
    destroyed the session it authenticated with (DT-2)."""
    if body.profile not in PROFILES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown seed profile '{body.profile}'. "
            f"Expected one of: {', '.join(PROFILES)}.",
        )

    app_settings = _app_settings(request)
    # Read before the wipe — this user row is about to be deleted.
    requested_username = body.login_as or current_user.username

    result = await reseed_service(
        request.app.state.engine,
        profile=body.profile,
        scheduler=scheduler,
        snapshot_root=app_settings.SNAPSHOT_ROOT,
        manager=manager,
        target_settings=app_settings,
    )

    # The caller's own account may not exist in the new profile (`empty`
    # seeds only admin), so fall back rather than 404 on a successful reseed.
    user = session.exec(
        select(User).where(
            User.username == requested_username, col(User.is_active).is_(True)
        )
    ).first()
    if user is None:
        user = session.exec(
            select(User).where(User.username == "admin", col(User.is_active).is_(True))
        ).first()
    if user is None:
        raise HTTPException(
            status_code=500,
            detail="Reseed completed but no active account is available to sign in as.",
        )

    return DevReseedResponse(
        **{
            field: getattr(result, field)
            for field in (
                "profile",
                "users",
                "cameras",
                "detections",
                "audit_rows",
                "health_samples",
                "export_jobs",
                "snapshots",
            )
        },
        session=_mint_session(request, response, session, user),
    )


@router.post("/login-as", response_model=DevLoginAsResponse)
def dev_login_as(
    body: DevLoginAsRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DevLoginAsResponse:
    """Any authenticated user, deliberately — DT-5. Unauthenticated this
    would be a complete auth bypass whenever the flag is on. You log in
    normally once; after that you can hop between seeded accounts."""
    target = session.exec(
        select(User).where(
            User.username == body.username, col(User.is_active).is_(True)
        )
    ).first()
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active user named '{body.username}'.",
        )

    # Revoke the session being switched away from, so the old cookie cannot
    # keep working alongside the new one.
    token = request.cookies.get(_app_settings(request).SESSION_COOKIE_NAME)
    if token:
        try:
            _, auth_session = authenticate_session_token(token, session)
            revoke_session(session, auth_session.session_id, "admin_revoke")
        except AppHTTPException:
            # get_current_user already authenticated this request, so this
            # is unreachable in practice; not worth failing the switch over.
            pass

    return DevLoginAsResponse(session=_mint_session(request, response, session, target))


@router.post("/detections", response_model=DetectionLog, status_code=201)
def dev_inject_detection(
    body: DevDetectionRequest,
    request: Request,
    _current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
    manager: RealtimeManager = Depends(get_realtime_manager),
) -> DetectionLog:
    """Runs the real ingest path (services/incidents.ingest_detection), so
    the self-blindfold pause, the WebSocket broadcasts and the siren all
    behave exactly as they do for a genuine detection — with no AI engine,
    no RTSP and no GPU."""
    app_settings = _app_settings(request)
    camera_id = body.camera_id
    if camera_id is None:
        camera_id = _pick_free_camera(session)

    detected_at = body.detected_at or datetime.now(UTC)
    source_event_id = str(uuid.uuid4())
    snapshot_key = f"{detected_at:%Y/%m/%d}/camera_{camera_id}/{source_event_id}.jpg"
    write_snapshot(snapshot_key, snapshot_root=app_settings.SNAPSHOT_ROOT)

    payload = DetectionLogCreateV2(
        camera_id=camera_id,
        detected_at=detected_at,
        snapshot_key=snapshot_key,
        confidence_score=body.confidence if body.confidence is not None else 0.87,
        source_event_id=source_event_id,
    )

    try:
        log, camera, created = ingest_detection(session, payload)
    except CameraUnavailableForIngest as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OpenIncidentConflict as exc:
        raise AppHTTPException(
            409,
            str(exc),
            code="CONFLICT_STATE",
            extra={
                "existing_log_id": exc.existing.log_id if exc.existing else None,
            },
        ) from exc

    if created:
        manager.broadcast(new_detection_event(log, camera_name=camera.camera_name))
        manager.broadcast(camera_status_update_event(camera))
    return log


def _pick_free_camera(session: Session) -> int:
    """A camera that can actually take a new incident: enabled, active, and
    without an open one (ux_detection_open_camera would 409 otherwise)."""
    busy = {
        row.camera_id
        for row in session.exec(
            select(DetectionLog).where(
                col(DetectionLog.detection_status).in_(_OPEN_STATUSES)
            )
        )
    }
    candidates = [
        camera
        for camera in session.exec(
            select(Camera).where(
                col(Camera.is_active).is_(True), col(Camera.is_enabled).is_(True)
            )
        )
        if camera.camera_id not in busy
    ]
    if not candidates:
        raise AppHTTPException(
            409,
            "Every enabled camera already has an open incident. Resolve or "
            "dismiss one first, or pass an explicit camera_id.",
            code="CONFLICT_STATE",
        )
    return random.choice(candidates).camera_id


@router.post("/cameras/{camera_id}/state", response_model=Camera)
def dev_set_camera_state(
    camera_id: int,
    body: DevCameraStateRequest,
    request: Request,
    _current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
    manager: RealtimeManager = Depends(get_realtime_manager),
) -> Camera:
    camera = session.get(Camera, camera_id)
    if camera is None or not camera.is_active:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found.")

    app_settings = _app_settings(request)
    now = datetime.now(UTC)

    if body.connection_status is not None or body.ai_status is not None:
        apply_observed(
            camera,
            ObservedReport(
                connection_status=(
                    body.connection_status.value
                    if body.connection_status
                    else camera.connection_status
                ),
                ai_status=(
                    body.ai_status.value if body.ai_status else camera.ai_status
                ),
                applied_config_version=camera.applied_config_version,
                measured_fps=camera.measured_fps,
                inference_latency_ms=camera.inference_latency_ms,
                error_code=camera.last_error_code,
                error_message=camera.last_error_message,
            ),
            now=now,
        )

    if body.stale_heartbeat is not None:
        # Well past the threshold rather than exactly on it, so the camera
        # stays Unresponsive while you look at it. `false` makes it fresh
        # again, which lasts HEARTBEAT_STALE_SECONDS (10s) — nothing is
        # heartbeating, so it necessarily goes stale again.
        camera.last_heartbeat_at = (
            now - timedelta(seconds=app_settings.HEARTBEAT_STALE_SECONDS + 60)
            if body.stale_heartbeat
            else now
        )
    if body.clear_cooldown:
        camera.cooldown_until = None

    session.add(camera)
    session.commit()
    session.refresh(camera)

    manager.broadcast(camera_status_update_event(camera))
    return camera


@router.post("/health-history", response_model=DevHealthHistoryResponse)
def dev_health_history(
    body: DevHealthHistoryRequest,
    _current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> DevHealthHistoryResponse:
    """Package A's generator. Its own idempotency guard bails if any
    sys_health_raw row already exists, so this is a no-op (0 rows) against a
    profile that already seeded history."""
    written = seed_health_history(session, days=body.days, now=datetime.now(UTC))
    return DevHealthHistoryResponse(rows_written=written)


@router.post("/uat/reset", response_model=DevUatResetResponse)
async def dev_uat_reset(
    body: DevUatResetRequest,
    request: Request,
    _current_user: User = Depends(get_current_admin),
    manager: RealtimeManager = Depends(get_realtime_manager),
    scheduler=Depends(get_scheduler),
) -> DevUatResetResponse:
    """Prepare the next UAT state without wiping participant audit evidence."""
    try:
        result = await reset_uat_session(
            request.app.state.engine,
            phase=body.phase,
            scheduler=scheduler,
            snapshot_root=_app_settings(request).SNAPSHOT_ROOT,
            manager=manager,
        )
    except UatProfileRequired as exc:
        raise AppHTTPException(409, str(exc), code="CONFLICT_STATE") from exc
    return DevUatResetResponse(**result.__dict__)
