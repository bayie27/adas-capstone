"""10_PKG_migration_evidence.md's Verification item 1 and Step 7's CI
migration job — "assert the schema matches SQLModel.metadata".

Builds two disposable SQLite files: one via `alembic upgrade head`, one via
`SQLModel.metadata.create_all()`, then diffs every table/index/trigger's
`sqlite_master` SQL text object-by-object. A hand-edited migration
drifting from the models (a forgotten index, a renamed constraint, a
missing trigger) shows up here as a real difference, not just "looks
right" — SQL text differences that are purely constraint-ordering/
whitespace (autogenerate's own nondeterminism) are tolerated by comparing
the parsed structure, not raw string equality, but no *object* may be
missing from either side.

Usage: `uv run python backend/scripts/verify_migration_schema.py`
Exit code 0 = schemas match. Non-zero = drift detected, printed to stderr.
"""

from __future__ import annotations

import re
import sqlite3
import sys
import tempfile
from pathlib import Path

from _bootstrap import bootstrap_backend

bootstrap_backend()

import app.models  # noqa: E402, F401  (populates SQLModel.metadata)
from alembic import command  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.db import create_db_engine  # noqa: E402
from app.core.migrations import get_alembic_config  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402


def _normalize(sql: str) -> str:
    """Collapses whitespace and reorders comma-separated CHECK/FK/UNIQUE
    clauses so autogenerate's nondeterministic constraint ordering (a
    known, harmless artifact — see the initial migration's docstring)
    doesn't register as drift."""
    collapsed = re.sub(r"\s+", " ", sql).strip()
    # Split the column/constraint list inside the outermost parens and
    # sort it, so ordering differences don't matter while still catching
    # a genuinely added/removed/changed clause. Table name is one token
    # (`CREATE TABLE alarm_settings (`), so exactly one `\S+` between the
    # keyword and the opening paren.
    match = re.match(r"^(CREATE \w+ \S+ ?\()(.*)(\)[^()]*)$", collapsed)
    if not match:
        return collapsed
    head, body, tail = match.groups()
    parts = [p.strip() for p in body.split(",")]
    return f"{head}{', '.join(sorted(parts))}{tail}"


def _dump_schema(db_path: Path, *, exclude: frozenset[str] = frozenset()) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE type IN ('table','index','trigger') AND name NOT LIKE 'sqlite_%'"
        )
        return {
            (typ, name): _normalize(sql)
            for typ, name, sql in cur.fetchall()
            if name not in exclude and sql is not None
        }
    finally:
        conn.close()


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        migrated_db = tmp_path / "migrated.db"
        modeled_db = tmp_path / "modeled.db"

        migrated_settings = Settings(
            _env_file=None,
            SECRET_KEY="verify-migration-schema-secret",
            INTERNAL_API_KEY="verify-migration-schema-key",
            DEFAULT_ADMIN_PASSWORD="verify-migration-schema-pw",
            DATABASE_URL=f"sqlite:///{migrated_db}",
        )
        command.upgrade(get_alembic_config(migrated_settings), "head")

        modeled_settings = Settings(
            _env_file=None,
            SECRET_KEY="verify-migration-schema-secret",
            INTERNAL_API_KEY="verify-migration-schema-key",
            DEFAULT_ADMIN_PASSWORD="verify-migration-schema-pw",
            DATABASE_URL=f"sqlite:///{modeled_db}",
        )
        modeled_engine = create_db_engine(modeled_settings)
        SQLModel.metadata.create_all(modeled_engine)
        # Explicit dispose, not just letting it fall out of scope — on
        # Windows a still-open DBAPI connection blocks the
        # TemporaryDirectory cleanup below with a PermissionError.
        modeled_engine.dispose()

        migrated = _dump_schema(migrated_db, exclude=frozenset({"alembic_version"}))
        modeled = _dump_schema(modeled_db)

        only_migrated = sorted(migrated.keys() - modeled.keys())
        only_modeled = sorted(modeled.keys() - migrated.keys())
        text_diffs = sorted(
            key
            for key in migrated.keys() & modeled.keys()
            if migrated[key] != modeled[key]
        )

        if not (only_migrated or only_modeled or text_diffs):
            print("OK: migrated schema matches SQLModel.metadata exactly.")
            return 0

        print(
            "MISMATCH between the Alembic-migrated schema and SQLModel.metadata:",
            file=sys.stderr,
        )
        for key in only_migrated:
            print(f"  only in migration: {key}", file=sys.stderr)
        for key in only_modeled:
            print(f"  only in models (missing from migration): {key}", file=sys.stderr)
        for key in text_diffs:
            print(f"  differs: {key}", file=sys.stderr)
            print(f"    migrated: {migrated[key]}", file=sys.stderr)
            print(f"    modeled:  {modeled[key]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
