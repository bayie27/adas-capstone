from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import field_validator
from sqlalchemy import CheckConstraint, Column, Index, String
from sqlmodel import Field, Relationship, SQLModel

from app.core.types import UtcDateTime
from app.core.validation import reject_null_bytes
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.detection import DetectionLog


class UserBase(SQLModel):
    username: str = Field(unique=True, index=True, min_length=3, max_length=20)
    first_name: str = Field(min_length=1, max_length=20)
    last_name: str = Field(min_length=1, max_length=20)
    role: UserRole

    @field_validator("username", "first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.strip()
        return reject_null_bytes(v)


class User(UserBase, table=True):
    __tablename__ = "user"
    __table_args__ = (
        CheckConstraint("role IN ('Admin', 'Operator')", name="ck_user_role_valid"),
    )

    # Overrides UserBase.role's inferred column type: SQLAlchemy's default
    # Enum column stores the member *name* ("ADMIN"), not its value ("Admin").
    # A plain string column stores exactly what the StrEnum's value is, which
    # is what the ck_user_role_valid CHECK constraint (and every other enum
    # column in this schema) compares against.
    role: UserRole = Field(sa_type=String)

    user_id: int | None = Field(default=None, primary_key=True)
    password_hash: str
    is_active: bool = Field(default=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=UtcDateTime
    )
    updated_at: datetime = Field(
        default=None,
        sa_column=Column(
            UtcDateTime,
            default=lambda: datetime.now(UTC),
            onupdate=lambda: datetime.now(UTC),
            nullable=False,
        ),
    )
    password_changed_at: datetime | None = Field(default=None, sa_type=UtcDateTime)
    last_login: datetime | None = Field(default=None, sa_type=UtcDateTime)

    # Relationships
    verified_detections: list["DetectionLog"] = Relationship(
        back_populates="verified_by",
        sa_relationship_kwargs={"foreign_keys": "DetectionLog.verified_by_id"},
    )
    closed_detections: list["DetectionLog"] = Relationship(
        back_populates="closed_by",
        sa_relationship_kwargs={"foreign_keys": "DetectionLog.closed_by_id"},
    )
    snoozed_detections: list["DetectionLog"] = Relationship(
        back_populates="snoozed_by",
        sa_relationship_kwargs={"foreign_keys": "DetectionLog.snoozed_by_id"},
    )
    alarm_settings: "AlarmSettings" = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"uselist": False, "passive_deletes": True},
    )


class AuthSession(SQLModel, table=True):
    """D-006 — server-side revocable session record. The JWT `sid` claim is
    this row's `session_id`."""

    __tablename__ = "auth_session"
    __table_args__ = (
        CheckConstraint(
            "revocation_reason IS NULL OR revocation_reason IN "
            "('logout', 'password_change', 'password_reset', 'role_change', "
            "'account_disabled', 'admin_revoke', 'expired_cleanup')",
            name="ck_auth_session_revocation_reason_valid",
        ),
        Index("ix_auth_session_user_revoked", "user_id", "revoked_at"),
    )

    session_id: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.user_id", index=True, ondelete="RESTRICT")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=UtcDateTime
    )
    expires_at: datetime = Field(sa_type=UtcDateTime, index=True)
    revoked_at: datetime | None = Field(default=None, sa_type=UtcDateTime)
    revocation_reason: str | None = Field(default=None)
    user_agent: str | None = Field(default=None, max_length=256)
    source_ip: str | None = Field(default=None)


class AlarmSettings(SQLModel, table=True):
    """D-004 — one row per user, created with every new account."""

    __tablename__ = "alarm_settings"
    __table_args__ = (
        CheckConstraint("volume >= 0 AND volume <= 100", name="ck_alarm_volume_range"),
        CheckConstraint(
            "snooze_duration >= 15 AND snooze_duration <= 60",
            name="ck_alarm_snooze_duration_range",
        ),
    )

    alarm_settings_id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.user_id", unique=True, ondelete="CASCADE")
    alarm_sound: str = Field(default="default")
    volume: int = Field(default=80)
    snooze_duration: int = Field(default=30)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=UtcDateTime
    )
    updated_at: datetime = Field(
        default=None,
        sa_column=Column(
            UtcDateTime,
            default=lambda: datetime.now(UTC),
            onupdate=lambda: datetime.now(UTC),
            nullable=False,
        ),
    )

    user: User = Relationship(back_populates="alarm_settings")
