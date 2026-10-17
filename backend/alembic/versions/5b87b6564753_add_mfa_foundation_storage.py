"""Additive MFA foundation storage.

The three MFA tables are introduced without changing authentication behavior.
Existing sessions receive ``auth_method='password'`` from a server default so
their ids, timestamps, revocation history, and validity remain intact. SQLite
requires batch rebuilds for the expanded session and audit CHECK constraints;
the rebuilds preserve indexes, and audit immutability triggers are explicitly
dropped and recreated around the audit table copy.

Revision ID: 5b87b6564753
Revises: c28d3f1a9e7b
Create Date: 2026-10-18 01:21:16.181267
"""

from collections.abc import Sequence

import app.core.types  # noqa: F401
import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "5b87b6564753"
down_revision: str | Sequence[str] | None = "c28d3f1a9e7b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REVOCATION_REASONS_BEFORE = (
    "logout",
    "password_change",
    "password_reset",
    "role_change",
    "account_disabled",
    "admin_revoke",
    "expired_cleanup",
)
_REVOCATION_REASONS_AFTER = (
    *_REVOCATION_REASONS_BEFORE,
    "mfa_rollout",
    "mfa_recovery",
    "mfa_replacement",
    "mfa_enrollment",
    "mfa_restore",
)

# Frozen catalog at c28d3f1a9e7b (after ALERT_RESOLVE -> ALERT_CLEAR).
_AUDIT_ACTIONS_BEFORE = (
    "LOGIN_SUCCESS",
    "LOGIN_FAILURE",
    "LOGOUT",
    "ALERT_CONFIRM",
    "ALERT_DISMISS",
    "ALERT_CLEAR",
    "ALERT_CORRECTION",
    "ALERT_SNOOZE",
    "CAMERA_CREATE",
    "CAMERA_UPDATE",
    "CAMERA_ENABLE",
    "CAMERA_DISABLE",
    "CAMERA_DELETE",
    "CAMERA_RESTORE",
    "REPORT_EXPORT",
    "AUDIT_EXPORT",
    "USER_CREATE",
    "USER_UPDATE",
    "USER_ENABLE",
    "USER_DISABLE",
    "USER_ROLE_CHANGE",
    "USER_PASSWORD_RESET",
    "USER_PROFILE_UPDATE",
    "USER_PASSWORD_CHANGE",
    "ALARM_SETTINGS_UPDATE",
    "BACKUP_TRIGGER",
    "RESTORE_TRIGGER",
)
_AUDIT_ACTIONS_AFTER = (
    "LOGIN_SUCCESS",
    "LOGIN_FAILURE",
    "MFA_CHALLENGE_START",
    "MFA_CHALLENGE_CANCEL",
    "MFA_ENROLL",
    "MFA_REPLACE",
    "MFA_RECOVERY_USE",
    "MFA_RECOVERY_ROTATE",
    "MFA_ROLLOUT",
    "MFA_RESTORE_INVALIDATE",
    "LOGOUT",
    "ALERT_CONFIRM",
    "ALERT_DISMISS",
    "ALERT_CLEAR",
    "ALERT_CORRECTION",
    "ALERT_SNOOZE",
    "CAMERA_CREATE",
    "CAMERA_UPDATE",
    "CAMERA_ENABLE",
    "CAMERA_DISABLE",
    "CAMERA_DELETE",
    "CAMERA_RESTORE",
    "REPORT_EXPORT",
    "AUDIT_EXPORT",
    "USER_CREATE",
    "USER_UPDATE",
    "USER_ENABLE",
    "USER_DISABLE",
    "USER_ROLE_CHANGE",
    "USER_PASSWORD_RESET",
    "USER_PROFILE_UPDATE",
    "USER_PASSWORD_CHANGE",
    "ALARM_SETTINGS_UPDATE",
    "BACKUP_TRIGGER",
    "RESTORE_TRIGGER",
)

_DROP_AUDIT_UPDATE_TRIGGER_SQL = "DROP TRIGGER IF EXISTS trg_audit_log_no_update"
_DROP_AUDIT_DELETE_TRIGGER_SQL = "DROP TRIGGER IF EXISTS trg_audit_log_no_delete"
_AUDIT_NO_UPDATE_TRIGGER_SQL = """
CREATE TRIGGER trg_audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END
"""
_AUDIT_NO_DELETE_TRIGGER_SQL = """
CREATE TRIGGER trg_audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END
"""


