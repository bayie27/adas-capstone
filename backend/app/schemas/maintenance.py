"""08_PKG_backup_ops.md Steps 4-5 — request/response models for
routes/maintenance.py. Never includes `artifact_path` or any absolute
filesystem path (01_CONTRACTS.md §1.6)."""

from datetime import datetime

from pydantic import field_validator
from sqlmodel import SQLModel

from app.core.validation import reject_null_bytes


class BackupRead(SQLModel):
    backup_id: str
    created_at: datetime
    origin: str
    file_size: int
    valid: bool
    checks: dict[str, bool]


class BackupListResponse(SQLModel):
    total_filtered: int
    items: list[BackupRead]


class BackupTriggerResponse(SQLModel):
    detail: str


class RestoreRequestIn(SQLModel):
    backup_id: str
    current_password: str
    confirmation: str

    @field_validator("backup_id", "current_password", "confirmation")
    @classmethod
    def no_null_bytes(cls, v: str) -> str:
        return reject_null_bytes(v)

    @staticmethod
    def expected_confirmation(backup_id: str) -> str:
        return f"RESTORE {backup_id}"


class RestoreTriggerResponse(SQLModel):
    detail: str
    backup_id: str


class RestoreStepRead(SQLModel):
    name: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: float | None = None
    ok: bool | None = None
    detail: str | None = None


class RestoreStateRead(SQLModel):
    status: str
    backup_id: str
    requested_at: datetime
    requested_by: str | None = None
    emergency_backup_id: str | None = None
    steps: list[RestoreStepRead] = []
    error: str | None = None
    completed_at: datetime | None = None
