from typing import Any

from sqlmodel import SQLModel


class ApiError(SQLModel):
    detail: str
    code: str
    errors: list[dict[str, Any]] | None = None


def validate_password_strength(v: str) -> str:
    if not any(char.isdigit() for char in v):
        raise ValueError("Password must contain at least 1 number.")
    return v


# 01_CONTRACTS.md §1.3 — the stable error-code catalog. A route that needs a
# more specific code than its status code's generic default (e.g.
# CONFLICT_DUPLICATE instead of CONFLICT_STATE for a 409) raises its
# HTTPException with that code explicitly; this table only supplies the
# fallback for routes that haven't been updated to do so yet.
_DEFAULT_ERROR_CODES: dict[int, str] = {
    400: "PRECONDITION_FAILED",
    401: "AUTH_REQUIRED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT_STATE",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "AUTH_RATE_LIMITED",
    500: "INTERNAL_SERVER_ERROR",
    503: "TEMPORARILY_UNAVAILABLE",
}


def default_error_code(status_code: int) -> str:
    return _DEFAULT_ERROR_CODES.get(status_code, f"HTTP_{status_code}")
