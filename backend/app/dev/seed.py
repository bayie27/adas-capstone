"""Seed writers and orchestration.

Moved here from `backend/scripts/seed_dev_data.py` (dev_plan/01_PKG_seed_core.md
Step 1). The CLI entrypoints in `backend/scripts/` are now thin wrappers over
this module, and Package B calls the same functions from a live request.

Imports flow one way: this module imports from `app.dev.profiles`, never the
reverse.
"""

from __future__ import annotations

import random
import time
import uuid
from collections import Counter
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy import insert as sa_insert
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.db import init_db
from app.core.security import get_password_hash
from app.dev.profiles import (
    _OPEN_STATUSES,
    DEFAULT_SEED_PROFILE,
    PERF_BATCH_SIZE,
    PERF_PROFILE,
    PERF_SPREAD_DAYS,
    PERF_TARGET_INCIDENT_COUNT,
    PROFILES,
    SeedAlertSpec,
    SeedAuditSpec,
    SeedCameraSpec,
    SeedUserSpec,
    build_default_cameras,
    build_default_users,
    get_profile,
    seeded_timestamp,
)
from app.models import (
    AlarmSettings,
    AuditLog,
    Camera,
    DetectionLog,
    DetectionStatus,
    ExportJob,
    SysHealthHourly,
    SysHealthRaw,
    User,
)
from app.services.cameras import reconcile_camera_desired_states


@dataclass(frozen=True)
class SeedResult:
    """Per-table row counts after a seed run. Package B returns this from
    POST /api/dev/reseed and Package C renders it, so the counts are what
    the database actually holds afterwards rather than what this run
    happened to insert — after a wipe those are the same number, and on a
    re-seed against an existing database the former is the useful one."""

    profile: str
    users: int
    cameras: int
    detections: int
    audit_rows: int
    health_samples: int
    export_jobs: int
    snapshots: int


def _collect_result(
    session: Session, *, profile: str, snapshots: int = 0
) -> SeedResult:
    def count(model) -> int:
        return session.exec(select(func.count()).select_from(model)).one()

    return SeedResult(
        profile=profile,
        users=count(User),
        cameras=count(Camera),
        detections=count(DetectionLog),
        audit_rows=count(AuditLog),
        health_samples=count(SysHealthRaw) + count(SysHealthHourly),
        export_jobs=count(ExportJob),
        snapshots=snapshots,
    )


# Deterministic per-run UUIDs (uuid5 of a stable label) so re-seeding a
# non-reset database stays idempotent — a fresh uuid4() every run would
# defeat ensure_alert()'s existing-row lookup and violate
# ux_detection_source_event on the second run.
_SEED_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "adas-capstone-seed-data")


def _seed_source_event_id(label: str) -> str:
    return str(uuid.uuid5(_SEED_NAMESPACE, label))


