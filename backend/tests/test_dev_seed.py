"""dev_plan/01_PKG_seed_core.md Verification — the seed profiles in app.dev.

Unlike most of this suite these tests need a real file-based database:
seed_profile() calls init_db(), which runs `alembic upgrade head`, and the
constraint under test (ux_detection_open_camera) is a partial unique index
that only exists in the migrated schema — the in-memory `session` fixture's
create_all() has it too, but the seeders take an engine, not a session.

Everything is seeded once per module at a pinned `now`. Pinning matters
beyond ordinary determinism: several seeded timestamps are relative to it,
so which incident survives the open-camera enforcer is genuinely
time-of-day dependent (see the Step 4 commit), and a floating `now` would
make these assertions flaky a few minutes a day.
"""

from datetime import UTC, datetime

import pytest
from app.core.config import Settings
from app.core.db import create_db_engine
from app.dev import PROFILES, seed_perf_data, seed_profile
from app.models import (
    AUDIT_ACTIONS,
    AlarmSettings,
    AuditLog,
    Camera,
    DetectionLog,
    ExportJob,
    HelpArticle,
    SysHealthHourly,
    SysHealthRaw,
    User,
)
from app.services import snapshots
from app.services.cameras import presented_statuses
from sqlmodel import Session, select

PINNED_NOW = datetime(2026, 8, 11, 16, 30, tzinfo=UTC)

# perf's real target is 100,000 rows / ~33s. The invariant under test is a
# property of the generator, not of the row count, so it is exercised at a
# size that keeps this suite runnable.
PERF_SMOKE_COUNT = 200

OPEN_STATUSES = ("Unverified", "Ongoing")


def _settings_for(tmp_path, name: str) -> Settings:
    snapshot_root = tmp_path / name / "snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    return Settings(
        _env_file=None,
        SECRET_KEY="dev-seed-test-secret-key-not-for-production",
        INTERNAL_API_KEY="dev-seed-test-internal-api-key",
        DEFAULT_ADMIN_PASSWORD="dev-seed-test-admin-password-123",
        DATABASE_URL=f"sqlite:///{tmp_path / name / 'adas.db'}",
        SNAPSHOT_ROOT=snapshot_root,
        LEGACY_SNAPSHOT_DIR=snapshot_root,
        SCHEDULER_ENABLED=False,
    )


def _seed(tmp_path, name: str, *, now=PINNED_NOW):
    settings = _settings_for(tmp_path, name)
    engine = create_db_engine(settings)
    if PROFILES[name].bulk is not None:
        result = seed_perf_data(
            engine,
            target_count=PERF_SMOKE_COUNT,
            now=now,
            target_settings=settings,
        )
    else:
        result = seed_profile(
            engine,
            profile=name,
            now=now,
            target_settings=settings,
            snapshot_root=settings.SNAPSHOT_ROOT,
        )
    return engine, settings, result


@pytest.fixture(scope="module")
def seeded(tmp_path_factory) -> dict:
    """Every registered profile, each in its own migrated database."""
    root = tmp_path_factory.mktemp("dev_seed")
    return {name: _seed(root, name) for name in PROFILES}


# ---------------------------------------------------------------------------
# 1. Every profile satisfies ux_detection_open_camera
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("profile", list(PROFILES))
def test_profile_respects_one_open_incident_per_camera(seeded, profile):
    """Parametrised over the registry rather than a hand-written list, so a
    profile added later cannot quietly skip this. The index makes a second
    open row an IntegrityError, so a violation means the seed would have
    crashed against the real schema — these assertions catch a generator
    that got lucky on ordering."""
    engine, _, _ = seeded[profile]
    with Session(engine) as session:
        rows = session.exec(
            select(DetectionLog).where(DetectionLog.detection_status.in_(OPEN_STATUSES))
        ).all()

    per_camera: dict[int, int] = {}
    for row in rows:
        per_camera[row.camera_id] = per_camera.get(row.camera_id, 0) + 1

    offenders = {cam: n for cam, n in per_camera.items() if n > 1}
    assert not offenders, f"{profile} has cameras with >1 open incident: {offenders}"


# ---------------------------------------------------------------------------
# 2. empty
# ---------------------------------------------------------------------------


