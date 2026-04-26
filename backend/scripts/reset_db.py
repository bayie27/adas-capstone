from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import bootstrap_backend

bootstrap_backend()

from app.core.config import settings
from app.core.db import init_db


def resolve_sqlite_db_path() -> Path:
    database_url = settings.DATABASE_URL
    sqlite_prefix = "sqlite:///"

    if not database_url.startswith(sqlite_prefix):
        raise ValueError(
            "reset_db.py only supports file-based SQLite DATABASE_URL values."
        )

    path_str = database_url[len(sqlite_prefix) :]
    if not path_str or path_str == ":memory:":
        raise ValueError("reset_db.py requires a file-based SQLite database path.")

    db_path = Path(path_str)
    if not db_path.is_absolute():
        db_path = (Path.cwd() / db_path).resolve()
    return db_path


def reset_sqlite_db(*, initialize: bool = True) -> Path:
    db_path = resolve_sqlite_db_path()
    sidecars = [
        db_path,
        db_path.with_name(f"{db_path.name}-wal"),
        db_path.with_name(f"{db_path.name}-shm"),
    ]

    for path in sidecars:
        if path.exists():
            try:
                path.unlink()
                print(f"Deleted {path}")
            except PermissionError as exc:
                raise SystemExit(
                    f"Could not delete {path}. Stop the backend server or any process using the database, then try again."
                ) from exc
        else:
            print(f"Skipped {path} (not found)")

    if initialize:
        init_db()
        print(f"Reinitialized database at {db_path}")

    return db_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete the local SQLite database and recreate schema/admin."
    )
    parser.add_argument(
        "--no-init",
        action="store_true",
        help="Delete the SQLite files without recreating tables afterward.",
    )
    args = parser.parse_args()

    reset_sqlite_db(initialize=not args.no_init)


if __name__ == "__main__":
    main()
