"""05_PKG_incidents_cameras.md Step 5 — per-user alarm sound/volume/snooze
duration (D-004). Snoozing itself is shared incident state and lives on
`/api/alerts/{log_id}/snooze`, not here."""

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from app.api.dependencies import get_current_user
from app.core.db import get_session
from app.models import AlarmSettings, AuditResult, User
from app.schemas.settings import (
    AlarmSettingsRead,
    AlarmSettingsUpdate,
    build_alarm_settings_options,
)
from app.services import audit

router = APIRouter(
    prefix="/api/settings",
    tags=["Alarm Settings"],
    dependencies=[Depends(get_current_user)],
)

# Must match AlarmSettings' own column defaults (app/models/user.py) — the
# fallback returned when a user somehow has no settings row yet.
_DEFAULT_ALARM_SOUND = "default"
_DEFAULT_VOLUME = 80
_DEFAULT_SNOOZE_DURATION = 30


@router.get("/alarm", response_model=AlarmSettingsRead)
def get_alarm_settings(current_user: User = Depends(get_current_user)):
    """Side-effect free. Returns the defaults rather than 404 when the row
    is somehow missing — PUT creates it lazily on the next save."""
    options = build_alarm_settings_options()
    row = current_user.alarm_settings
    if row is None:
        return AlarmSettingsRead(
            alarm_sound=_DEFAULT_ALARM_SOUND,
            volume=_DEFAULT_VOLUME,
            snooze_duration=_DEFAULT_SNOOZE_DURATION,
            options=options,
        )
    return AlarmSettingsRead(
        alarm_sound=row.alarm_sound,
        volume=row.volume,
        snooze_duration=row.snooze_duration,
        options=options,
    )


@router.put("/alarm", response_model=AlarmSettingsRead)
def update_alarm_settings(
    update_in: AlarmSettingsUpdate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Full replacement, idempotent. UC-11: saving without an actual change
    writes no redundant audit row."""
    row = current_user.alarm_settings
    created = row is None
    if row is None:
        row = AlarmSettings(user_id=current_user.user_id)

    changed = (
        created
        or row.alarm_sound != update_in.alarm_sound
        or row.volume != update_in.volume
        or row.snooze_duration != update_in.snooze_duration
    )

    row.alarm_sound = update_in.alarm_sound
    row.volume = update_in.volume
    row.snooze_duration = update_in.snooze_duration
    session.add(row)

    if changed:
        audit.record(
            session,
            action="ALARM_SETTINGS_UPDATE",
            result=AuditResult.SUCCESS,
            actor=current_user,
            target_type="user",
            target_ref=str(current_user.user_id),
            detail={"target_username": current_user.username},
            source_ip=request.client.host if request.client else None,
        )

    session.commit()
    session.refresh(row)
    return AlarmSettingsRead(
        alarm_sound=row.alarm_sound,
        volume=row.volume,
        snooze_duration=row.snooze_duration,
        options=build_alarm_settings_options(),
    )
