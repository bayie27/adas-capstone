"""P1 migration evidence against real Alembic revisions and disposable files."""

from __future__ import annotations

import os
import subprocess

import pytest
from alembic import command
from app.core.config import Settings
from app.core.db import create_db_engine
from app.core.migrations import get_alembic_config, get_code_head_revision
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

_PREVIOUS_REVISION = "c28d3f1a9e7b"
_NOW = "2026-10-18 01:02:03.000000"
_OLD_SESSION_COLUMNS = (
    "session_id, user_id, created_at, expires_at, revoked_at, "
    "revocation_reason, user_agent, source_ip"
)


def _settings(db_path) -> Settings:
    return Settings(
        _env_file=None,
        SECRET_KEY="mfa-migration-test-secret-not-for-production",
        INTERNAL_API_KEY="mfa-migration-test-internal-key",
        DEFAULT_ADMIN_PASSWORD="MfaMigrationTest123!",
        DATABASE_URL=f"sqlite:///{db_path}",
    )


def _insert_previous_user(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO user "
                "(user_id, username, first_name, last_name, role, password_hash, "
                "is_active, created_at, updated_at) "
                "VALUES (1, 'mfa-user', 'Migration', 'User', 'Operator', 'hash', "
                "1, :created_at, :updated_at)"
            ),
            {"created_at": _NOW, "updated_at": _NOW},
        )


def _seed_previous_revision(settings: Settings) -> None:
    """Populate the actual current predecessor without create_all()."""
    command.upgrade(get_alembic_config(settings), _PREVIOUS_REVISION)
    engine = create_db_engine(settings)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO user "
                "(user_id, username, first_name, last_name, role, password_hash, "
                "is_active, created_at, updated_at) "
                "VALUES (1, 'mfa-user', 'Migration', 'User', 'Operator', 'hash', "
                "1, :created_at, :updated_at)"
            ),
            {"created_at": _NOW, "updated_at": _NOW},
        )
        conn.execute(
            text(
                "INSERT INTO auth_session "
                "(session_id, user_id, created_at, expires_at, revoked_at, "
                "revocation_reason, user_agent, source_ip) "
                "VALUES ('session-before-mfa', 1, :created_at, :expires_at, NULL, "
                "NULL, 'migration-test', '127.0.0.1')"
            ),
            {
                "created_at": _NOW,
                "expires_at": "2026-10-18 09:02:03.000000",
            },
        )
        conn.execute(
            text(
                "INSERT INTO camera "
                "(camera_id, camera_name, channel_id, is_active, is_enabled, "
                "desired_ai_state, desired_state_reason, config_version, "
                "connection_status, ai_status, created_at, updated_at) "
                "VALUES (1, 'Foundation Camera', 1, 1, 1, 'Active', NULL, 1, "
                "'Connected', 'Active', :created_at, :updated_at)"
            ),
            {"created_at": _NOW, "updated_at": _NOW},
        )
        conn.execute(
            text(
                "INSERT INTO detection_log "
                "(log_id, source_event_id, camera_id, detected_at, snapshot_key, "
                "confidence_score, detection_status, created_at, updated_at) "
                "VALUES (1, 'open-before-mfa', 1, :detected_at, 'legacy/open.jpg', "
                "0.91, 'Unverified', :created_at, :updated_at)"
            ),
            {
                "detected_at": _NOW,
                "created_at": _NOW,
                "updated_at": _NOW,
            },
        )
        conn.execute(
            text(
                "INSERT INTO audit_log "
                "(audit_id, actor_type, user_id, username, role, action, "
                "target_type, target_ref, result, detail, request_id, source_ip, "
                "created_at) VALUES (1, 'user', 1, 'mfa-user', 'Operator', "
                "'LOGIN_SUCCESS', NULL, NULL, 'success', '{\"source\":\"test\"}', "
                "'mfa-before', '127.0.0.1', :created_at)"
            ),
            {"created_at": _NOW},
        )
    engine.dispose()


def _rows(engine, table: str, columns: str = "*") -> list[tuple]:
    with engine.connect() as conn:
        return list(conn.execute(text(f"SELECT {columns} FROM {table} ORDER BY 1")))


def _indexes_and_triggers(engine) -> dict[tuple[str, str], str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE type IN ('index', 'trigger') "
                "AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL"
            )
        )
        return {(row.type, row.name): row.sql for row in rows}


