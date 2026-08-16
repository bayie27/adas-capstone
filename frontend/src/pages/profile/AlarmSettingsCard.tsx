import { useState, type FormEvent } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { Input } from "@/components/ui/Input"
import { NoticeBanner, type NoticeState } from "@/components/ui/NoticeBanner"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { getAlarmSettings, updateAlarmSettings } from "@/api/settings"
import type { AlarmSettings } from "@/api/settings"
import { getApiErrorMessage } from "@/api/client"
import { previewDetectionSound, setDetectionSoundVolume } from "@/utils/detectionSound"

const ALARM_SETTINGS_QUERY_KEY = ["alarm-settings"] as const

/**
 * D-3. No Figma frame. `GET /api/settings/alarm` returns only the actor's
 * current `{alarm_sound, volume, snooze_duration}` — not `ALARM_SOUND_KEYS`,
 * not the snooze-duration bounds. Both exist only as backend validation
 * constants (Q13). Rather than hardcode them and drift the day either
 * changes, this form renders exactly what the endpoint returns and states
 * plainly where it can't offer more: the sound field is read-only (a picker
 * needs a real allowlist to populate, which doesn't exist yet) and the
 * duration field carries no client-side bound, relying on the backend's own
 * 422 message rather than a guessed range.
 */
export function AlarmSettingsCard() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<AlarmSettings | null>(null)
  const [notice, setNotice] = useState<NoticeState | null>(null)

  const settingsQuery = useQuery({
    queryKey: ALARM_SETTINGS_QUERY_KEY,
    queryFn: getAlarmSettings,
  })

  // Seed the editable form once, the moment the fetch resolves — same
  // pattern ProfileSettings uses for its own form, so a background refetch
  // can't stomp on an in-progress edit. Also the first point this session
  // learns the actor's real saved volume, so the alarm — hardcoded to the
  // browser default until now — picks it up here.
  if (settingsQuery.data && !form) {
    setForm(settingsQuery.data)
    setDetectionSoundVolume(settingsQuery.data.volume)
  }

  const mutation = useMutation({
    // Full replacement (PUT) — the backend requires all three fields on
    // every call, even one that only touched the volume slider.
    mutationFn: (input: AlarmSettings) => updateAlarmSettings(input),
    onSuccess: (updated) => {
      queryClient.setQueryData(ALARM_SETTINGS_QUERY_KEY, updated)
      setForm(updated)
      setDetectionSoundVolume(updated.volume)
      setNotice({ tone: "success", message: "Alarm settings saved." })
    },
  })

  function updateField<K extends keyof AlarmSettings>(field: K, value: AlarmSettings[K]) {
    setNotice(null)
    mutation.reset()
    setForm((current) => (current ? { ...current, [field]: value } : current))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!form || !settingsQuery.data) return

    // Saving without an actual change writes no audit row on the backend —
    // preserve that in the UI by not firing the request at all rather than
    // relying on the backend to silently no-op it.
    const unchanged =
      form.alarm_sound === settingsQuery.data.alarm_sound &&
      form.volume === settingsQuery.data.volume &&
      form.snooze_duration === settingsQuery.data.snooze_duration

    if (unchanged) {
      setNotice({ tone: "success", message: "No changes to save." })
      return
    }

    mutation.mutate(form)
  }

  const errorMessage = mutation.isError
    ? getApiErrorMessage(mutation.error, "Unable to save alarm settings.")
    : null

  return (
    <Card className="p-8">
      <div className="mb-6">
        <h2 className="text-h3 font-semibold text-fg">Alarm Settings</h2>
        <p className="text-secondary text-fg-muted">
          Control the sound and volume of the accident alarm, and how long an unverified incident
          stays muted when you snooze it.
        </p>
      </div>

      {settingsQuery.isLoading ? (
        <div className="py-12 text-center text-secondary text-fg-muted">
          Loading alarm settings...
        </div>
      ) : settingsQuery.isError ? (
        <QueryErrorBanner
          error={settingsQuery.error}
          fallback="Unable to load alarm settings."
          onRetry={() => settingsQuery.refetch()}
        />
      ) : form ? (
        <form onSubmit={handleSubmit} className="max-w-sm space-y-6">
          <div>
            <label className="mb-2 block text-caption font-semibold text-fg-body">
              Alarm Sound
            </label>
            <p className="text-secondary text-fg">{form.alarm_sound}</p>
            {/*
              A picker needs the real allowlist to populate — the backend
              validates alarm_sound against ALARM_SOUND_KEYS but never
              returns it (Q13). Showing a dropdown of one hardcoded option
              would 422 the moment a second sound is added with no warning
              at build time. This states the gap instead of hiding it.
            */}
            <p className="mt-1 text-caption text-fg-muted">
              Additional sounds aren't available yet — the server doesn't expose the list of allowed
              sounds.
            </p>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <label className="text-caption font-semibold text-fg-body">
                Volume: {form.volume}
                {form.volume === 0 ? " (Muted)" : ""}
              </label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={form.volume === 0}
                onClick={() => previewDetectionSound(form.volume)}
              >
                Test
              </Button>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={form.volume}
              disabled={mutation.isPending}
              onChange={(event) => updateField("volume", Number(event.target.value))}
              className="w-full disabled:cursor-not-allowed disabled:opacity-60"
            />
            {form.volume === 0 ? (
              <p className="mt-1 text-caption text-warning">
                The alarm is muted at this volume — it will not be audible.
              </p>
            ) : null}
          </div>

          <Input
            label="Snooze Duration (seconds)"
            type="number"
            inputMode="numeric"
            value={form.snooze_duration}
            disabled={mutation.isPending}
            onChange={(event) => updateField("snooze_duration", Number(event.target.value))}
            hint="The server enforces the allowed range; an out-of-range value is rejected on save."
          />

          {notice ? <NoticeBanner notice={notice} /> : null}
          {errorMessage ? <p className="text-caption text-danger">{errorMessage}</p> : null}

          <Button type="submit" isLoading={mutation.isPending} loadingLabel="Saving…">
            Save Alarm Settings
          </Button>
        </form>
      ) : null}
    </Card>
  )
}
