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
  const unverifiedAlerts = alerts.filter((a) => a.detection_status === "Unverified")
  const unsnoozedAlerts = unverifiedAlerts.filter((a) => !isSnoozedNow(a.log_id, snoozedUntil))
  const allSnoozed = unverifiedAlerts.length > 0 && unsnoozedAlerts.length === 0

  function invalidateAlerts() {
    queryClient.invalidateQueries({ queryKey: ["alerts"] })
    queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] })
    queryClient.invalidateQueries({ queryKey: ["performance-analytics"] })
  }

  async function runAction(action: (logId: number) => Promise<unknown>, failure: string) {
    setSlideTransition(null)
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
      const newLength = alerts.length - 1
      if (newLength > 0 && selectedIndex >= newLength) {
        setSelectedIndex(newLength - 1)
      }
      invalidateAlerts()
    } catch (err) {
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
    if (allSnoozed) return
    setSlideTransition(null)
    const targets = unverifiedAlerts.length > 0 ? unverifiedAlerts : [alert]
    const primaryId = alert.log_id
    setLoadingId(primaryId)
    setError(null)
    setConflict(null)
    try {
      const results = await Promise.allSettled(targets.map((t) => snoozeAlert(t.log_id)))
      let lastConflict: IncidentHandledInfo | null = null
      let lastError: unknown = null

      for (let i = 0; i < results.length; i++) {
        const res = results[i]
        const target = targets[i]
        if (res.status === "fulfilled") {
          if (res.value.snoozed_until) {
            activateSnooze(target.log_id, res.value.snoozed_until, username)
          }
        } else {
          const raceLost = getIncidentConflict(res.reason)
          if (raceLost) {
            lastConflict = raceLost
          } else {
            lastError = res.reason
          }
        }
      }

      if (lastConflict) {
        setConflict(lastConflict)
        invalidateAlerts()
      } else if (lastError) {
        setError(getApiErrorMessage(lastError, "Failed to snooze alert."))
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
      overlayClassName="z-9999"
      backdropClassName="bg-backdrop-alert"
      className="w-full max-w-[1060px] overflow-hidden p-0 rounded-none sm:rounded-lg border-0"
      noEntrance
      outerContent={
        hasMultiple ? (
          <>
            {/* ── Left arrow floating on modal left edge ── */}
            <button
              type="button"
              onClick={() => navigate(-1)}
              disabled={isFirst || busy}
              aria-label="Previous alert"
              className={cn(
                "absolute -left-6 sm:-left-8 md:-left-16 top-1/2 -translate-y-1/2 z-50",
                "flex h-12 w-12 sm:h-14 sm:w-14 items-center justify-center rounded-full",
                "bg-black/80 hover:bg-black/95 text-white border border-white/20 shadow-2xl",
                "transition-all duration-150 backdrop-blur-md",
                (isFirst || busy) &&
                  "opacity-30 pointer-events-none cursor-not-allowed hover:bg-black/80",
              )}
            >
              <RiArrowLeftSLine size={32} aria-hidden />
            </button>

            {/* ── Right arrow floating on modal right edge ── */}
            <button
              type="button"
              onClick={() => navigate(1)}
              disabled={isLast || busy}
              aria-label="Next alert"
              className={cn(
                "absolute -right-6 sm:-right-8 md:-right-16 top-1/2 -translate-y-1/2 z-50",
                "flex h-12 w-12 sm:h-14 sm:w-14 items-center justify-center rounded-full",
                "bg-black/80 hover:bg-black/95 text-white border border-white/20 shadow-2xl",
                "transition-all duration-150 backdrop-blur-md",
                (isLast || busy) &&
                  "opacity-30 pointer-events-none cursor-not-allowed hover:bg-black/80",
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
            {/* Snooze Button placed top right in the telemetry section. Snoozes all active unverified alerts for the configured duration. */}
            <Button
              variant="ghost"
              size="icon"
              className={cn(
                "absolute right-4 top-4 z-10 rounded text-fg-muted hover:bg-surface-3 hover:text-fg",
                allSnoozed &&
                  "cursor-not-allowed text-warning opacity-80 hover:bg-transparent hover:text-warning",
              )}
              title={allSnoozed ? "Alarms snoozed" : "Snooze Alarm"}
              aria-label={allSnoozed ? "Alarms snoozed" : "Snooze alarm"}
              disabled={busy || allSnoozed}
              onClick={handleSnooze}
            >
              {allSnoozed ? <RiNotificationOffLine size={20} /> : <RiNotification2Line size={20} />}
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
