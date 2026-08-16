import api from "@/api/client"

/**
 * GET /api/settings/alarm returns the actor's current values and nothing
 * else — no `ALARM_SOUND_KEYS` allowlist, no `SNOOZE_MIN_SECONDS`/
 * `SNOOZE_MAX_SECONDS`. Those exist only as backend validation constants
 * (`app/schemas/settings.py`, reading `app.core.config.settings`), so this
 * type deliberately has no field for them either — the frontend cannot
 * assert bounds the backend has never sent. See Q13, filed as a `gh issue
 * create` in Phase 14's PR body: a `GET /api/settings/alarm/options` (or
 * equivalent) is what would let the sound picker and the duration bounds be
 * built for real instead of rendered around their absence.
 */
export interface AlarmSettings {
  alarm_sound: string
  volume: number
  snooze_duration: number
}

/**
 * `PUT /api/settings/alarm` is a **full replacement** — all three fields are
 * required on every call, even one that only changes the volume slider.
 * Saving without an actual change writes no audit row (backend behaviour);
 * callers should skip the request entirely when nothing changed rather than
 * relying on the backend to no-op it silently.
 */
export type AlarmSettingsUpdate = AlarmSettings

export async function getAlarmSettings() {
  const { data } = await api.get<AlarmSettings>("/settings/alarm")
  return data
}

export async function updateAlarmSettings(input: AlarmSettingsUpdate) {
  const { data } = await api.put<AlarmSettings>("/settings/alarm", input)
  return data
}
