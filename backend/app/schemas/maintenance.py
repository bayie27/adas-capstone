"""08_PKG_backup_ops.md Steps 4-5 — request/response models for
routes/maintenance.py. Never includes `artifact_path` or any absolute
filesystem path (01_CONTRACTS.md §1.6)."""

from datetime import datetime
from typing import Literal

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.core.validation import reject_null_bytes

RESTORE_CONFIRMATION_PHRASE = "RESTORE DATABASE"


class BackupRead(SQLModel):
    backup_id: str
    created_at: datetime
    origin: str
    file_size: int
    valid: bool
    checks: dict[str, bool]
    storage_tier: Literal["protected", "degraded"]
    storage_reason: str | None = None


class BackupListResponse(SQLModel):
    total_filtered: int
    items: list[BackupRead]


class BackupTriggerResponse(SQLModel):
    detail: str


class RestoreRequestIn(SQLModel):
    backup_id: str
    storage_tier: Literal["protected", "degraded"]
    current_password: str
    confirmation: str

    @field_validator("backup_id", "current_password", "confirmation")
    @classmethod
    def no_null_bytes(cls, v: str) -> str:
        return reject_null_bytes(v)

    @staticmethod
    def expected_confirmation(_backup_id: str | None = None) -> str:
        """Return the human-readable phrase required for a destructive restore.

        The selected backup id is carried by the row action and request body;
        it is never part of the phrase an Administrator has to type or
        understand. The optional argument preserves compatibility for callers
        that previously mirrored the phrase helper with the selected id.
        """
        return RESTORE_CONFIRMATION_PHRASE


class RestoreTriggerResponse(SQLModel):
    detail: str
    backup_id: str
    storage_tier: Literal["protected", "degraded"]
    request_id: str
    status: Literal["requested"] = "requested"


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
    storage_tier: Literal["protected", "degraded"] = "degraded"
    requested_at: datetime
    requested_by: str | None = None
    request_id: str | None = None
    emergency_backup_id: str | None = None
    emergency_storage_tier: Literal["protected", "degraded"] = "degraded"
    steps: list[RestoreStepRead] = Field(default_factory=list)
    error: str | None = None
    completed_at: datetime | None = None


class BackupSummaryRead(SQLModel):
    backup_id: str
    storage_tier: Literal["protected", "degraded"] = "degraded"
    created_at: datetime
    valid: bool


class LastRestartRead(SQLModel):
    ran_at: datetime
    downtime_seconds: float | None = None
    ready: bool
    exit_code: int


class RestoreCoordinatorRead(SQLModel):
    available: bool
    state: Literal["unavailable", "idle", "executing", "error"]
    platform: Literal["windows", "systemd"] | None = None
    last_seen_at: datetime | None = None
    reason: (
        Literal[
            "not_running",
            "stale",
            "runtime_uncontrolled",
            "busy",
            "error",
        ]
        | None
    ) = None


class MaintenanceStatusRead(SQLModel):
    last_scheduled_backup: BackupSummaryRead | None = None
    last_manual_backup: BackupSummaryRead | None = None
    next_scheduled_backup_at: datetime | None = None
    backup_overdue: bool
    maintenance_hour_local: int
    maintenance_timezone: str
    last_restart: LastRestartRead | None = None
    latest_restore: RestoreStateRead | None = None
    restore_coordinator: RestoreCoordinatorRead
    protected_backup_available: bool
    protected_backup_reason: str | None = None
    protection_state: Literal["protected", "degraded", "unavailable"]
    latest_protected_backup: BackupSummaryRead | None = None
    protected_backup_overdue: bool
    backup_warning: str | None = None