def _check_sql(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _replace_auth_session_constraints(*, downgrade: bool = False) -> None:
    with op.batch_alter_table("auth_session", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_auth_session_revocation_reason_valid", type_="check"
        )
        if downgrade:
            batch_op.drop_constraint(
                "ck_auth_session_totp_requires_mfa_version", type_="check"
            )
            batch_op.drop_constraint(
                "ck_auth_session_mfa_credential_version_nonnegative", type_="check"
            )
            batch_op.drop_constraint("ck_auth_session_auth_method_valid", type_="check")
            batch_op.drop_column("mfa_credential_version")
            batch_op.drop_column("auth_method")
            reasons = _REVOCATION_REASONS_BEFORE
        else:
            batch_op.add_column(
                sa.Column(
                    "auth_method",
                    sa.String(),
                    server_default="password",
                    nullable=False,
                )
            )
            batch_op.add_column(
                sa.Column("mfa_credential_version", sa.Integer(), nullable=True)
            )
            batch_op.create_check_constraint(
                "ck_auth_session_auth_method_valid",
                _check_sql("auth_method", ("password", "totp", "demo_impersonation")),
            )
            batch_op.create_check_constraint(
                "ck_auth_session_mfa_credential_version_nonnegative",
                "mfa_credential_version IS NULL OR mfa_credential_version >= 0",
            )
            batch_op.create_check_constraint(
                "ck_auth_session_totp_requires_mfa_version",
                "auth_method <> 'totp' OR mfa_credential_version IS NOT NULL",
            )
            reasons = _REVOCATION_REASONS_AFTER
        batch_op.create_check_constraint(
            "ck_auth_session_revocation_reason_valid",
            f"revocation_reason IS NULL OR {_check_sql('revocation_reason', reasons)}",
        )


def _replace_audit_action_constraint(actions: tuple[str, ...]) -> None:
    # Batch-copying audit_log would otherwise fire its append-only triggers.
    op.execute(_DROP_AUDIT_UPDATE_TRIGGER_SQL)
    op.execute(_DROP_AUDIT_DELETE_TRIGGER_SQL)
    try:
        with op.batch_alter_table("audit_log", schema=None) as batch_op:
            batch_op.drop_constraint("ck_audit_action_valid", type_="check")
            batch_op.create_check_constraint(
                "ck_audit_action_valid", _check_sql("action", actions)
            )
    finally:
        # Restore protection even if a batch-copy operation raises.
        op.execute(_AUDIT_NO_UPDATE_TRIGGER_SQL)
        op.execute(_AUDIT_NO_DELETE_TRIGGER_SQL)


def _create_mfa_tables() -> None:
    op.create_table(
        "mfa_credential",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("state", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "active_secret_ciphertext",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        ),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("last_accepted_step", sa.Integer(), nullable=True),
        sa.Column("enrolled_at", app.core.types.UtcDateTime(), nullable=True),
        sa.Column("recovery_started_at", app.core.types.UtcDateTime(), nullable=True),
        sa.Column("recovery_generation", sa.Integer(), nullable=False),
        sa.Column("created_at", app.core.types.UtcDateTime(), nullable=False),
        sa.Column("updated_at", app.core.types.UtcDateTime(), nullable=False),
        sa.CheckConstraint(
            "(state = 'enrolled' AND active_secret_ciphertext IS NOT NULL "
            "AND enrolled_at IS NOT NULL) OR "
            "(state <> 'enrolled' AND active_secret_ciphertext IS NULL "
            "AND last_accepted_step IS NULL AND enrolled_at IS NULL)",
            name="ck_mfa_credential_active_secret_matches_state",
        ),
        sa.CheckConstraint(
            "state IN ('unenrolled', 'enrolled', 'recovery_pending')",
            name="ck_mfa_credential_state_valid",
        ),
        sa.CheckConstraint(
            "credential_version >= 0",
            name="ck_mfa_credential_version_nonnegative",
        ),
        sa.CheckConstraint(
            "last_accepted_step IS NULL OR last_accepted_step >= 0",
            name="ck_mfa_credential_last_step_nonnegative",
        ),
        sa.CheckConstraint(
            "recovery_generation >= 0",
            name="ck_mfa_credential_recovery_generation_nonnegative",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "mfa_challenge",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "token_hash", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False
        ),
        sa.Column("purpose", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("password_changed_at", app.core.types.UtcDateTime(), nullable=True),
        sa.Column(
            "pending_secret_ciphertext",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        ),
        sa.Column("created_at", app.core.types.UtcDateTime(), nullable=False),
        sa.Column("expires_at", app.core.types.UtcDateTime(), nullable=False),
        sa.CheckConstraint(
            "(purpose IN ('enroll', 'recovery_enroll', 'replace') "
            "AND pending_secret_ciphertext IS NOT NULL) OR "
            "(purpose IN ('login', 'recovery_verify') "
            "AND pending_secret_ciphertext IS NULL)",
            name="ck_mfa_challenge_pending_secret_matches_purpose",
        ),
        sa.CheckConstraint(
            "purpose IN ('login', 'enroll', 'recovery_verify', "
            "'recovery_enroll', 'replace')",
            name="ck_mfa_challenge_purpose_valid",
        ),
        sa.CheckConstraint(
            "credential_version >= 0",
            name="ck_mfa_challenge_credential_version_nonnegative",
        ),
        sa.CheckConstraint(
            "length(token_hash) = 64",
            name="ck_mfa_challenge_token_hash_length",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("token_hash", name="uq_mfa_challenge_token_hash"),
    )
    op.create_table(
        "mfa_recovery_code",
        sa.Column("recovery_code_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column(
            "code_hash", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False
        ),
        sa.Column("created_at", app.core.types.UtcDateTime(), nullable=False),
        sa.Column("consumed_at", app.core.types.UtcDateTime(), nullable=True),
        sa.CheckConstraint(
            "generation >= 1", name="ck_mfa_recovery_code_generation_positive"
        ),
        sa.CheckConstraint(
            "length(code_hash) = 64", name="ck_mfa_recovery_code_hash_length"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("recovery_code_id"),
        sa.UniqueConstraint(
            "user_id",
            "generation",
            "code_hash",
            name="uq_mfa_recovery_code_user_generation_hash",
        ),
    )
    op.create_index(
        "ix_mfa_recovery_code_user_generation_consumed",
        "mfa_recovery_code",
        ["user_id", "generation", "consumed_at"],
        unique=False,
    )


def upgrade() -> None:
    """Add storage and compatibility metadata without activating MFA."""
    _create_mfa_tables()
    _replace_auth_session_constraints()
    _replace_audit_action_constraint(_AUDIT_ACTIONS_AFTER)


def _refuse_downgrade_with_mfa_data() -> None:
    bind = op.get_bind()
    data_checks = (
        "SELECT 1 FROM mfa_credential WHERE state <> 'unenrolled' "
        "OR active_secret_ciphertext IS NOT NULL OR last_accepted_step IS NOT NULL "
        "OR enrolled_at IS NOT NULL OR recovery_started_at IS NOT NULL "
        "OR credential_version <> 0 OR recovery_generation <> 0 LIMIT 1",
        "SELECT 1 FROM mfa_recovery_code LIMIT 1",
        "SELECT 1 FROM mfa_challenge LIMIT 1",
        "SELECT 1 FROM auth_session WHERE auth_method = 'totp' LIMIT 1",
    )
    if any(bind.execute(sa.text(query)).first() for query in data_checks):
        raise RuntimeError("Refusing MFA downgrade because it would destroy MFA data.")


def downgrade() -> None:
    """Remove only an empty foundation; refuse to destroy active MFA state."""
    _refuse_downgrade_with_mfa_data()
    _replace_auth_session_constraints(downgrade=True)
    _replace_audit_action_constraint(_AUDIT_ACTIONS_BEFORE)
    op.drop_index(
        "ix_mfa_recovery_code_user_generation_consumed",
        table_name="mfa_recovery_code",
    )
    op.drop_table("mfa_recovery_code")
    op.drop_table("mfa_challenge")
    op.drop_table("mfa_credential")
