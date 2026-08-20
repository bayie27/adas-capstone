"""camera_restore audit action

P23 adds CAMERA_RESTORE to the audit action catalog (the counterpart to
CAMERA_DELETE — restoring a soft-deleted camera). audit_log.action is
guarded by ck_audit_action_valid, and SQLite cannot alter a CHECK
constraint in place, so this is an op.batch_alter_table move-and-copy
rebuild of audit_log — the append-only trail, the one table the system is
never allowed to lose.

Two things this rebuild must get right, both a consequence of SQLite
forcing a copy-the-whole-table strategy here rather than a true ALTER:

1. trg_audit_log_no_update / trg_audit_log_no_delete (D-007/NFR-21) are
   attached to audit_log via a SQLAlchemy ``after_create`` DDL event, not
   declarative metadata, so they are outside what batch mode reflects and
   carries over. Left in place, a BEFORE UPDATE ... RAISE(ABORT) trigger is
   also incompatible with the rebuild itself. They're dropped before the
   batch block and recreated immediately after, so the trail is never left
   unguarded on the far side of a migration that appeared to succeed.
2. audit_log carries four plain (non-expression, non-partial) indexes
   (ix_audit_created_at, ix_audit_action_created_at, ix_audit_user_created_at,
   ix_audit_target). Unlike camera's expression/partial indexes, these ARE
   part of what SQLAlchemy reflects, so batch mode recreates them
   automatically — nothing hand-written needed here, but their survival is
   exactly what verify_migration_schema.py (and this package's tests)
   confirm rather than assume.

The trigger SQL below is a literal copy of 09e6d3163265's own
_AUDIT_NO_UPDATE_TRIGGER_SQL / _AUDIT_NO_DELETE_TRIGGER_SQL, not an import
of app.models.audit.AUDIT_IMMUTABILITY_TRIGGERS. That "one source of
truth" rule is about runtime code; a migration is a frozen snapshot of the
schema at a point in time, and importing live code would make this
migration's meaning drift the next time that module changes. See
09e6d3163265's module docstring for the same precedent.

Revision ID: b0a3652a3d4d
Revises: 09e6d3163265
Create Date: 2026-08-20 10:44:26.169511

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b0a3652a3d4d"
down_revision: str | Sequence[str] | None = "09e6d3163265"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The 26-action catalog as of 09e6d3163265, and the 27-action catalog with
# CAMERA_RESTORE inserted after CAMERA_DELETE — matching
# app.models.audit.AUDIT_ACTIONS's order at the time this migration was
# written. Literal copies, not an import — see the module docstring.
_ACTIONS_BEFORE = (
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
_ACTIONS_AFTER = (
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


def _check_sql(actions: tuple[str, ...]) -> str:
    return "action IN ({})".format(", ".join(f"'{a}'" for a in actions))


# D-007 / NFR-21 — literal copies of 09e6d3163265's trigger SQL. See the
# module docstring for why these aren't imported from app.models.audit.
_AUDIT_NO_UPDATE_TRIGGER_SQL = """
CREATE TRIGGER trg_audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END
"""
_AUDIT_NO_DELETE_TRIGGER_SQL = """
CREATE TRIGGER trg_audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END
"""
_DROP_NO_UPDATE_TRIGGER_SQL = "DROP TRIGGER IF EXISTS trg_audit_log_no_update"
_DROP_NO_DELETE_TRIGGER_SQL = "DROP TRIGGER IF EXISTS trg_audit_log_no_delete"


def upgrade() -> None:
    """Upgrade schema."""
    # Must go before the batch rebuild — see module docstring point 1.
    op.execute(_DROP_NO_UPDATE_TRIGGER_SQL)
    op.execute(_DROP_NO_DELETE_TRIGGER_SQL)

    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_audit_action_valid", type_="check")
        batch_op.create_check_constraint(
            "ck_audit_action_valid", _check_sql(_ACTIONS_AFTER)
        )

    # Recreate immediately after — the trail must never be left mutable.
    op.execute(_AUDIT_NO_UPDATE_TRIGGER_SQL)
    op.execute(_AUDIT_NO_DELETE_TRIGGER_SQL)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(_DROP_NO_UPDATE_TRIGGER_SQL)
    op.execute(_DROP_NO_DELETE_TRIGGER_SQL)

    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_audit_action_valid", type_="check")
        batch_op.create_check_constraint(
            "ck_audit_action_valid", _check_sql(_ACTIONS_BEFORE)
        )

    op.execute(_AUDIT_NO_UPDATE_TRIGGER_SQL)
    op.execute(_AUDIT_NO_DELETE_TRIGGER_SQL)
