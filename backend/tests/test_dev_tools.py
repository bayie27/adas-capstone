"""dev_plan/02_PKG_dev_api.md Verification — the /api/dev/* routes.

These need a real file-based database with a real schema: the reseed runs
`alembic upgrade head` through init_db(), and the wipe drops and restores
the audit triggers, neither of which the in-memory `session` fixture's
create_all() world can exercise honestly.

SECRET_KEY is taken from the process-global settings on purpose. Session
validation (app/api/dependencies.py) reads that global rather than the
per-app Settings a test builds, so a test-only secret would mint cookies
that the very next request rejects — the trap conftest.py's
`internal_headers()` documents.
"""

import asyncio
from datetime import UTC, datetime

import pytest
from app.core.config import Settings
from app.core.config import settings as global_settings
from app.main import create_app
from app.models import AuditLog, Camera, DetectionLog, HelpArticle, User
from app.schemas.events import EventType
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import ArgumentError
from sqlmodel import Session, select

ADMIN_PASSWORD = "dev-tools-admin-password-123"


@pytest.fixture(name="dev_settings")
def dev_settings_fixture(tmp_path) -> Settings:
    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir()
    return Settings(
        _env_file=None,
        SECRET_KEY=global_settings.SECRET_KEY.get_secret_value(),
        INTERNAL_API_KEY="dev-tools-internal-api-key",
        DEFAULT_ADMIN_PASSWORD=ADMIN_PASSWORD,
        DATABASE_URL=f"sqlite:///{tmp_path / 'adas.db'}",
        SNAPSHOT_ROOT=snapshot_root,
        LEGACY_SNAPSHOT_DIR=snapshot_root,
        SCHEDULER_ENABLED=False,
        EXPORT_JOB_WORKERS=0,
        SESSION_COOKIE_SECURE=False,
        DEV_TOOLS_ENABLED=True,
    )


@pytest.fixture(name="dev_client")
def dev_client_fixture(dev_settings: Settings):
    """`base_url="https://testserver"` is required, not cosmetic.

    app/core/security.py reads the process-global `app.core.config.settings`
    singleton for the session cookie's Secure flag — not `dev_settings`
    above, whatever `SESSION_COOKIE_SECURE` says here — so the cookie this
    app issues is Secure whenever the *real* global settings is (its
    default, and true in production/the LAN demo, per the audit decision
    that the demo gets real TLS). Over a plain "http://testserver" base
    url, httpx's cookie jar correctly refuses to resend a Secure cookie on
    later requests, so every test past the first login would silently see
    no cookie and 401 AUTH_REQUIRED. This only surfaces when the local .env
    omits `SESSION_COOKIE_SECURE=false` — CI always has it, via
    `.env.example`, so this was invisible there."""
    app = create_app(dev_settings)
    with TestClient(app, base_url="https://testserver") as client:
        yield client


@pytest.fixture(name="captured_broadcasts")
def captured_broadcasts_fixture(dev_client: TestClient) -> list:
    events: list = []
    manager = dev_client.app.state.realtime_manager
    original = manager.broadcast

    def capture(event):
        events.append(event)
        return original(event)

    manager.broadcast = capture
    return events


def login(client: TestClient, username: str, password: str):
    return client.post(
        "/api/auth/login", data={"username": username, "password": password}
    )


def login_admin(client: TestClient) -> None:
    resp = login(client, "admin", ADMIN_PASSWORD)
    assert resp.status_code == 200, resp.text


def engine_of(client: TestClient):
    return client.app.state.engine


# ---------------------------------------------------------------------------
# 1 & 2. Gating and auth
# ---------------------------------------------------------------------------


def test_status_is_reachable_without_a_session(dev_client: TestClient):
    resp = dev_client.get("/api/dev/status")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


def test_unauthenticated_cannot_switch_accounts(dev_client: TestClient):
    """DT-5 — unauthenticated, login-as would be a complete auth bypass
    whenever the flag is on, which DT-3 explicitly permits in production."""
    resp = dev_client.post("/api/dev/login-as", json={"username": "admin"})
    assert resp.status_code == 401


def test_unauthenticated_cannot_reseed(dev_client: TestClient):
    resp = dev_client.post("/api/dev/reseed", json={"profile": "empty"})
    assert resp.status_code == 401


def test_operator_cannot_reseed(dev_client: TestClient):
    login_admin(dev_client)
    dev_client.post("/api/dev/reseed", json={"profile": "demo"})

    resp = login(dev_client, "dsahagun", "operator123")
    assert resp.status_code == 200, resp.text
    assert (
        dev_client.post("/api/dev/reseed", json={"profile": "empty"}).status_code == 403
    )
    assert dev_client.post("/api/dev/detections", json={}).status_code == 403
    assert (
        dev_client.post("/api/dev/health-history", json={"days": 1}).status_code == 403
    )