def ensure_user(session: Session, spec: SeedUserSpec, *, now: datetime) -> User:
    user = session.exec(select(User).where(User.username == spec.username)).first()
    if user:
        return user

    user = User(
        username=spec.username,
        first_name=spec.first_name,
        last_name=spec.last_name,
        role=spec.role,
        password_hash=get_password_hash(spec.password),
        is_active=spec.is_active,
        password_changed_at=now if spec.password_changed else None,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    alarm = AlarmSettings(user_id=user.user_id)
    if spec.alarm_sound is not None:
        alarm.alarm_sound = spec.alarm_sound
    if spec.alarm_volume is not None:
        alarm.volume = spec.alarm_volume
    if spec.alarm_snooze_duration is not None:
        alarm.snooze_duration = spec.alarm_snooze_duration
    session.add(alarm)
    session.commit()

    print(f"Created user {spec.username}")
    return user


def ensure_camera(session: Session, spec: SeedCameraSpec, *, now: datetime) -> Camera:
    camera = session.exec(
        select(Camera).where(Camera.camera_name == spec.camera_name)
    ).first()
    if camera:
        return camera

    camera = Camera(
        camera_name=spec.camera_name,
        channel_id=spec.channel_id,
        connection_status=spec.connection_status.value,
        ai_status=spec.ai_status.value,
        is_enabled=spec.is_enabled,
        is_active=spec.is_active,
        measured_fps=spec.measured_fps,
        inference_latency_ms=spec.inference_latency_ms,
        last_error_code=spec.last_error_code,
        last_error_message=spec.last_error_message,
        applied_config_version=spec.applied_config_version,
    )
    if spec.last_heartbeat_minutes_ago is not None:
        camera.last_heartbeat_at = now - timedelta(
            minutes=spec.last_heartbeat_minutes_ago
        )
    if spec.cooldown_minutes_from_now is not None:
        camera.cooldown_until = now + timedelta(minutes=spec.cooldown_minutes_from_now)
    session.add(camera)
    session.commit()
    session.refresh(camera)
    print(f"Created camera {spec.camera_name}")
    return camera


def seed_cameras(
    session: Session, specs: list[SeedCameraSpec], *, now: datetime
) -> dict[str, Camera]:
    """Keyed off SeedCameraSpec.key, which is what the alert specs refer
    to. The old version returned a fixed 6-tuple that the caller
    destructured into a hard-coded dict, so a profile could not vary its
    cameras at all."""
    return {spec.key: ensure_camera(session, spec, now=now) for spec in specs}


def seed_users(
    session: Session, specs: list[SeedUserSpec], *, now: datetime
) -> dict[str, User]:
    return {spec.key: ensure_user(session, spec, now=now) for spec in specs}


def ensure_alert(
    session: Session,
    *,
    label: str,
    camera_id: int,
    snapshot_key: str,
    detected_at: datetime,
    confidence_score: float,
    detection_status: DetectionStatus,
    verified_by_id: int | None = None,
    verified_at: datetime | None = None,
    closed_by_id: int | None = None,
    closed_at: datetime | None = None,
) -> DetectionLog:
    source_event_id = _seed_source_event_id(label)
    alert = session.exec(
        select(DetectionLog).where(DetectionLog.source_event_id == source_event_id)
    ).first()
    if alert:
        return alert

    alert = DetectionLog(
        camera_id=camera_id,
        source_event_id=source_event_id,
        snapshot_key=snapshot_key,
        detected_at=detected_at,
        confidence_score=confidence_score,
        detection_status=detection_status.value,
        verified_by_id=verified_by_id,
        verified_at=verified_at,
        closed_by_id=closed_by_id,
        closed_at=closed_at,
    )
    session.add(alert)
    session.commit()
    session.refresh(alert)
    print(f"Created alert {label}")
    return alert


def seed_sample_cameras(session: Session) -> list[Camera]:
    """Compat wrapper for backend/tests/perf/conftest.py, which reuses the
    default camera set. Step 7 repoints that conftest at seed_cameras()
    and this goes away."""
    return list(
        seed_cameras(session, build_default_cameras(), now=datetime.now(UTC)).values()
    )


def _enforce_one_open_incident_per_camera(
    specs: list[SeedAlertSpec],
) -> list[SeedAlertSpec]:
    """ux_detection_open_camera allows at most one Unverified/Ongoing row
    per camera. The hand-written specs above don't know about that
    constraint (some cameras get two), so demote every extra open spec —
    in list order, keeping the first one seen per camera — to Resolved.

    A demoted spec always ends up with a verifier and closer even if the
    original (often Unverified, with neither) didn't have one — a Resolved
    row with no verified_by/closed_by would be a nonsensical seed record.
    """
    seen_open_cameras: set[str] = set()
    normalized: list[SeedAlertSpec] = []

    for spec in specs:
        if spec.detection_status in _OPEN_STATUSES:
            if spec.camera_key in seen_open_cameras:
                verified_by_key = spec.verified_by_key or "dsahagun"
                verified_after_minutes = spec.verified_after_minutes or 5
                closed_by_key = spec.closed_by_key or verified_by_key
                closed_after_minutes = spec.closed_after_minutes or (
                    verified_after_minutes + 15
                )
                spec = replace(
                    spec,
                    detection_status=DetectionStatus.RESOLVED,
                    verified_by_key=verified_by_key,
                    verified_after_minutes=verified_after_minutes,
                    closed_by_key=closed_by_key,
                    closed_after_minutes=closed_after_minutes,
                )
            else:
                seen_open_cameras.add(spec.camera_key)
        normalized.append(spec)

    return normalized


def _seed_audit_log_rows(
    session: Session,
    *,
    specs: list[SeedAuditSpec],
    users_by_key: dict[str, User],
    now: datetime,
) -> int:
    """Representative audit_log rows so the audit viewer has something to
    page through. Real audit *writing* happens through
    app/services/audit.py; these are seeded directly rather than by
    exercising that path.

    The bail-if-any-row-exists guard is the idempotency contract — audit_log
    carries BEFORE UPDATE/DELETE triggers, so a partial re-seed could not be
    corrected afterwards.
    """
    if session.exec(select(AuditLog).limit(1)).first():
        return 0

    rows: list[AuditLog] = []
    for spec in specs:
        actor = users_by_key.get(spec.actor_key) if spec.actor_key else None
        target_ref = spec.target_ref
        if target_ref is None and spec.target_ref_key is not None:
            target = users_by_key.get(spec.target_ref_key)
            target_ref = str(target.user_id) if target else None

        rows.append(
            AuditLog(
                actor_type=spec.actor_type,
                user_id=actor.user_id if actor else None,
                username=spec.username or (actor.username if actor else None),
                role=actor.role if actor else None,
                action=spec.action,
                target_type=spec.target_type,
                target_ref=target_ref,
                result=spec.result,
                detail=spec.detail,
                created_at=seeded_timestamp(now, minutes_ago=spec.minutes_ago),
            )
        )

    for row in rows:
        session.add(row)
    session.commit()
    print(f"Seeded {len(rows)} audit_log row(s).")
    return len(rows)


def ensure_default_operators(session: Session) -> dict[str, User]:
    """Compat wrapper for backend/tests/perf/conftest.py. Step 7 repoints
    that conftest at seed_users()."""
    return seed_users(session, build_default_users(), now=datetime.now(UTC))


def seed_profile(
    engine: Engine,
    *,
    profile: str = DEFAULT_SEED_PROFILE,
    now: datetime | None = None,
    target_settings: Settings | None = None,
) -> SeedResult:
    """`engine` is explicit because create_app() binds a different engine per
    Settings instance to app.state.engine, and Package B seeds from inside a
    request handler using that one — not app.core.db's module global.

    `target_settings` must be the Settings that `engine` was built from
    whenever that is not the process-global singleton. init_db() ->
    check_schema_revision() reopens `target_settings.DATABASE_URL` itself
    through backend/alembic/env.py and ignores the engine argument
    entirely, so passing an isolated engine without its Settings migrates
    the wrong database — the trap recorded as F18 in be_audit/00_FINDINGS.md.
    Defaults to the process-global, which is what the CLI wants.

    `now` is injectable so tests get determinism instead of whatever
    datetime.now(UTC) returns mid-run."""
    profile_def = get_profile(profile)
    now = now if now is not None else datetime.now(UTC)

    # perf writes 100,000 rows through a bulk path that has nothing in
    # common with the spec path below. Registering it on the profile is
    # what removes the duplicated `if profile == PERF_PROFILE` branch that
    # used to live in both CLI entrypoints.
    if profile_def.bulk is not None:
        return profile_def.bulk(engine, now=now, target_settings=target_settings)

    init_db(engine, target_settings)

    with Session(engine) as session:
        admin = session.exec(select(User).where(User.username == "admin")).first()
        if not admin:
            raise RuntimeError("Expected default admin to exist after init_db().")

        operators = seed_users(session, profile_def.users(), now=now)
        users_by_key = {"admin": admin, **operators}
        cameras = seed_cameras(session, profile_def.cameras(), now=now)

        alert_specs = _enforce_one_open_incident_per_camera(profile_def.alerts(now))

        def make_snapshot(cam_id: int, dt: datetime, source_event_id: str) -> str:
            # 01_CONTRACTS.md §7.1 nested key format, not a flat filename.
            return f"{dt:%Y/%m/%d}/camera_{cam_id}/{source_event_id}.jpg"

        status_counts: Counter[str] = Counter()
        camera_counts: Counter[str] = Counter()
        verifier_counts: Counter[str] = Counter()
        closer_counts: Counter[str] = Counter()

        for spec in alert_specs:
            try:
                camera = cameras[spec.camera_key]
            except KeyError as exc:
                raise RuntimeError(
                    f"Unknown camera key in seed spec: {spec.camera_key}"
                ) from exc

            if camera.camera_id is None:
                raise RuntimeError(
                    f"Camera {camera.camera_name} was expected to have a database ID."
                )

            verified_by = (
                operators.get(spec.verified_by_key) if spec.verified_by_key else None
            )
            closed_by = (
                operators.get(spec.closed_by_key) if spec.closed_by_key else None
            )

            if spec.verified_after_minutes is not None and verified_by is None:
                raise RuntimeError(
                    f"Alert {spec.label} has a verification offset but no verifier."
                )
            if spec.closed_after_minutes is not None and closed_by is None:
                raise RuntimeError(
                    f"Alert {spec.label} has a closure offset but no closer."
                )

            source_event_id = _seed_source_event_id(spec.label)
            ensure_alert(
                session,
                label=spec.label,
                camera_id=camera.camera_id,
                snapshot_key=make_snapshot(
                    camera.camera_id, spec.detected_at, source_event_id
                ),
                detected_at=spec.detected_at,
                confidence_score=spec.confidence_score,
                detection_status=spec.detection_status,
                verified_by_id=verified_by.user_id if verified_by else None,
                verified_at=(
                    spec.detected_at + timedelta(minutes=spec.verified_after_minutes)
                    if spec.verified_after_minutes is not None
                    else None
                ),
                closed_by_id=closed_by.user_id if closed_by else None,
                closed_at=(
                    spec.detected_at + timedelta(minutes=spec.closed_after_minutes)
                    if spec.closed_after_minutes is not None
                    else None
                ),
            )
            status_counts[spec.detection_status.value] += 1
            camera_counts[camera.camera_name] += 1
            if verified_by:
                verifier_counts[verified_by.username] += 1
            if closed_by:
                closer_counts[closed_by.username] += 1

        _seed_audit_log_rows(
            session,
            specs=profile_def.audit(now),
            users_by_key=users_by_key,
            now=now,
        )

        print(f"Dev data seeding complete for profile '{profile}'.")
        print(f"Total alerts seeded: {len(alert_specs)}")
        print("Seeded alert mix:")
        for status in DetectionStatus:
            print(f"  {status.value}: {status_counts.get(status.value, 0)}")
        print("Alerts by camera:")
        for camera_name, count in sorted(
            camera_counts.items(),
            key=lambda item: (-item[1], item[0].lower()),
        ):
            print(f"  {camera_name}: {count}")
        print("Verified by operator:")
        if verifier_counts:
            for username, count in sorted(
                verifier_counts.items(),
                key=lambda item: (-item[1], item[0].lower()),
            ):
                print(f"  {username}: {count}")
        else:
            print("  (none)")
        print("Closed by operator:")
        if closer_counts:
            for username, count in sorted(
                closer_counts.items(),
                key=lambda item: (-item[1], item[0].lower()),
            ):
                print(f"  {username}: {count}")
        else:
            print("  (none)")
        print("Users:")
        print("  admin / DEFAULT_ADMIN_PASSWORD from .env")
        print("  dsahagun / operator123")
        print("  ealonzo / operator123")
        print("  smeer / operator123")
        print("  jtenorio / operator123")

        result = _collect_result(session, profile=profile)

    # Derive desired_ai_state/reason/cooldown_until from the incidents just
    # seeded (D-003) — a camera with a seeded open incident must come out
    # Paused/'incident', or it would contradict ux_detection_open_camera.
    reconcile_camera_desired_states(engine)

    return result


# ---------------------------------------------------------------------------
# perf profile — 10_PKG_migration_evidence.md Step 2
#
# The 100,000-row NFR-08 performance dataset. Deliberately *not* built on
# ensure_alert()'s one-row-at-a-time ORM pattern (a SELECT existence check
# plus an individual commit per row) — that path is fine for ~20-200 hand
# written specs, but would take unreasonably long at 100,000 rows. This
# builds plain dict rows and bulk-inserts them in batches via SQLAlchemy
# Core (`session.execute(insert(DetectionLog), batch)`), which is a single
# executemany per batch rather than 100,000 individual INSERT statements.
# ---------------------------------------------------------------------------

# Snapshot files are not generated for perf rows — a handful of reused
# fake keys exercise the missing-snapshot-file path (§7.1 "resolution
# order" / the 404 branch of GET /api/alerts/{log_id}/snapshot), which is
# realistic anyway: no perf dataset should carry 100,000 real JPEGs.
_PERF_SNAPSHOT_POOL = [
    "2025/03/14/camera_1/perf-sample-a.jpg",
    "2025/07/02/camera_2/perf-sample-b.jpg",
    "2025/11/20/camera_3/perf-sample-c.jpg",
    "2026/01/09/camera_4/perf-sample-d.jpg",
    "2026/04/18/camera_5/perf-sample-e.jpg",
]


def _perf_pick_status(rng: random.Random) -> DetectionStatus:
    """Roughly 60% Resolved / 25% Dismissed / 14% (candidate) Ongoing / 1%
    (candidate) Unverified, per the package doc. The Ongoing/Unverified
    shares are only *candidates* — ux_detection_open_camera allows at most
    one open incident per camera, so _enforce_open_camera_limit below
    demotes every extra candidate to Resolved, same as the hand-written
    demo/analytics/edge profiles already do via
    _enforce_one_open_incident_per_camera."""
    roll = rng.random()
    if roll < 0.61:
        return DetectionStatus.RESOLVED
    if roll < 0.86:
        return DetectionStatus.DISMISSED
    if roll < 0.99:
        return DetectionStatus.ONGOING
    return DetectionStatus.UNVERIFIED


def _build_perf_rows(
    *,
    now: datetime,
    camera_ids: list[int],
    operator_ids: list[int],
    target_count: int,
    seed: int = 20260810,
    spread_days: int = PERF_SPREAD_DAYS,
) -> list[dict]:
    """Deterministic (fixed `seed`) so re-running the perf profile against
    an already-seeded database is reproducible, matching the rest of this
    script's idempotency conventions. `spread_days` defaults to the
    NFR-08 100,000-row profile's ~18-month span; A6 passes a tighter
    30-day window to build the ~10-incidents/day operating-envelope
    dataset at its own (much lower) density instead."""
    rng = random.Random(seed)
    rows: list[dict] = []

    for i in range(target_count):
        camera_id = camera_ids[i % len(camera_ids)]
        days_ago = rng.uniform(0, spread_days)
        detected_at = (now - timedelta(days=days_ago)).replace(microsecond=0)
        status = _perf_pick_status(rng)
        confidence_score = round(rng.uniform(0.35, 0.99), 4)
        snapshot_key = _PERF_SNAPSHOT_POOL[i % len(_PERF_SNAPSHOT_POOL)]

        verified_by_id: int | None = None
        verified_at: datetime | None = None
        closed_by_id: int | None = None
        closed_at: datetime | None = None

        if status in (DetectionStatus.RESOLVED, DetectionStatus.ONGOING):
            # Confirm: verified_by/verified_at set, closed fields empty
            # (10.1 in 01_CONTRACTS.md).
            verified_by_id = operator_ids[i % len(operator_ids)]
            verified_at = detected_at + timedelta(minutes=rng.randint(1, 8))
        if status == DetectionStatus.RESOLVED:
            # Resolve: closed_by/closed_at added, verifier retained.
            closed_by_id = operator_ids[(i + 1) % len(operator_ids)]
            closed_at = verified_at + timedelta(minutes=rng.randint(5, 60))
        elif status == DetectionStatus.DISMISSED:
            if rng.random() < 0.2:
                # Correction (Ongoing -> Dismissed): original verifier
                # retained, correcting actor recorded as closer.
                verified_by_id = operator_ids[i % len(operator_ids)]
                verified_at = detected_at + timedelta(minutes=rng.randint(1, 8))
                closed_by_id = operator_ids[(i + 1) % len(operator_ids)]
                closed_at = verified_at + timedelta(minutes=rng.randint(2, 20))
            else:
                # Immediate dismiss: verified_by/verified_at set, closed
                # fields stay empty (01_CONTRACTS.md §10.1).
                verified_by_id = operator_ids[i % len(operator_ids)]
                verified_at = detected_at + timedelta(minutes=rng.randint(1, 5))

        rows.append(
            {
                "camera_id": camera_id,
                "source_event_id": _seed_source_event_id(f"perf_{i}"),
                "detected_at": detected_at,
                "snapshot_key": snapshot_key,
                "confidence_score": confidence_score,
                "detection_status": status.value,
                "verified_by_id": verified_by_id,
                "verified_at": verified_at,
                "closed_by_id": closed_by_id,
                "closed_at": closed_at,
                "created_at": detected_at,
                "updated_at": closed_at or verified_at or detected_at,
            }
        )

    return rows


def _enforce_open_camera_limit(
    rows: list[dict], *, operator_ids: list[int]
) -> list[dict]:
    """Bulk-row equivalent of _enforce_one_open_incident_per_camera:
    ux_detection_open_camera is a real partial-unique index (at most one
    Unverified/Ongoing row per camera_id), not merely a convention the
    generator needs to respect voluntarily. Keeps the most recently
    detected open row per camera and demotes every earlier one to
    Resolved with a synthesized verifier/closer."""
    open_by_camera: dict[int, list[dict]] = {}
    for row in rows:
        if row["detection_status"] in (
            DetectionStatus.UNVERIFIED.value,
            DetectionStatus.ONGOING.value,
        ):
            open_by_camera.setdefault(row["camera_id"], []).append(row)

    for camera_rows in open_by_camera.values():
        camera_rows.sort(key=lambda r: r["detected_at"], reverse=True)
        for row in camera_rows[1:]:
            detected_at = row["detected_at"]
            verified_by_id = row["verified_by_id"] or operator_ids[0]
            verified_at = row["verified_at"] or detected_at + timedelta(minutes=4)
            closed_by_id = row["closed_by_id"] or verified_by_id
            closed_at = verified_at + timedelta(minutes=20)
            row.update(
                detection_status=DetectionStatus.RESOLVED.value,
                verified_by_id=verified_by_id,
                verified_at=verified_at,
                closed_by_id=closed_by_id,
                closed_at=closed_at,
                updated_at=closed_at,
            )

    return rows


def seed_perf_data(
    engine: Engine,
    *,
    target_count: int = PERF_TARGET_INCIDENT_COUNT,
    now: datetime | None = None,
    target_settings: Settings | None = None,
) -> SeedResult:
    init_db(engine, target_settings)
    now = now if now is not None else datetime.now(UTC)

    with Session(engine) as session:
        admin = session.exec(select(User).where(User.username == "admin")).first()
        if not admin:
            raise RuntimeError("Expected default admin to exist after init_db().")

        operators = seed_users(session, build_default_users(), now=now)
        cameras = seed_cameras(session, build_default_cameras(), now=now).values()
        camera_ids = [c.camera_id for c in cameras]
        if any(cid is None for cid in camera_ids):
            raise RuntimeError("Cameras must be persisted before perf seeding.")
        operator_ids = [u.user_id for u in operators.values()]

        existing_count = session.exec(
            select(func.count()).select_from(DetectionLog)
        ).one()
        if existing_count >= target_count:
            print(
                f"detection_log already has {existing_count} rows "
                f"(>= target {target_count}); skipping bulk insert."
            )
            result = _collect_result(session, profile=PERF_PROFILE)
            reconcile_camera_desired_states(engine)
            return result

        print(f"Generating {target_count} detection_log rows...")
        rows = _build_perf_rows(
            now=now,
            camera_ids=camera_ids,
            operator_ids=operator_ids,
            target_count=target_count,
        )
        rows = _enforce_open_camera_limit(rows, operator_ids=operator_ids)

        print(f"Bulk-inserting {len(rows)} rows in batches of {PERF_BATCH_SIZE}...")
        started_at = time.perf_counter()
        for batch_start in range(0, len(rows), PERF_BATCH_SIZE):
            batch = rows[batch_start : batch_start + PERF_BATCH_SIZE]
            session.execute(sa_insert(DetectionLog), batch)
        session.commit()
        elapsed = time.perf_counter() - started_at

        print(
            f"Perf profile: inserted {len(rows)} rows in {elapsed:.2f}s "
            f"({len(rows) / elapsed:.0f} rows/sec)."
        )

        result = _collect_result(session, profile=PERF_PROFILE)

    # Derive desired_ai_state/reason/cooldown_until from the incidents just
    # seeded (D-003), same as every other profile.
    reconcile_camera_desired_states(engine)

    return result


# Late binding: the registry declares that `perf` is written by a bulk
# path, but the writer lives here with the other writers because
# profiles.py must not import this module.
PROFILES[PERF_PROFILE] = replace(PROFILES[PERF_PROFILE], bulk=seed_perf_data)
