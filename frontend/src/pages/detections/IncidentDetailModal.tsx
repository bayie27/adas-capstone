import type { ReactNode } from "react"

import { Button, focusRing } from "@/components/ui/Button"
import { Modal } from "@/components/ui/Modal"
import { SnapshotImage } from "@/components/ui/SnapshotImage"
import type { AlertLog } from "@/api/alerts"
import {
  formatAlertCode,
  formatAlertConfidence,
  getAlertBadgeClass,
  getAlertBorderClass,
} from "@/utils/format"
import { formatDuration, formatFullDateTime, secondsSince } from "@/utils/datetime"
import { cn } from "@/utils/cn"
import { RiCloseLine } from "@remixicon/react"
import { useNow } from "@/hooks/useNow"

/** See GlobalAlerts — an outbox-delayed detection carries its original time. */
const STALE_DETECTION_SECONDS = 90

/**
 * The incident detail modal, in the three variants Figma draws.
 *
 * | Status                | Frame      | Accent  | Extra blocks           | Actions            |
 * | --------------------- | ---------- | ------- | ---------------------- | ------------------ |
 * | Unverified            | `118:8948` | danger  | —                      | Dismiss / Confirm  |
 * | Ongoing               | `129:9234` | warning | verified-by            | Dismiss / Resolve  |
 * | Dismissed \| Resolved | `124:9186` | neutral | verified-by, closed-by | **none**           |
 *
 * The terminal variant having no actions at all is the load-bearing part: a
 * closed incident is a record, and the modal must not offer a transition the
 * backend would reject.
 *
 * D-8(b) settled this as a modal rather than a drawer. An incident detail is
 * an *interrupting decision surface* — the operator opens it to commit to
 * confirm / dismiss / resolve, and blocking the rest of the screen while they
 * decide is the point. Camera telemetry (Phase 19) is a reference surface and
 * gets `SidePanel` instead.
 */

export interface IncidentDetailModalProps {
  alert: AlertLog | null
  isOpen: boolean
  onClose: () => void
  /** Rendered above the actions — the already-handled dialog and query errors. */
  notice?: ReactNode
  isTransitionPending: boolean
  isDismissing: boolean
  isConfirming: boolean
  isResolving: boolean
  onDismiss: (logId: number) => void
  onConfirm: (logId: number) => void
  onResolve: (logId: number) => void
  /**
   * D-2 — the third action slot on the Unverified variant.
   *
   * Snooze is Phase 13's feature, but the *shape* of this row is Phase 7's
   * decision: the row is built three-up now so adding the control later is a
   * prop, not a rebuild of the product's most important dialog. Until Phase 13
   * passes something, this renders nothing and the row reads as two buttons.
   */
  snoozeAction?: ReactNode
  overlayClassName?: string
}

