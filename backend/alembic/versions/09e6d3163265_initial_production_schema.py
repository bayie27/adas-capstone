"""initial production schema

D-005's "one clean initial migration" — this is autogenerate's output,
hand-reviewed and patched per 10_PKG_migration_evidence.md Step 1.
Autogenerate cannot see three things that live outside declarative
SQLAlchemy metadata, so they're added by hand below:

1. ``ux_camera_name_active`` — a case-insensitive expression index
   (``lower(camera_name)``). Alembic's SQLite autogenerate explicitly
   cannot reflect/diff expression indexes and skips them with a warning;
   `01_CONTRACTS.md` §3.3 has the literal SQL.
2. The ``audit_log`` append-only triggers (D-007) — attached in
   ``app/models/audit.py`` via a SQLAlchemy ``after_create`` DDL event on
   the table, not via declarative metadata, so autogenerate never sees
   them.
3. The ``help_article_fts`` FTS5 external-content table and its three sync
   triggers — same reason, attached via an ``after_create`` event in
   ``app/models/help.py``. Some SQLite builds ship without FTS5 compiled
   in (edge case 6.17), so creation is guarded exactly like the ORM
   event listener: log and continue rather than fail the migration.

Revision ID: 09e6d3163265
Revises:
Create Date: 2026-08-10 12:33:29.377239

"""

import logging
from collections.abc import Sequence

import app.core.types  # noqa: F401  (referenced by app.core.types.UtcDateTime below)
import sqlalchemy as sa
import sqlmodel  # noqa: F401  (referenced by sqlmodel.sql.sqltypes.AutoString below)
from alembic import op

logger = logging.getLogger("alembic.runtime.migration")

# revision identifiers, used by Alembic.
revision: str = "09e6d3163265"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 01_CONTRACTS.md §3.3 — case-insensitive active-only uniqueness. This is
# the one index alembic's autogenerate cannot express: SQLite expression
# indexes aren't reflectable/diffable, so autogenerate silently skips it.
_CAMERA_NAME_ACTIVE_INDEX_SQL = (
    "CREATE UNIQUE INDEX ux_camera_name_active "
    "ON camera (lower(camera_name)) WHERE is_active = 1"
)
_DROP_CAMERA_NAME_ACTIVE_INDEX_SQL = "DROP INDEX IF EXISTS ux_camera_name_active"

# D-007 / NFR-21 — append-only enforcement, matching app/models/audit.py's
# after_create DDL events exactly.
_AUDIT_NO_UPDATE_TRIGGER_SQL = """
CREATE TRIGGER trg_audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END
"""
_AUDIT_NO_DELETE_TRIGGER_SQL = """
CREATE TRIGGER trg_audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END
"""