def _table_names(engine) -> set[str]:
    with engine.connect() as conn:
        return set(
            conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            ).scalars()
        )


def _upgrade(settings: Settings):
    command.upgrade(get_alembic_config(settings), "head")
    return create_db_engine(settings)


def _add_valid_credential(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO mfa_credential "
                "(user_id, state, active_secret_ciphertext, credential_version, "
                "last_accepted_step, enrolled_at, recovery_started_at, "
                "recovery_generation, created_at, updated_at) "
                "VALUES (1, 'unenrolled', NULL, 0, NULL, NULL, NULL, 0, "
                ":created_at, :updated_at)"
            ),
            {"created_at": _NOW, "updated_at": _NOW},
        )


def _assert_integrity_error(engine, statement: str, params: dict) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text(statement), params)


def test_foundation_preserves_populated_previous_revision(tmp_path):
    settings = _settings(tmp_path / "preserve.db")
    _seed_previous_revision(settings)
    engine = create_db_engine(settings)
    previous_rows = {
        "user": _rows(engine, "user"),
        "auth_session": _rows(engine, "auth_session", _OLD_SESSION_COLUMNS),
        "audit_log": _rows(engine, "audit_log"),
        "camera": _rows(engine, "camera"),
        "detection_log": _rows(engine, "detection_log"),
    }
    previous_objects = _indexes_and_triggers(engine)
    engine.dispose()

    engine = _upgrade(settings)
    current_rows = {
        "user": _rows(engine, "user"),
        "auth_session": _rows(engine, "auth_session", _OLD_SESSION_COLUMNS),
        "audit_log": _rows(engine, "audit_log"),
        "camera": _rows(engine, "camera"),
        "detection_log": _rows(engine, "detection_log"),
    }
    assert current_rows == previous_rows
    assert {"mfa_credential", "mfa_challenge", "mfa_recovery_code"} <= _table_names(
        engine
    )

    with engine.connect() as conn:
        session = conn.execute(
            text(
                "SELECT auth_method, mfa_credential_version FROM auth_session "
                "WHERE session_id='session-before-mfa'"
            )
        ).one()
    assert session == ("password", None)

    current_objects = _indexes_and_triggers(engine)
    assert previous_objects.items() <= current_objects.items()
    assert "ux_detection_open_camera" in {
        name for (kind, name) in current_objects if kind == "index"
    }
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO detection_log "
                "(source_event_id, camera_id, detected_at, snapshot_key, "
                "confidence_score, detection_status, created_at, updated_at) "
                "VALUES ('second-open', 1, :detected_at, 'legacy/second.jpg', "
                "0.90, 'Ongoing', :created_at, :updated_at)"
            ),
            {
                "detected_at": _NOW,
                "created_at": _NOW,
                "updated_at": _NOW,
            },
        )
    engine.dispose()


