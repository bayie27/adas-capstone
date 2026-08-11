"""Seed-profile definitions: the spec dataclasses and the per-profile
builders that turn a `now` into a list of rows to write.

Moved here from `backend/scripts/seed_dev_data.py` (dev_plan/01_PKG_seed_core.md
Step 1) so the app can import them — `backend/scripts/` is not a package and
is only reachable through `_bootstrap.py`'s sys.path injection, which works
for a CLI entrypoint and nothing else.

This module holds no database access. `seed.py` imports from here; nothing
here imports from `seed.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.models import AIStatus, ConnectionStatus, DetectionStatus, UserRole

DEFAULT_SEED_PROFILE = "demo"
PERF_PROFILE = "perf"

# 10_PKG_migration_evidence.md Step 2 — NFR-08's 100,000-incident dataset.
PERF_TARGET_INCIDENT_COUNT = 100_000
PERF_SPREAD_DAYS = 548  # ~18 months
PERF_BATCH_SIZE = 2000

_OPEN_STATUSES = (DetectionStatus.UNVERIFIED, DetectionStatus.ONGOING)


@dataclass(frozen=True)
class SeedAlertSpec:
    label: str
    camera_key: str
    detected_at: datetime
    confidence_score: float
    detection_status: DetectionStatus
    verified_by_key: str | None = None
    verified_after_minutes: int | None = None
    closed_by_key: str | None = None
    closed_after_minutes: int | None = None
    snoozed_by_key: str | None = None
    snoozed_after_minutes: int | None = None
    snooze_minutes: int | None = None


@dataclass(frozen=True)
class SeedCameraSpec:
    """`key` is what SeedAlertSpec.camera_key refers to. It stays stable
    across profiles even when the camera list varies, because the alert
    specs are written against it."""

    key: str
    camera_name: str
    channel_id: int
    connection_status: ConnectionStatus
    ai_status: AIStatus
    is_enabled: bool = True
    is_active: bool = True

    # Observed telemetry (D-003, AI-owned columns). `Unresponsive` is not
    # settable here on purpose: presented_statuses() derives it from a
    # stale heartbeat and never writes it to the row, so a camera that
    # should present as Unresponsive gets a backdated
    # last_heartbeat_minutes_ago instead of a fake stored status.
    last_heartbeat_minutes_ago: int | None = None
    measured_fps: float | None = None
    inference_latency_ms: float | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    applied_config_version: int | None = None
    cooldown_minutes_from_now: int | None = None


@dataclass(frozen=True)
class SeedUserSpec:
    key: str
    username: str
    first_name: str
    last_name: str
    role: UserRole
    password: str
    is_active: bool = True
    # False leaves password_changed_at NULL, which is what the frontend
    # reads as "must change password on first login".
    password_changed: bool = True
    alarm_sound: str | None = None
    alarm_volume: int | None = None
    alarm_snooze_duration: int | None = None


@dataclass(frozen=True)
class SeedAuditSpec:
    """`actor_key` and `target_ref_key` are resolved against the seeded
    users at write time; `username` overrides the actor's own name for
    rows that record an actor who never existed (a failed login)."""

    action: str
    result: str
    minutes_ago: int
    actor_type: str = "user"
    actor_key: str | None = None
    username: str | None = None
    target_type: str | None = None
    target_ref_key: str | None = None
    target_ref: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class SeedProfile:
    name: str
    description: str  # shown in the dev panel
    cameras: Callable[[], list[SeedCameraSpec]]
    users: Callable[[], list[SeedUserSpec]]
    alerts: Callable[[datetime], list[SeedAlertSpec]]
    audit: Callable[[datetime], list[SeedAuditSpec]]
    health_days: int = 0
    exports: bool = False
    snapshots: bool = True
    # perf's bulk path. Declared here so the registry is the single place
    # that says how a profile is written, but bound in app.dev.seed — the
    # writer lives with the other writers, and profiles.py must not import
    # seed.py (the dependency runs one way).
    bulk: Callable[..., None] | None = field(default=None, compare=False)


def seeded_timestamp(
    now: datetime,
    *,
    days_ago: int = 0,
    hour: int | None = None,
    minute: int = 0,
    minutes_ago: int | None = None,
) -> datetime:
    """Create stable dev timestamps without accidentally seeding future rows."""
    if minutes_ago is not None:
        return (now - timedelta(minutes=minutes_ago)).replace(second=0, microsecond=0)

    if hour is None:
        raise ValueError("`hour` is required when `minutes_ago` is not provided.")

    candidate = (now - timedelta(days=days_ago)).replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )
    if candidate > now:
        candidate -= timedelta(days=1)
    return candidate


def build_demo_alert_specs(now: datetime) -> list[SeedAlertSpec]:
    return [
        SeedAlertSpec(
            label="ayala_recent_unverified",
            camera_key="ayala",
            detected_at=seeded_timestamp(now, minutes_ago=12),
            confidence_score=0.97,
            detection_status=DetectionStatus.UNVERIFIED,
        ),
        SeedAlertSpec(
            label="ayala_ongoing_morning",
            camera_key="ayala",
            detected_at=seeded_timestamp(now, days_ago=0, hour=8, minute=12),
            confidence_score=0.93,
            detection_status=DetectionStatus.ONGOING,
            verified_by_key="dsahagun",
            verified_after_minutes=3,
        ),
        SeedAlertSpec(
            label="ayala_resolved_evening",
            camera_key="ayala",
            detected_at=seeded_timestamp(now, days_ago=1, hour=19, minute=40),
            confidence_score=0.95,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="ealonzo",
            verified_after_minutes=4,
            closed_by_key="jtenorio",
            closed_after_minutes=28,
        ),
        SeedAlertSpec(
            label="ayala_resolved_weekend",
            camera_key="ayala",
            detected_at=seeded_timestamp(now, days_ago=7, hour=10, minute=30),
            confidence_score=0.89,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="smeer",
            verified_after_minutes=5,
            closed_by_key="ealonzo",
            closed_after_minutes=14,
        ),
        SeedAlertSpec(
            label="southbound_recent_unverified",
            camera_key="southbound",
            detected_at=seeded_timestamp(now, minutes_ago=33),
            confidence_score=0.79,
            detection_status=DetectionStatus.UNVERIFIED,
        ),
        SeedAlertSpec(
            label="southbound_resolved_peak",
            camera_key="southbound",
            detected_at=seeded_timestamp(now, days_ago=0, hour=14, minute=5),
            confidence_score=0.88,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="ealonzo",
            verified_after_minutes=5,
            closed_by_key="ealonzo",
            closed_after_minutes=18,
        ),
        SeedAlertSpec(
            label="southbound_dismissed_false_positive",
            camera_key="southbound",
            detected_at=seeded_timestamp(now, days_ago=2, hour=11, minute=35),
            confidence_score=0.41,
            detection_status=DetectionStatus.DISMISSED,
            closed_by_key="smeer",
            closed_after_minutes=7,
        ),
        SeedAlertSpec(
            label="north_exit_dismissed_human_correction",
            camera_key="north_exit",
            detected_at=seeded_timestamp(now, days_ago=3, hour=6, minute=50),
            confidence_score=0.73,
            detection_status=DetectionStatus.DISMISSED,
            verified_by_key="smeer",
            verified_after_minutes=2,
            closed_by_key="dsahagun",
            closed_after_minutes=10,
        ),
        SeedAlertSpec(
            label="inosluban_ongoing_evening",
            camera_key="inosluban",
            detected_at=seeded_timestamp(now, days_ago=0, hour=17, minute=20),
            confidence_score=0.90,
            detection_status=DetectionStatus.ONGOING,
            verified_by_key="jtenorio",
            verified_after_minutes=6,
        ),
        SeedAlertSpec(
            label="inosluban_resolved_crossover",
            camera_key="inosluban",
            detected_at=seeded_timestamp(now, days_ago=4, hour=9, minute=10),
            confidence_score=0.86,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="dsahagun",
            verified_after_minutes=3,
            closed_by_key="jtenorio",
            closed_after_minutes=25,
        ),
        SeedAlertSpec(
            label="inosluban_dismissed_false_positive",
            camera_key="inosluban",
            detected_at=seeded_timestamp(now, days_ago=1, hour=7, minute=45),
            confidence_score=0.38,
            detection_status=DetectionStatus.DISMISSED,
            closed_by_key="dsahagun",
            closed_after_minutes=6,
        ),
        SeedAlertSpec(
            label="tambo_recent_unverified",
            camera_key="tambo",
            detected_at=seeded_timestamp(now, minutes_ago=5),
            confidence_score=0.82,
            detection_status=DetectionStatus.UNVERIFIED,
        ),
        SeedAlertSpec(
            label="tambo_ongoing_midday",
            camera_key="tambo",
            detected_at=seeded_timestamp(now, days_ago=3, hour=12, minute=5),
            confidence_score=0.91,
            detection_status=DetectionStatus.ONGOING,
            verified_by_key="smeer",
            verified_after_minutes=3,
        ),
        SeedAlertSpec(
            label="tambo_resolved_longtail",
            camera_key="tambo",
            detected_at=seeded_timestamp(now, days_ago=6, hour=20, minute=25),
            confidence_score=0.84,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="jtenorio",
            verified_after_minutes=5,
            closed_by_key="ealonzo",
            closed_after_minutes=40,
        ),
        SeedAlertSpec(
            label="tambo_dismissed_false_positive",
            camera_key="tambo",
            detected_at=seeded_timestamp(now, days_ago=2, hour=15, minute=55),
            confidence_score=0.52,
            detection_status=DetectionStatus.DISMISSED,
            closed_by_key="ealonzo",
            closed_after_minutes=8,
        ),
        SeedAlertSpec(
            label="dagatan_ongoing_pre_dawn",
            camera_key="dagatan",
            detected_at=seeded_timestamp(now, days_ago=0, hour=5, minute=55),
            confidence_score=0.92,
            detection_status=DetectionStatus.ONGOING,
            verified_by_key="ealonzo",
            verified_after_minutes=4,
        ),
        SeedAlertSpec(
            label="dagatan_resolved_night",
            camera_key="dagatan",
            detected_at=seeded_timestamp(now, days_ago=1, hour=22, minute=10),
            confidence_score=0.94,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="jtenorio",
            verified_after_minutes=3,
            closed_by_key="jtenorio",
            closed_after_minutes=45,
        ),
        SeedAlertSpec(
            label="dagatan_dismissed_human_correction",
            camera_key="dagatan",
            detected_at=seeded_timestamp(now, days_ago=5, hour=13, minute=15),
            confidence_score=0.68,
            detection_status=DetectionStatus.DISMISSED,
            verified_by_key="dsahagun",
            verified_after_minutes=2,
            closed_by_key="smeer",
            closed_after_minutes=20,
        ),
    ]


def build_analytics_alert_specs(now: datetime) -> list[SeedAlertSpec]:
    specs = list(build_demo_alert_specs(now))
    operator_keys = ["dsahagun", "ealonzo", "smeer", "jtenorio"]

    for day in range(14):
        verifier = operator_keys[day % len(operator_keys)]
        closer = operator_keys[(day + 1) % len(operator_keys)]
        correction_verifier = operator_keys[(day + 2) % len(operator_keys)]
        correction_closer = operator_keys[(day + 3) % len(operator_keys)]

        specs.append(
            SeedAlertSpec(
                label=f"analytics_ayala_resolved_day_{day + 1}",
                camera_key="ayala",
                detected_at=seeded_timestamp(
                    now,
                    days_ago=day,
                    hour=8,
                    minute=10 + (day % 3) * 7,
                ),
                confidence_score=0.96 - (day % 5) * 0.02,
                detection_status=DetectionStatus.RESOLVED,
                verified_by_key=verifier,
                verified_after_minutes=3 + (day % 3),
                closed_by_key=closer,
                closed_after_minutes=18 + (day % 4) * 6,
            )
        )
        specs.append(
            SeedAlertSpec(
                label=f"analytics_inosluban_dismissed_day_{day + 1}",
                camera_key="inosluban",
                detected_at=seeded_timestamp(
                    now,
                    days_ago=day,
                    hour=17,
                    minute=5 + (day % 4) * 6,
                ),
                confidence_score=0.57 - (day % 4) * 0.04,
                detection_status=DetectionStatus.DISMISSED,
                verified_by_key=correction_verifier if day % 2 == 0 else None,
                verified_after_minutes=2 if day % 2 == 0 else None,
                closed_by_key=correction_closer,
                closed_after_minutes=9 + (day % 3) * 4,
            )
        )

        if day % 2 == 0:
            specs.append(
                SeedAlertSpec(
                    label=f"analytics_tambo_ongoing_day_{day + 1}",
                    camera_key="tambo",
                    detected_at=seeded_timestamp(
                        now,
                        days_ago=day,
                        hour=12,
                        minute=20 + (day % 2) * 10,
                    ),
                    confidence_score=0.90 - (day % 3) * 0.02,
                    detection_status=DetectionStatus.ONGOING,
                    verified_by_key=operator_keys[(day + 1) % len(operator_keys)],
                    verified_after_minutes=4,
                )
            )

        if day % 3 == 0:
            specs.append(
                SeedAlertSpec(
                    label=f"analytics_dagatan_resolved_day_{day + 1}",
                    camera_key="dagatan",
                    detected_at=seeded_timestamp(
                        now,
                        days_ago=day,
                        hour=5,
                        minute=40 + (day % 3) * 5,
                    ),
                    confidence_score=0.93 - (day % 4) * 0.01,
                    detection_status=DetectionStatus.RESOLVED,
                    verified_by_key=operator_keys[(day + 2) % len(operator_keys)],
                    verified_after_minutes=3,
                    closed_by_key=operator_keys[(day + 2) % len(operator_keys)],
                    closed_after_minutes=26,
                )
            )

        if day % 4 == 0:
            specs.append(
                SeedAlertSpec(
                    label=f"analytics_southbound_unverified_day_{day + 1}",
                    camera_key="southbound",
                    detected_at=seeded_timestamp(
                        now,
                        days_ago=day,
                        hour=21,
                        minute=15 + (day % 2) * 10,
                    ),
                    confidence_score=0.74 - (day % 3) * 0.03,
                    detection_status=DetectionStatus.UNVERIFIED,
                )
            )

    return specs


def build_edge_alert_specs(now: datetime) -> list[SeedAlertSpec]:
    return [
        SeedAlertSpec(
            label="edge_ayala_unverified_recent",
            camera_key="ayala",
            detected_at=seeded_timestamp(now, minutes_ago=3),
            confidence_score=0.99,
            detection_status=DetectionStatus.UNVERIFIED,
        ),
        SeedAlertSpec(
            label="edge_ayala_dismissed_closed_only",
            camera_key="ayala",
            detected_at=seeded_timestamp(now, days_ago=0, hour=9, minute=5),
            confidence_score=0.44,
            detection_status=DetectionStatus.DISMISSED,
            closed_by_key="dsahagun",
            closed_after_minutes=5,
        ),
        SeedAlertSpec(
            label="edge_ayala_ongoing_verified_only",
            camera_key="ayala",
            detected_at=seeded_timestamp(now, days_ago=0, hour=9, minute=40),
            confidence_score=0.87,
            detection_status=DetectionStatus.ONGOING,
            verified_by_key="ealonzo",
            verified_after_minutes=2,
        ),
        SeedAlertSpec(
            label="edge_southbound_resolved_same_user",
            camera_key="southbound",
            detected_at=seeded_timestamp(now, days_ago=1, hour=14, minute=15),
            confidence_score=0.91,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="smeer",
            verified_after_minutes=3,
            closed_by_key="smeer",
            closed_after_minutes=16,
        ),
        SeedAlertSpec(
            label="edge_southbound_resolved_different_users",
            camera_key="southbound",
            detected_at=seeded_timestamp(now, days_ago=1, hour=15, minute=5),
            confidence_score=0.89,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="dsahagun",
            verified_after_minutes=4,
            closed_by_key="jtenorio",
            closed_after_minutes=22,
        ),
        SeedAlertSpec(
            label="edge_north_exit_dismissed_after_verification",
            camera_key="north_exit",
            detected_at=seeded_timestamp(now, days_ago=2, hour=6, minute=25),
            confidence_score=0.67,
            detection_status=DetectionStatus.DISMISSED,
            verified_by_key="jtenorio",
            verified_after_minutes=2,
            closed_by_key="ealonzo",
            closed_after_minutes=12,
        ),
        SeedAlertSpec(
            label="edge_inosluban_resolved_long_close",
            camera_key="inosluban",
            detected_at=seeded_timestamp(now, days_ago=3, hour=19, minute=10),
            confidence_score=0.85,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="ealonzo",
            verified_after_minutes=5,
            closed_by_key="dsahagun",
            closed_after_minutes=55,
        ),
        SeedAlertSpec(
            label="edge_tambo_unverified_older",
            camera_key="tambo",
            detected_at=seeded_timestamp(now, days_ago=4, hour=11, minute=45),
            confidence_score=0.78,
            detection_status=DetectionStatus.UNVERIFIED,
        ),
        SeedAlertSpec(
            label="edge_dagatan_dismissed_closed_only",
            camera_key="dagatan",
            detected_at=seeded_timestamp(now, days_ago=5, hour=13, minute=5),
            confidence_score=0.49,
            detection_status=DetectionStatus.DISMISSED,
            closed_by_key="smeer",
            closed_after_minutes=6,
        ),
        SeedAlertSpec(
            label="edge_dagatan_ongoing_recent",
            camera_key="dagatan",
            detected_at=seeded_timestamp(now, minutes_ago=48),
            confidence_score=0.93,
            detection_status=DetectionStatus.ONGOING,
            verified_by_key="jtenorio",
            verified_after_minutes=4,
        ),
    ]


def build_default_cameras() -> list[SeedCameraSpec]:
    return [
        SeedCameraSpec(
            key="ayala",
            camera_name="Ayala Highway Cam",
            channel_id=1,
            connection_status=ConnectionStatus.CONNECTED,
            ai_status=AIStatus.ACTIVE,
        ),
        SeedCameraSpec(
            key="southbound",
            camera_name="Southbound Entry Cam",
            channel_id=2,
            connection_status=ConnectionStatus.RECONNECTING,
            ai_status=AIStatus.PAUSED,
        ),
        SeedCameraSpec(
            key="north_exit",
            camera_name="North Exit Cam",
            channel_id=3,
            connection_status=ConnectionStatus.DISCONNECTED,
            ai_status=AIStatus.INACTIVE,
            is_enabled=False,
        ),
        SeedCameraSpec(
            key="inosluban",
            camera_name="Inosluban Intersection",
            channel_id=4,
            connection_status=ConnectionStatus.CONNECTED,
            ai_status=AIStatus.ACTIVE,
        ),
        SeedCameraSpec(
            key="tambo",
            camera_name="Tambo Highway Cam",
            channel_id=5,
            connection_status=ConnectionStatus.CONNECTED,
            ai_status=AIStatus.ACTIVE,
        ),
        SeedCameraSpec(
            key="dagatan",
            camera_name="Dagatan Entry Cam",
            channel_id=6,
            connection_status=ConnectionStatus.CONNECTED,
            ai_status=AIStatus.ACTIVE,
        ),
    ]


# The four operator accounts shared by every profile. The `admin` account
# is not here — init_db() creates it from DEFAULT_ADMIN_PASSWORD before any
# profile runs.
_OPERATOR_KEYS = ("dsahagun", "ealonzo", "smeer", "jtenorio")


def build_default_users() -> list[SeedUserSpec]:
    return [
        SeedUserSpec(
            key="dsahagun",
            username="dsahagun",
            first_name="Daniel Luis",
            last_name="Sahagun",
            role=UserRole.OPERATOR,
            password="operator123",
        ),
        SeedUserSpec(
            key="ealonzo",
            username="ealonzo",
            first_name="Enjey Kashlee",
            last_name="Alonzo",
            role=UserRole.OPERATOR,
            password="operator123",
        ),
        SeedUserSpec(
            key="smeer",
            username="smeer",
            first_name="Sebastian Angelo",
            last_name="Meer",
            role=UserRole.OPERATOR,
            password="operator123",
        ),
        SeedUserSpec(
            key="jtenorio",
            username="jtenorio",
            first_name="Jhon Paulo",
            last_name="Tenorio",
            role=UserRole.OPERATOR,
            password="operator123",
        ),
    ]


def build_default_audit_specs(now: datetime) -> list[SeedAuditSpec]:
    """Representative audit_log rows so the audit viewer has something to
    page through. `now` is accepted for signature parity with the other
    builders — every offset here is relative, not absolute."""
    specs = [
        SeedAuditSpec(
            actor_key="admin",
            action="LOGIN_SUCCESS",
            target_type="session",
            result="success",
            minutes_ago=180,
        ),
        SeedAuditSpec(
            actor_key=None,
            username="ghost",
            action="LOGIN_FAILURE",
            target_type="session",
            result="denied",
            detail='{"reason": "invalid_credentials"}',
            minutes_ago=42,
        ),
    ]

    for offset, key in enumerate(_OPERATOR_KEYS, start=1):
        specs.append(
            SeedAuditSpec(
                actor_key="admin",
                action="USER_CREATE",
                target_type="user",
                target_ref_key=key,
                result="success",
                detail=f'{{"created_username": "{key}"}}',
                minutes_ago=170 - offset,
            )
        )
        specs.append(
            SeedAuditSpec(
                actor_key=key,
                action="LOGIN_SUCCESS",
                target_type="session",
                result="success",
                minutes_ago=60 + offset * 5,
            )
        )

    return specs


def _no_alerts(now: datetime) -> list[SeedAlertSpec]:
    return []


PROFILES: dict[str, SeedProfile] = {
    "demo": SeedProfile(
        name="demo",
        description="Balanced dataset for manual testing and demos.",
        cameras=build_default_cameras,
        users=build_default_users,
        alerts=build_demo_alert_specs,
        audit=build_default_audit_specs,
    ),
    "analytics": SeedProfile(
        name="analytics",
        description="Denser, chart-friendly data across 14 days.",
        cameras=build_default_cameras,
        users=build_default_users,
        alerts=build_analytics_alert_specs,
        audit=build_default_audit_specs,
    ),
    "edge": SeedProfile(
        name="edge",
        description="Unusual workflow combinations and boundary values.",
        cameras=build_default_cameras,
        users=build_default_users,
        alerts=build_edge_alert_specs,
        audit=build_default_audit_specs,
    ),
    PERF_PROFILE: SeedProfile(
        name=PERF_PROFILE,
        description="100,000 incidents over ~18 months (NFR-08). Slow (~33s).",
        cameras=build_default_cameras,
        users=build_default_users,
        alerts=_no_alerts,
        audit=build_default_audit_specs,
        snapshots=False,
    ),
}

# Was a hand-maintained literal tuple that `perf` was missing from, which
# is why the CLI dispatched it through a duplicated `if` in two places.
SEED_PROFILES = tuple(PROFILES)


def get_profile(profile: str) -> SeedProfile:
    try:
        return PROFILES[profile]
    except KeyError as exc:
        valid_profiles = ", ".join(SEED_PROFILES)
        raise ValueError(
            f"Unknown seed profile '{profile}'. Expected one of: {valid_profiles}."
        ) from exc


def build_alert_specs(profile: str, now: datetime) -> list[SeedAlertSpec]:
    return get_profile(profile).alerts(now)
