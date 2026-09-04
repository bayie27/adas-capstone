"""Regression tests for the P28 Alembic migration.

These tests deliberately seed the database at the preceding real revision,
not with ``create_all()``. The latter would only prove that the current model
looks right; it would not prove that existing incident and audit history can
make the breaking vocabulary change without losing data or append-only
protection.
"""

from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from alembic import command
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from app.core.config import Settings
from app.core.db import create_db_engine
from app.core.migrations import get_alembic_config
from sqlalchemy import text

_PREVIOUS_REVISION = "b0a3652a3d4d"

_DETECTION_COLUMNS = (
    "log_id, source_event_id, camera_id, detected_at, snapshot_key, "
    "confidence_score, detection_status, verified_by_id, verified_at, "
    "closed_by_id, closed_at, snoozed_at, snoozed_until, snoozed_by_id, "
    "created_at, updated_at"
)
_AUDIT_COLUMNS = (
    "audit_id, actor_type, user_id, username, role, action, target_type, "
    "target_ref, result, detail, request_id, source_ip, created_at"
)


def _migration_settings(db_path) -> Settings:
    return Settings(
        _env_file=None,
        SECRET_KEY="p28-migration-test-secret-32-bytes-long",
        INTERNAL_API_KEY="p28-migration-test-internal-key",
        DEFAULT_ADMIN_PASSWORD="P28Migration123!",
        DATABASE_URL=f"sqlite:///{db_path}",
    )


def _seed_pre_p28_database(settings: Settings) -> None:
    command.upgrade(get_alembic_config(settings), _PREVIOUS_REVISION)
    engine = create_db_engine(settings)
    now = datetime(2026, 9, 3, 4, 0, tzinfo=UTC).isoformat()
    detected = datetime(2026, 9, 2, 12, 30, tzinfo=UTC).isoformat()
    verified = datetime(2026, 9, 2, 12, 31, tzinfo=UTC).isoformat()
    closed = datetime(2026, 9, 2, 12, 45, tzinfo=UTC).isoformat()

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO user "
                "(user_id, username, first_name, last_name, role, password_hash, "
                "is_active, created_at, updated_at) "
                "VALUES (1, 'operator', 'Test', 'Operator', 'Operator', 'hash', 1, "
                ":created_at, :updated_at)"
            ),
            {"created_at": now, "updated_at": now},
        )
        conn.execute(
            text(
                "INSERT INTO camera "
                "(camera_id, camera_name, channel_id, is_active, is_enabled, "
                "desired_ai_state, desired_state_reason, config_version, "
                "connection_status, ai_status, created_at, updated_at) "
                "VALUES (1, 'Migration Camera', 1, 1, 1, 'Active', NULL, 1, "
                "'Connected', 'Active', :created_at, :updated_at)"
            ),
            {"created_at": now, "updated_at": now},
        )
        conn.execute(
            text(
                "INSERT INTO detection_log "
                f"({_DETECTION_COLUMNS}) "
                "VALUES (1, 'legacy-event-1', 1, :detected_at, 'legacy/one.jpg', "
                "0.91, 'Resolved', 1, :verified_at, 1, :closed_at, NULL, NULL, "
                "NULL, :created_at, :updated_at)"
            ),
            {
                "detected_at": detected,
                "verified_at": verified,
                "closed_at": closed,
                "created_at": now,
                "updated_at": closed,
            },
        )
        conn.execute(
            text(
                "INSERT INTO detection_log "
                f"({_DETECTION_COLUMNS}) "
                "VALUES (2, 'legacy-event-2', 1, :detected_at, 'legacy/two.jpg', "
                "0.22, 'Dismissed', 1, :verified_at, NULL, NULL, NULL, NULL, "
                "NULL, :created_at, :updated_at)"
            ),
            {
                "detected_at": detected,
                "verified_at": verified,
                "created_at": now,
                "updated_at": verified,
            },
        )
        conn.execute(
            text(
                "INSERT INTO audit_log "
                f"({_AUDIT_COLUMNS}) "
                "VALUES (1, 'user', 1, 'operator', 'Operator', 'ALERT_RESOLVE', "
                "'incident', '1', 'success', :detail, 'req-1', "
                "'127.0.0.1', :created_at)"
            ),
            {"created_at": closed, "detail": '{"camera_id":1}'},
        )
        conn.execute(
            text(
                "INSERT INTO audit_log "
                f"({_AUDIT_COLUMNS}) "
                "VALUES (2, 'system', NULL, NULL, NULL, 'LOGIN_SUCCESS', NULL, "
                "NULL, 'success', :detail, 'req-2', NULL, "
                ":created_at)"
            ),
            {"created_at": now, "detail": '{"source":"test"}'},
        )
    engine.dispose()


