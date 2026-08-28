import type { ReactNode } from "react"

import { Button, focusRing } from "@/components/ui/Button"
import { Modal } from "@/components/ui/Modal"
import { SnapshotImage } from "@/components/ui/SnapshotImage"
import type { AlertLog } from "@/api/alerts"
import { formatAlertCode, formatAlertConfidence, getAlertBadgeClass } from "@/utils/format"
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

  const statusBorderClass =
    alert?.detection_status === "Ongoing"
      ? "border-t-warning"
      : alert?.detection_status === "Resolved"
        ? "border-t-success"
        : "border-t-stroke-strong"

  const isUnverified = alert?.detection_status === "Unverified"

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      hideClose
      overlayClassName={cn("z-[9500]", overlayClassName)}
      className={cn(
        "w-full overflow-hidden p-0 rounded-none sm:rounded-lg border-0",
        isUnverified ? "max-w-[1060px]" : "max-w-[1220px]",
      )}
    >
      <div className="-mx-6 -mb-6 flex flex-col">
        {/* ── Section 1: Header ───────────────────────────────────────────── */}
        {isUnverified ? (
          <div className="relative flex h-[55px] w-full items-center justify-center bg-danger px-6 sm:px-[34px]">
            <h2 className="text-center font-sans text-[24px] font-bold uppercase leading-[36px] tracking-wide text-surface-3">
              Accident Detected
            </h2>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close incident details"
              className={cn(
                "absolute right-4 top-1/2 -translate-y-1/2 rounded p-1 text-surface-3 transition-colors duration-150 hover:text-canvas",
                focusRing,
              )}
            >
              <RiCloseLine size={24} />
            </button>
          </div>
        ) : (
          <div
            className={cn(
              "flex h-[60px] items-center justify-between border-t-4 bg-surface-1 px-6 sm:px-7",
              statusBorderClass,
            )}
          >
            <h2 className="font-sans text-[21px] font-bold uppercase leading-[36px] tracking-wide text-fg-body">
              Accident Details
            </h2>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close incident details"
              className={cn(
                "rounded p-1 text-fg-muted transition-colors duration-150 hover:text-fg",
                focusRing,
              )}
            >
              <RiCloseLine size={24} />
            </button>
          </div>
        )}

        {/* ── Section 2: Split Body Layout (Snapshot Image + Telemetry Panel) ── */}
        <div className="flex w-full flex-col items-stretch overflow-hidden md:flex-row">
          {/* Left Column: Snapshot Image Preview */}
          <div
            className={cn(
              "flex min-h-[260px] w-full shrink-0 items-center justify-center overflow-hidden bg-canvas md:h-[370px]",
              isUnverified ? "md:w-[560px] lg:w-[658px]" : "md:w-[600px] lg:w-[658px]",
            )}
          >
            {alert ? (
              <SnapshotImage
                snapshotUrl={alert.snapshot_url}
                alt={`Accident snapshot for log ${alert.log_id}`}
                className="h-full w-full object-cover"
                fallbackClassName="h-full w-full rounded-none"
              />
            ) : (
              <div className="text-xs text-fg-muted">Loading preview…</div>
            )}
          </div>

          {/* Right Column: Telemetry & Actions */}
          <div
            className={cn(
              "relative flex flex-1 flex-col justify-between bg-surface-2 min-w-0",
              isUnverified ? "sm:min-w-[380px]" : "sm:min-w-[480px] lg:min-w-[540px]",
            )}
          >
            {alert ? (
              <>
                <div className="custom-scrollbar flex flex-1 flex-col justify-between gap-4 overflow-y-auto p-6 sm:p-7">
                  {/* Top Row: Accident ID + Status Badge */}
                  <div className="flex items-center justify-between">
                    <span className="font-sans text-[28px] font-medium leading-8 text-fg-body">
                      {formatAlertCode(alert.log_id)}
                    </span>
                    <span
                      className={cn(
                        "rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide",
                        alert.detection_status === "Ongoing"
                          ? "bg-warning text-canvas"
                          : getAlertBadgeClass(alert.detection_status),
                      )}
                    >
                      {alert.detection_status}
                    </span>
                  </div>

                  {/* Telemetry rows: horizontal key-value alignment */}
                  <div className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[12px] font-normal uppercase leading-[21px] tracking-wider text-fg-muted">
                        TIMESTAMP
                      </span>
                      <span className="text-right tabular-nums text-[16px] font-medium leading-8 text-white">
                        {formatFullDateTime(alert.detected_at)}
                        {isDelayed && alert.detection_status === "Unverified" ? (
                          <span className="ml-2 inline-block text-[10px] font-medium text-warning">
                            ({formatDuration(ageSeconds)} ago — delayed)
                          </span>
                        ) : null}
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-[12px] font-normal uppercase leading-[21px] tracking-wider text-fg-muted">
                        CAMERA NAME
                      </span>
                      <span className="max-w-[75%] truncate text-right text-[16px] font-medium uppercase leading-8 text-white">
                        {alert.camera_name ?? `Camera ${alert.camera_id}`}
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-[12px] font-normal uppercase leading-[21px] tracking-wider text-fg-muted">
                        AI-CONFIDENCE SCORE
                      </span>
                      <span
                        className={cn(
                          "text-right tabular-nums text-[16px] font-medium leading-8",
                          alert.confidence_score * 100 < 75 ? "text-danger" : "text-white",
                        )}
                      >
                        {formatAlertConfidence(alert.confidence_score)}
                      </span>
                    </div>
                  </div>

                  {/* Divider */}
                  <div className="border-t border-stroke-strong" />

                  {/* Lower metadata: Verified By & Time Verified (or Closed info) */}
                  {alert.detection_status !== "Unverified" ? (
                    <div>
                      <div className="grid grid-cols-2 gap-6">
                        <div className="flex flex-col items-start">
                          <span className="text-[12px] font-normal uppercase leading-[21px] tracking-wider text-fg-muted">
                            VERIFIED BY
                          </span>
                          <span className="max-w-full truncate text-[14px] font-medium leading-7 text-white">
                            {alert.verified_by_name ?? "—"}
                          </span>
                        </div>
                        <div className="flex flex-col items-start">
                          <span className="text-[12px] font-normal uppercase leading-[21px] tracking-wider text-fg-muted">
                            TIME VERIFIED
                          </span>
                          <span className="max-w-full truncate tabular-nums text-[14px] font-medium leading-7 text-fg-body">
                            {formatFullDateTime(alert.verified_at)}
                          </span>
                        </div>
                      </div>
                      {isTerminal && (
                        <div className="mt-3 grid grid-cols-2 gap-4">
                          <div className="flex flex-col items-start">
                            <span className="text-[12px] font-normal uppercase leading-[21px] tracking-wider text-fg-muted">
                              CLOSED BY
                            </span>
                            <span className="max-w-full truncate text-[14px] font-medium leading-7 text-white">
                              {alert.closed_by_name ?? "—"}
                            </span>
                          </div>
                          <div className="flex flex-col items-start">
                            <span className="text-[12px] font-normal uppercase leading-[21px] tracking-wider text-fg-muted">
                              {closedTimeLabel}
                            </span>
                            <span className="max-w-full truncate tabular-nums text-[14px] font-medium leading-7 text-fg-body">
                              {formatFullDateTime(alert.closed_at)}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : null}

                  {notice ? <div className="pt-2">{notice}</div> : null}
                </div>

                {/* ── Section 3: Footer Action Buttons ──────────────────────── */}
                {!isTerminal && (
                  <div className="flex w-full items-center gap-3 sm:gap-4 bg-surface-1 px-5 sm:px-6 py-3">
                    {alert.detection_status === "Unverified" ? (
                      <>
                        {snoozeAction}
                        <Button
                          variant="secondary"
                          className="flex-1 whitespace-nowrap h-[44px] rounded-[4px] bg-border px-3 sm:px-4 py-2 text-xs sm:text-[14px] font-medium uppercase leading-[20px] tracking-wide text-fg hover:bg-surface-3"
                          disabled={isTransitionPending}
                          isLoading={isDismissing}
                          loadingLabel="…"
                          onClick={() => onDismiss(alert.log_id)}
                        >
                          Dismiss Accident
                        </Button>
                        <Button
                          className="flex-1 whitespace-nowrap h-[44px] rounded-[4px] bg-fg-body px-3 sm:px-4 py-2 text-xs sm:text-[14px] font-medium uppercase leading-[28px] tracking-wide text-surface-2 hover:bg-fg"
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
                          className="flex-1 whitespace-nowrap h-[44px] rounded-[4px] bg-border px-3 sm:px-4 py-2 text-xs sm:text-[14px] font-medium uppercase leading-[20px] tracking-wide text-fg hover:bg-surface-3"
                          disabled={isTransitionPending}
                          isLoading={isDismissing}
                          loadingLabel="…"
                          onClick={() => onDismiss(alert.log_id)}
                        >
                          Dismiss Accident
                        </Button>
                        <Button
                          className="flex-1 whitespace-nowrap h-[44px] rounded-[4px] bg-fg-body px-3 sm:px-4 py-2 text-xs sm:text-[14px] font-medium uppercase leading-[28px] tracking-wide text-surface-2 hover:bg-fg"
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
              <div className="flex flex-1 items-center justify-center p-6 text-sm text-fg-muted">
                Loading alert details…
              </div>
            )}
          </div>
        </div>
      </div>
    </Modal>
  )
}
