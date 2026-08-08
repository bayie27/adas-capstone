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
