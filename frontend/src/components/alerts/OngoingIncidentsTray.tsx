import { useRef, useState } from "react"
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

// True when the primary pointing device is precise (mouse / trackpad).
// Evaluated once at module load — changing input device mid-session is
// uncommon enough that a static check is acceptable here.
const IS_POINTER_FINE =
  typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(pointer: fine)").matches
    : true

// ── Thumbnail hover state ────────────────────────────────────────────────────

interface ThumbHover {
  logId: number
  /** Viewport-relative top of the thumbnail element, for vertical anchoring. */
  top: number
}

// ── Card ─────────────────────────────────────────────────────────────────────

function OngoingIncidentCard({
  alert,
  onOpenDetails,
  onThumbEnter,
  onThumbLeave,
}: {
  alert: AlertLog
  onOpenDetails: () => void
  onThumbEnter: (logId: number, top: number) => void
  onThumbLeave: () => void
}) {
  const thumbRef = useRef<HTMLDivElement>(null)
  const isHighConfidence = alert.confidence_score * 100 >= 75

  const handleMouseEnter = () => {
    if (!IS_POINTER_FINE || !thumbRef.current) return
    const rect = thumbRef.current.getBoundingClientRect()
    onThumbEnter(alert.log_id, rect.top)
  }

  return (
    <div className="relative overflow-hidden rounded-lg border border-stroke bg-surface-1 p-3.5 shadow-sm transition-colors duration-150 hover:border-stroke-strong">
      <div className="flex items-start gap-3">
        {/* Snapshot Thumbnail — hover shows enlarged flyout on pointer-fine devices */}
        <div
          ref={thumbRef}
          className={cn(
            "relative h-16 w-20 shrink-0 overflow-hidden rounded border border-stroke bg-surface-3",
            IS_POINTER_FINE && alert.snapshot_url && "cursor-zoom-in",
          )}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={onThumbLeave}
        >
          <SnapshotImage
            snapshotUrl={alert.snapshot_url}
            alt={`Accident snapshot for log ${alert.log_id}`}
            className="h-full w-full object-cover"
            fallbackClassName="h-full w-full"
          />
        </div>

        {/* Incident Info */}
        <div className="min-w-0 flex-1">
          <h4 className="truncate text-xs font-semibold text-fg">
            {alert.camera_name ?? `Camera ${alert.camera_id}`}
          </h4>

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
          <span>Review &amp; Resolve</span>
          <RiArrowRightSLine size={14} />
        </Button>
      </div>

      {/* Glowing yellow bottom animation line */}
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 h-[2px] overflow-hidden"
        aria-hidden="true"
      >
        <div className="h-full w-full bg-gradient-to-r from-transparent via-warning to-transparent opacity-75 animate-pulse" />
      </div>
    </div>
  )
}

// ── Tray ─────────────────────────────────────────────────────────────────────

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

  // Thumbnail hover preview state. null when no thumbnail is hovered.
  const [thumbHover, setThumbHover] = useState<ThumbHover | null>(null)

  if (ongoingAlerts.length === 0) {
    return null
  }

  // Multi-operator sync: keep the active detail alert reference up to date
  const selectedAlert =
    activeDetailAlert &&
    (ongoingAlerts.find((a) => a.log_id === activeDetailAlert.log_id) ?? activeDetailAlert)

  // The hovered alert object, resolved from the live list so the preview
  // always shows the most recent snapshot URL even after a WS update.
  const hoveredAlert = thumbHover
    ? (ongoingAlerts.find((a) => a.log_id === thumbHover.logId) ?? null)
    : null

  function handleOpenDetails(alert: AlertLog) {
    setIsOpen(false)
    setThumbHover(null)
    setActiveDetailAlert(alert)
    // Filter out stale "Now Ongoing" notices from when the incident was initially
    // confirmed. Only show if another operator resolved or dismissed it.
    const notice = handledByOther[alert.log_id]
    setConflictNotice(notice && notice.currentStatus !== "Ongoing" ? notice : null)
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
          "fixed top-8 right-8 z-[8000] flex h-9 items-center gap-2 rounded-full px-3.5",
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
        onClose={() => {
          setIsOpen(false)
          setThumbHover(null)
        }}
        title="Ongoing Incidents"
        subtitle="Confirmed accidents currently being handled in the field"
      >
        <div className="flex flex-col gap-3 py-1">
          {ongoingAlerts.map((alert) => (
            <OngoingIncidentCard
              key={alert.log_id}
              alert={alert}
              onOpenDetails={() => handleOpenDetails(alert)}
              onThumbEnter={(logId, top) => setThumbHover({ logId, top })}
              onThumbLeave={() => setThumbHover(null)}
            />
          ))}
        </div>
      </SidePanel>

      {/*
        ── Thumbnail Hover Preview Flyout ────────────────────────────────────
        Shown only on pointer-fine (desktop) devices when a card thumbnail is
        hovered. Rendered outside the SidePanel so it escapes the overflow
        clipping of the drawer. pointer-events-none ensures it never captures
        mouse events and blocks the mouseleave that would dismiss it.
        Positioned to the left of the 420px-wide SidePanel with an 8px gap.
      */}
      {hoveredAlert && thumbHover && IS_POINTER_FINE ? (
        <div
          role="img"
          aria-label={`Enlarged snapshot preview for incident at ${hoveredAlert.camera_name ?? `Camera ${hoveredAlert.camera_id}`}`}
          className="pointer-events-none fixed z-[9600] overflow-hidden rounded-xl border border-stroke bg-surface-1 shadow-2xl"
          style={{
            // Sit just left of the 420px SidePanel
            right: "calc(420px + 12px)",
            // Anchor vertically to the hovered thumbnail, clamped to viewport
            top: Math.max(8, thumbHover.top - 60),
            width: 248,
            height: 186,
          }}
        >
          <SnapshotImage
            snapshotUrl={hoveredAlert.snapshot_url}
            alt={`Snapshot preview for incident ${hoveredAlert.log_id}`}
            className="h-full w-full object-cover"
            fallbackClassName="h-full w-full"
            loading="eager"
          />
          {/* Caption overlay */}
          <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent px-2.5 pb-2 pt-6">
            <p className="truncate text-[10px] font-semibold text-white">
              {hoveredAlert.camera_name ?? `Camera ${hoveredAlert.camera_id}`}
            </p>
            <p className="text-[9px] text-white/70">
              {formatAlertConfidence(hoveredAlert.confidence_score)} confidence
            </p>
          </div>
        </div>
      ) : null}

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
