import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import {
  RiAlarmWarningLine,
  RiArrowRightSLine,
  RiCameraLine,
  RiCheckLine,
  RiTimeLine,
} from "@remixicon/react"

import {
  dismissAlert,
  getIncidentConflict,
  resolveAlert,
  type AlertLog,
  type IncidentHandledInfo,
} from "@/api/alerts"
import { Badge } from "@/components/ui/Badge"
import { Button, focusRing } from "@/components/ui/Button"
import { IncidentHandledNotice } from "@/components/ui/IncidentHandledNotice"
import { SidePanel } from "@/components/ui/SidePanel"
import { SnapshotImage } from "@/components/ui/SnapshotImage"
import { IncidentDetailModal } from "@/pages/detections/IncidentDetailModal"
import { useAlertStore } from "@/store/useAlertStore"
import { toast } from "@/store/useToastStore"
import { cn } from "@/utils/cn"
import { formatRelativeDateTime } from "@/utils/datetime"
import { formatAlertConfidence } from "@/utils/format"

function OngoingIncidentCard({
  alert,
  onOpenDetails,
}: {
  alert: AlertLog
  onOpenDetails: () => void
}) {
  const isHighConfidence = alert.confidence_score * 100 >= 75

  return (
    <div className="rounded-lg border border-stroke bg-surface-1 p-3.5 shadow-sm transition-colors duration-150 hover:border-stroke-strong">
      <div className="flex items-start gap-3">
        {/* Snapshot Thumbnail */}
        <div className="relative h-16 w-20 shrink-0 overflow-hidden rounded border border-stroke bg-surface-3">
          <SnapshotImage
            snapshotUrl={alert.snapshot_url}
            alt={`Accident snapshot for log ${alert.log_id}`}
            className="h-full w-full object-cover"
            fallbackClassName="h-full w-full"
          />
        </div>

        {/* Incident Info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-1">
            <h4 className="truncate text-xs font-semibold text-fg">
              {alert.camera_name ?? `Camera ${alert.camera_id}`}
            </h4>
            <Badge tone="warning" variant="subtle" className="shrink-0 text-[10px]">
              Ongoing
            </Badge>
          </div>

          <div className="mt-1 flex flex-col gap-0.5 text-caption text-fg-muted">
            <div className="flex items-center gap-1">
              <RiTimeLine size={12} className="shrink-0" />
              <span className="truncate">{formatRelativeDateTime(alert.detected_at)}</span>
            </div>
            <div className="flex items-center gap-1">
              <RiCameraLine size={12} className="shrink-0" />
              <span className="truncate">
                AI Confidence:{" "}
                <span
                  className={cn("font-semibold", isHighConfidence ? "text-success" : "text-danger")}
                >
                  {formatAlertConfidence(alert.confidence_score)}
                </span>
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Card Footer */}
      <div className="mt-3 flex items-center justify-between border-t border-stroke pt-2.5">
        <div className="truncate text-[11px] text-fg-muted">
          {alert.verified_by_name ? (
            <span>Verified by {alert.verified_by_name}</span>
          ) : (
            <span>Confirmed active</span>
          )}
        </div>
        <Button size="sm" variant="outline" className="h-7 px-2.5 text-xs" onClick={onOpenDetails}>
          <span>Review & Resolve</span>
          <RiArrowRightSLine size={14} />
        </Button>
      </div>
    </div>
  )
}

