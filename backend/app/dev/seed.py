"""Seed writers and orchestration.

Moved here from `backend/scripts/seed_dev_data.py` (dev_plan/01_PKG_seed_core.md
Step 1). The CLI entrypoints in `backend/scripts/` are now thin wrappers over
this module, and Package B calls the same functions from a live request.

Imports flow one way: this module imports from `app.dev.profiles`, never the
reverse.
"""

from __future__ import annotations

import math
import random
import time
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy import insert as sa_insert
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.core.config import Settings, settings
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
    snoozed_by_id: int | None = None,
    snoozed_at: datetime | None = None,
    snoozed_until: datetime | None = None,
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
        snoozed_by_id=snoozed_by_id,
        snoozed_at=snoozed_at,
        snoozed_until=snoozed_until,
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


# The single source of truth for the rule. ux_detection_open_camera is a
# partial unique index (at most one Unverified/Ongoing row per camera_id),
# so this is not a convention a generator may respect voluntarily — an
# extra open row is an IntegrityError, not a cosmetic problem.
#
# Most-recent-wins: the open incident a camera actually has is its latest
# one. Both call sites used to enforce this differently — the spec path
# kept the *first* open spec in list order, the perf path kept the most
# recently detected — and they synthesized different closure metadata on
# the rows they demoted.
_DEMOTED_VERIFY_MINUTES = 4
_DEMOTED_CLOSE_MINUTES = 20


def _keep_latest_open_per_camera[T](
    items: list[T],
    *,
    is_open: Callable[[T], bool],
    camera_of: Callable[[T], object],
    detected_at_of: Callable[[T], datetime],
) -> set[int]:
    """Returns the identities of the open items to demote, keeping the most
    recently detected one per camera.

    Ties break toward earlier list position: the collected order is the
    input order and `sorted` is stable, which is what the perf path's
    in-place sort already did.
    """
    open_by_camera: dict[object, list[T]] = {}
    for item in items:
        if is_open(item):
            open_by_camera.setdefault(camera_of(item), []).append(item)

    demote: set[int] = set()
    for camera_items in open_by_camera.values():
        ranked = sorted(camera_items, key=detected_at_of, reverse=True)
        demote.update(id(item) for item in ranked[1:])
    return demote


def _enforce_one_open_incident_per_camera(
    specs: list[SeedAlertSpec],
) -> list[SeedAlertSpec]:
    """Spec-path adapter over _keep_latest_open_per_camera.

    A demoted spec always ends up with a verifier and closer even if the
    original (often Unverified, with neither) didn't have one — a Resolved
    row with no verified_by/closed_by would be a nonsensical seed record.
    """
    demote = _keep_latest_open_per_camera(
        specs,
        is_open=lambda spec: spec.detection_status in _OPEN_STATUSES,
        camera_of=lambda spec: spec.camera_key,
        detected_at_of=lambda spec: spec.detected_at,
    )

    normalized: list[SeedAlertSpec] = []
    for spec in specs:
        if id(spec) in demote:
            verified_by_key = spec.verified_by_key or "dsahagun"
            verified_after_minutes = (
                spec.verified_after_minutes or _DEMOTED_VERIFY_MINUTES
            )
            spec = replace(
                spec,
                detection_status=DetectionStatus.RESOLVED,
                verified_by_key=verified_by_key,
                verified_after_minutes=verified_after_minutes,
                closed_by_key=spec.closed_by_key or verified_by_key,
                closed_after_minutes=verified_after_minutes + _DEMOTED_CLOSE_MINUTES,
            )
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
    if not specs or session.exec(select(AuditLog).limit(1)).first():
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


def _clamp_percent(value: float) -> float:
    """Every percentage column carries a 0-100 CHECK constraint."""
    return round(min(100.0, max(0.0, value)), 2)


