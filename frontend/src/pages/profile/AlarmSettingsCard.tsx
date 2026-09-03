import { useCallback, useEffect, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { Badge, BadgeDot } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { FilterSelect } from "@/components/ui/FilterSelect"
import { Input } from "@/components/ui/Input"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { getAlarmSettings, updateAlarmSettings } from "@/api/settings"
import type { AlarmSettings } from "@/api/settings"
import { getApiErrorMessage } from "@/api/client"
import {
  previewDetectionSound,
  setDetectionSound,
  setDetectionSoundVolume,
  stopPreviewDetectionSound,
} from "@/utils/detectionSound"
import { toast } from "@/store/useToastStore"
import { cn } from "@/utils/cn"

const ALARM_SETTINGS_QUERY_KEY = ["alarm-settings"] as const

// How long a field has to sit still (no edits, no Test-button presses) before
// the settled value is sent. A single delay for every field keeps the model
// simple: it's not "debounce per field," it's "debounce the save," and any
// interaction that means the user is still deciding — including a Test
// press that doesn't itself change a value — pushes the save back out.
const AUTOSAVE_DEBOUNCE_MS = 900

/** `alert_chime` -> "Alert Chime" — the backend sends raw allowlist keys,
 * not display labels (confirmed: `AlarmSettingsOptions.alarm_sound_keys` is
 * `list[str]`, nothing else). */
function formatSoundLabel(key: string): string {
  return key
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")
}

type SaveStatus = "saving" | "error" | "pending" | "saved"

function SaveStatusBadge({ status, onRetry }: { status: SaveStatus; onRetry: () => void }) {
  switch (status) {
    case "saving":
      return (
        <Badge
          tone="neutral"
          variant="subtle"
          icon={<BadgeDot tone="neutral" className="animate-pulse" />}
        >
          Saving…
        </Badge>
      )
    case "pending":
      return (
        <Badge tone="warning" variant="subtle" icon={<BadgeDot tone="warning" />}>
          Unsaved changes
        </Badge>
      )
    case "error":
      return (
        <div className="flex items-center gap-2">
          <Badge tone="danger" variant="subtle" icon={<BadgeDot tone="danger" />}>
            Couldn&apos;t save
          </Badge>
          <button
            type="button"
            onClick={onRetry}
            className="text-caption font-medium text-fg underline-offset-2 hover:underline"
          >
            Retry
          </button>
        </div>
      )
    case "saved":
      return (
        <Badge tone="success" variant="subtle" icon={<BadgeDot tone="success" />}>
          All changes saved
        </Badge>
      )
  }
}

/**
 * D-3. `GET`/`PUT /api/settings/alarm` now return `options` alongside the
 * three values (P21 Step 2) -- the real sound allowlist and the real
 * snooze/volume bounds, sourced from the backend's own config rather than a
 * second copy of a number that could drift from what the PUT route
 * actually enforces.
 */
export function AlarmSettingsCard({ className }: { className?: string } = {}) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<AlarmSettings | null>(null)
  const [snoozeInput, setSnoozeInput] = useState<string>("")
  const [validationError, setValidationError] = useState<string | null>(null)

  useEffect(() => {
    return () => {
      stopPreviewDetectionSound()
    }
  }, [])

  const settingsQuery = useQuery({
    queryKey: ALARM_SETTINGS_QUERY_KEY,
    queryFn: getAlarmSettings,
  })

  // Seed the editable form once, the moment the fetch resolves — same
  // pattern ProfileSettings uses for its own form, so a background refetch
  // can't stomp on an in-progress edit. Also syncs the alarm sound and
  // volume to the detection sound engine.
  if (settingsQuery.data && !form) {
    setForm(settingsQuery.data)
    setSnoozeInput(String(settingsQuery.data.snooze_duration))
    setDetectionSound(settingsQuery.data.alarm_sound, settingsQuery.data.volume)
  }

  const mutation = useMutation({
    // Full replacement (PUT) — the backend requires all three fields on
    // every call, even one that only touched the volume slider.
    mutationFn: (input: AlarmSettings) => updateAlarmSettings(input),
    onSuccess: (updated) => {
      queryClient.setQueryData(ALARM_SETTINGS_QUERY_KEY, updated)
      setForm(updated)
      setSnoozeInput(String(updated.snooze_duration))
      setDetectionSound(updated.alarm_sound, updated.volume)
      setValidationError(null)
    },
    onError: (error) => {
      const message = getApiErrorMessage(error, "Unable to save alarm settings.")
      toast.error(message)
    },
    onSettled: () => {
      // An edit that arrived while this save was in flight was queued
      // rather than fired concurrently — send it now, on the settled state.
      if (queuedRef.current) {
        queuedRef.current = false
        flush()
      }
    },
  })

  // Refs mirror the latest render's state so the debounce timer and the
  // unmount/beforeunload handlers — which close over this callback long
  // before it actually fires — always read current values instead of a
  // stale snapshot from whichever render scheduled them.
  const formRef = useRef(form)
  const snoozeInputRef = useRef(snoozeInput)
  const settingsDataRef = useRef(settingsQuery.data)
  const mutationRef = useRef(mutation)
  useEffect(() => {
    formRef.current = form
    snoozeInputRef.current = snoozeInput
    settingsDataRef.current = settingsQuery.data
    mutationRef.current = mutation
  })

  const saveTimerRef = useRef<number | null>(null)
  const queuedRef = useRef(false)

  const dirty =
    form && settingsQuery.data
      ? form.alarm_sound !== settingsQuery.data.alarm_sound ||
        form.volume !== settingsQuery.data.volume ||
        snoozeInput.trim() !== String(settingsQuery.data.snooze_duration)
      : false

  const clearSaveTimer = useCallback(() => {
    if (saveTimerRef.current !== null) {
      window.clearTimeout(saveTimerRef.current)
      saveTimerRef.current = null
    }
  }, [])

  // The one place that actually sends the PUT. Validates and diffs against
  // the last-synced server value first — an invalid or unchanged snapshot
  // never reaches the network, which is what keeps ALARM_SETTINGS_UPDATE
  // audit rows tied to real settled edits instead of every keystroke/tick.
  const flush = useCallback(() => {
    clearSaveTimer()
    const data = settingsDataRef.current
    const currentForm = formRef.current
    if (!data || !currentForm) return

    const trimmed = snoozeInputRef.current.trim()
    const durationNum = parseInt(trimmed, 10)

    if (!trimmed || isNaN(durationNum)) {
      setValidationError("Please enter a valid snooze duration.")
      return
    }

    if (
      durationNum < currentForm.options.snooze_min_seconds ||
      durationNum > currentForm.options.snooze_max_seconds
    ) {
      setValidationError(
        `Snooze duration must be between ${currentForm.options.snooze_min_seconds} and ${currentForm.options.snooze_max_seconds} seconds.`,
      )
      return
    }

    const isUnchanged =
      currentForm.alarm_sound === data.alarm_sound &&
      currentForm.volume === data.volume &&
      durationNum === data.snooze_duration

    if (isUnchanged) return

    if (mutationRef.current.isPending) {
      queuedRef.current = true
      return
    }

    setValidationError(null)
    mutationRef.current.mutate({ ...currentForm, snooze_duration: durationNum })
  }, [clearSaveTimer])

  const scheduleSave = useCallback(() => {
    clearSaveTimer()
    saveTimerRef.current = window.setTimeout(() => {
      saveTimerRef.current = null
      flush()
    }, AUTOSAVE_DEBOUNCE_MS)
  }, [clearSaveTimer, flush])

  function updateField<K extends keyof AlarmSettings>(field: K, value: AlarmSettings[K]) {
    // Fields are disabled while a save is in flight, so this can only run
    // between saves — safe to clear a previous attempt's error state here
    // rather than have the badge show a stale "Couldn't save" until the
    // next debounce fires.
    mutation.reset()
    setValidationError(null)
    setForm((current) => (current ? { ...current, [field]: value } : current))
    scheduleSave()
  }

  const status: SaveStatus = mutation.isPending
    ? "saving"
    : validationError || mutation.isError
      ? "error"
      : dirty
        ? "pending"
        : "saved"

  return (
    <Card className={cn("p-8", className)}>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[18px] font-semibold text-fg">Alarm Settings</h2>
          <p className="text-secondary text-fg-muted">
            Control the sound and volume of the accident alarm, and how long an unverified incident
            stays muted when you snooze it.
          </p>
        </div>
        {form ? <SaveStatusBadge status={status} onRetry={flush} /> : null}
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
        <div className="max-w-sm space-y-6">
          <div>
            <label className="mb-2 block text-caption font-semibold text-fg-body">
              Alarm Sound
            </label>
            <FilterSelect
              value={form.alarm_sound}
              options={form.options.alarm_sound_keys.map((key) => ({
                value: key,
                label: formatSoundLabel(key),
              }))}
              onChange={(value) => {
                updateField("alarm_sound", value)
                if (form.volume > 0) previewDetectionSound(value, form.volume)
              }}
              disabled={mutation.isPending}
              className="w-full"
            />
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
                disabled={form.volume === 0 || mutation.isPending}
                onClick={() => {
                  previewDetectionSound(form.alarm_sound, form.volume)
                  // Auditioning the current value is still "deciding" —
                  // push the save back out so a preview between two
                  // slider drags doesn't split one adjustment into two
                  // separate audit rows.
                  scheduleSave()
                }}
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
              onChange={(event) => {
                const vol = Number(event.target.value)
                updateField("volume", vol)
                setDetectionSoundVolume(vol)
              }}
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
            min={form.options.snooze_min_seconds}
            max={form.options.snooze_max_seconds}
            value={snoozeInput}
            disabled={mutation.isPending}
            onChange={(event) => {
              mutation.reset()
              setValidationError(null)
              setSnoozeInput(event.target.value)
              scheduleSave()
            }}
            onBlur={flush}
            onKeyDown={(event) => {
              if (event.key === "Enter") event.currentTarget.blur()
            }}
            hint={`Must be between ${form.options.snooze_min_seconds} and ${form.options.snooze_max_seconds} seconds.`}
          />

          {validationError ? <p className="text-caption text-danger">{validationError}</p> : null}
        </div>
      ) : null}
    </Card>
  )
}