def test_empty_profile_seeds_nothing_but_keeps_help_articles(seeded):
    engine, _, result = seeded["empty"]
    with Session(engine) as session:
        cameras = session.exec(select(Camera)).all()
        detections = session.exec(select(DetectionLog)).all()
        users = session.exec(select(User)).all()
        audit = session.exec(select(AuditLog)).all()
        articles = session.exec(select(HelpArticle)).all()

    assert cameras == []
    assert detections == []
    assert audit == []
    # init_db()'s default admin survives; nothing else is created.
    assert [u.username for u in users] == ["admin"]
    # FR-20's help content is seeded by init_db(), not by a profile, so an
    # empty database is still a usable one.
    assert articles, "empty must not take the help articles with it"
    assert result.cameras == 0
    assert result.detections == 0
    assert result.snapshots == 0


# ---------------------------------------------------------------------------
# 3. demo covers the tables and states that were never seeded before
# ---------------------------------------------------------------------------


def test_demo_seeds_health_history(seeded):
    engine, _, _ = seeded["demo"]
    with Session(engine) as session:
        raw = session.exec(select(SysHealthRaw)).all()
        hourly = session.exec(select(SysHealthHourly)).all()

    assert raw, "sys_health_raw must not be empty — the System Health page reads it"
    assert hourly, "sys_health_hourly is what a multi-day view aggregates from"
    # The hourly rollups have to agree with the raw rows they summarise.
    assert sum(h.sample_count for h in hourly) == len(raw)
    assert all(0.0 <= h.avg_cpu_usage <= 100.0 for h in hourly)


def test_demo_seeds_every_export_job_status(seeded):
    engine, _, _ = seeded["demo"]
    with Session(engine) as session:
        jobs = session.exec(select(ExportJob)).all()

    assert {j.status for j in jobs} == {
        "queued",
        "processing",
        "completed",
        "failed",
        "expired",
    }
    completed = next(j for j in jobs if j.status == "completed")
    assert completed.artifact_path and completed.artifact_bytes
    failed = next(j for j in jobs if j.status == "failed")
    assert failed.failure_category
    expired = next(j for j in jobs if j.status == "expired")
    assert expired.expires_at < PINNED_NOW


def test_demo_covers_every_audit_action(seeded):
    engine, _, _ = seeded["demo"]
    with Session(engine) as session:
        rows = session.exec(select(AuditLog)).all()

    missing = set(AUDIT_ACTIONS) - {r.action for r in rows}
    assert not missing, f"audit actions never seeded: {sorted(missing)}"
    # The viewer filters on all three results and both actor types.
    assert {r.result for r in rows} == {"success", "denied", "failure"}
    assert {r.actor_type for r in rows} == {"user", "system"}


def test_demo_seeds_a_snoozed_detection(seeded):
    engine, _, _ = seeded["demo"]
    with Session(engine) as session:
        snoozed = session.exec(
            select(DetectionLog).where(DetectionLog.snoozed_until.is_not(None))
        ).all()

    assert len(snoozed) >= 1
    row = snoozed[0]
    assert row.snoozed_by_id is not None
    assert row.snoozed_at is not None
    assert row.snoozed_until > row.snoozed_at
    # Snoozing a closed incident would be nonsense.
    assert row.detection_status in OPEN_STATUSES


def test_demo_seeds_unresponsive_and_soft_deleted_cameras(seeded):
    engine, _, _ = seeded["demo"]
    with Session(engine) as session:
        cameras = session.exec(select(Camera)).all()

    soft_deleted = [c for c in cameras if not c.is_active]
    assert soft_deleted, "no soft-deleted camera to demo the is_active filter with"

    # Asserted at the pinned `now`, which is the only way this is stable:
    # HEARTBEAT_STALE_SECONDS is 10, so against a real clock every seeded
    # camera presents as Unresponsive shortly after seeding.
    presented = {
        c.camera_name: presented_statuses(c, now=PINNED_NOW)[0] for c in cameras
    }
    unresponsive = [
        name for name, status in presented.items() if name and status == "Unresponsive"
    ]
    assert len(unresponsive) == 1, f"expected exactly one, got {unresponsive}"

    # Telemetry is populated, not left NULL as it was for every profile.
    connected = [c for c in cameras if c.measured_fps is not None]
    assert connected
    assert any(c.last_error_code for c in cameras)


