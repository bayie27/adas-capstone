import { useCallback, useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import {
  RiArrowLeftSLine,
  RiArrowRightSLine,
  RiNotification2Line,
  RiNotificationOffLine,
} from "@remixicon/react"

import { Button } from "@/components/ui/Button"
import { Modal } from "@/components/ui/Modal"
import { SnapshotImage } from "@/components/ui/SnapshotImage"
import { isSnoozedNow, useAlertStore } from "@/store/useAlertStore"
import { useAuthStore } from "@/store/useAuthStore"
import {
  confirmAlert,
  dismissAlert,
  getIncidentConflict,
  snoozeAlert,
  type AlertLog,
  type IncidentHandledInfo,
} from "@/api/alerts"
import { IncidentHandledNotice } from "@/components/ui/IncidentHandledNotice"
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
 *
 * When multiple alerts are queued, Back/Forward chevrons let the operator
 * browse any alert freely. Navigation is unrestricted — browsing does not
 * silence the siren; only an explicit snooze does. Actions (confirm/dismiss)
 * apply to the currently viewed alert and stay at the nearest remaining index.
 */
export function GlobalAlerts() {
  const queryClient = useQueryClient()
  const allAlerts = useAlertStore((state) => state.alerts)
  const alerts = allAlerts.filter((a) => a.detection_status === "Unverified")
  const snoozedUntil = useAlertStore((state) => state.snoozedUntil)
  const addAlert = useAlertStore((state) => state.addAlert)
  const removeAlert = useAlertStore((state) => state.removeAlert)
  const activateSnooze = useAlertStore((state) => state.activateSnooze)
  const username = useAuthStore((state) => state.username)
  const [loadingId, setLoadingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState<IncidentHandledInfo | null>(null)

  // ── Navigation index & transition state ──────────────────────────────────
  // Clamped on every render, so it self-corrects when an alert is removed.
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [slideTransition, setSlideTransition] = useState<{
    id: number
    direction: "next" | "prev"
  } | null>(null)

  const noop = useCallback(() => {}, [])

  const clampedIndex = alerts.length > 0 ? Math.min(selectedIndex, alerts.length - 1) : 0
  const hasMultiple = alerts.length > 1
  const isFirst = clampedIndex === 0
  const isLast = alerts.length > 0 ? clampedIndex === alerts.length - 1 : true

  const navigate = useCallback(
    (direction: -1 | 1) => {
      if (alerts.length <= 1) return
      const nextIndex = clampedIndex + direction
      if (nextIndex < 0 || nextIndex >= alerts.length) return
      const targetAlert = alerts[nextIndex]
      if (targetAlert) {
        setSlideTransition({
          id: targetAlert.log_id,
          direction: direction === 1 ? "next" : "prev",
        })
      }
      setSelectedIndex(nextIndex)
      // Clear stale feedback when the operator navigates away.
      setError(null)
      setConflict(null)
    },
    [clampedIndex, alerts],
  )

  // Auto-clear slide transition after animation completes (240ms safety timer)
  useEffect(() => {
    if (!slideTransition) return
    const timer = setTimeout(() => {
      setSlideTransition(null)
    }, 240)
    return () => clearTimeout(timer)
  }, [slideTransition])

  // ── Keyboard shortcut: ArrowLeft / ArrowRight to cycle queued alerts ────────
  useEffect(() => {
    if (!hasMultiple) return

    function handleKeyDown(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return

      if (e.key === "ArrowLeft") {
        e.preventDefault()
        navigate(-1)
      } else if (e.key === "ArrowRight") {
        e.preventDefault()
        navigate(1)
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [hasMultiple, navigate])

  if (!alerts.length) return null

  const alert = alerts[clampedIndex]
  const busy = loadingId === alert.log_id
  const isSnoozed = isSnoozedNow(alert.log_id, snoozedUntil)

  function invalidateAlerts() {
    queryClient.invalidateQueries({ queryKey: ["alerts"] })
  }

  async function runAction(action: (logId: number) => Promise<unknown>, failure: string) {
    const logId = alert.log_id
    setLoadingId(logId)
    setError(null)
    setConflict(null)
    try {
      const result = await action(logId)
      if (result && typeof result === "object" && "detection_status" in result) {
        addAlert(result as AlertLog)
      } else {
        removeAlert(logId)
      }
      setSlideTransition(null)
      // Stay at the same position; if the tail was removed, clampedIndex will
      // naturally back up to the new last element on the next render. We only
      // need to explicitly correct when the raw selectedIndex now overshoots.
      const newLength = alerts.length - 1
      if (newLength > 0 && selectedIndex >= newLength) {
        setSelectedIndex(newLength - 1)
      } else {
        setSelectedIndex(clampedIndex)
      }
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
    if (isSnoozed) return
    setSlideTransition(null)
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
      ariaLabel="Accident detected"
      // Above every other overlay: an alert firing while an operator has an
      // incident modal open must land on top of it, not behind it.
      overlayClassName="z-9999"
      backdropClassName="bg-backdrop-alert"
      className="w-full max-w-[1060px] overflow-hidden p-0 rounded-none sm:rounded-lg border-0"
      noEntrance
      outerContent={
        hasMultiple ? (
          <>
            {/* ── Left Navigation Arrow (Previous alert) ── */}
            <button
              type="button"
              aria-label="Previous alert"
              disabled={isFirst}
              onClick={() => navigate(-1)}
              className={cn(
                "absolute -left-14 sm:-left-16 md:-left-20 top-1/2 z-[10000] -translate-y-1/2",
                "flex h-12 w-12 sm:h-14 sm:w-14 items-center justify-center rounded-full border border-white/20",
                "bg-surface-1/90 text-white shadow-2xl backdrop-blur-md transition-all",
                isFirst
                  ? "cursor-not-allowed opacity-20"
                  : "opacity-90 hover:scale-110 hover:bg-surface-2 hover:border-white/40 hover:opacity-100 active:scale-95",
              )}
            >
              <RiArrowLeftSLine size={32} aria-hidden />
            </button>

            {/* ── Right Navigation Arrow (Next alert) ── */}
            <button
              type="button"
              aria-label="Next alert"
              disabled={isLast}
              onClick={() => navigate(1)}
              className={cn(
                "absolute -right-14 sm:-right-16 md:-right-20 top-1/2 z-[10000] -translate-y-1/2",
                "flex h-12 w-12 sm:h-14 sm:w-14 items-center justify-center rounded-full border border-white/20",
                "bg-surface-1/90 text-white shadow-2xl backdrop-blur-md transition-all",
                isLast
                  ? "cursor-not-allowed opacity-20"
                  : "opacity-90 hover:scale-110 hover:bg-surface-2 hover:border-white/40 hover:opacity-100 active:scale-95",
              )}
            >
              <RiArrowRightSLine size={32} aria-hidden />
            </button>

            {/* ── Alert N of M badge — centered directly below the modal ── */}
            <div
              key={`counter-${clampedIndex}`}
              aria-live="polite"
              aria-atomic="true"
              className={cn(
                "mt-4 flex items-center gap-2 rounded-full border border-white/20",
                "bg-black/80 px-5 py-2 backdrop-blur-md shadow-2xl",
                "text-xs sm:text-sm font-bold tracking-wide tabular-nums text-white",
              )}
            >
              Alert {clampedIndex + 1} of {alerts.length}
            </div>
          </>
        ) : null
      }
    >
      <div
        key={alert.log_id}
        onAnimationEnd={() => setSlideTransition(null)}
        className={cn(
          "-mx-6 -mb-6 flex flex-col",
          slideTransition?.id === alert.log_id &&
            slideTransition.direction === "next" &&
            "animate-alert-slide-right",
          slideTransition?.id === alert.log_id &&
            slideTransition.direction === "prev" &&
            "animate-alert-slide-left",
        )}
      >
        {/* ── Section 1: Header ─────────────────────────────────────────────
            Edge-to-edge solid background header enforcing urgency.
            Text: ACCIDENT DETECTED, font size 24px, weight 700, line-height 36px, color #252529 */}
        <div className="w-full h-[55px] bg-danger px-6 sm:px-[34px] flex items-center justify-center">
          <h2 className="text-center text-[24px] font-bold font-sans uppercase leading-[36px] tracking-wide text-surface-3">
            Accident Detected
          </h2>
        </div>

        {/* ── Section 2: Split Body Layout (Snapshot Image + Telemetry Panel) ── */}
        <div className="flex flex-col md:flex-row items-stretch w-full overflow-hidden">
          {/* Left Column: Snapshot Image Preview */}
          <div className="w-full md:w-[600px] lg:w-[658px] min-h-[260px] bg-canvas self-stretch flex overflow-hidden shrink-0">
            <SnapshotImage
              snapshotUrl={alert.snapshot_url}
              alt={`Accident snapshot for log ${alert.log_id}`}
              className="w-full h-full min-h-full object-cover block"
              fallbackClassName="h-full w-full rounded-none"
            />
          </div>

          {/* Right Column: Telemetry & Actions */}
          <div className="flex-1 flex flex-col justify-between bg-surface-2 min-w-0 sm:min-w-[380px] relative">
            {/* Snooze Button placed top right in the telemetry section. Disabled once snoozed until expiry. */}
            <Button
              variant="ghost"
              size="icon"
              className={cn(
                "absolute right-4 top-4 z-10 rounded text-fg-muted hover:bg-surface-3 hover:text-fg",
                isSnoozed &&
                  "cursor-not-allowed text-warning opacity-80 hover:bg-transparent hover:text-warning",
              )}
              title={isSnoozed ? "Alarm snoozed" : "Snooze Alarm"}
              aria-label={isSnoozed ? "Alarm snoozed" : "Snooze alarm"}
              disabled={busy || isSnoozed}
              onClick={handleSnooze}
            >
              {isSnoozed ? <RiNotificationOffLine size={20} /> : <RiNotification2Line size={20} />}
            </Button>

            {/* Telemetry metadata list */}
            <div className="p-6 flex flex-col justify-center gap-6 flex-1">
              <div className="flex flex-col justify-start items-start">
                <span className="text-[12px] font-normal leading-[21px] uppercase tracking-wider text-fg-muted">
                  TIMESTAMP
                </span>
                <span className="text-[16px] font-semibold leading-[32px] tabular-nums text-fg">
                  {formatFullDateTime(alert.detected_at)}
                </span>
              </div>

              <div className="flex flex-col justify-start items-start">
                <span className="text-[12px] font-normal leading-[21px] uppercase tracking-wider text-fg-muted">
                  CAMERA NAME
                </span>
                <span className="text-[16px] font-semibold leading-[32px] uppercase text-fg truncate max-w-full">
                  {alert.camera_name ?? `Camera ${alert.camera_id}`}
                </span>
              </div>

              <div className="flex flex-col justify-start items-start">
                <span className="text-[12px] font-normal leading-[21px] uppercase tracking-wider text-fg-muted">
                  AI-CONFIDENCE SCORE
                </span>
                <span
                  className={cn(
                    "text-[16px] font-semibold leading-[32px] tabular-nums",
                    alert.confidence_score * 100 < 75 ? "text-danger" : "text-fg",
                  )}
                >
                  {formatAlertConfidence(alert.confidence_score)}
                </span>
              </div>

              {conflict ? (
                <div className="pt-2">
                  <IncidentHandledNotice info={conflict} />
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-2 w-full"
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
                <div className="pt-2">
                  <p className="rounded border border-danger-border bg-danger-subtle px-3 py-2 text-xs text-danger">
                    {error}
                  </p>
                </div>
              ) : null}
            </div>

            {/* ── Section 3: Footer Action Buttons ────────────────────────── */}
            <div className="w-full bg-surface-1 px-5 sm:px-6 py-3 flex items-center gap-3 sm:gap-4">
              <Button
                variant="secondary"
                className="flex-1 whitespace-nowrap h-[44px] px-3 sm:px-4 py-2 bg-border hover:bg-surface-3 text-fg text-xs sm:text-[14px] font-medium leading-[20px] rounded-[4px] flex items-center justify-center uppercase tracking-wide transition-colors"
                disabled={busy}
                onClick={() => runAction(dismissAlert, "Failed to dismiss alert.")}
              >
                {busy ? "…" : "Dismiss Accident"}
              </Button>
              <Button
                className="flex-1 whitespace-nowrap h-[44px] px-3 sm:px-4 py-2 bg-fg-body hover:bg-fg text-surface-2 text-xs sm:text-[14px] font-medium leading-[28px] rounded-[4px] flex items-center justify-center uppercase tracking-wide transition-colors"
                disabled={busy}
                onClick={() => runAction(confirmAlert, "Failed to confirm alert.")}
              >
                {busy ? "…" : "Confirm Accident"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </Modal>
  )
}
