import json
import logging

from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.core.logging import request_id_ctx
from app.core.redaction import redact_text
from app.models import AuditLog, AuditResult, User

logger = logging.getLogger("uvicorn.error")

# Key names that are always fully masked in an audit `detail` dict, on top of
# the text-level redaction every string value also goes through
# (01_CONTRACTS.md §1.6 — secrets that must never leave the backend).
_BANNED_DETAIL_KEYS = {
    "password",
    "old_password",
    "new_password",
    "password_hash",
    "token",
    "access_token",
    "jwt",
    "cookie",
    "session_token",
    "api_key",
    "internal_api_key",
    "secret_key",
    "secret",
    "authorization",
}


def _redact_detail_value(value):
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {
            key: (
                "***REDACTED***"
                if key.lower() in _BANNED_DETAIL_KEYS
                else _redact_detail_value(val)
            )
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_redact_detail_value(item) for item in value]
    return value


def record(
    session: Session,
    *,
    action: str,
    result: AuditResult = AuditResult.SUCCESS,
    actor: User | None = None,
    actor_username: str | None = None,
    target_type: str | None = None,
    target_ref: str | None = None,
    detail: dict | None = None,
    source_ip: str | None = None,
) -> AuditLog:
    """D-007 append-only audit row. Adds to the caller's session and does
    **not** commit — coupling a successful action to its audit row(s) in one
    transaction is the caller's job (see record_out_of_band for the
    denied/failure path, which cannot share a rolled-back transaction).

    `actor_username` lets a failed login snapshot the *attempted* username
    even when no matching User row exists (D-007: "Failed logins can be
    recorded without a user foreign key while retaining the attempted
    normalized username and result")."""
    username = actor.username if actor is not None else actor_username
    role = str(actor.role) if actor is not None else None
    request_id = request_id_ctx.get()

    audit_log = AuditLog(
        actor_type="user"
        if (actor is not None or actor_username is not None)
        else "system",
        user_id=actor.user_id if actor is not None else None,
        username=username,
        role=role,
        action=action,
        target_type=target_type,
        target_ref=target_ref,
        result=str(result),
        detail=(
            json.dumps(_redact_detail_value(detail), default=str)
            if detail is not None
            else None
        ),
        request_id=None if request_id == "-" else request_id,
        source_ip=source_ip,
    )
    session.add(audit_log)
    return audit_log


def record_out_of_band(
    engine: Engine,
    *,
    action: str,
    result: AuditResult,
    actor: User | None = None,
    actor_username: str | None = None,
    target_type: str | None = None,
    target_ref: str | None = None,
    detail: dict | None = None,
    source_ip: str | None = None,
) -> None:
    """D-007 — for `denied`/`failure` results, which by definition cannot
    share the primary transaction (it already rolled back, or never
    started). Opens its own short-lived session and commits immediately.
    If *that* write also fails, the original action stays denied/failed
    regardless — this only logs a critical structured error and swallows,
    it never raises into the caller."""
    try:
        with Session(engine) as out_of_band_session:
            record(
                out_of_band_session,
                action=action,
                result=result,
                actor=actor,
                actor_username=actor_username,
                target_type=target_type,
                target_ref=target_ref,
                detail=detail,
                source_ip=source_ip,
            )
            out_of_band_session.commit()
    except Exception:
        logger.critical(
            "Failed to write out-of-band audit row for action=%s result=%s "
            "target_type=%s target_ref=%s",
            action,
            result,
            target_type,
            target_ref,
            exc_info=True,
        )