def test_foundation_matches_metadata(tmp_path):
    settings = _settings(tmp_path / "schema-match.db")
    engine = _upgrade(settings)
    assert {"mfa_credential", "mfa_challenge", "mfa_recovery_code"} <= _table_names(
        engine
    )
    engine.dispose()

    repo_root = __import__("pathlib").Path(__file__).parents[2]
    result = subprocess.run(
        ["uv", "run", "python", "backend/scripts/verify_migration_schema.py"],
        cwd=repo_root,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "matches SQLModel.metadata" in result.stdout


def test_mfa_checks_and_foreign_keys(tmp_path):
    settings = _settings(tmp_path / "constraints.db")
    command.upgrade(get_alembic_config(settings), _PREVIOUS_REVISION)
    engine = create_db_engine(settings)
    _insert_previous_user(engine)
    command.upgrade(get_alembic_config(settings), "head")

    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1

    _assert_integrity_error(
        engine,
        "INSERT INTO mfa_credential "
        "(user_id, state, credential_version, recovery_generation, created_at, "
        "updated_at) VALUES (1, 'not-a-state', 0, 0, :now, :now)",
        {"now": _NOW},
    )
    _add_valid_credential(engine)
    _assert_integrity_error(
        engine,
        "INSERT INTO mfa_credential "
        "(user_id, state, credential_version, recovery_generation, created_at, "
        "updated_at) VALUES (999, 'unenrolled', 0, 0, :now, :now)",
        {"now": _NOW},
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO user "
                "(user_id, username, first_name, last_name, role, password_hash, "
                "is_active, created_at, updated_at) "
                "VALUES (2, 'mfa-user-two', 'Migration', 'User', 'Operator', "
                "'hash', 1, :created_at, :updated_at)"
            ),
            {"created_at": _NOW, "updated_at": _NOW},
        )

    challenge_sql = (
        "INSERT INTO mfa_challenge "
        "(user_id, token_hash, purpose, credential_version, created_at, expires_at) "
        "VALUES (:user_id, :token_hash, :purpose, 0, :created_at, :expires_at)"
    )
    valid_challenge = {
        "user_id": 1,
        "token_hash": "a" * 64,
        "purpose": "login",
        "created_at": _NOW,
        "expires_at": "2026-10-18 01:07:03.000000",
    }
    with engine.begin() as conn:
        conn.execute(text(challenge_sql), valid_challenge)
    _assert_integrity_error(
        engine,
        challenge_sql,
        {**valid_challenge, "token_hash": "b" * 64},
    )
    _assert_integrity_error(
        engine,
        challenge_sql,
        {**valid_challenge, "user_id": 2},
    )
    _assert_integrity_error(
        engine,
        challenge_sql,
        {**valid_challenge, "user_id": 2, "purpose": "unknown"},
    )

    recovery_sql = (
        "INSERT INTO mfa_recovery_code "
        "(user_id, generation, code_hash, created_at) "
        "VALUES (1, :generation, :code_hash, :created_at)"
    )
    valid_recovery = {"generation": 1, "code_hash": "c" * 64, "created_at": _NOW}
    with engine.begin() as conn:
        conn.execute(text(recovery_sql), valid_recovery)
    _assert_integrity_error(engine, recovery_sql, valid_recovery)
    _assert_integrity_error(
        engine,
        recovery_sql,
        {**valid_recovery, "generation": 0, "code_hash": "d" * 64},
    )

    _assert_integrity_error(
        engine,
        "INSERT INTO auth_session "
        "(session_id, user_id, created_at, expires_at, auth_method) "
        "VALUES ('bad-method', 1, :now, :expires, 'unknown')",
        {"now": _NOW, "expires": "2026-10-18 09:02:03.000000"},
    )
    _assert_integrity_error(
        engine,
        "INSERT INTO auth_session "
        "(session_id, user_id, created_at, expires_at, auth_method) "
        "VALUES ('missing-totp-version', 1, :now, :expires, 'totp')",
        {"now": _NOW, "expires": "2026-10-18 09:02:03.000000"},
    )
    engine.dispose()


def test_audit_triggers_survive_constraint_rebuild(tmp_path):
    settings = _settings(tmp_path / "audit.db")
    _seed_previous_revision(settings)
    engine = create_db_engine(settings)
    previous_objects = _indexes_and_triggers(engine)
    engine.dispose()

    engine = _upgrade(settings)
    current_objects = _indexes_and_triggers(engine)
    for name in ("trg_audit_log_no_update", "trg_audit_log_no_delete"):
        assert previous_objects[("trigger", name)] == current_objects[("trigger", name)]

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO audit_log (actor_type, action, result, created_at) "
                "VALUES ('system', 'MFA_CHALLENGE_START', 'success', :created_at)"
            ),
            {"created_at": _NOW},
        )
    _assert_integrity_error(
        engine,
        "INSERT INTO audit_log (actor_type, action, result, created_at) "
        "VALUES ('system', 'NOT_A_REAL_ACTION', 'success', :created_at)",
        {"created_at": _NOW},
    )
    with (
        pytest.raises(Exception, match="audit_log is append-only"),
        engine.begin() as conn,
    ):
        conn.execute(text("UPDATE audit_log SET detail='changed' WHERE audit_id=1"))
    with (
        pytest.raises(Exception, match="audit_log is append-only"),
        engine.begin() as conn,
    ):
        conn.execute(text("DELETE FROM audit_log WHERE audit_id=1"))
    engine.dispose()