def test_an_unknown_profile_is_a_404(dev_client: TestClient):
    login_admin(dev_client)
    resp = dev_client.post("/api/dev/reseed", json={"profile": "nope"})
    assert resp.status_code == 404


def test_request_bodies_forbid_unknown_fields(dev_client: TestClient):
    login_admin(dev_client)
    resp = dev_client.post("/api/dev/reseed", json={"profile": "empty", "typo": True})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 3. Reseed round-trip
# ---------------------------------------------------------------------------


def test_reseed_returns_a_working_cookie_for_the_requested_user(
    dev_client: TestClient,
):
    """DT-2 — the reseed destroys the session it authenticated with, so it
    mints a new one rather than bouncing the operator to /login."""
    login_admin(dev_client)
    resp = dev_client.post(
        "/api/dev/reseed", json={"profile": "demo", "login_as": "dsahagun"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["detections"] == 18
    assert body["session"]["username"] == "dsahagun"
    assert body["session"]["role"] == "Operator"
    assert resp.cookies.get(global_settings.SESSION_COOKIE_NAME)

    # The returned cookie authenticates the very next request.
    me = dev_client.get("/api/users/me")
    assert me.status_code == 200, me.text
    assert me.json()["username"] == "dsahagun"


def test_reseed_falls_back_to_admin_when_the_caller_is_gone(
    dev_client: TestClient,
):
    """`empty` seeds only admin, so a reseed to it has nobody else to sign
    back in as. Driven from demo's *second* admin (rmanalo), since reseed is
    admin-gated and that account is one `empty` removes."""
    login_admin(dev_client)
    dev_client.post("/api/dev/reseed", json={"profile": "demo"})
    assert login(dev_client, "rmanalo", "admin123").status_code == 200

    resp = dev_client.post(
        "/api/dev/reseed", json={"profile": "empty", "login_as": "rmanalo"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["session"]["username"] == "admin"


def test_the_server_keeps_running_and_the_schema_survives(dev_client: TestClient):
    login_admin(dev_client)
    dev_client.post("/api/dev/reseed", json={"profile": "analytics"})
    # Same process, same app, no restart — an ordinary route still works.
    assert dev_client.get("/").status_code == 200
    with Session(engine_of(dev_client)) as ses:
        tables = {
            row[0]
            for row in ses.exec(
                text("select name from sqlite_master where type='table'")
            )
        }
    assert "alembic_version" in tables
    assert {"camera", "detection_log", "audit_log"} <= tables


# ---------------------------------------------------------------------------
# 4. The regression that matters most
# ---------------------------------------------------------------------------


def test_audit_log_is_still_append_only_after_a_reseed(dev_client: TestClient):
    """The wipe has to drop audit_log's BEFORE UPDATE/DELETE triggers to
    empty it, and put them back. An earlier implementation put them back
    inside the same transaction as the deletes, so a failure left the table
    permanently mutable — NFR-21 gone, silently."""
    login_admin(dev_client)
    assert (
        dev_client.post("/api/dev/reseed", json={"profile": "demo"}).status_code == 200
    )

    with Session(engine_of(dev_client)) as ses:
        for statement in (
            "DELETE FROM audit_log",
            "UPDATE audit_log SET result='denied'",
        ):
            with pytest.raises(Exception, match="append-only"):
                ses.exec(text(statement))
                ses.commit()
            ses.rollback()


def test_the_triggers_survive_a_wipe_that_fails_halfway(dev_settings: Settings):
    """Directly against the wipe, because a failure injected through the
    route would be rolled back by FastAPI's error handling first."""
    import app.dev.wipe as wipe
    from app.core.db import create_db_engine
    from app.dev import seed_profile

    engine = create_db_engine(dev_settings)
    seed_profile(
        engine,
        profile="demo",
        now=datetime(2026, 8, 11, 16, 30, tzinfo=UTC),
        target_settings=dev_settings,
        snapshot_root=dev_settings.SNAPSHOT_ROOT,
    )

    original = wipe._DELETE_ORDER
    # audit_log first, so its triggers are genuinely dropped at the moment
    # the wipe blows up.
    wipe._DELETE_ORDER = (("audit_log", AuditLog), ("boom", object()))
    try:
        with pytest.raises(ArgumentError):
            wipe.wipe_operational_data(engine, snapshot_root=dev_settings.SNAPSHOT_ROOT)
    finally:
        wipe._DELETE_ORDER = original

    with Session(engine) as ses:
        # The deletes rolled back, so the rows are still there...
        assert ses.exec(select(AuditLog)).first() is not None
        # ...and the table is still immutable.
        with pytest.raises(Exception, match="append-only"):
            ses.exec(text("DELETE FROM audit_log"))
            ses.commit()
        ses.rollback()


# ---------------------------------------------------------------------------
# 5. empty really is empty
# ---------------------------------------------------------------------------


def test_empty_profile_leaves_no_rows_and_no_snapshot_files(
    dev_client: TestClient, dev_settings: Settings
):
    login_admin(dev_client)
    dev_client.post("/api/dev/reseed", json={"profile": "demo"})
    assert list(dev_settings.SNAPSHOT_ROOT.rglob("*.jpg"))

    resp = dev_client.post("/api/dev/reseed", json={"profile": "empty"})
    assert resp.status_code == 200, resp.text

    with Session(engine_of(dev_client)) as ses:
        assert ses.exec(select(Camera)).all() == []
        assert ses.exec(select(DetectionLog)).all() == []
        assert [u.username for u in ses.exec(select(User))] == ["admin"]
        # init_db() owns these and re-derives them idempotently.
        assert ses.exec(select(HelpArticle)).first() is not None

    assert not list(dev_settings.SNAPSHOT_ROOT.rglob("*.jpg"))


# ---------------------------------------------------------------------------
# 6 & 7. The injector runs the real ingest path
# ---------------------------------------------------------------------------


def test_injection_pauses_the_camera_and_broadcasts(
    dev_client: TestClient, captured_broadcasts: list
):
    """With no AI engine, no RTSP and no GPU: the self-blindfold pause and
    both broadcasts have to happen, or the panel demos a path that is not
    the production one."""
    login_admin(dev_client)
    dev_client.post("/api/dev/reseed", json={"profile": "empty"})
    captured_broadcasts.clear()

    # `empty` has no cameras, so create one through the real route.
    created = dev_client.post(
        "/api/cameras/", json={"camera_name": "Inject Cam", "channel_id": 42}
    )
    assert created.status_code == 201, created.text
    camera_id = created.json()["camera_id"]
    captured_broadcasts.clear()

    resp = dev_client.post("/api/dev/detections", json={"camera_id": camera_id})
    assert resp.status_code == 201, resp.text
    assert resp.json()["detection_status"] == "Unverified"

    types = [event.type for event in captured_broadcasts]
    assert EventType.NEW_DETECTION in types
    assert EventType.CAMERA_STATUS_UPDATE in types

    with Session(engine_of(dev_client)) as ses:
        camera = ses.get(Camera, camera_id)
    assert camera.desired_ai_state == "Paused"
    assert camera.desired_state_reason == "incident"


def test_a_second_injection_on_the_same_camera_conflicts(dev_client: TestClient):
    """ux_detection_open_camera still holds — the injector does not get a
    private exemption from it."""
    login_admin(dev_client)
    dev_client.post("/api/dev/reseed", json={"profile": "empty"})
    created = dev_client.post(
        "/api/cameras/", json={"camera_name": "Conflict Cam", "channel_id": 43}
    )
    camera_id = created.json()["camera_id"]

    assert (
        dev_client.post(
            "/api/dev/detections", json={"camera_id": camera_id}
        ).status_code
        == 201
    )
    second = dev_client.post("/api/dev/detections", json={"camera_id": camera_id})
    assert second.status_code == 409
    assert second.json()["code"] == "CONFLICT_STATE"


def test_injection_without_a_camera_id_picks_a_free_one(dev_client: TestClient):
    login_admin(dev_client)
    dev_client.post("/api/dev/reseed", json={"profile": "demo"})
    # demo leaves some cameras open and some free; either a 201 on a free
    # camera or a clean 409 when none are left is correct, never a 500.
    resp = dev_client.post("/api/dev/detections", json={})
    assert resp.status_code in (201, 409), resp.text
    if resp.status_code == 409:
        assert resp.json()["code"] == "CONFLICT_STATE"


def test_injected_snapshot_is_retrievable(
    dev_client: TestClient, dev_settings: Settings, monkeypatch
):
    """The global settings are patched here because GET
    /api/alerts/{log_id}/snapshot resolves against the process-global
    `settings.SNAPSHOT_ROOT`, not `app.state.settings` — a pre-existing
    inconsistency in routes/alerts.py, harmless in production where the two
    are the same object, but it means an app built with an isolated
    SNAPSHOT_ROOT cannot serve the snapshots it just wrote."""
    monkeypatch.setattr(global_settings, "SNAPSHOT_ROOT", dev_settings.SNAPSHOT_ROOT)
    monkeypatch.setattr(
        global_settings, "LEGACY_SNAPSHOT_DIR", dev_settings.LEGACY_SNAPSHOT_DIR
    )
    login_admin(dev_client)
    dev_client.post("/api/dev/reseed", json={"profile": "empty"})
    created = dev_client.post(
        "/api/cameras/", json={"camera_name": "Snapshot Cam", "channel_id": 44}
    )
    log_id = dev_client.post(
        "/api/dev/detections", json={"camera_id": created.json()["camera_id"]}
    ).json()["log_id"]

    resp = dev_client.get(f"/api/alerts/{log_id}/snapshot")
    assert resp.status_code == 200, resp.text
    assert resp.content.startswith(b"\xff\xd8")


# ---------------------------------------------------------------------------
# Camera state and health history
# ---------------------------------------------------------------------------


def test_stale_heartbeat_makes_a_camera_present_as_unresponsive(
    dev_client: TestClient,
):
    login_admin(dev_client)
    dev_client.post("/api/dev/reseed", json={"profile": "empty"})
    camera_id = dev_client.post(
        "/api/cameras/", json={"camera_name": "Stale Cam", "channel_id": 45}
    ).json()["camera_id"]

    resp = dev_client.post(
        f"/api/dev/cameras/{camera_id}/state", json={"stale_heartbeat": True}
    )
    assert resp.status_code == 200, resp.text

    listing = dev_client.get("/api/cameras/")
    assert listing.status_code == 200
    row = next(c for c in listing.json()["cameras"] if c["camera_id"] == camera_id)
    # Derived by presented_statuses() from the backdated heartbeat — the
    # value is never stored on the row.
    assert row["connection_status"] == "Unresponsive"


def test_camera_state_404s_for_an_unknown_camera(dev_client: TestClient):
    login_admin(dev_client)
    resp = dev_client.post(
        "/api/dev/cameras/999999/state", json={"clear_cooldown": True}
    )
    assert resp.status_code == 404


def test_health_history_writes_rows_and_is_idempotent(dev_client: TestClient):
    login_admin(dev_client)
    dev_client.post("/api/dev/reseed", json={"profile": "empty"})

    first = dev_client.post("/api/dev/health-history", json={"days": 2})
    assert first.status_code == 200, first.text
    assert first.json()["rows_written"] > 0
    # The generator's own guard bails when history already exists.
    second = dev_client.post("/api/dev/health-history", json={"days": 2})
    assert second.json()["rows_written"] == 0


# ---------------------------------------------------------------------------
# 8 & 9. Concurrency and the scheduler
# ---------------------------------------------------------------------------


def test_two_reseeds_do_not_interleave(dev_settings: Settings):
    import app.dev.service as service
    from app.core.db import create_db_engine

    engine = create_db_engine(dev_settings)
    order: list[str] = []
    real = service._wipe_and_seed

    def tracking(*args, **kwargs):
        order.append("enter")
        result = real(*args, **kwargs)
        order.append("exit")
        return result

    service._wipe_and_seed = tracking
    try:

        async def run_both():
            await asyncio.gather(
                service.reseed(
                    engine,
                    profile="empty",
                    scheduler=None,
                    snapshot_root=dev_settings.SNAPSHOT_ROOT,
                    target_settings=dev_settings,
                ),
                service.reseed(
                    engine,
                    profile="edge",
                    scheduler=None,
                    snapshot_root=dev_settings.SNAPSHOT_ROOT,
                    target_settings=dev_settings,
                ),
            )

        asyncio.run(run_both())
    finally:
        service._wipe_and_seed = real

    assert order == ["enter", "exit", "enter", "exit"]


def test_the_scheduler_is_resumed_even_when_the_seed_raises(
    dev_settings: Settings,
):
    import app.dev.service as service
    from app.core.db import create_db_engine

    class FakeScheduler:
        def __init__(self):
            self.paused = 0
            self.resumed = 0

        def pause(self):
            self.paused += 1

        def resume(self):
            self.resumed += 1

    scheduler = FakeScheduler()
    engine = create_db_engine(dev_settings)
    real = service._wipe_and_seed

    def boom(*args, **kwargs):
        raise RuntimeError("seed exploded")

    service._wipe_and_seed = boom
    try:
        with pytest.raises(RuntimeError, match="seed exploded"):
            asyncio.run(
                service.reseed(
                    engine,
                    profile="demo",
                    scheduler=scheduler,
                    snapshot_root=dev_settings.SNAPSHOT_ROOT,
                    target_settings=dev_settings,
                )
            )
    finally:
        service._wipe_and_seed = real

    assert scheduler.paused == 1
    assert scheduler.resumed == 1
    # A leaked lock would deadlock every later reseed in the process.
    assert not service._reseed_lock.locked()
