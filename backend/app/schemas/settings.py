from annotated_types import Ge, Le
from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.core.config import settings


class AlarmSettingsOptions(SQLModel):
    """P21 Step 2 — rides AlarmSettingsRead so a client can build a real
    sound picker and bound the snooze-duration field, instead of
    hardcoding a second copy of these numbers or discovering the bound
    through a 422."""

    alarm_sound_keys: list[str]
    snooze_min_seconds: int
    snooze_max_seconds: int
    volume_min: int
    volume_max: int


class AlarmSettingsRead(SQLModel):
    alarm_sound: str
    volume: int
    snooze_duration: int
    options: AlarmSettingsOptions


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


def _field_bounds(field_name: str) -> tuple[int, int]:
    """Reads ge/le straight off AlarmSettingsUpdate's own Field constraint
    metadata — the options block must never hardcode a second copy of a
    bound that could drift from the one the PUT route actually enforces."""
    metadata = AlarmSettingsUpdate.model_fields[field_name].metadata
    ge = next(m.ge for m in metadata if isinstance(m, Ge))
    le = next(m.le for m in metadata if isinstance(m, Le))
    return ge, le


def build_alarm_settings_options() -> AlarmSettingsOptions:
    volume_min, volume_max = _field_bounds("volume")
    snooze_min, snooze_max = _field_bounds("snooze_duration")
    return AlarmSettingsOptions(
        alarm_sound_keys=list(settings.ALARM_SOUND_KEYS),
        snooze_min_seconds=snooze_min,
        snooze_max_seconds=snooze_max,
        volume_min=volume_min,
        volume_max=volume_max,
    )
