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

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models import DetectionStatus

DEFAULT_SEED_PROFILE = "demo"
PERF_PROFILE = "perf"
SEED_PROFILES = ("demo", "analytics", "edge", PERF_PROFILE)

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


PROFILE_BUILDERS = {
    "demo": build_demo_alert_specs,
    "analytics": build_analytics_alert_specs,
    "edge": build_edge_alert_specs,
}


def build_alert_specs(profile: str, now: datetime) -> list[SeedAlertSpec]:
    try:
        return PROFILE_BUILDERS[profile](now)
    except KeyError as exc:
        valid_profiles = ", ".join(SEED_PROFILES)
        raise ValueError(
            f"Unknown seed profile '{profile}'. Expected one of: {valid_profiles}."
        ) from exc
