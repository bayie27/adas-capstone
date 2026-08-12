"""10_PKG_migration_evidence.md Step 3 — fixtures for the measured
performance evidence suite.

Every test here runs against a real file-based SQLite database (WAL,
foreign_keys=ON, the same D-005 connection policy the running app uses),
seeded once per session with the NFR-08 100,000-row perf dataset, rather
than the fast in-memory `session`/`client` fixtures the rest of the suite
uses. That is the whole point: these numbers are only meaningful if the
database looks like the one the paper's performance claims are about.

Session-scoped and slow by construction (seeding alone takes ~30s — see
backend/app/dev/seed.py's own measured figure) — this whole package is
excluded from the default `pytest` run (see pyproject.toml's
`addopts = "-q -m 'not slow'"`) and only runs via
`uv run pytest -m slow backend/tests/perf/`.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.core.config import Settings
from app.core.db import create_db_engine, init_db
from app.dev import seed as perf_seed
from app.dev.profiles import SeedCameraSpec, build_default_cameras, build_default_users
from app.main import create_app
from app.models import AIStatus, ConnectionStatus, DetectionLog
from app.services.cameras import reconcile_camera_desired_states
from fastapi.testclient import TestClient
from sqlalchemy import insert
from sqlmodel import Session

PERF_ROW_COUNT = 100_000

# A6 (be_audit/A6_manual_evidence.md Part 2) — the real operating envelope
# is ~10 incidents/day (Lipa CDRRMO estimate), not the NFR-08 100k-row
# profile's ~182/day density. A 30-day export at that envelope is ~300
# rows; this is a separate, deliberately lower-density dataset, not a
# filtered slice of perf_seeded's dense one.
ENVELOPE_ROW_COUNT = 300
ENVELOPE_SPREAD_DAYS = 30


def _incident_free_cameras() -> list[SeedCameraSpec]:
    """Two cameras outside the default set, so they carry no seeded
    incident and a test can POST a genuinely new one."""
    return [
        SeedCameraSpec(
            key="perf_latency",
            camera_name="Perf Latency Cam",
            channel_id=201,
            connection_status=ConnectionStatus.CONNECTED,
            ai_status=AIStatus.ACTIVE,
        ),
        SeedCameraSpec(
            key="perf_isolation",
            camera_name="Perf Isolation Cam",
            channel_id=202,
            connection_status=ConnectionStatus.CONNECTED,
            ai_status=AIStatus.ACTIVE,
        ),
    ]


_PERF_DIR = Path(__file__).resolve().parent


def pytest_collection_modifyitems(config, items):
    """Auto-applies @pytest.mark.slow to every test collected under this
    directory. A bare `pytestmark` module attribute only marks tests in
    the file that defines it — it does not propagate to sibling test
    files the way this collection hook does, so this is the one place
    that needs to know backend/tests/perf/ is slow-by-default, not every
    test module under it."""
    for item in items:
        if _PERF_DIR in item.path.parents:
            item.add_marker(pytest.mark.slow)


def _build_perf_settings(db_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        SECRET_KEY="perf-test-secret-key-not-for-production-use",
        INTERNAL_API_KEY="perf-test-internal-api-key-not-for-production",
        DEFAULT_ADMIN_PASSWORD="perf-test-admin-password-123",
        DATABASE_URL=f"sqlite:///{db_path}",
        SCHEDULER_ENABLED=False,
    )


@pytest.fixture(scope="session")
def perf_settings(tmp_path_factory) -> Settings:
    db_dir = tmp_path_factory.mktemp("perf_db")
    return _build_perf_settings(db_dir / "adas_perf.db")


@pytest.fixture(scope="session")
def perf_engine(perf_settings):
    engine = create_db_engine(perf_settings)
    init_db(engine, perf_settings)  # alembic upgrade head + admin/help seed
    return engine


@pytest.fixture(scope="session")
def perf_seeded(perf_engine, perf_settings) -> dict:
    """Bulk-inserts the 100,000-row NFR-08 dataset, plus two cameras kept
    deliberately incident-free (unlike every perf-seeded camera, which
    ends up with exactly one open incident by construction — see
    app/dev/seed.py's _enforce_open_camera_limit) for the alert-latency
    and slow-client-isolation tests, which each need to POST a genuinely
    new incident without hitting ux_detection_open_camera's 409."""
    now = datetime.now(UTC)
    with Session(perf_engine) as session:
        operators = perf_seed.seed_users(session, build_default_users(), now=now)
        cameras = perf_seed.seed_cameras(session, build_default_cameras(), now=now)
        camera_ids = [c.camera_id for c in cameras.values()]
        operator_ids = [u.user_id for u in operators.values()]

        extra = perf_seed.seed_cameras(session, _incident_free_cameras(), now=now)
        latency_camera = extra["perf_latency"]
        isolation_camera = extra["perf_isolation"]

        rows = perf_seed._build_perf_rows(
            now=now,
            camera_ids=camera_ids,
            operator_ids=operator_ids,
            target_count=PERF_ROW_COUNT,
        )
        rows = perf_seed._enforce_open_camera_limit(rows, operator_ids=operator_ids)

        for batch_start in range(0, len(rows), perf_seed.PERF_BATCH_SIZE):
            batch = rows[batch_start : batch_start + perf_seed.PERF_BATCH_SIZE]
            session.execute(insert(DetectionLog), batch)
        session.commit()

        # Captured before the session closes below — session.commit()
        # expires every loaded ORM instance's attributes by default, and
        # accessing them again afterward (once the `with` block has closed
        # this session) raises DetachedInstanceError.
        latency_camera_id = latency_camera.camera_id
        isolation_camera_id = isolation_camera.camera_id

    reconcile_camera_desired_states(perf_engine)

    return {
        "now": now,
        "camera_ids": camera_ids,
        "operator_ids": operator_ids,
        "operators": operators,
        "latency_camera_id": latency_camera_id,
        "isolation_camera_id": isolation_camera_id,
    }


@pytest.fixture(scope="session")
def perf_client(perf_settings, perf_seeded):
    app = create_app(perf_settings)
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
def envelope_settings(tmp_path_factory) -> Settings:
    db_dir = tmp_path_factory.mktemp("envelope_db")
    return _build_perf_settings(db_dir / "adas_envelope.db")


@pytest.fixture(scope="session")
def envelope_engine(envelope_settings):
    engine = create_db_engine(envelope_settings)
    init_db(engine, envelope_settings)
    return engine


@pytest.fixture(scope="session")
def envelope_seeded(envelope_engine, envelope_settings) -> dict:
    """A dedicated, separately-seeded ~10-incidents/day dataset (own DB
    file, not a slice of `perf_seeded`) — see `ENVELOPE_ROW_COUNT`."""
    now = datetime.now(UTC)
    with Session(envelope_engine) as session:
        operators = perf_seed.seed_users(session, build_default_users(), now=now)
        cameras = perf_seed.seed_cameras(session, build_default_cameras(), now=now)
        camera_ids = [c.camera_id for c in cameras.values()]
        operator_ids = [u.user_id for u in operators.values()]

        rows = perf_seed._build_perf_rows(
            now=now,
            camera_ids=camera_ids,
            operator_ids=operator_ids,
            target_count=ENVELOPE_ROW_COUNT,
            spread_days=ENVELOPE_SPREAD_DAYS,
        )
        rows = perf_seed._enforce_open_camera_limit(rows, operator_ids=operator_ids)

        for batch_start in range(0, len(rows), perf_seed.PERF_BATCH_SIZE):
            batch = rows[batch_start : batch_start + perf_seed.PERF_BATCH_SIZE]
            session.execute(insert(DetectionLog), batch)
        session.commit()

    reconcile_camera_desired_states(envelope_engine)

    return {"now": now, "operators": operators}


@pytest.fixture(scope="session")
def envelope_client(envelope_settings, envelope_seeded):
    app = create_app(envelope_settings)
    with TestClient(app) as client:
        yield client


def internal_headers(_perf_settings: Settings) -> dict:
    """`_perf_settings` is intentionally unused: app.api.dependencies
    validates `x-api-key` against the process-global `app.core.config
    .settings` singleton, not the per-instance Settings a test builds
    (the same pre-existing pattern backend/tests/conftest.py's own
    `internal_headers()` and test_maintenance.py's route tests already
    work around — see that file's module docstring). Kept as a parameter
    for call-site symmetry with the rest of this module."""
    from app.core.config import settings as global_settings

    return {"x-api-key": global_settings.INTERNAL_API_KEY.get_secret_value()}


def operator_auth_headers(perf_client: TestClient, perf_seeded: dict) -> dict:
    username = next(iter(perf_seeded["operators"]))
    resp = perf_client.post(
        "/api/auth/login",
        data={"username": username, "password": "operator123"},
    )
    assert resp.status_code == 200, f"perf login failed: {resp.text}"
    cookie_name = "adas_session"
    cookie_value = resp.cookies.get(cookie_name)
    return {"Cookie": f"{cookie_name}={cookie_value}"}