def test_demo_seeds_disabled_and_password_change_users(seeded):
    engine, _, _ = seeded["demo"]
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        alarms = session.exec(select(AlarmSettings)).all()

    assert [u for u in users if not u.is_active], "no disabled user to demo"
    assert [u for u in users if u.password_changed_at is None]
    assert len([u for u in users if u.role == "Admin"]) >= 2

    # Per-user alarm config was identical for everyone before.
    distinct = {(a.alarm_sound, a.volume, a.snooze_duration) for a in alarms}
    assert len(distinct) > 1


def test_edge_seeds_the_confidence_score_boundaries(seeded):
    engine, _, _ = seeded["edge"]
    with Session(engine) as session:
        scores = {d.confidence_score for d in session.exec(select(DetectionLog))}
        cooldowns = [
            c for c in session.exec(select(Camera)) if c.cooldown_until is not None
        ]

    # The column's declared bounds are ge=0.0, le=1.0.
    assert 0.0 in scores
    assert 1.0 in scores
    assert cooldowns


# ---------------------------------------------------------------------------
# 4. Snapshots resolve
# ---------------------------------------------------------------------------


def test_seeded_snapshots_resolve_to_a_real_file(seeded):
    """GET /api/alerts/{log_id}/snapshot 404'd for every seeded row before
    Step 6, because the seeder built keys but never wrote files."""
    engine, settings, result = seeded["demo"]
    with Session(engine) as session:
        keys = [d.snapshot_key for d in session.exec(select(DetectionLog))]

    assert keys
    resolved = [
        snapshots.resolve(
            key,
            snapshot_root=settings.SNAPSHOT_ROOT,
            legacy_dir=settings.LEGACY_SNAPSHOT_DIR,
        )
        for key in keys
    ]
    assert all(path is not None for path in resolved)
    assert result.snapshots == len(keys)

    # Existence is not enough: resolve() checks containment and is_file(),
    # not that the bytes are a decodable image, so a corrupt placeholder
    # would pass the check above while rendering as a broken image.
    for path in resolved:
        data = path.read_bytes()
        assert data.startswith(b"\xff\xd8"), f"{path} is not a JPEG"
        assert data.endswith(b"\xff\xd9"), f"{path} is a truncated JPEG"
        assert len(data) > 100


def test_profiles_that_opt_out_write_no_snapshots(seeded):
    for name, (_, settings, result) in seeded.items():
        if PROFILES[name].snapshots:
            continue
        assert result.snapshots == 0, f"{name} opted out but wrote snapshots"
        written = list(settings.SNAPSHOT_ROOT.rglob("*.jpg"))
        assert not written, f"{name} opted out but left files: {written}"


# ---------------------------------------------------------------------------
# 5 & 6. Idempotency and determinism
# ---------------------------------------------------------------------------


def test_reseeding_without_a_reset_is_idempotent(tmp_path):
    """ux_detection_source_event is unique, so a second run that minted
    fresh UUIDs would raise. What makes this work is _seed_source_event_id's
    uuid5-of-a-stable-label plus ensure_alert's existing-row short-circuit."""
    engine, settings, first = _seed(tmp_path, "demo")
    second = seed_profile(
        engine,
        profile="demo",
        now=PINNED_NOW,
        target_settings=settings,
        snapshot_root=settings.SNAPSHOT_ROOT,
    )

    assert second.detections == first.detections
    assert second.users == first.users
    assert second.cameras == first.cameras
    assert second.audit_rows == first.audit_rows
    assert second.export_jobs == first.export_jobs
    assert second.health_samples == first.health_samples
    # Every file was already on disk, so the second pass writes none.
    assert second.snapshots == 0


def test_same_now_produces_the_same_counts(tmp_path):
    _, _, first = _seed(tmp_path, "demo", now=PINNED_NOW)
    _, _, second = _seed(tmp_path / "again", "demo", now=PINNED_NOW)
    assert first == second


def test_a_different_now_still_satisfies_the_open_camera_index(tmp_path):
    """The enforcer's outcome is time-of-day dependent (Step 4), so the
    invariant is checked at an hour other than the pinned one — 08:17 is
    the window where demo's surviving incident differs."""
    engine, _, _ = _seed(tmp_path, "demo", now=datetime(2026, 8, 11, 8, 17, tzinfo=UTC))
    with Session(engine) as session:
        rows = session.exec(
            select(DetectionLog).where(DetectionLog.detection_status.in_(OPEN_STATUSES))
        ).all()

    per_camera: dict[int, int] = {}
    for row in rows:
        per_camera[row.camera_id] = per_camera.get(row.camera_id, 0) + 1
    assert all(n == 1 for n in per_camera.values())
