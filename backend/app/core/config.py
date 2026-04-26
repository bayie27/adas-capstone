from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from pathlib import Path

ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

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

settings = Settings()
