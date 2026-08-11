"""CLI entrypoint for the dev seed profiles.

The seeding logic lives in `app.dev` (dev_plan/01_PKG_seed_core.md) so the
FastAPI app can import it; this module is only the argparse front-end.
"""

from __future__ import annotations

import argparse

from _bootstrap import bootstrap_backend

bootstrap_backend()

from app.core.db import engine
from app.dev import (
    DEFAULT_SEED_PROFILE,
    PERF_PROFILE,
    PERF_TARGET_INCIDENT_COUNT,
    SEED_PROFILES,
    seed_perf_data,
    seed_profile,
)
from app.dev.profiles import PROFILES


def profile_help() -> str:
    """Built from the registry, so a new profile documents itself."""
    return "Seed profile to load. " + " ".join(
        f"'{name}': {profile.description}" for name, profile in PROFILES.items()
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed predictable local dev data for demos, analytics, or edge-case testing."
    )
    parser.add_argument(
        "--profile",
        choices=SEED_PROFILES,
        default=DEFAULT_SEED_PROFILE,
        help=profile_help(),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=PERF_TARGET_INCIDENT_COUNT,
        help="Row count for --profile perf only (default: 100,000).",
    )
    args = parser.parse_args()

    if args.profile == PERF_PROFILE:
        seed_perf_data(engine, target_count=args.count)
    else:
        seed_profile(engine, profile=args.profile)


if __name__ == "__main__":
    main()