# FR-20 — matching app/models/help.py's _FTS_DDL / _FTS_SYNC_TRIGGERS
# exactly, so the migration-created schema and the create_all()-created
# schema (still used by fast unit-test fixtures) never drift apart.
_HELP_FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS help_article_fts USING fts5(
    title, summary, body_markdown,
    content='help_article', content_rowid='article_id'
)
"""
_HELP_FTS_TRIGGERS_SQL = [
    """
    CREATE TRIGGER IF NOT EXISTS trg_help_article_fts_insert AFTER INSERT ON help_article
    BEGIN
        INSERT INTO help_article_fts(rowid, title, summary, body_markdown)
        VALUES (new.article_id, new.title, new.summary, new.body_markdown);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_help_article_fts_update AFTER UPDATE ON help_article
    BEGIN
        INSERT INTO help_article_fts(help_article_fts, rowid, title, summary, body_markdown)
        VALUES ('delete', old.article_id, old.title, old.summary, old.body_markdown);
        INSERT INTO help_article_fts(rowid, title, summary, body_markdown)
        VALUES (new.article_id, new.title, new.summary, new.body_markdown);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_help_article_fts_delete AFTER DELETE ON help_article
    BEGIN
        INSERT INTO help_article_fts(help_article_fts, rowid, title, summary, body_markdown)
        VALUES ('delete', old.article_id, old.title, old.summary, old.body_markdown);
    END
    """,
]
_DROP_HELP_FTS_TRIGGERS_SQL = [
    "DROP TRIGGER IF EXISTS trg_help_article_fts_insert",
    "DROP TRIGGER IF EXISTS trg_help_article_fts_update",
    "DROP TRIGGER IF EXISTS trg_help_article_fts_delete",
]
_DROP_HELP_FTS_TABLE_SQL = "DROP TABLE IF EXISTS help_article_fts"


def _create_help_article_fts() -> None:
    """Guarded exactly like app/models/help.py's after_create listener:
    some SQLite builds lack FTS5, and that must degrade to a logged
    warning (help search falls back to LIKE), never a failed migration."""
    bind = op.get_bind()
    try:
        bind.exec_driver_sql(_HELP_FTS_DDL)
        for trigger_sql in _HELP_FTS_TRIGGERS_SQL:
            bind.exec_driver_sql(trigger_sql)
    except Exception:
        logger.warning(
            "help_article_fts (FTS5) could not be created — this SQLite "
            "build likely lacks FTS5 support. Help search will need to "
            "fall back to LIKE.",
            exc_info=True,
        )


def _drop_help_article_fts() -> None:
    bind = op.get_bind()
    try:
        for drop_sql in _DROP_HELP_FTS_TRIGGERS_SQL:
            bind.exec_driver_sql(drop_sql)
        bind.exec_driver_sql(_DROP_HELP_FTS_TABLE_SQL)
    except Exception:
        logger.warning("help_article_fts cleanup failed (FTS5 unavailable).")


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "camera",
        sa.Column(
            "camera_name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False
        ),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "desired_ai_state", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "desired_state_reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("cooldown_until", app.core.types.UtcDateTime(), nullable=True),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column(
            "connection_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("ai_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("applied_config_version", sa.Integer(), nullable=True),
        sa.Column("last_heartbeat_at", app.core.types.UtcDateTime(), nullable=True),
        sa.Column("measured_fps", sa.Float(), nullable=True),
        sa.Column("inference_latency_ms", sa.Float(), nullable=True),
        sa.Column("last_error_code", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "last_error_message",
            sqlmodel.sql.sqltypes.AutoString(length=256),
            nullable=True,
        ),
        sa.Column("created_at", app.core.types.UtcDateTime(), nullable=False),
        sa.Column("updated_at", app.core.types.UtcDateTime(), nullable=False),
        sa.CheckConstraint(
            "ai_status IN ('Active', 'Inactive', 'Paused', 'Unresponsive')",
            name="ck_camera_ai_status_valid",
        ),
        sa.CheckConstraint(
            "connection_status IN ('Connected', 'Disconnected', 'Reconnecting', 'Unresponsive')",
            name="ck_camera_connection_status_valid",
        ),
        sa.CheckConstraint(
            "desired_ai_state IN ('Active', 'Paused', 'Inactive')",
            name="ck_camera_desired_ai_state_valid",
        ),
        sa.CheckConstraint(
            "desired_state_reason IS NULL OR desired_state_reason IN ('incident', 'cooldown', 'disabled')",
            name="ck_camera_desired_state_reason_valid",
        ),
        sa.CheckConstraint("channel_id > 0", name="ck_camera_channel_id_positive"),
        sa.PrimaryKeyConstraint("camera_id"),
    )
    with op.batch_alter_table("camera", schema=None) as batch_op:
        batch_op.create_index(
            "ix_camera_active_state",
            ["is_active", "is_enabled", "connection_status", "ai_status"],
            unique=False,
        )
        batch_op.create_index(
            "ux_camera_channel_active",
            ["channel_id"],
            unique=True,
            sqlite_where=sa.text("is_active = 1"),
        )
    # Hand-written — see the module docstring. Autogenerate cannot express
    # a SQLite expression index.
    op.execute(_CAMERA_NAME_ACTIVE_INDEX_SQL)

    op.create_table(
        "help_article",
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("roles", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("summary", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("body_markdown", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_faq", sa.Boolean(), nullable=False),
        sa.Column("content_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", app.core.types.UtcDateTime(), nullable=False),
        sa.Column("updated_at", app.core.types.UtcDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("article_id"),
        sa.UniqueConstraint("slug"),
    )
    # Hand-written — see the module docstring. Not declarative metadata, so
    # autogenerate never sees it.
    _create_help_article_fts()

    op.create_table(
        "sys_health_hourly",
        sa.Column("avg_cpu_usage", sa.Float(), nullable=False),
        sa.Column("avg_ram_usage", sa.Float(), nullable=False),
        sa.Column("avg_gpu_usage", sa.Float(), nullable=True),
        sa.Column("avg_cpu_temp", sa.Float(), nullable=True),
        sa.Column("peak_cpu_temp", sa.Float(), nullable=True),
        sa.Column("peak_gpu_temp", sa.Float(), nullable=True),
        sa.Column("avg_gpu_mem_pct", sa.Float(), nullable=True),
        sa.Column("peak_gpu_mem_pct", sa.Float(), nullable=True),
        sa.Column("hourly_id", sa.Integer(), nullable=False),
        sa.Column("hour_start", app.core.types.UtcDateTime(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "avg_cpu_usage >= 0.0 AND avg_cpu_usage <= 100.0",
            name="ck_sys_health_hourly_avg_cpu_range",
        ),
        sa.CheckConstraint(
            "avg_gpu_mem_pct IS NULL OR (avg_gpu_mem_pct >= 0.0 AND avg_gpu_mem_pct <= 100.0)",
            name="ck_sys_health_hourly_avg_gpu_mem_range",
        ),
        sa.CheckConstraint(
            "avg_gpu_usage IS NULL OR (avg_gpu_usage >= 0.0 AND avg_gpu_usage <= 100.0)",
            name="ck_sys_health_hourly_avg_gpu_range",
        ),
        sa.CheckConstraint(
            "avg_ram_usage >= 0.0 AND avg_ram_usage <= 100.0",
            name="ck_sys_health_hourly_avg_ram_range",
        ),
        sa.CheckConstraint(
            "peak_gpu_mem_pct IS NULL OR (peak_gpu_mem_pct >= 0.0 AND peak_gpu_mem_pct <= 100.0)",
            name="ck_sys_health_hourly_peak_gpu_mem_range",
        ),
        sa.PrimaryKeyConstraint("hourly_id"),
    )
    with op.batch_alter_table("sys_health_hourly", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_sys_health_hourly_hour_start"), ["hour_start"], unique=True
        )

    op.create_table(
        "sys_health_raw",
        sa.Column("cpu_usage", sa.Float(), nullable=False),
        sa.Column("ram_usage", sa.Float(), nullable=False),
        sa.Column("gpu_usage_avg", sa.Float(), nullable=True),
        sa.Column("gpu_temp_max", sa.Float(), nullable=True),
        sa.Column("cpu_temp", sa.Float(), nullable=True),
        sa.Column("gpu_mem_pct_max", sa.Float(), nullable=True),
        sa.Column("sys_health_id", sa.Integer(), nullable=False),
        sa.Column("created_at", app.core.types.UtcDateTime(), nullable=False),
        sa.CheckConstraint(
            "cpu_usage >= 0.0 AND cpu_usage <= 100.0",
            name="ck_sys_health_raw_cpu_range",
        ),
        sa.CheckConstraint(
            "gpu_mem_pct_max IS NULL OR (gpu_mem_pct_max >= 0.0 AND gpu_mem_pct_max <= 100.0)",
            name="ck_sys_health_raw_gpu_mem_range",
        ),
        sa.CheckConstraint(
            "gpu_usage_avg IS NULL OR (gpu_usage_avg >= 0.0 AND gpu_usage_avg <= 100.0)",
            name="ck_sys_health_raw_gpu_usage_range",
        ),
        sa.CheckConstraint(
            "ram_usage >= 0.0 AND ram_usage <= 100.0",
            name="ck_sys_health_raw_ram_range",
        ),
        sa.PrimaryKeyConstraint("sys_health_id"),
    )
    with op.batch_alter_table("sys_health_raw", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_sys_health_raw_created_at"), ["created_at"], unique=False
        )

    op.create_table(
        "user",
        sa.Column(
            "username", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column(
            "first_name", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column(
            "last_name", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("password_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", app.core.types.UtcDateTime(), nullable=False),
        sa.Column("updated_at", app.core.types.UtcDateTime(), nullable=False),
        sa.Column("password_changed_at", app.core.types.UtcDateTime(), nullable=True),
        sa.Column("last_login", app.core.types.UtcDateTime(), nullable=True),
        sa.CheckConstraint("role IN ('Admin', 'Operator')", name="ck_user_role_valid"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_user_username"), ["username"], unique=True)

    op.create_table(
        "alarm_settings",
        sa.Column("alarm_settings_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("alarm_sound", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("snooze_duration", sa.Integer(), nullable=False),
        sa.Column("created_at", app.core.types.UtcDateTime(), nullable=False),
        sa.Column("updated_at", app.core.types.UtcDateTime(), nullable=False),
        sa.CheckConstraint(
            "snooze_duration >= 15 AND snooze_duration <= 60",
            name="ck_alarm_snooze_duration_range",
        ),
        sa.CheckConstraint(
            "volume >= 0 AND volume <= 100", name="ck_alarm_volume_range"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("alarm_settings_id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "audit_log",
        sa.Column("audit_id", sa.Integer(), nullable=False),
        sa.Column("actor_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("action", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("target_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("target_ref", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("result", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("detail", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("request_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("source_ip", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", app.core.types.UtcDateTime(), nullable=False),
        sa.CheckConstraint(
            "action IN ('LOGIN_SUCCESS', 'LOGIN_FAILURE', 'LOGOUT', 'ALERT_CONFIRM', 'ALERT_DISMISS', 'ALERT_RESOLVE', 'ALERT_CORRECTION', 'ALERT_SNOOZE', 'CAMERA_CREATE', 'CAMERA_UPDATE', 'CAMERA_ENABLE', 'CAMERA_DISABLE', 'CAMERA_DELETE', 'REPORT_EXPORT', 'AUDIT_EXPORT', 'USER_CREATE', 'USER_UPDATE', 'USER_ENABLE', 'USER_DISABLE', 'USER_ROLE_CHANGE', 'USER_PASSWORD_RESET', 'USER_PROFILE_UPDATE', 'USER_PASSWORD_CHANGE', 'ALARM_SETTINGS_UPDATE', 'BACKUP_TRIGGER', 'RESTORE_TRIGGER')",
            name="ck_audit_action_valid",
        ),
        sa.CheckConstraint(
            "actor_type IN ('user', 'system')", name="ck_audit_actor_type_valid"
        ),
        sa.CheckConstraint(
            "result IN ('success', 'denied', 'failure')", name="ck_audit_result_valid"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("audit_id"),
    )
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.create_index(
            "ix_audit_action_created_at", ["action", "created_at"], unique=False
        )
        batch_op.create_index("ix_audit_created_at", ["created_at"], unique=False)
        batch_op.create_index(
            "ix_audit_target", ["target_type", "target_ref"], unique=False
        )
        batch_op.create_index(
            "ix_audit_user_created_at", ["user_id", "created_at"], unique=False
        )
    # Hand-written — see the module docstring. Attached via an ORM
    # after_create event, so autogenerate never sees it.
    op.execute(_AUDIT_NO_UPDATE_TRIGGER_SQL)
    op.execute(_AUDIT_NO_DELETE_TRIGGER_SQL)

    op.create_table(
        "auth_session",
        sa.Column("session_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", app.core.types.UtcDateTime(), nullable=False),
        sa.Column("expires_at", app.core.types.UtcDateTime(), nullable=False),
        sa.Column("revoked_at", app.core.types.UtcDateTime(), nullable=True),
        sa.Column(
            "revocation_reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column(
            "user_agent", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=True
        ),
        sa.Column("source_ip", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.CheckConstraint(
            "revocation_reason IS NULL OR revocation_reason IN ('logout', 'password_change', 'password_reset', 'role_change', 'account_disabled', 'admin_revoke', 'expired_cleanup')",
            name="ck_auth_session_revocation_reason_valid",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("session_id"),
    )
    with op.batch_alter_table("auth_session", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_auth_session_expires_at"), ["expires_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_auth_session_user_id"), ["user_id"], unique=False
        )
        batch_op.create_index(
            "ix_auth_session_user_revoked", ["user_id", "revoked_at"], unique=False
        )

    op.create_table(
        "detection_log",
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.Column("detected_at", app.core.types.UtcDateTime(), nullable=False),
        sa.Column("snapshot_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("log_id", sa.Integer(), nullable=False),
        sa.Column(
            "source_event_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "detection_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("verified_by_id", sa.Integer(), nullable=True),
        sa.Column("verified_at", app.core.types.UtcDateTime(), nullable=True),
        sa.Column("closed_by_id", sa.Integer(), nullable=True),
        sa.Column("closed_at", app.core.types.UtcDateTime(), nullable=True),
        sa.Column("snoozed_at", app.core.types.UtcDateTime(), nullable=True),
        sa.Column("snoozed_until", app.core.types.UtcDateTime(), nullable=True),
        sa.Column("snoozed_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", app.core.types.UtcDateTime(), nullable=False),
        sa.Column("updated_at", app.core.types.UtcDateTime(), nullable=False),
        sa.CheckConstraint(
            "detection_status IN ('Unverified', 'Ongoing', 'Dismissed', 'Resolved')",
            name="ck_detection_status_valid",
        ),
        sa.CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_detection_confidence_score_range",
        ),
        sa.ForeignKeyConstraint(
            ["camera_id"], ["camera.camera_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["closed_by_id"], ["user.user_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["snoozed_by_id"], ["user.user_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["verified_by_id"], ["user.user_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("log_id"),
        sa.UniqueConstraint("source_event_id"),
    )
    with op.batch_alter_table("detection_log", schema=None) as batch_op:
        batch_op.create_index(
            "ix_detection_camera_time", ["camera_id", "detected_at"], unique=False
        )
        batch_op.create_index("ix_detection_closed_by", ["closed_by_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_detection_log_camera_id"), ["camera_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_detection_log_detected_at"), ["detected_at"], unique=False
        )
        batch_op.create_index(
            "ix_detection_snooze_due",
            ["snoozed_until"],
            unique=False,
            sqlite_where=sa.text("snoozed_until IS NOT NULL"),
        )
        batch_op.create_index(
            "ix_detection_status_time",
            ["detection_status", "detected_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_detection_verified_by", ["verified_by_id"], unique=False
        )
        batch_op.create_index(
            "ux_detection_open_camera",
            ["camera_id"],
            unique=True,
            sqlite_where=sa.text("detection_status IN ('Unverified', 'Ongoing')"),
        )
        batch_op.create_index(
            "ux_detection_source_event", ["source_event_id"], unique=True
        )

    op.create_table(
        "export_job",
        sa.Column("job_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), nullable=False),
        sa.Column("report_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("format", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("filters_json", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("sort_json", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("progress_current", sa.Integer(), nullable=False),
        sa.Column("progress_total", sa.Integer(), nullable=True),
        sa.Column("artifact_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("artifact_bytes", sa.Integer(), nullable=True),
        sa.Column(
            "failure_category", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("created_at", app.core.types.UtcDateTime(), nullable=False),
        sa.Column("started_at", app.core.types.UtcDateTime(), nullable=True),
        sa.Column("completed_at", app.core.types.UtcDateTime(), nullable=True),
        sa.Column("expires_at", app.core.types.UtcDateTime(), nullable=True),
        sa.CheckConstraint(
            "format IN ('csv', 'pdf', 'zip')", name="ck_export_job_format_valid"
        ),
        sa.CheckConstraint(
            "report_type IN ('incidents', 'dashboard', 'performance', 'audit', 'retraining')",
            name="ck_export_job_report_type_valid",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'expired')",
            name="ck_export_job_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"], ["user.user_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("job_id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("export_job")
    with op.batch_alter_table("detection_log", schema=None) as batch_op:
        batch_op.drop_index("ux_detection_source_event")
        batch_op.drop_index(
            "ux_detection_open_camera",
            sqlite_where=sa.text("detection_status IN ('Unverified', 'Ongoing')"),
        )
        batch_op.drop_index("ix_detection_verified_by")
        batch_op.drop_index("ix_detection_status_time")
        batch_op.drop_index(
            "ix_detection_snooze_due", sqlite_where=sa.text("snoozed_until IS NOT NULL")
        )
        batch_op.drop_index(batch_op.f("ix_detection_log_detected_at"))
        batch_op.drop_index(batch_op.f("ix_detection_log_camera_id"))
        batch_op.drop_index("ix_detection_closed_by")
        batch_op.drop_index("ix_detection_camera_time")

    op.drop_table("detection_log")
    with op.batch_alter_table("auth_session", schema=None) as batch_op:
        batch_op.drop_index("ix_auth_session_user_revoked")
        batch_op.drop_index(batch_op.f("ix_auth_session_user_id"))
        batch_op.drop_index(batch_op.f("ix_auth_session_expires_at"))

    op.drop_table("auth_session")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_no_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_no_update")
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.drop_index("ix_audit_user_created_at")
        batch_op.drop_index("ix_audit_target")
        batch_op.drop_index("ix_audit_created_at")
        batch_op.drop_index("ix_audit_action_created_at")

    op.drop_table("audit_log")
    op.drop_table("alarm_settings")
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_username"))

    op.drop_table("user")
    with op.batch_alter_table("sys_health_raw", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sys_health_raw_created_at"))

    op.drop_table("sys_health_raw")
    with op.batch_alter_table("sys_health_hourly", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sys_health_hourly_hour_start"))

    op.drop_table("sys_health_hourly")
    _drop_help_article_fts()
    op.drop_table("help_article")
    op.execute(_DROP_CAMERA_NAME_ACTIVE_INDEX_SQL)
    with op.batch_alter_table("camera", schema=None) as batch_op:
        batch_op.drop_index(
            "ux_camera_channel_active", sqlite_where=sa.text("is_active = 1")
        )
        batch_op.drop_index("ix_camera_active_state")

    op.drop_table("camera")
    # ### end Alembic commands ###
