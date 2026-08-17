import api from "@/api/client"

/**
 * `GET`/`PUT /api/settings/alarm` both return this alongside the three
 * values (P21 Step 2, `schemas/settings.py`) — every bound sourced from the
 * backend's own config and field constraints, never a second copy the
 * frontend could drift from. `alarm_sound_keys` is `["default"]` today; a
 * one-option select is the honest render of that, not a reason to hide it.
 */
export interface AlarmSettingsOptions {
  alarm_sound_keys: string[]
  snooze_min_seconds: number
  snooze_max_seconds: number
  volume_min: number
  volume_max: number
}

export interface AlarmSettings {
  alarm_sound: string
  volume: number
  snooze_duration: number
  options: AlarmSettingsOptions
}

/**
 * `PUT /api/settings/alarm` is a **full replacement** of the three writable
 * fields — required on every call, even one that only changes the volume
 * slider. `options` is read-only and server-owned, so this is its own type
 * rather than an alias of `AlarmSettings`: the backend ignores an
 * unexpected `options` key on the body rather than rejecting it, so sending
 * it wouldn't fail loudly, it would just be noise on every save. Saving
 * without an actual change writes no audit row (backend behaviour); callers
 * should skip the request entirely when nothing changed rather than relying
 * on the backend to no-op it silently.
 */
export interface AlarmSettingsUpdate {
  alarm_sound: string
  volume: number
  snooze_duration: number
}

export async function getAlarmSettings() {
  const { data } = await api.get<AlarmSettings>("/settings/alarm")
  return data
}

export async function updateAlarmSettings(input: AlarmSettingsUpdate) {
  const { data } = await api.put<AlarmSettings>("/settings/alarm", input)
  return data
}
