"""
Tests for the SQLite connection policy (P1 Step 2 / D-005).

Uses a throwaway temp-file engine with the same pragma installer the real
app engine uses — never the module-level `app.core.db.engine`, which points
at the real repo-root adas.db.
"""

from pathlib import Path

import pytest
from app.core.config import settings
from app.core.db import install_sqlite_pragmas
from sqlalchemy import text
from sqlmodel import create_engine


@pytest.fixture()
def pragma_engine(tmp_path: Path):
    db_path = tmp_path / "pragma_probe.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    install_sqlite_pragmas(engine, settings.SQLITE_BUSY_TIMEOUT_MS)
    yield engine
    engine.dispose()


class TestSqlitePragmas:
    def test_foreign_keys_enabled_on_fresh_connection(self, pragma_engine):
        with pragma_engine.connect() as conn:
            assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1

    def test_journal_mode_is_wal_on_fresh_connection(self, pragma_engine):
        with pragma_engine.connect() as conn:
            assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"

    def test_synchronous_is_full_on_fresh_connection(self, pragma_engine):
        with pragma_engine.connect() as conn:
            # SQLite reports synchronous as an integer: FULL == 2
            assert conn.execute(text("PRAGMA synchronous")).scalar() == 2

    def test_busy_timeout_matches_configured_value(self, pragma_engine):
        with pragma_engine.connect() as conn:
            assert (
                conn.execute(text("PRAGMA busy_timeout")).scalar()
                == settings.SQLITE_BUSY_TIMEOUT_MS
            )
