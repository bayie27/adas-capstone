import re

from app.core.config import settings

# A URL with embedded credentials: scheme://user:pass@host/... . Matches the
# resolved RTSP URL (01_CONTRACTS.md §1.6) generically, not just rtsp://.
CREDENTIAL_URL_PATTERN = re.compile(r"://[^/@\s:]+:[^/@\s]+@")


def collect_secret_values() -> list[str]:
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


def collect_path_replacements() -> dict[str, str]:
    """Absolute filesystem paths (01_CONTRACTS.md §1.6) — never logged or
    audited raw."""
    return {
        str(settings.SNAPSHOT_ROOT): "<SNAPSHOT_ROOT>",
        str(settings.LEGACY_SNAPSHOT_DIR): "<LEGACY_SNAPSHOT_DIR>",
        str(settings.BACKUP_DIR): "<BACKUP_DIR>",
        str(settings.EXPORT_DIR): "<EXPORT_DIR>",
        str(settings.ARCHIVE_DIR): "<ARCHIVE_DIR>",
    }


def redact_text(
    message: str,
    secrets: list[str] | None = None,
    path_replacements: dict[str, str] | None = None,
) -> str:
    """Scrubs credential-bearing URLs, known secret values, and absolute
    storage paths from a single string. Shared by the logging RedactingFilter
    and the audit service's detail-dict redaction so the two never drift."""
    secrets = secrets if secrets is not None else collect_secret_values()
    path_replacements = (
        path_replacements
        if path_replacements is not None
        else collect_path_replacements()
    )
    message = CREDENTIAL_URL_PATTERN.sub("://***:***@", message)
    for secret in secrets:
        message = message.replace(secret, "***REDACTED***")
    for path, placeholder in path_replacements.items():
        message = message.replace(path, placeholder)
    return message
