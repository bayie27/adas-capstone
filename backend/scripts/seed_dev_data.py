"""CLI entrypoint for the dev seed profiles.

The seeding logic itself lives in `app.dev` (dev_plan/01_PKG_seed_core.md
Step 1) so the FastAPI app can import it; this module is the argparse
front-end. The re-exports below keep `reseed_dev.py` and
`backend/tests/perf/conftest.py` working against their existing import
paths — Step 7 repoints those at `app.dev` directly.
"""

from __future__ import annotations

import argparse

from _bootstrap import bootstrap_backend

bootstrap_backend()

from app.core.db import engine
from app.dev.profiles import (
    DEFAULT_SEED_PROFILE,
    PERF_BATCH_SIZE,
    PERF_PROFILE,
    PERF_SPREAD_DAYS,
    PERF_TARGET_INCIDENT_COUNT,
    SEED_PROFILES,
    SeedAlertSpec,
    build_alert_specs,
    build_analytics_alert_specs,
    build_demo_alert_specs,
    build_edge_alert_specs,
    seeded_timestamp,
)
from app.dev.seed import (
    SeedResult,
    _build_perf_rows,
    _enforce_one_open_incident_per_camera,
    _enforce_open_camera_limit,
    _perf_pick_status,
    _seed_source_event_id,
    ensure_alert,
    ensure_camera,
    ensure_default_operators,
    ensure_user,
    seed_sample_cameras,
)
from app.dev.seed import seed_perf_data as _seed_perf_data
from app.dev.seed import seed_profile as _seed_profile


def seed_dev_data(*, profile: str = DEFAULT_SEED_PROFILE) -> SeedResult:
    """CLI-shaped wrapper over app.dev.seed.seed_profile, binding the
    module-global engine that scripts have always used."""
    return _seed_profile(engine, profile=profile)


def seed_perf_data(*, target_count: int = PERF_TARGET_INCIDENT_COUNT) -> SeedResult:
    return _seed_perf_data(engine, target_count=target_count)


__all__ = [
    "DEFAULT_SEED_PROFILE",
    "PERF_BATCH_SIZE",
    "PERF_PROFILE",
    "PERF_SPREAD_DAYS",
    "PERF_TARGET_INCIDENT_COUNT",
    "SEED_PROFILES",
    "SeedAlertSpec",
    "SeedResult",
    "_build_perf_rows",
    "_enforce_one_open_incident_per_camera",
    "_enforce_open_camera_limit",
    "_perf_pick_status",
    "_seed_source_event_id",
    "build_alert_specs",
    "build_analytics_alert_specs",
    "build_demo_alert_specs",
    "build_edge_alert_specs",
    "ensure_alert",
    "ensure_camera",
    "ensure_default_operators",
    "ensure_user",
    "main",
    "seed_dev_data",
    "seed_perf_data",
    "seed_sample_cameras",
    "seeded_timestamp",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed predictable local dev data for demos, analytics, or edge-case testing."
    )
    parser.add_argument(
        "--profile",
        choices=SEED_PROFILES,
        default=DEFAULT_SEED_PROFILE,
        help=(
            "Seed profile to load: "
            "'demo' for a balanced dataset, "
            "'analytics' for denser chart-friendly data, "
            "'edge' for tricky workflow combinations, or "
            "'perf' for the NFR-08 100,000-incident performance dataset."
        ),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=PERF_TARGET_INCIDENT_COUNT,
        help="Row count for --profile perf only (default: 100,000).",
    )
    args = parser.parse_args()

    if args.profile == PERF_PROFILE:
        seed_perf_data(target_count=args.count)
    else:
        seed_dev_data(profile=args.profile)


if __name__ == "__main__":
    main()
