"""rename Resolved incidents to Cleared

P28 is a breaking terminology change across the persisted incident and audit
contracts. SQLite cannot alter a CHECK constraint in place, so both affected
tables are rebuilt through Alembic batch mode. The old values are temporarily
accepted by a constraint-free copy, rewritten, and then constrained to the
new vocabulary.

The audit trail needs extra care: its append-only triggers are not reflected
by Alembic's batch operation and would also reject the table-copy UPDATEs.
They are dropped immediately before the audit rebuild and recreated
immediately after the final constraint is installed. All work remains inside
Alembic's migration transaction, so an error rolls back the value rewrites,
table copies, and trigger removal together.

Batch mode reflects and recreates the existing indexes. The migration tests
assert that the primary keys, timestamps, actor/target/detail columns, row
counts, all detection indexes, all audit indexes, and both triggers survive.

Revision ID: c28d3f1a9e7b
Revises: b0a3652a3d4d
Create Date: 2026-09-03 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c28d3f1a9e7b"
down_revision: str | Sequence[str] | None = "b0a3652a3d4d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


_DETECTION_STATUSES = ("Unverified", "Ongoing", "Dismissed", "Cleared")
_DETECTION_STATUSES_BEFORE = ("Unverified", "Ongoing", "Dismissed", "Resolved")

_AUDIT_ACTIONS_BEFORE = (
    "LOGIN_SUCCESS",
    "LOGIN_FAILURE",
    "LOGOUT",
    "ALERT_CONFIRM",
    "ALERT_DISMISS",
    "ALERT_RESOLVE",
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
_AUDIT_ACTIONS = tuple(
    "ALERT_CLEAR" if action == "ALERT_RESOLVE" else action
    for action in _AUDIT_ACTIONS_BEFORE
)


def _drop_detection_status_check() -> None:
    with op.batch_alter_table("detection_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_detection_status_valid", type_="check")


def _create_detection_status_check(values: tuple[str, ...]) -> None:
    with op.batch_alter_table("detection_log", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "ck_detection_status_valid", _check_sql("detection_status", values)
        )


def _drop_audit_action_check() -> None:
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_audit_action_valid", type_="check")


def _create_audit_action_check(values: tuple[str, ...]) -> None:
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "ck_audit_action_valid", _check_sql("action", values)
        )


def _drop_audit_triggers() -> None:
    op.execute(_DROP_AUDIT_UPDATE_TRIGGER_SQL)
    op.execute(_DROP_AUDIT_DELETE_TRIGGER_SQL)


def _create_audit_triggers() -> None:
    op.execute(_AUDIT_NO_UPDATE_TRIGGER_SQL)
    op.execute(_AUDIT_NO_DELETE_TRIGGER_SQL)


def upgrade() -> None:
    """Install the Cleared incident vocabulary and rewrite existing rows."""
    # The old values must remain insertable while the first table copies run.
    # Removing only the status/action checks is temporary and transactional;
    # the final checks are recreated before this migration returns.
    _drop_detection_status_check()
    op.execute(
        "UPDATE detection_log "
        "SET detection_status = 'Cleared' "
        "WHERE detection_status = 'Resolved'"
    )
    _create_detection_status_check(_DETECTION_STATUSES)

    # Batch-copying audit_log would otherwise fire its append-only triggers.
    _drop_audit_triggers()
    try:
        _drop_audit_action_check()
        op.execute(
            "UPDATE audit_log SET action = 'ALERT_CLEAR' WHERE action = 'ALERT_RESOLVE'"
        )
        _create_audit_action_check(_AUDIT_ACTIONS)
    finally:
        # This is defensive in addition to Alembic's transaction rollback:
        # a failed SQLite batch copy must never leave the trail writable if a
        # caller is using a migration context that does not wrap DDL.
        _create_audit_triggers()


def downgrade() -> None:
    """Restore the preceding Resolved incident vocabulary."""
    _drop_detection_status_check()
    op.execute(
        "UPDATE detection_log "
        "SET detection_status = 'Resolved' "
        "WHERE detection_status = 'Cleared'"
    )
    _create_detection_status_check(_DETECTION_STATUSES_BEFORE)

    _drop_audit_triggers()
    try:
        _drop_audit_action_check()
        op.execute(
            "UPDATE audit_log SET action = 'ALERT_RESOLVE' WHERE action = 'ALERT_CLEAR'"
        )
        _create_audit_action_check(_AUDIT_ACTIONS_BEFORE)
    finally:
        _create_audit_triggers()
