from __future__ import annotations

import argparse

from _bootstrap import bootstrap_backend

bootstrap_backend()

from reset_db import reset_sqlite_db
from seed_dev_data import (
    DEFAULT_SEED_PROFILE,
    PERF_PROFILE,
    PERF_TARGET_INCIDENT_COUNT,
    SEED_PROFILES,
    seed_dev_data,
    seed_perf_data,
)


def reseed_dev(*, profile: str = DEFAULT_SEED_PROFILE) -> None:
    reset_sqlite_db(initialize=False)
    if profile == PERF_PROFILE:
        seed_perf_data(target_count=PERF_TARGET_INCIDENT_COUNT)
    else:
        seed_dev_data(profile=profile)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset the local SQLite DB and reseed it with a named dev-data profile."
    )
    parser.add_argument(
        "--profile",
        choices=SEED_PROFILES,
        default=DEFAULT_SEED_PROFILE,
        help="Seed profile to use after the database reset.",
    )
    args = parser.parse_args()

    reseed_dev(profile=args.profile)


if __name__ == "__main__":
    main()
