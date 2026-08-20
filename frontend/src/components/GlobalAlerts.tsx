import { useCallback, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { BellRing, BellOff } from "lucide-react"

import { Button } from "@/components/ui/Button"
import { Modal } from "@/components/ui/Modal"
import { SnapshotImage } from "@/components/ui/SnapshotImage"
import { isSnoozedNow, useAlertStore } from "@/store/useAlertStore"
import { useAuthStore } from "@/store/useAuthStore"
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
import { formatFullDateTime } from "@/utils/datetime"
import { getApiErrorMessage } from "@/api/client"
import { cn } from "@/utils/cn"

/**
 * The alarm dialog — the product's reason for existing.
 *
 * Rebuilt on `Modal` so it inherits body-scroll lock and focus-on-open from
 * `useOverlayBehavior`, which it previously had neither of: it hand-rolled its
 * own fixed overlay, on the single most important dialog in the app.
 *
 * **Escape is deliberately inert here**, which is the one thing it does not
 * take from `Modal`. The backdrop is not clickable, so a stray keypress cannot
 * silence a live alert.
 *
 * Standard top-right window controls (X button) are strictly omitted from this
 * modal to enforce the HITL (Human-in-the-Loop) workflow.
 */
export function GlobalAlerts() {
  const queryClient = useQueryClient()
  const alerts = useAlertStore((state) => state.alerts)
  const snoozedUntil = useAlertStore((state) => state.snoozedUntil)
  const removeAlert = useAlertStore((state) => state.removeAlert)
  const activateSnooze = useAlertStore((state) => state.activateSnooze)
  const username = useAuthStore((state) => state.username)
  const [loadingId, setLoadingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState<IncidentHandledInfo | null>(null)

  // Snoozed incidents (FR-07) mute the alarm modal for that incident until
  // the shared deadline expires or a RE_ALARM event reactivates it.
  const activeAlerts = alerts.filter((a) => !isSnoozedNow(a.log_id, snoozedUntil))
  const alert = activeAlerts[0]

  const noop = useCallback(() => {}, [])

  if (!alert) return null

  const busy = loadingId === alert.log_id
  const isUnverified = alert.detection_status === "Unverified"
  const isOngoing = alert.detection_status === "Ongoing"
  const hasAuditTrail = Boolean(alert.verified_by_name || alert.verified_at)

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
      // The broadcast carries a formatted name (P21 Step 3); this tab has no
      // equivalent lookup for its own actor without an extra fetch, so it
      // uses the session's own username as "who" for its own action.
      if (snoozed.snoozed_until) {
        activateSnooze(logId, snoozed.snoozed_until, username)
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
        {/* ── Section 1: Header ─────────────────────────────────────────────
            Edge-to-edge solid background header enforcing urgency. */}
        <div className="w-full bg-danger px-6 py-4">
          <h2 className="text-center text-2xl font-bold uppercase tracking-widest text-black">
            Accident Detected
          </h2>
          {activeAlerts.length > 1 && (
            <p className="mt-1 text-center text-xs font-medium text-black/70">
              +{activeAlerts.length - 1} more alert
              {activeAlerts.length > 2 ? "s" : ""} queued
            </p>
          )}
        </div>

        {/* ── Core Telemetry Section Wrapper ──────────────────────────────
            Relative positioning anchors the absolutely positioned Snooze button. */}
        <div className="relative">
          {/* Snooze Button placed top right in the telemetry section. */}
          {isUnverified ? (
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-4 top-4 z-10 rounded-md text-fg-muted hover:bg-surface-2 hover:text-fg"
              title="Snooze Alarm"
              disabled={busy}
              onClick={handleSnooze}
            >
              {isSnoozedNow(alert.log_id, snoozedUntil) ? (
                <BellOff size={20} />
              ) : (
                <BellRing size={20} />
              )}
            </Button>
          ) : null}

          {/* ── Section 2a: Snapshot image ────────────────────────────────── */}
          <div className="flex min-h-[220px] items-center justify-center bg-surface-3 p-6">
            <SnapshotImage
              snapshotUrl={alert.snapshot_url}
              alt={`Accident snapshot for log ${alert.log_id}`}
              className="max-h-52 w-auto rounded border-2 border-stroke object-contain"
              fallbackClassName="h-40 w-full rounded"
            />
          </div>

          {/* ── Section 3: Core Telemetry ─────────────────────────────────── */}
          <div className="space-y-3 bg-surface-1 px-6 py-4">
            <div className="flex items-start justify-between">
              <span className="text-xs font-normal uppercase tracking-wider text-fg-muted">
                Timestamp
              </span>
              <span className="text-right text-sm tabular-nums text-fg">
                {formatFullDateTime(alert.detected_at)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-normal uppercase tracking-wider text-fg-muted">
                Camera Name
              </span>
              <span className="text-sm font-bold uppercase text-fg">
                {alert.camera_name ?? `Camera ${alert.camera_id}`}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-normal uppercase tracking-wider text-fg-muted">
                AI-Confidence Score
              </span>
              {/*
                Red when the AI confidence is below 75 % — a low score means the
                detection is less certain and warrants closer operator scrutiny.
                Green (success) at 75 % and above signals a high-confidence event.
              */}
              <span
                className={cn(
                  "text-sm font-bold",
                  alert.confidence_score * 100 < 75 ? "text-danger" : "text-success",
                )}
              >
                {formatAlertConfidence(alert.confidence_score)}
              </span>
            </div>

            {/* ── Section 4: Audit Trail ──────────────────────────────────────
                Only rendered when a verification record is present. For fresh
                Unverified incidents both fields are null, so this section stays
                hidden until an operator has confirmed the incident. */}
            {hasAuditTrail && (
              <>
                <hr className="my-[14px] border-border" />
                <div className="mt-2 grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs font-normal uppercase tracking-wider text-fg-muted">
                      Verified By
                    </p>
                    <p className="mt-1 text-sm text-fg">{alert.verified_by_name ?? "—"}</p>
                  </div>
                  <div>
                    <p className="text-xs font-normal uppercase tracking-wider text-fg-muted">
                      Time Verified
                    </p>
                    <p className="mt-1 text-sm text-fg">{formatFullDateTime(alert.verified_at)}</p>
                  </div>
                </div>
              </>
            )}
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
        </div>

        {/* ── Section 5: Footer Action Buttons ──────────────────────────────
            Full-width flex row with equal-width buttons (flex-1). All onClick
            handlers and disabled logic are unchanged from the original. */}
        <div className="flex w-full gap-4 border-t border-stroke bg-surface-1 p-4">
          <Button
            variant="secondary"
            className="flex-1 rounded-md bg-surface-3 py-3 text-xs font-medium uppercase tracking-[0.08em] text-fg hover:bg-surface-2"
            disabled={busy}
            onClick={() => runAction(dismissAlert, "Failed to dismiss alert.")}
          >
            {busy ? "…" : "Dismiss Accident"}
          </Button>
          <Button
            className="flex-1 rounded-md bg-primary py-3 text-xs font-medium uppercase tracking-[0.08em] text-fg-on-primary hover:bg-primary-hover"
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
