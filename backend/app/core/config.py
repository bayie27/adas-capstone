from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, field_validator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV_FILE = REPO_ROOT / ".env"

class Settings(BaseSettings):
    # Security
    SECRET_KEY: SecretStr
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # Internal API Webhook
    INTERNAL_API_KEY: SecretStr

    # Database
    DATABASE_URL: str
    DEFAULT_ADMIN_PASSWORD: str

    # Dahua DSS Pro VMS Gateway Credentials
    DSS_IP: str
    DSS_PORT: int
    DSS_USERNAME: str
    DSS_PASS: SecretStr

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

settings = Settings()
