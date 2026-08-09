import logging
import logging.config
from contextvars import ContextVar

from app.core.redaction import (
    collect_path_replacements,
    collect_secret_values,
    redact_text,
)

# Bound per-request by the middleware in main.py; read by RequestIdFilter so
# every log line (and, later, every audit row) can carry the same
# correlation id without threading it through every function signature.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RedactingFilter(logging.Filter):
    """Scrubs credential-bearing URLs, known secret values, and absolute
    storage paths from every log line (01_CONTRACTS.md §1.6). Delegates the
    actual substitution to app.core.redaction, shared with the audit
    service's detail-dict redaction."""

    def __init__(
        self,
        secrets: list[str] | None = None,
        path_replacements: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self._secrets = secrets if secrets is not None else collect_secret_values()
        self._path_replacements = (
            path_replacements
            if path_replacements is not None
            else collect_path_replacements()
        )

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.redact(record.getMessage())
        record.args = ()
        return True

    def redact(self, message: str) -> str:
        return redact_text(message, self._secrets, self._path_replacements)


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
