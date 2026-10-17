"""Additive MFA persistence used by the staged P1–P3 implementation."""

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, Column, Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.types import UtcDateTime


class MfaCredential(SQLModel, table=True):
    """One per-user factor state; secrets are stored only as Fernet ciphertext."""

    __tablename__ = "mfa_credential"
    __table_args__ = (
        CheckConstraint(
            "state IN ('unenrolled', 'enrolled', 'recovery_pending')",
            name="ck_mfa_credential_state_valid",
        ),
        CheckConstraint(
            "credential_version >= 0",
            name="ck_mfa_credential_version_nonnegative",
        ),
        CheckConstraint(
            "last_accepted_step IS NULL OR last_accepted_step >= 0",
            name="ck_mfa_credential_last_step_nonnegative",
        ),
        CheckConstraint(
            "recovery_generation >= 0",
            name="ck_mfa_credential_recovery_generation_nonnegative",
        ),
        CheckConstraint(
            "(state = 'enrolled' AND active_secret_ciphertext IS NOT NULL "
            "AND enrolled_at IS NOT NULL) OR "
            "(state <> 'enrolled' AND active_secret_ciphertext IS NULL "
            "AND last_accepted_step IS NULL AND enrolled_at IS NULL)",
            name="ck_mfa_credential_active_secret_matches_state",
        ),
    )

    user_id: int = Field(
        primary_key=True,
        foreign_key="user.user_id",
        ondelete="CASCADE",
    )
    state: str = Field(default="unenrolled")
    active_secret_ciphertext: str | None = Field(default=None)
    credential_version: int = Field(default=0)
    last_accepted_step: int | None = Field(default=None)
    enrolled_at: datetime | None = Field(default=None, sa_type=UtcDateTime)
    recovery_started_at: datetime | None = Field(default=None, sa_type=UtcDateTime)
    recovery_generation: int = Field(default=0)
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


class MfaChallenge(SQLModel, table=True):
    """The single short-lived, one-purpose MFA flow allowed per user."""

    __tablename__ = "mfa_challenge"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_mfa_challenge_token_hash"),
        CheckConstraint(
            "length(token_hash) = 64",
            name="ck_mfa_challenge_token_hash_length",
        ),
        CheckConstraint(
            "purpose IN ('login', 'enroll', 'recovery_verify', "
            "'recovery_enroll', 'replace')",
            name="ck_mfa_challenge_purpose_valid",
        ),
        CheckConstraint(
            "credential_version >= 0",
            name="ck_mfa_challenge_credential_version_nonnegative",
        ),
        CheckConstraint(
            "(purpose IN ('enroll', 'recovery_enroll', 'replace') "
            "AND pending_secret_ciphertext IS NOT NULL) OR "
            "(purpose IN ('login', 'recovery_verify') "
            "AND pending_secret_ciphertext IS NULL)",
            name="ck_mfa_challenge_pending_secret_matches_purpose",
        ),
    )

    user_id: int = Field(
        primary_key=True,
        foreign_key="user.user_id",
        ondelete="CASCADE",
    )
    token_hash: str = Field(max_length=64)
    purpose: str
    credential_version: int = Field(default=0)
    password_changed_at: datetime | None = Field(default=None, sa_type=UtcDateTime)
    pending_secret_ciphertext: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=UtcDateTime
    )
    expires_at: datetime = Field(sa_type=UtcDateTime)


class MfaRecoveryCode(SQLModel, table=True):
    """Hashed, generation-scoped single-use recovery proof."""

    __tablename__ = "mfa_recovery_code"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "generation",
            "code_hash",
            name="uq_mfa_recovery_code_user_generation_hash",
        ),
        CheckConstraint(
            "generation >= 1",
            name="ck_mfa_recovery_code_generation_positive",
        ),
        CheckConstraint(
            "length(code_hash) = 64",
            name="ck_mfa_recovery_code_hash_length",
        ),
        Index(
            "ix_mfa_recovery_code_user_generation_consumed",
            "user_id",
            "generation",
            "consumed_at",
        ),
    )

    recovery_code_id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.user_id", ondelete="CASCADE")
    generation: int
    code_hash: str = Field(max_length=64)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=UtcDateTime
    )
    consumed_at: datetime | None = Field(default=None, sa_type=UtcDateTime)