@pytest.fixture()
def p28_database(tmp_path):
    settings = _migration_settings(tmp_path / "p28.db")
    _seed_pre_p28_database(settings)
    return settings


def _fetch_rows(engine, table: str, columns: str) -> list[dict]:
    with engine.connect() as conn:
        return [
            dict(row._mapping)
            for row in conn.execute(text(f"SELECT {columns} FROM {table} ORDER BY 1"))
        ]


def test_p28_preserves_history_and_rewrites_only_the_contract_values(p28_database):
    engine = create_db_engine(p28_database)
    before_detection = _fetch_rows(engine, "detection_log", _DETECTION_COLUMNS)
    before_audit = _fetch_rows(engine, "audit_log", _AUDIT_COLUMNS)
    engine.dispose()

    command.upgrade(get_alembic_config(p28_database), "head")
    engine = create_db_engine(p28_database)
    after_detection = _fetch_rows(engine, "detection_log", _DETECTION_COLUMNS)
    after_audit = _fetch_rows(engine, "audit_log", _AUDIT_COLUMNS)

    expected_detection = [dict(row) for row in before_detection]
    expected_detection[0]["detection_status"] = "Cleared"
    expected_audit = [dict(row) for row in before_audit]
    expected_audit[0]["action"] = "ALERT_CLEAR"

    assert after_detection == expected_detection
    assert after_audit == expected_audit
    assert len(after_detection) == len(before_detection) == 2
    assert len(after_audit) == len(before_audit) == 2
    engine.dispose()


def test_p28_preserves_indexes_and_restores_append_only_triggers(p28_database):
    command.upgrade(get_alembic_config(p28_database), "head")
    engine = create_db_engine(p28_database)
    with engine.connect() as conn:
        detection_indexes = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'index' AND tbl_name = 'detection_log'"
                )
            )
        }
        audit_indexes = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'index' AND tbl_name = 'audit_log'"
                )
            )
        }
        triggers = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'trigger' AND tbl_name = 'audit_log'"
                )
            )
        }

    assert {
        "ix_detection_camera_time",
        "ix_detection_closed_by",
        "ix_detection_log_camera_id",
        "ix_detection_log_detected_at",
        "ix_detection_snooze_due",
        "ix_detection_status_time",
        "ix_detection_verified_by",
        "ux_detection_open_camera",
        "ux_detection_source_event",
    } <= detection_indexes
    assert {
        "ix_audit_created_at",
        "ix_audit_action_created_at",
        "ix_audit_user_created_at",
        "ix_audit_target",
    } <= audit_indexes
    assert triggers == {"trg_audit_log_no_update", "trg_audit_log_no_delete"}

    with (
        pytest.raises(Exception, match="audit_log is append-only"),
        engine.begin() as conn,
    ):
        conn.execute(text("UPDATE audit_log SET detail = '{}' WHERE audit_id = 1"))

    with (
        pytest.raises(Exception, match="audit_log is append-only"),
        engine.begin() as conn,
    ):
        conn.execute(text("DELETE FROM audit_log WHERE audit_id = 1"))

    engine.dispose()


def test_p28_failure_rolls_back_and_keeps_audit_log_append_only(
    p28_database, monkeypatch
):
    """Edge case 11.2 — a failure after trigger removal must not leave a
    half-migrated or writable database behind."""
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "c28d3f1a9e7b_cleared_incident_terminology.py"
    )
    spec = spec_from_file_location("p28_migration_under_test", migration_path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    def fail_after_trigger_drop(_values):
        raise RuntimeError("injected P28 failure")

    monkeypatch.setattr(
        migration, "_create_audit_action_check", fail_after_trigger_drop
    )
    engine = create_db_engine(p28_database)
    try:
        with (
            pytest.raises(RuntimeError, match="injected P28 failure"),
            engine.begin() as conn,
        ):
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()

        assert (
            _fetch_rows(engine, "detection_log", _DETECTION_COLUMNS)[0][
                "detection_status"
            ]
            == "Resolved"
        )
        assert _fetch_rows(engine, "audit_log", _AUDIT_COLUMNS)[0]["action"] == (
            "ALERT_RESOLVE"
        )
        with (
            pytest.raises(Exception, match="audit_log is append-only"),
            engine.begin() as conn,
        ):
            conn.execute(text("DELETE FROM audit_log WHERE audit_id = 1"))
    finally:
        engine.dispose()
