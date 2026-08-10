from pathlib import Path
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV_FILE = REPO_ROOT / ".env"


def _resolve_repo_path(value: Path) -> Path:
    """Anchor a relative path to REPO_ROOT so it no longer depends on CWD."""
    if value.is_absolute():
        return value
    return (REPO_ROOT / value).resolve()


class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: Literal["development", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    SQL_ECHO: bool = False

    # Security
    SECRET_KEY: SecretStr
    ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "adas-backend"
    JWT_AUDIENCE: str = "adas-dashboard"

    # Sessions (D-006)
    SESSION_LIFETIME_MINUTES: int = 480
    SESSION_COOKIE_NAME: str = "adas_session"
    SESSION_COOKIE_SECURE: bool = True

    # CORS
    # NoDecode: without it, pydantic-settings tries to JSON-decode the raw
    # env value before our comma-split validator ever runs, and a plain
    # "a,b" string isn't valid JSON — it would hard-fail Settings() itself.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Login rate limiting
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 10
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300

    # Internal API Webhook
    INTERNAL_API_KEY: SecretStr

    # Database
    DATABASE_URL: str = "sqlite:///./adas.db"
    DEFAULT_ADMIN_PASSWORD: SecretStr
    SQLITE_BUSY_TIMEOUT_MS: int = 5000

    # Scheduler (P1 Step 7)
    SCHEDULER_ENABLED: bool = True

    # Storage roots
    SNAPSHOT_ROOT: Path = Path("ai_engine/snapshots")
    LEGACY_SNAPSHOT_DIR: Path = Path("ai_engine/snapshots")
    BACKUP_DIR: Path = Path("var/backups")
    EXPORT_DIR: Path = Path("var/exports")
    ARCHIVE_DIR: Path = Path("var/archive")

    # RTSP construction (backend-owned, §7.2)
    RTSP_URL_TEMPLATE: str = "rtsp://localhost:8554/channel{channel_id}"

    # Dahua DSS Pro VMS Gateway Credentials — optional, consumed only by
    # RTSP_URL_TEMPLATE when it references them.
    DSS_IP: str | None = None
    DSS_PORT: int | None = None
    DSS_USERNAME: str | None = None
    DSS_PASS: SecretStr | None = None

    # Alarm settings (D-004)
    ALARM_SOUND_KEYS: Annotated[list[str], NoDecode] = ["default"]
    SNOOZE_MIN_SECONDS: int = 15
    SNOOZE_MAX_SECONDS: int = 60
    DISMISS_COOLDOWN_SECONDS: int = 60

    # Heartbeat / health (D-003, D-009)
    HEARTBEAT_STALE_SECONDS: int = 10
    HEALTH_SAMPLE_SECONDS: int = 5
    HEALTH_PERSIST_SECONDS: int = 300
    HEALTH_RAW_RETENTION_HOURS: int = 48
    HEALTH_HOURLY_RETENTION_DAYS: int = 30
    GPU_TEMP_CRITICAL_C: float = 85
    RAM_CRITICAL_PCT: float = 95
    DISK_WARNING_PCT: float = 80
    DISK_CRITICAL_PCT: float = 90

    # Exports (D-010)
    EXPORT_PDF_MAX_ROWS: int = 10000
    EXPORT_CSV_MAX_ROWS: int = 50000
    EXPORT_ARTIFACT_TTL_HOURS: int = 72
    # D-010 — "one bounded local worker on the demo profile; concurrency is
    # configurable for future hardware." No Celery/Redis/broker.
    EXPORT_JOB_WORKERS: int = 1
    # IANA zone name for the "configured local-display timestamp" every PDF
    # report shows alongside its UTC generation time (01_CONTRACTS.md §1.1,
    # D-010). The Philippines has no DST, so this is a fixed offset in
    # practice, but the setting stays named/typed for portability.
    REPORT_LOCAL_TIMEZONE: str = "Asia/Manila"

    # WebSocket (D-008)
    WS_MAX_CONNECTIONS_TOTAL: int = 50
    WS_MAX_CONNECTIONS_PER_USER: int = 5
    WS_QUEUE_MAXSIZE: int = 100
    WS_SEND_TIMEOUT_SECONDS: float = 5

    # Backups (D-011)
    BACKUP_DAILY_RETENTION: int = 30
    BACKUP_MANUAL_RETENTION: int = 10

    # Maintenance
    MAINTENANCE_HOUR_LOCAL: int = 3

    # Automatically load from the .env file in the root directory
    model_config = SettingsConfigDict(env_file=ROOT_ENV_FILE, extra="ignore")

    @field_validator("DATABASE_URL")
    @classmethod
    def resolve_sqlite_path(cls, v: str) -> str:
        """Anchor a relative SQLite path to REPO_ROOT so it no longer depends on CWD."""
        prefix = "sqlite:///"
        if not v.startswith(prefix):
            return v

        path_str = v[len(prefix) :]
        if path_str == ":memory:" or Path(path_str).is_absolute():
            return v

        resolved = (REPO_ROOT / path_str).resolve()
        return f"{prefix}{resolved.as_posix()}"

    @field_validator(
        "SNAPSHOT_ROOT",
        "LEGACY_SNAPSHOT_DIR",
        "BACKUP_DIR",
        "EXPORT_DIR",
        "ARCHIVE_DIR",
    )
    @classmethod
    def resolve_repo_relative_path(cls, v: Path) -> Path:
        return _resolve_repo_path(v)

    @field_validator("CORS_ORIGINS", "ALARM_SOUND_KEYS", mode="before")
    @classmethod
    def split_comma_separated(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_secret_key(self) -> "Settings":
        if (
            self.ENVIRONMENT == "production"
            and len(self.SECRET_KEY.get_secret_value()) < 32
        ):
            raise ValueError(
                "SECRET_KEY must be at least 32 characters long when ENVIRONMENT=production."
            )
        return self


settings = Settings()
