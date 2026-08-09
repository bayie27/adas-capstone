from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.core.config import settings


class AlarmSettingsRead(SQLModel):
    alarm_sound: str
    volume: int
    snooze_duration: int


class AlarmSettingsUpdate(SQLModel):
    """PUT /api/settings/alarm — full replacement (01_CONTRACTS.md §5.6)."""

    alarm_sound: str
    volume: int = Field(ge=0, le=100)
    snooze_duration: int = Field(
        ge=settings.SNOOZE_MIN_SECONDS, le=settings.SNOOZE_MAX_SECONDS
    )

    @field_validator("alarm_sound")
    @classmethod
    def alarm_sound_allowlisted(cls, v: str) -> str:
        """D-004: the sound enum must match real frontend audio assets, so
        it's a config allowlist (currently just `["default"]`) rather than a
        hardcoded StrEnum."""
        if v not in settings.ALARM_SOUND_KEYS:
            allowed = ", ".join(settings.ALARM_SOUND_KEYS)
            raise ValueError(f"alarm_sound must be one of: {allowed}")
        return v
