"""Revoke legacy sessions and activate mandatory MFA.

Revision ID: 8d4e7a2c9f10
Revises: 5b87b6564753
Create Date: 2026-10-18
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "8d4e7a2c9f10"
down_revision: str | Sequence[str] | None = "5b87b6564753"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLLOUT_TARGET = "p4-mandatory-mfa-cutover"
_NO_DELETE_TRIGGER = """
CREATE TRIGGER trg_audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END
"""


def upgrade() -> None:
    """Close password-only sessions as one audited, atomic rollout."""
    with op.batch_alter_table("auth_session", schema=None) as batch_op:
        batch_op.alter_column(
            "auth_method",
            existing_type=sa.String(),
            existing_nullable=False,
            existing_server_default="password",
            server_default=None,
        )

    now = (
        datetime.now(UTC)
        .replace(tzinfo=None)
        .isoformat(sep=" ", timespec="microseconds")
    )
    connection = op.get_bind()
    revoked = connection.execute(
        sa.text(
            "UPDATE auth_session SET revoked_at=:now, "
            "revocation_reason='mfa_rollout' WHERE revoked_at IS NULL"
        ),
        {"now": now},
    ).rowcount
    cleared = connection.execute(sa.text("DELETE FROM mfa_challenge")).rowcount
    connection.execute(
        sa.text(
            "INSERT INTO audit_log "
            "(actor_type, action, target_type, target_ref, result, detail, created_at) "
            "VALUES ('system', 'MFA_ROLLOUT', 'system', :target_ref, 'success', "
            ":detail, :created_at)"
        ),
        {
            "target_ref": _ROLLOUT_TARGET,
            "detail": json.dumps(
                {
                    "revoked_sessions": max(0, revoked or 0),
                    "cleared_challenges": max(0, cleared or 0),
                },
                separators=(",", ":"),
            ),
            "created_at": now,
        },
    )


def _refuse_populated_downgrade(connection) -> None:
    checks = (
        "SELECT 1 FROM user LIMIT 1",
        "SELECT 1 FROM mfa_credential WHERE state <> 'unenrolled' "
        "OR active_secret_ciphertext IS NOT NULL OR credential_version <> 0 "
        "OR last_accepted_step IS NOT NULL OR enrolled_at IS NOT NULL "
        "OR recovery_started_at IS NOT NULL OR recovery_generation <> 0 LIMIT 1",
        "SELECT 1 FROM mfa_challenge LIMIT 1",
        "SELECT 1 FROM mfa_recovery_code LIMIT 1",
        "SELECT 1 FROM auth_session WHERE auth_method <> 'password' LIMIT 1",
        "SELECT 1 FROM audit_log WHERE NOT (actor_type='system' "
        "AND action='MFA_ROLLOUT' AND target_type='system' "
        f"AND target_ref='{_ROLLOUT_TARGET}') LIMIT 1",
    )
    if any(connection.execute(sa.text(query)).first() for query in checks):
        raise RuntimeError(
            "Refusing MFA cutover downgrade on populated data; restore a verified "
            "pre-cutover backup with its matching code instead."
        )
    rollout_count = connection.execute(
        sa.text(
            "SELECT count(*) FROM audit_log WHERE actor_type='system' "
            "AND action='MFA_ROLLOUT' AND target_type='system' AND target_ref=:target"
        ),
        {"target": _ROLLOUT_TARGET},
    ).scalar_one()
    if rollout_count != 1:
        raise RuntimeError(
            "Refusing MFA cutover downgrade with unexpected audit history."
        )


def downgrade() -> None:
    """Allow the migration verification's empty-database downgrade only.

    A deployed cutover has user/audit history and must be rolled back by
    restoring a verified pre-cutover backup with matching code. The one
    system rollout row is removed only from a genuinely empty scratch schema
    so P1's older action catalog can be downgraded without rewriting history.
    """
    connection = op.get_bind()
    _refuse_populated_downgrade(connection)

    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_no_delete")
    try:
        connection.execute(
            sa.text(
                "DELETE FROM audit_log WHERE actor_type='system' "
                "AND action='MFA_ROLLOUT' AND target_type='system' "
                "AND target_ref=:target"
            ),
            {"target": _ROLLOUT_TARGET},
        )
    finally:
        op.execute(_NO_DELETE_TRIGGER)

    with op.batch_alter_table("auth_session", schema=None) as batch_op:
        batch_op.alter_column(
            "auth_method",
            existing_type=sa.String(),
            existing_nullable=False,
            server_default="password",
        )
