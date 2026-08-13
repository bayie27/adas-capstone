import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { SnapshotImage } from "@/components/ui/SnapshotImage"
import { isSnoozedNow, useAlertStore } from "@/store/useAlertStore"
import { confirmAlert, dismissAlert, resolveAlert } from "@/api/alerts"
import { formatAlertConfidence } from "@/utils/format"
import { formatFullDateTime } from "@/utils/datetime"
import { getApiErrorMessage } from "@/api/client"

export function GlobalAlerts() {
  const queryClient = useQueryClient()
  const alerts = useAlertStore((state) => state.alerts)
  const snoozedUntil = useAlertStore((state) => state.snoozedUntil)
  const removeAlert = useAlertStore((state) => state.removeAlert)
  const [loadingId, setLoadingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Snoozed incidents (FR-07) mute the alarm modal for that incident until
  // the shared deadline expires or a RE_ALARM event reactivates it.
  const activeAlerts = alerts.filter((a) => !isSnoozedNow(a.log_id, snoozedUntil))
  const alert = activeAlerts[0]
  if (!alert) return null

  const busy = loadingId === alert.log_id
  const isUnverified = alert.detection_status === "Unverified"
  const isOngoing = alert.detection_status === "Ongoing"

  function invalidateAlerts() {
    queryClient.invalidateQueries({ queryKey: ["alerts"] })
  }

  async function handleDismiss() {
    setLoadingId(alert.log_id)
    setError(null)
    try {
      await dismissAlert(alert.log_id)
      removeAlert(alert.log_id)
      invalidateAlerts()
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to dismiss alert."))
    } finally {
      setLoadingId(null)
    }
  }

  async function handleConfirm() {
    setLoadingId(alert.log_id)
    setError(null)
    try {
      await confirmAlert(alert.log_id)
      removeAlert(alert.log_id)
      invalidateAlerts()
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to confirm alert."))
    } finally {
      setLoadingId(null)
    }
  }

  async function handleResolve() {
    setLoadingId(alert.log_id)
    setError(null)
    try {
      await resolveAlert(alert.log_id)
      removeAlert(alert.log_id)
      invalidateAlerts()
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to resolve alert."))
    } finally {
      setLoadingId(null)
    }
  }

  return (
    <div
      className="fixed inset-0 z-9999 flex items-center justify-center p-4"
      aria-modal="true"
      role="alertdialog"
      aria-label="Accident Detected"
    >
      {/* backdrop */}
      <div className="absolute inset-0 bg-backdrop-alert" />

      {/* modal card */}
      <div className="relative w-full max-w-md overflow-hidden rounded-xl shadow-2xl">
        {/* header banner — red for Unverified, amber for Ongoing */}
        <div className={`px-6 py-4 text-center ${isOngoing ? "bg-warning" : "bg-danger"}`}>
          <p className="text-xl font-black uppercase tracking-widest text-fg-on-primary">
            {isOngoing ? "Ongoing Accident" : "Accident Detected"}
          </p>
          {activeAlerts.length > 1 && (
            <p className="mt-1 text-xs font-semibold text-fg-on-primary/70">
              +{activeAlerts.length - 1} more alert{activeAlerts.length > 2 ? "s" : ""} queued
            </p>
          )}
        </div>

        {/* snapshot area */}
        <div className="flex min-h-[220px] items-center justify-center bg-surface-3 p-6">
          <SnapshotImage
            snapshotUrl={alert.snapshot_url}
            alt={`Accident snapshot for log ${alert.log_id}`}
            className="max-h-52 w-auto rounded border-2 border-stroke object-contain"
            fallbackClassName="h-40 w-full rounded"
          />
        </div>

        {/* metadata rows */}
        <div className="space-y-3 bg-surface-1 px-6 py-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-widest text-fg-muted">
              Timestamp
            </span>
            <span className="tabular-nums text-sm font-semibold text-fg">
              {formatFullDateTime(alert.detected_at)}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-widest text-fg-muted">
              Camera Name
            </span>
            <span className="text-sm font-bold uppercase text-fg">
              {alert.camera_name ?? `Camera ${alert.camera_id}`}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-widest text-fg-muted">
              AI-Confidence Score
            </span>
            <span className="text-sm font-bold text-danger">
              {formatAlertConfidence(alert.confidence_score)}
            </span>
          </div>
        </div>

        {/* error message */}
        {error ? (
          <div className="bg-surface-1 px-6 pb-3">
            <p className="rounded-md border border-danger-border bg-danger-subtle px-3 py-2 text-xs text-danger">
              {error}
            </p>
          </div>
        ) : null}

        {/* action buttons — vary by status */}
        <div className="grid grid-cols-2 border-t border-stroke bg-surface-1">
          <button
            type="button"
            onClick={handleDismiss}
            disabled={busy}
            className="border-r border-stroke-strong bg-surface-3 py-4 text-xs font-black uppercase tracking-widest text-fg transition-colors hover:bg-stroke-strong disabled:opacity-50"
          >
            {busy && loadingId === alert.log_id ? "..." : "Dismiss Accident"}
          </button>
          {isUnverified ? (
            <button
              type="button"
              onClick={handleConfirm}
              disabled={busy}
              className="bg-primary py-4 text-xs font-black uppercase tracking-widest text-fg-on-primary transition-colors hover:bg-primary-hover disabled:opacity-50"
            >
              {busy ? "..." : "Confirm Accident"}
            </button>
          ) : (
            <button
              type="button"
              onClick={handleResolve}
              disabled={busy}
              className="bg-primary py-4 text-xs font-black uppercase tracking-widest text-fg-on-primary transition-colors hover:bg-primary-hover disabled:opacity-50"
            >
              {busy ? "..." : "Resolve Accident"}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
