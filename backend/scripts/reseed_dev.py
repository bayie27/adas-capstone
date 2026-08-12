"""Reset the local SQLite database and reseed it with a named profile.

Deletes the database file, so it cannot run while the backend holds it
open — Package B's POST /api/dev/reseed is the in-process equivalent that
keeps the server up.
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
    SeedResult,
    seed_perf_data,
    seed_profile,
)
from reset_db import reset_sqlite_db
from seed_dev_data import profile_help


def reseed_dev(
    *,
    profile: str = DEFAULT_SEED_PROFILE,
    target_count: int = PERF_TARGET_INCIDENT_COUNT,
) -> SeedResult:
    reset_sqlite_db(initialize=False)
    if profile == PERF_PROFILE:
        return seed_perf_data(engine, target_count=target_count)
    return seed_profile(engine, profile=profile)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset the local SQLite DB and reseed it with a named dev-data profile."
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

    reseed_dev(profile=args.profile, target_count=args.count)


if __name__ == "__main__":
    main()