export function OngoingIncidentsTray() {
  const queryClient = useQueryClient()
  const alerts = useAlertStore((state) => state.alerts)
  const ongoingAlerts = alerts.filter((a) => a.detection_status === "Ongoing")
  const removeAlert = useAlertStore((state) => state.removeAlert)
  const handledByOther = useAlertStore((state) => state.handledByOther)

  const [isOpen, setIsOpen] = useState(false)
  const [activeDetailAlert, setActiveDetailAlert] = useState<AlertLog | null>(null)
  const [isResolving, setIsResolving] = useState(false)
  const [isDismissing, setIsDismissing] = useState(false)
  const [conflictNotice, setConflictNotice] = useState<IncidentHandledInfo | null>(null)

  if (ongoingAlerts.length === 0) {
    return null
  }

  // Multi-operator sync: keep the active detail alert reference up to date
  const selectedAlert =
    activeDetailAlert &&
    (ongoingAlerts.find((a) => a.log_id === activeDetailAlert.log_id) ?? activeDetailAlert)

  function handleOpenDetails(alert: AlertLog) {
    setIsOpen(false)
    setActiveDetailAlert(alert)
    setConflictNotice(handledByOther[alert.log_id] ?? null)
  }

  function handleCloseDetails() {
    setActiveDetailAlert(null)
    setConflictNotice(null)
  }

  function invalidateQueries() {
    void queryClient.invalidateQueries({ queryKey: ["alerts"] })
    void queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] })
  }

  async function handleResolve(logId: number) {
    setIsResolving(true)
    setConflictNotice(null)
    try {
      await resolveAlert(logId)
      removeAlert(logId)
      handleCloseDetails()
      invalidateQueries()
      toast.success("Incident resolved successfully.")
    } catch (err) {
      const conflict = getIncidentConflict(err)
      if (conflict) {
        setConflictNotice(conflict)
        removeAlert(logId)
      } else {
        toast.error("Failed to resolve incident.")
      }
    } finally {
      setIsResolving(false)
    }
  }

  async function handleDismiss(logId: number) {
    setIsDismissing(true)
    setConflictNotice(null)
    try {
      await dismissAlert(logId)
      removeAlert(logId)
      handleCloseDetails()
      invalidateQueries()
      toast.info("Incident dismissed.")
    } catch (err) {
      const conflict = getIncidentConflict(err)
      if (conflict) {
        setConflictNotice(conflict)
        removeAlert(logId)
      } else {
        toast.error("Failed to dismiss incident.")
      }
    } finally {
      setIsDismissing(false)
    }
  }

  return (
    <>
      {/* ── Floating Trigger Button / Pill ──────────────────────────────── */}
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        aria-label="Ongoing incidents tray"
        title="Ongoing incidents"
        className={cn(
          "fixed bottom-4 right-16 z-[8000] flex h-10 items-center gap-2 rounded-full px-3.5",
          "border border-warning/40 bg-surface-1 text-warning shadow-overlay transition-all duration-150",
          "hover:border-warning/80 hover:bg-surface-2 hover:shadow-lg active:scale-95",
          focusRing,
        )}
      >
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-warning opacity-75" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-warning" />
        </span>
        <RiAlarmWarningLine size={16} className="shrink-0 text-warning" />
        <span className="text-xs font-semibold tabular-nums text-fg">
          {ongoingAlerts.length} Ongoing
        </span>
      </button>

      {/* ── Expandable SidePanel ────────────────────────────────────────── */}
      <SidePanel
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="Ongoing Incidents"
        subtitle="Confirmed accidents currently being handled in the field"
      >
        <div className="flex flex-col gap-3 py-1">
          {ongoingAlerts.map((alert) => (
            <OngoingIncidentCard
              key={alert.log_id}
              alert={alert}
              onOpenDetails={() => handleOpenDetails(alert)}
            />
          ))}
        </div>
      </SidePanel>

      {/* ── Reused IncidentDetailModal for Full Telemetry & Resolve ─────── */}
      {selectedAlert ? (
        <IncidentDetailModal
          isOpen={Boolean(selectedAlert)}
          alert={selectedAlert}
          onClose={handleCloseDetails}
          isTransitionPending={isResolving || isDismissing}
          isResolving={isResolving}
          isDismissing={isDismissing}
          isConfirming={false}
          onResolve={handleResolve}
          onDismiss={handleDismiss}
          onConfirm={() => {}}
          notice={
            conflictNotice ? (
              <div className="mb-4">
                <IncidentHandledNotice info={conflictNotice} />
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-2 w-full"
                  onClick={handleCloseDetails}
                >
                  <RiCheckLine size={14} />
                  Dismiss this notice
                </Button>
              </div>
            ) : null
          }
        />
      ) : null}
    </>
  )
}
