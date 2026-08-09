import logging
import logging.config
import re
from contextvars import ContextVar

from app.core.config import settings

# Bound per-request by the middleware in main.py; read by RequestIdFilter so
# every log line (and, later, every audit row) can carry the same
# correlation id without threading it through every function signature.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

# A URL with embedded credentials: scheme://user:pass@host/... . Matches the
# resolved RTSP URL (01_CONTRACTS.md §1.6) generically, not just rtsp://.
_CREDENTIAL_URL_PATTERN = re.compile(r"://[^/@\s:]+:[^/@\s]+@")


def _collect_secret_values() -> list[str]:
    """Exact-value redaction targets: real configured secrets. Doing this by
    value (rather than guessing at a JWT/token shape) reliably catches
    SECRET_KEY, INTERNAL_API_KEY, and DSS_PASS wherever they appear."""
    candidates = [
        settings.SECRET_KEY.get_secret_value(),
        settings.INTERNAL_API_KEY.get_secret_value(),
        settings.DEFAULT_ADMIN_PASSWORD.get_secret_value(),
    ]
    if settings.DSS_PASS is not None:
        candidates.append(settings.DSS_PASS.get_secret_value())
    return [value for value in candidates if value]


def _collect_path_replacements() -> dict[str, str]:
    """Absolute filesystem paths (01_CONTRACTS.md §1.6) — never logged raw."""
    return {
        str(settings.SNAPSHOT_ROOT): "<SNAPSHOT_ROOT>",
        str(settings.LEGACY_SNAPSHOT_DIR): "<LEGACY_SNAPSHOT_DIR>",
        str(settings.BACKUP_DIR): "<BACKUP_DIR>",
        str(settings.EXPORT_DIR): "<EXPORT_DIR>",
        str(settings.ARCHIVE_DIR): "<ARCHIVE_DIR>",
    }


class RedactingFilter(logging.Filter):
    """Scrubs credential-bearing URLs, known secret values, and absolute
    storage paths from every log line (01_CONTRACTS.md §1.6)."""

    def __init__(
        self,
        secrets: list[str] | None = None,
        path_replacements: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self._secrets = secrets if secrets is not None else _collect_secret_values()
        self._path_replacements = (
            path_replacements
            if path_replacements is not None
            else _collect_path_replacements()
        )

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.redact(record.getMessage())
        record.args = ()
        return True

    def redact(self, message: str) -> str:
        message = _CREDENTIAL_URL_PATTERN.sub("://***:***@", message)
        for secret in self._secrets:
            message = message.replace(secret, "***REDACTED***")
        for path, placeholder in self._path_replacements.items():
            message = message.replace(path, placeholder)
        return message


class RequestIdFilter(logging.Filter):
    """Stamps the current request's correlation id onto every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_id": {"()": RequestIdFilter},
                "redact": {"()": RedactingFilter},
            },
            "formatters": {
                "default": {
                    "format": (
                        "%(asctime)s %(levelname)s [%(request_id)s] "
                        "%(name)s: %(message)s"
                    ),
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["request_id", "redact"],
                },
            },
            "root": {
                "handlers": ["console"],
                "level": level,
            },
        }
    )
