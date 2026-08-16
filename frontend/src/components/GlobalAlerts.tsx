import { useCallback, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/Button"
import { Modal } from "@/components/ui/Modal"
import { SnapshotImage } from "@/components/ui/SnapshotImage"
import { isSnoozedNow, useAlertStore } from "@/store/useAlertStore"
import { useNow } from "@/hooks/useNow"
import {
  confirmAlert,
  dismissAlert,
  getIncidentConflict,
  resolveAlert,
  snoozeAlert,
} from "@/api/alerts"
import { IncidentHandledNotice } from "@/components/ui/IncidentHandledNotice"
import type { IncidentHandledInfo } from "@/api/alerts"
import { formatAlertConfidence } from "@/utils/format"
import { formatDuration, formatFullDateTime, secondsSince } from "@/utils/datetime"
import { getApiErrorMessage } from "@/api/client"
import { cn } from "@/utils/cn"

/**
 * Above this age, a detection is presented as delayed rather than current.
 * 90s comfortably clears the sub-second happy path and the outbox's first
 * two retries (2s, 4s), so it only fires on a genuine delivery delay.
 */
const STALE_DETECTION_SECONDS = 90

/**
 * The alarm dialog — the product's reason for existing.
 *
 * Rebuilt on `Modal` so it inherits body-scroll lock and focus-on-open from
 * `useOverlayBehavior`, which it previously had neither of: it hand-rolled its
 * own fixed overlay, on the single most important dialog in the app.
 *
 * **Escape is deliberately inert here**, which is the one thing it does not
 * take from `Modal`. There is no "close" for an accident alarm — the only ways
 * out are Dismiss, Confirm or Resolve, each a real HITL decision the backend
 * records. `onClose` is a no-op and the backdrop is not clickable, so a stray
 * keypress cannot silence a live alert. (Closing it would not even work: the
 * incident stays in the store, so the dialog would immediately re-render.)
 */
export function GlobalAlerts() {
  const queryClient = useQueryClient()
  const alerts = useAlertStore((state) => state.alerts)
  const snoozedUntil = useAlertStore((state) => state.snoozedUntil)
  const removeAlert = useAlertStore((state) => state.removeAlert)
  const activateSnooze = useAlertStore((state) => state.activateSnooze)
  const [loadingId, setLoadingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState<IncidentHandledInfo | null>(null)

  // Ticked at 30s because the only thing it drives is a minutes-resolution
  // age line. A per-second interval on a dialog an operator stares at during
  // an incident buys nothing and re-renders the snapshot.
  const now = useNow(true, 30_000)

  // Snoozed incidents (FR-07) mute the alarm modal for that incident until
  // the shared deadline expires or a RE_ALARM event reactivates it.
  const activeAlerts = alerts.filter((a) => !isSnoozedNow(a.log_id, snoozedUntil))
  const alert = activeAlerts[0]

  const noop = useCallback(() => {}, [])

  if (!alert) return null

  const detectionAgeSeconds = secondsSince(alert.detected_at, now)
  const busy = loadingId === alert.log_id
  const isUnverified = alert.detection_status === "Unverified"
  const isOngoing = alert.detection_status === "Ongoing"

  function invalidateAlerts() {
    queryClient.invalidateQueries({ queryKey: ["alerts"] })
  }

  async function runAction(action: (logId: number) => Promise<unknown>, failure: string) {
    const logId = alert.log_id
    setLoadingId(logId)
    setError(null)
    setConflict(null)
    try {
      await action(logId)
      removeAlert(logId)
      invalidateAlerts()
    } catch (err) {
      // A lost race is not a failure to retry — a colleague already decided.
      // Name them, drop the incident from this queue, and let the operator
      // move to the next alert rather than re-clicking a button that cannot
      // succeed.
      const raceLost = getIncidentConflict(err)
      if (raceLost) {
        setConflict(raceLost)
        invalidateAlerts()
      } else {
        setError(getApiErrorMessage(err, failure))
      }
    } finally {
      setLoadingId(null)
    }
  }

  async function handleSnooze() {
    const logId = alert.log_id
    setLoadingId(logId)
    setError(null)
    setConflict(null)
    try {
      const snoozed = await snoozeAlert(logId)
      // Applied directly from the response rather than waiting for the
      // SNOOZE_ACTIVATED broadcast — this tab acted, so it shouldn't need
      // to hear its own echo to mute. Other connected tabs still get it via
      // the broadcast, same as every other transition in this component.
      if (snoozed.snoozed_until) {
        activateSnooze(logId, snoozed.snoozed_until)
      }
    } catch (err) {
      // Same distinction runAction makes for confirm/dismiss/resolve: a lost
      // race (409 CONFLICT_STATE) names the colleague who got there first,
      // via the same already-handled dialog. A 400 PRECONDITION_FAILED —
      // the incident is no longer Unverified — is not a race to explain;
      // its own plain-string detail ("Only an 'Unverified' incident can be
      // snoozed.") is specific enough to render as-is.
      const raceLost = getIncidentConflict(err)
      if (raceLost) {
        setConflict(raceLost)
        invalidateAlerts()
      } else {
        setError(getApiErrorMessage(err, "Failed to snooze alert."))
      }
    } finally {
      setLoadingId(null)
    }
  }

  return (
    <Modal
      isOpen
      onClose={noop}
      hideClose
      closeOnBackdrop={false}
      role="alertdialog"
      ariaLabel={isOngoing ? "Ongoing accident" : "Accident detected"}
      // Above every other overlay: an alert firing while an operator has an
      // incident modal open must land on top of it, not behind it.
      overlayClassName="z-9999"
      backdropClassName="bg-backdrop-alert"
      className="max-w-md overflow-hidden p-0"
    >
      <div className="-mx-6 -mb-6">
        {/* header banner — danger for Unverified, warning for Ongoing */}
        <div className={`px-6 py-4 text-center ${isOngoing ? "bg-warning" : "bg-danger"}`}>
          <p className="text-xl font-black uppercase tracking-[0.08em] text-fg-on-primary">
            {isOngoing ? "Ongoing Accident" : "Accident Detected"}
          </p>
          {activeAlerts.length > 1 && (
            <p className="mt-1 text-xs font-semibold text-fg-on-primary/70">
              +{activeAlerts.length - 1} more alert{activeAlerts.length > 2 ? "s" : ""} queued
            </p>
          )}
        </div>

        <div className="flex min-h-[220px] items-center justify-center bg-surface-3 p-6">
          <SnapshotImage
            snapshotUrl={alert.snapshot_url}
            alt={`Accident snapshot for log ${alert.log_id}`}
            className="max-h-52 w-auto rounded border-2 border-stroke object-contain"
            fallbackClassName="h-40 w-full rounded"
          />
        </div>

        <div className="space-y-3 bg-surface-1 px-6 py-4">
          <div className="flex items-start justify-between">
            <span className="text-xs font-semibold uppercase tracking-[0.08em] text-fg-muted">
              Timestamp
            </span>
            <span className="text-right">
              <span className="block text-sm font-semibold tabular-nums text-fg">
                {formatFullDateTime(alert.detected_at)}
              </span>
              {/*
                An alarm that fires now is not necessarily an accident that
                happened now. The AI engine's durable outbox retries with capped
                exponential backoff (2s, doubling to 300s + jitter), so a
                detection made while the backend was down is delivered late
                carrying its ORIGINAL detected_at. Without this line the
                operator reads "ACCIDENT DETECTED" and a wall-clock time and
                reasonably assumes both are current.
              */}
              {detectionAgeSeconds !== null && detectionAgeSeconds >= STALE_DETECTION_SECONDS ? (
                <span className="mt-0.5 block text-[10px] font-medium text-warning">
                  Detected {formatDuration(detectionAgeSeconds)} ago — delivered late
                </span>
              ) : null}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-[0.08em] text-fg-muted">
              Camera Name
            </span>
            <span className="text-sm font-bold uppercase text-fg">
              {alert.camera_name ?? `Camera ${alert.camera_id}`}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-[0.08em] text-fg-muted">
              AI-Confidence Score
            </span>
            <span className="text-sm font-bold text-danger">
              {formatAlertConfidence(alert.confidence_score)}
            </span>
          </div>
        </div>

        {conflict ? (
          <div className="bg-surface-1 px-6 pb-1 pt-1">
            <IncidentHandledNotice info={conflict} />
            <Button
              variant="outline"
              size="sm"
              className="mb-3 w-full"
              onClick={() => {
                setConflict(null)
                removeAlert(alert.log_id)
              }}
            >
              Dismiss this notice
            </Button>
          </div>
        ) : null}

        {error ? (
          <div className="bg-surface-1 px-6 pb-3">
            <p className="rounded-md border border-danger-border bg-danger-subtle px-3 py-2 text-xs text-danger">
              {error}
            </p>
          </div>
        ) : null}

        <div
          className={cn(
            "grid gap-px border-t border-stroke bg-stroke",
            isUnverified ? "grid-cols-3" : "grid-cols-2",
          )}
        >
          {/*
            Snooze only exists for Unverified — the backend 400s a snooze on
            anything else (a terminal or Ongoing incident can't become
            Unverified again) — so it has no button on the Ongoing variant at
            all rather than one that can only fail.
          */}
          {isUnverified ? (
            <Button
              variant="secondary"
              className="rounded-none py-4 text-xs font-black uppercase tracking-[0.08em]"
              disabled={busy}
              onClick={handleSnooze}
            >
              {busy ? "…" : "Snooze"}
            </Button>
          ) : null}
          <Button
            variant="secondary"
            className="rounded-none py-4 text-xs font-black uppercase tracking-[0.08em]"
            disabled={busy}
            onClick={() => runAction(dismissAlert, "Failed to dismiss alert.")}
          >
            {busy ? "…" : "Dismiss Accident"}
          </Button>
          <Button
            variant="primary"
            className="rounded-none py-4 text-xs font-black uppercase tracking-[0.08em]"
            disabled={busy}
            onClick={() =>
              isUnverified
                ? runAction(confirmAlert, "Failed to confirm alert.")
                : runAction(resolveAlert, "Failed to resolve alert.")
            }
          >
            {busy ? "…" : isUnverified ? "Confirm Accident" : "Resolve Accident"}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
