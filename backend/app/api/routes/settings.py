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

    # A freshly-constructed row already carries AlarmSettings' own column
    # defaults (must match _DEFAULT_ALARM_SOUND et al. above), so these are
    # a correct "from" snapshot in both the update and the first-ever-save
    # case, with no separate branch needed for `created`.
    old_alarm_sound = row.alarm_sound
    old_volume = row.volume
    old_snooze_duration = row.snooze_duration

    sound_changed = created or old_alarm_sound != update_in.alarm_sound
    volume_changed = created or old_volume != update_in.volume
    snooze_changed = created or old_snooze_duration != update_in.snooze_duration
    changed = sound_changed or volume_changed or snooze_changed

    row.alarm_sound = update_in.alarm_sound
    row.volume = update_in.volume
    row.snooze_duration = update_in.snooze_duration
    session.add(row)

    if changed:
        changed_fields = [
            field
            for field, is_changed in (
                ("alarm_sound", sound_changed),
                ("volume", volume_changed),
                ("snooze_duration", snooze_changed),
            )
            if is_changed
        ]
        detail: dict = {
            "changed_fields": changed_fields,
            "target_username": current_user.username,
        }
        # Only the fields that actually changed get a from/to pair — an
        # unchanged field repeated as a no-op from==to entry would just be
        # noise on every save that only touched one of the other two.
        if sound_changed:
            detail["alarm_sound_from"] = old_alarm_sound
            detail["alarm_sound_to"] = update_in.alarm_sound
        if volume_changed:
            detail["volume_from"] = old_volume
            detail["volume_to"] = update_in.volume
        if snooze_changed:
            detail["snooze_duration_from"] = old_snooze_duration
            detail["snooze_duration_to"] = update_in.snooze_duration

        audit.record(
            session,
            action="ALARM_SETTINGS_UPDATE",
            result=AuditResult.SUCCESS,
            actor=current_user,
            target_type="user",
            target_ref=str(current_user.user_id),
            detail=detail,
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
