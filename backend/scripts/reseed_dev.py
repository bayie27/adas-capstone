from __future__ import annotations

from _bootstrap import bootstrap_backend

bootstrap_backend()

from reset_db import reset_sqlite_db
from seed_dev_data import seed_dev_data


def reseed_dev() -> None:
    reset_sqlite_db(initialize=False)
    seed_dev_data()


def main() -> None:
    reseed_dev()


if __name__ == "__main__":
    main()