def seed_health_history(
    session: Session, *, days: int, now: datetime, seed: int = 20260811
) -> int:
    """sys_health_raw at HEALTH_PERSIST_SECONDS resolution plus the hourly
    rollups derived from it. Both tables were never seeded, so the System
    Health page had no history to draw at all.

    The curve is a daily cycle with a periodic afternoon spike rather than
    uniform noise, because the point is for a chart to be legible. Raw rows
    older than HEALTH_RAW_RETENTION_HOURS (48h) are written deliberately —
    a seed is allowed to exceed the retention window, and the hourly table
    is what a 30-day view reads from anyway.
    """
    if days <= 0:
        return 0
    if session.exec(select(SysHealthRaw).limit(1)).first():
        return 0

    rng = random.Random(seed)
    step = timedelta(seconds=settings.HEALTH_PERSIST_SECONDS)
    start = (now - timedelta(days=days)).replace(minute=0, second=0, microsecond=0)

    raw_rows: list[dict] = []
    by_hour: dict[datetime, list[dict]] = {}

    sample_at = start
    while sample_at < now:
        # Peaks mid-afternoon, troughs pre-dawn.
        phase = ((sample_at.hour * 60 + sample_at.minute) / 1440.0 - 0.25) * 2 * math.pi
        wave = math.sin(phase)
        spike = 22.0 if (sample_at.hour == 14 and sample_at.day % 3 == 0) else 0.0

        row = {
            "cpu_usage": _clamp_percent(38 + 18 * wave + spike + rng.uniform(-3, 3)),
            "ram_usage": _clamp_percent(52 + 11 * wave + rng.uniform(-2, 2)),
            "gpu_usage_avg": _clamp_percent(
                44 + 26 * wave + spike + rng.uniform(-4, 4)
            ),
            "gpu_temp_max": _clamp_percent(52 + 14 * wave + rng.uniform(-2, 2)),
            "cpu_temp": None,  # null on Windows, which is the demo platform
            "gpu_mem_pct_max": _clamp_percent(48 + 17 * wave + rng.uniform(-3, 3)),
            "created_at": sample_at,
        }
        raw_rows.append(row)
        by_hour.setdefault(sample_at.replace(minute=0), []).append(row)
        sample_at += step

    def _avg(rows: list[dict], key: str) -> float | None:
        values = [r[key] for r in rows if r[key] is not None]
        return round(sum(values) / len(values), 2) if values else None

    def _peak(rows: list[dict], key: str) -> float | None:
        values = [r[key] for r in rows if r[key] is not None]
        return max(values) if values else None

    hourly_rows = [
        {
            "hour_start": hour_start,
            "sample_count": len(rows),
            "avg_cpu_usage": _avg(rows, "cpu_usage"),
            "avg_ram_usage": _avg(rows, "ram_usage"),
            "avg_gpu_usage": _avg(rows, "gpu_usage_avg"),
            "avg_cpu_temp": _avg(rows, "cpu_temp"),
            "peak_cpu_temp": _peak(rows, "cpu_temp"),
            "peak_gpu_temp": _peak(rows, "gpu_temp_max"),
            "avg_gpu_mem_pct": _avg(rows, "gpu_mem_pct_max"),
            "peak_gpu_mem_pct": _peak(rows, "gpu_mem_pct_max"),
        }
        for hour_start, rows in sorted(by_hour.items())
    ]

    for batch_start in range(0, len(raw_rows), PERF_BATCH_SIZE):
        session.execute(
            sa_insert(SysHealthRaw),
            raw_rows[batch_start : batch_start + PERF_BATCH_SIZE],
        )
    session.execute(sa_insert(SysHealthHourly), hourly_rows)
    session.commit()

    print(
        f"Seeded {len(raw_rows)} sys_health_raw and {len(hourly_rows)} "
        f"sys_health_hourly row(s) over {days} day(s)."
    )
    return len(raw_rows) + len(hourly_rows)