export function IncidentDetailModal({
  alert,
  isOpen,
  onClose,
  notice,
  isTransitionPending,
  isDismissing,
  isConfirming,
  isResolving,
  onDismiss,
  onConfirm,
  onResolve,
  snoozeAction,
  overlayClassName,
}: IncidentDetailModalProps) {
  // Only ticks while an Unverified incident is open — the only case where the
  // gap between "detected" and "now" is a live decision input.
  const now = useNow(isOpen && alert?.detection_status === "Unverified", 30_000)
  const ageSeconds = alert ? secondsSince(alert.detected_at, now) : null
  const isDelayed = ageSeconds !== null && ageSeconds >= STALE_DETECTION_SECONDS

  const isTerminal =
    alert?.detection_status === "Dismissed" || alert?.detection_status === "Resolved"

  // M7 — the frame labels the closed-by timestamp "TIME VERIFIED", duplicating
  // the row above it. `closed_at` is a distinct field from `verified_at`.
  const closedTimeLabel = alert?.detection_status === "Resolved" ? "TIME RESOLVED" : "TIME CLOSED"

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      hideClose
      overlayClassName={cn("z-[9500]", overlayClassName)}
      className={cn(
        "w-full max-w-[590px] overflow-hidden p-0 border-t-4",
        alert ? getAlertBorderClass(alert.detection_status) : "border-t-stroke-strong",
      )}
    >
      <div className="-mx-6 -mb-6">
        {/* ── Section 1: Header ───────────────────────────────────────────── */}
        <div className="flex items-center justify-between border-b border-stroke px-6 py-4">
          <div>
            <p className="text-base font-bold uppercase tracking-widest text-fg">
              {alert?.detection_status === "Unverified" ? "Accident Detected" : "Accident Details"}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close incident details"
            className={cn(
              "rounded text-fg-muted transition-colors duration-150 hover:text-fg",
              focusRing,
            )}
          >
            <RiCloseLine size={20} />
          </button>
        </div>

        {/* ── Section 2a: Snapshot image ────────────────────────────────── */}
        <div className="flex min-h-[220px] items-center justify-center bg-surface-3 p-6">
          {alert ? (
            <SnapshotImage
              snapshotUrl={alert.snapshot_url}
              alt={`Accident snapshot for log ${alert.log_id}`}
              className="max-h-52 w-auto rounded border-2 border-stroke object-contain"
              fallbackClassName="h-40 w-full rounded"
            />
          ) : (
            <div className="text-xs text-fg-muted">Loading preview…</div>
          )}
        </div>

        {alert ? (
          <>
            {/* ── Section 2b: Accident ID + Status Badge ────────────────────── */}
            <div className="flex items-center justify-between bg-surface-1 px-6 py-3">
              <span className="text-2xl font-semibold text-fg">
                {formatAlertCode(alert.log_id)}
              </span>
              <span
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-semibold",
                  getAlertBadgeClass(alert.detection_status),
                )}
              >
                {alert.detection_status.toUpperCase()}
              </span>
            </div>

            {/* ── Section 3: Core Telemetry ─────────────────────────────────── */}
            <div className="space-y-3 bg-surface-1 px-6 pb-4">
              <div className="flex items-start justify-between">
                <span className="text-xs font-normal uppercase tracking-wider text-fg-muted">
                  Timestamp
                </span>
                <span className="text-right text-sm tabular-nums text-fg">
                  <span className="block">{formatFullDateTime(alert.detected_at)}</span>
                  {isDelayed && alert.detection_status === "Unverified" ? (
                    <span className="mt-0.5 block text-[10px] font-medium text-warning">
                      {formatDuration(ageSeconds)} ago — delivered late
                    </span>
                  ) : null}
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
                <span
                  className={cn(
                    "text-sm font-bold",
                    alert.confidence_score * 100 < 75 ? "text-danger" : "text-fg",
                  )}
                >
                  {formatAlertConfidence(alert.confidence_score)}
                </span>
              </div>

              {alert.detection_status !== "Unverified" && (
                <>
                  <hr className="border-border my-[14px]" />
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
                      <p className="mt-1 text-sm text-fg">
                        {formatFullDateTime(alert.verified_at)}
                      </p>
                    </div>
                  </div>
                  {isTerminal && (
                    <div className="mt-4 grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs font-normal uppercase tracking-wider text-fg-muted">
                          Closed By
                        </p>
                        <p className="mt-1 text-sm text-fg">{alert.closed_by_name ?? "—"}</p>
                      </div>
                      <div>
                        <p className="text-xs font-normal uppercase tracking-wider text-fg-muted">
                          {closedTimeLabel}
                        </p>
                        <p className="mt-1 text-sm text-fg">
                          {formatFullDateTime(alert.closed_at)}
                        </p>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {notice ? <div className="bg-surface-1 px-6 pb-1 pt-1">{notice}</div> : null}

            {/* ── Section 5: Footer Action Buttons ────────────────────────────── */}
            {!isTerminal && (
              <div className="flex w-full items-center gap-3 sm:gap-3.5 border-t border-stroke bg-surface-1 p-4 sm:p-5">
                {alert.detection_status === "Unverified" ? (
                  <>
                    {snoozeAction}
                    <Button
                      variant="secondary"
                      className="flex-1 whitespace-nowrap rounded bg-surface-3 py-3 px-3 text-xs sm:text-sm font-medium uppercase tracking-wider text-fg hover:bg-surface-2"
                      disabled={isTransitionPending}
                      isLoading={isDismissing}
                      loadingLabel="…"
                      onClick={() => onDismiss(alert.log_id)}
                    >
                      Dismiss Accident
                    </Button>
                    <Button
                      className="flex-1 whitespace-nowrap rounded bg-primary py-3 px-3 text-xs sm:text-sm font-medium uppercase tracking-wider text-fg-on-primary hover:bg-primary-hover"
                      disabled={isTransitionPending}
                      isLoading={isConfirming}
                      loadingLabel="…"
                      onClick={() => onConfirm(alert.log_id)}
                    >
                      Confirm Accident
                    </Button>
                  </>
                ) : alert.detection_status === "Ongoing" ? (
                  <>
                    <Button
                      variant="secondary"
                      className="flex-1 whitespace-nowrap rounded bg-surface-3 py-3 px-3 text-xs sm:text-sm font-medium uppercase tracking-wider text-fg hover:bg-surface-2"
                      disabled={isTransitionPending}
                      isLoading={isDismissing}
                      loadingLabel="…"
                      onClick={() => onDismiss(alert.log_id)}
                    >
                      Dismiss Accident
                    </Button>
                    <Button
                      className="flex-1 whitespace-nowrap rounded bg-primary py-3 px-3 text-xs sm:text-sm font-medium uppercase tracking-wider text-fg-on-primary hover:bg-primary-hover"
                      disabled={isTransitionPending}
                      isLoading={isResolving}
                      loadingLabel="…"
                      onClick={() => onResolve(alert.log_id)}
                    >
                      Resolve Accident
                    </Button>
                  </>
                ) : null}
              </div>
            )}
          </>
        ) : (
          <div className="bg-surface-1 py-12 text-center text-sm text-fg-muted">
            Loading alert details…
          </div>
        )}
      </div>
    </Modal>
  )
}
