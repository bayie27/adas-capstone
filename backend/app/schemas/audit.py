import json
from datetime import datetime
from typing import Any

from pydantic import field_validator
from sqlmodel import SQLModel


class AuditLogRead(SQLModel):
    audit_id: int
    actor_type: str
    user_id: int | None = None
    username: str | None = None
    role: str | None = None
    action: str
    target_type: str | None = None
    target_ref: str | None = None
    result: str
    detail: dict[str, Any] | None = None
    request_id: str | None = None
    source_ip: str | None = None
    created_at: datetime

    @field_validator("detail", mode="before")
    @classmethod
    def parse_detail(cls, v: Any) -> Any:
        """`detail` is stored as a JSON string (app/models/audit.py); the
        API exposes it as a parsed object."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
            except json.JSONDecodeError:
                # Keep legacy/plain-text audit rows readable instead of
                # failing the entire audit page when one older producer did
                # not JSON-encode its detail field.
                return {"message": v}
            if isinstance(parsed, dict):
                return parsed
            return {"value": parsed}
        return v


class AuditLogListResponse(SQLModel):
    total_filtered: int
    items: list[AuditLogRead]