# One row per export_job status, spanning several report_type/format
# combinations. No artifact file is written — artifact_path points where a
# real one would live, which is enough for the Exports page to render and
# for a download attempt to fail the way a swept artifact does.
_EXPORT_JOB_SPECS = (
    ("incidents", "csv", "queued", None, None),
    ("dashboard", "pdf", "processing", None, None),
    ("performance", "csv", "completed", "performance-2026-08.csv", 184_320),
    ("audit", "pdf", "failed", None, None),
    ("retraining", "zip", "expired", "retraining-2026-07.zip", 4_915_200),
)


def seed_export_jobs(session: Session, *, requested_by: User, now: datetime) -> int:
    if session.exec(select(ExportJob).limit(1)).first():
        return 0

    rows: list[ExportJob] = []
    for index, (report_type, fmt, status, artifact, size) in enumerate(
        _EXPORT_JOB_SPECS
    ):
        created_at = now - timedelta(hours=index * 6 + 1)
        rows.append(
            ExportJob(
                job_id=_seed_source_event_id(f"export_{report_type}_{status}"),
                requested_by_id=requested_by.user_id,
                report_type=report_type,
                format=fmt,
                filters_json='{"start_date": null, "end_date": null}',
                status=status,
                progress_current=100 if status in ("completed", "expired") else 0,
                progress_total=100,
                artifact_path=artifact,
                artifact_bytes=size,
                failure_category="render_error" if status == "failed" else None,
                created_at=created_at,
                started_at=created_at + timedelta(seconds=2)
                if status != "queued"
                else None,
                completed_at=created_at + timedelta(seconds=45)
                if status in ("completed", "failed", "expired")
                else None,
                # Deliberately in the past, so the expired row really is.
                expires_at=now - timedelta(hours=3) if status == "expired" else None,
            )
        )

    for row in rows:
        session.add(row)
    session.commit()
    print(f"Seeded {len(rows)} export_job row(s).")
    return len(rows)


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

            # A snooze only means anything on an incident that is still
            # open, and the enforcer above may have demoted this one.
            snoozed_by = (
                users_by_key.get(spec.snoozed_by_key) if spec.snoozed_by_key else None
            )
            snoozed_at = snoozed_until = None
            if snoozed_by is not None and spec.detection_status in _OPEN_STATUSES:
                snoozed_at = spec.detected_at + timedelta(
                    minutes=spec.snoozed_after_minutes or 0
                )
                snoozed_until = snoozed_at + timedelta(
                    minutes=spec.snooze_minutes or 30
                )
            else:
                snoozed_by = None

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
                snoozed_by_id=snoozed_by.user_id if snoozed_by else None,
                snoozed_at=snoozed_at,
                snoozed_until=snoozed_until,
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
        seed_health_history(session, days=profile_def.health_days, now=now)
        if profile_def.exports:
            seed_export_jobs(session, requested_by=admin, now=now)

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
    """Bulk-row adapter over _keep_latest_open_per_camera. Mutates in
    place, as the bulk-insert path expects."""
    open_values = (DetectionStatus.UNVERIFIED.value, DetectionStatus.ONGOING.value)
    demote = _keep_latest_open_per_camera(
        rows,
        is_open=lambda row: row["detection_status"] in open_values,
        camera_of=lambda row: row["camera_id"],
        detected_at_of=lambda row: row["detected_at"],
    )

    for row in rows:
        if id(row) not in demote:
            continue
        detected_at = row["detected_at"]
        verified_by_id = row["verified_by_id"] or operator_ids[0]
        verified_at = row["verified_at"] or detected_at + timedelta(
            minutes=_DEMOTED_VERIFY_MINUTES
        )
        closed_at = verified_at + timedelta(minutes=_DEMOTED_CLOSE_MINUTES)
        row.update(
            detection_status=DetectionStatus.RESOLVED.value,
            verified_by_id=verified_by_id,
            verified_at=verified_at,
            closed_by_id=row["closed_by_id"] or verified_by_id,
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
