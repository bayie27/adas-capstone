from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DDL, CheckConstraint, Index, event
from sqlmodel import Field, SQLModel

from app.core.types import UtcDateTime

# D-007 §8 — the complete audit action catalog. One row per semantic action.
AUDIT_ACTIONS = (
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

_AUDIT_ACTIONS_SQL = ", ".join(f"'{action}'" for action in AUDIT_ACTIONS)

# A proper enum type over the same catalog, generated from the single
# AUDIT_ACTIONS source of truth so the two can never drift. Used for typed
# query-parameter validation on the audit viewer (P2 Step 11) — an unknown
# action value becomes a normal 422 instead of a silently-empty filter.
AuditAction = StrEnum("AuditAction", {action: action for action in AUDIT_ACTIONS})


class AuditLog(SQLModel, table=True):
    """D-007 — append-only audit trail. No pruning, ever."""

    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('user', 'system')", name="ck_audit_actor_type_valid"
        ),
        CheckConstraint(
            f"action IN ({_AUDIT_ACTIONS_SQL})", name="ck_audit_action_valid"
        ),
        CheckConstraint(
            "result IN ('success', 'denied', 'failure')", name="ck_audit_result_valid"
        ),
        Index("ix_audit_created_at", "created_at"),
        Index("ix_audit_action_created_at", "action", "created_at"),
        Index("ix_audit_user_created_at", "user_id", "created_at"),
        Index("ix_audit_target", "target_type", "target_ref"),
    )

    audit_id: int | None = Field(default=None, primary_key=True)
    actor_type: str
    user_id: int | None = Field(
        default=None, foreign_key="user.user_id", ondelete="RESTRICT"
    )
    username: str | None = Field(default=None)
    role: str | None = Field(default=None)
    action: str
    target_type: str | None = Field(default=None)
    target_ref: str | None = Field(default=None)
    result: str
    detail: str | None = Field(default=None)
    request_id: str | None = Field(default=None)
    source_ip: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=UtcDateTime
    )


# Immutability triggers (D-007, NFR-21). SQLModel/SQLAlchemy cannot express
# these declaratively, so they're attached as raw DDL fired right after the
# table itself is created — under create_all() today and under Alembic once
# P9 lands.
_NO_UPDATE_TRIGGER = DDL(
    """
    CREATE TRIGGER trg_audit_log_no_update BEFORE UPDATE ON audit_log
    BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
    """
)

_NO_DELETE_TRIGGER = DDL(
    """
    CREATE TRIGGER trg_audit_log_no_delete BEFORE DELETE ON audit_log
    BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
    """
)

# Public so app/dev/wipe.py can drop and *re-execute these same objects*
# rather than re-typing the SQL. NFR-21's append-only guarantee must have
# exactly one source of truth: a second copy of this DDL that drifted from
# this one would be undetectable until it mattered.
AUDIT_IMMUTABILITY_TRIGGERS = (_NO_UPDATE_TRIGGER, _NO_DELETE_TRIGGER)
AUDIT_IMMUTABILITY_TRIGGER_NAMES = (
    "trg_audit_log_no_update",
    "trg_audit_log_no_delete",
)

for _trigger in AUDIT_IMMUTABILITY_TRIGGERS:
    event.listen(AuditLog.__table__, "after_create", _trigger)