def test_empty_foundation_downgrade(tmp_path):
    settings = _settings(tmp_path / "empty-downgrade.db")
    engine = _upgrade(settings)
    assert {"mfa_credential", "mfa_challenge", "mfa_recovery_code"} <= _table_names(
        engine
    )
    engine.dispose()

    command.downgrade(get_alembic_config(settings), _PREVIOUS_REVISION)
    engine = create_db_engine(settings)
    assert not {"mfa_credential", "mfa_challenge", "mfa_recovery_code"} & _table_names(
        engine
    )
    with engine.connect() as conn:
        columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(auth_session)"))
        }
        revision = conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert "auth_method" not in columns
    assert "mfa_credential_version" not in columns
    assert revision == _PREVIOUS_REVISION
    assert {"trg_audit_log_no_update", "trg_audit_log_no_delete"} <= {
        name for (kind, name) in _indexes_and_triggers(engine) if kind == "trigger"
    }
    engine.dispose()


@pytest.mark.parametrize(
    "loss_item",
    ["enrolled", "recovery_pending", "recovery_code", "totp_session", "pending_seed"],
)
def test_downgrade_refuses_mfa_data_loss(tmp_path, loss_item: str):
    settings = _settings(tmp_path / f"refuse-{loss_item}.db")
    _seed_previous_revision(settings)
    engine = _upgrade(settings)
    with engine.begin() as conn:
        if loss_item in {"enrolled", "recovery_pending"}:
            enrolled = loss_item == "enrolled"
            conn.execute(
                text(
                    "INSERT INTO mfa_credential "
                    "(user_id, state, active_secret_ciphertext, credential_version, "
                    "last_accepted_step, enrolled_at, recovery_started_at, "
                    "recovery_generation, created_at, updated_at) "
                    "VALUES (1, :state, :ciphertext, 1, :step, :enrolled_at, "
                    ":recovery_started_at, 1, :created_at, :updated_at)"
                ),
                {
                    "state": loss_item,
                    "ciphertext": "encrypted-test-payload" if enrolled else None,
                    "step": 10 if enrolled else None,
                    "enrolled_at": _NOW if enrolled else None,
                    "recovery_started_at": None if enrolled else _NOW,
                    "created_at": _NOW,
                    "updated_at": _NOW,
                },
            )
        elif loss_item == "recovery_code":
            conn.execute(
                text(
                    "INSERT INTO mfa_recovery_code "
                    "(user_id, generation, code_hash, created_at) "
                    "VALUES (1, 1, :code_hash, :created_at)"
                ),
                {"code_hash": "e" * 64, "created_at": _NOW},
            )
        elif loss_item == "totp_session":
            conn.execute(
                text(
                    "UPDATE auth_session SET auth_method='totp', "
                    "mfa_credential_version=1 WHERE session_id='session-before-mfa'"
                )
            )
        else:
            conn.execute(
                text(
                    "INSERT INTO mfa_challenge "
                    "(user_id, token_hash, purpose, credential_version, "
                    "pending_secret_ciphertext, created_at, expires_at) "
                    "VALUES (1, :token_hash, 'enroll', 0, 'encrypted-pending', "
                    ":created_at, :expires_at)"
                ),
                {
                    "token_hash": "f" * 64,
                    "created_at": _NOW,
                    "expires_at": "2026-10-18 01:17:03.000000",
                },
            )
    engine.dispose()

    with pytest.raises(RuntimeError, match="MFA data"):
        command.downgrade(get_alembic_config(settings), _PREVIOUS_REVISION)

    engine = create_db_engine(settings)
    assert {"mfa_credential", "mfa_challenge", "mfa_recovery_code"} <= _table_names(
        engine
    )
    with engine.connect() as conn:
        revision = conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        if loss_item == "totp_session":
            session = conn.execute(
                text(
                    "SELECT auth_method, mfa_credential_version FROM auth_session "
                    "WHERE session_id='session-before-mfa'"
                )
            ).one()
            assert session == ("totp", 1)
        elif loss_item in {"enrolled", "recovery_pending"}:
            row = conn.execute(
                text("SELECT state FROM mfa_credential WHERE user_id=1")
            ).scalar_one()
            assert row == loss_item
        elif loss_item == "recovery_code":
            assert (
                conn.execute(
                    text("SELECT count(*) FROM mfa_recovery_code")
                ).scalar_one()
                == 1
            )
        else:
            assert (
                conn.execute(text("SELECT count(*) FROM mfa_challenge")).scalar_one()
                == 1
            )
    assert revision == get_code_head_revision(settings)
    engine.dispose()
