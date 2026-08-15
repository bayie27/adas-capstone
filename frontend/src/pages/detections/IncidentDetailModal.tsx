import type { ReactNode } from "react"

import { Button } from "@/components/ui/Button"
import { Modal } from "@/components/ui/Modal"
import { SnapshotImage } from "@/components/ui/SnapshotImage"
import type { AlertLog, AlertStatus } from "@/api/alerts"
import { formatAlertCode, formatAlertConfidence } from "@/utils/format"
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

type Accent = "danger" | "warning" | "neutral"

const ACCENT_BORDER: Record<Accent, string> = {
  danger: "border-t-danger",
  warning: "border-t-warning",
  neutral: "border-t-stroke-strong",
}

const BADGE_CLASS: Record<Accent, string> = {
  danger: "bg-danger-subtle text-danger border border-danger-border",
  warning: "bg-warning-subtle text-warning border border-warning-border",
  neutral: "bg-surface-3 text-fg-muted border border-stroke",
}

function accentFor(status: AlertStatus): Accent {
  if (status === "Unverified") return "danger"
  if (status === "Ongoing") return "warning"
  return "neutral"
}

function MetaRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="font-medium tracking-[0.08em] text-fg-muted">{label}</span>
      <span className="font-medium text-fg-body">{value}</span>
    </div>
  )
}

function AttributionBlock({
  leftLabel,
  leftValue,
  rightLabel,
  rightValue,
}: {
  leftLabel: string
  leftValue: ReactNode
  rightLabel: string
  rightValue: ReactNode
}) {
  return (
    <div className="flex items-start justify-between">
      <div>
        <div className="mb-1.5 text-[10px] font-bold uppercase tracking-[0.08em] text-fg-muted">
          {leftLabel}
        </div>
        <div className="text-xs font-medium text-fg-body">{leftValue}</div>
      </div>
      <div className="text-right">
        <div className="mb-1.5 text-[10px] font-bold uppercase tracking-[0.08em] text-fg-muted">
          {rightLabel}
        </div>
        <div className="text-xs text-fg-body">{rightValue}</div>
      </div>
    </div>
  )
}

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
}: IncidentDetailModalProps) {
  // Only ticks while an Unverified incident is open — the only case where the
  // gap between "detected" and "now" is a live decision input.
  const now = useNow(isOpen && alert?.detection_status === "Unverified", 30_000)
  const ageSeconds = alert ? secondsSince(alert.detected_at, now) : null
  const isDelayed = ageSeconds !== null && ageSeconds >= STALE_DETECTION_SECONDS

  const accent: Accent = alert ? accentFor(alert.detection_status) : "neutral"
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
      className={cn("max-w-lg overflow-hidden border-t-4 p-0", ACCENT_BORDER[accent])}
    >
      <div className="flex flex-col bg-surface-2">
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="text-xs font-semibold uppercase tracking-[0.08em] text-fg">
            {alert?.detection_status === "Unverified" ? "Accident Detected" : "Accident Details"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close incident details"
            className="text-fg-muted transition-colors hover:text-fg"
          >
            <RiCloseLine size={18} />
          </button>
        </div>

        <div className="flex aspect-video w-full items-center justify-center border-b border-stroke bg-surface-1">
          {alert ? (
            <SnapshotImage
              snapshotUrl={alert.snapshot_url}
              alt={`${formatAlertCode(alert.log_id)} snapshot`}
              className="h-full w-full object-contain"
              fallbackClassName="h-32 w-48 border border-stroke-strong bg-surface-1 text-fg-muted"
            />
          ) : (
            <div className="text-xs text-fg-muted">Loading preview…</div>
          )}
        </div>

        <div className="p-6">
          {alert ? (
            <>
              <div className="mb-5 flex items-center gap-3">
                <span className="text-xl font-semibold text-fg">
                  {formatAlertCode(alert.log_id)}
                </span>
                <span
                  className={cn(
                    "rounded-sm px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.08em]",
                    BADGE_CLASS[accent],
                  )}
                >
                  {alert.detection_status}
                </span>
              </div>

              <div className="mb-6 space-y-3.5">
                <MetaRow
                  label="TIMESTAMP"
                  value={
                    <span className="text-right">
                      <span className="block">{formatFullDateTime(alert.detected_at)}</span>
                      {isDelayed && alert.detection_status === "Unverified" ? (
                        <span className="mt-0.5 block text-[10px] font-medium text-warning">
                          {formatDuration(ageSeconds)} ago — delivered late
                        </span>
                      ) : null}
                    </span>
                  }
                />
                <MetaRow label="CAMERA NAME" value={alert.camera_name ?? "Unknown Camera"} />
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium tracking-[0.08em] text-fg-muted">
                    AI-CONFIDENCE SCORE
                  </span>
                  <span className="rounded bg-danger-subtle px-1.5 py-0.5 font-bold text-danger">
                    {formatAlertConfidence(alert.confidence_score)}
                  </span>
                </div>
              </div>

              {/*
                The unverified variant has nothing to attribute yet — nobody has
                verified or closed it — so the whole block is omitted rather
                than rendered full of dashes.
              */}
              {alert.detection_status !== "Unverified" ? (
                <div className="mb-6 space-y-4 border-t border-border pt-5">
                  <AttributionBlock
                    leftLabel="VERIFIED BY"
                    leftValue={alert.verified_by_name ?? "-"}
                    rightLabel="TIME VERIFIED"
                    rightValue={formatFullDateTime(alert.verified_at)}
                  />
                  {isTerminal ? (
                    <AttributionBlock
                      leftLabel="CLOSED BY"
                      leftValue={alert.closed_by_name ?? "-"}
                      rightLabel={closedTimeLabel}
                      rightValue={formatFullDateTime(alert.closed_at)}
                    />
                  ) : null}
                </div>
              ) : null}

              {notice}

              {alert.detection_status === "Unverified" ? (
                <div className="flex items-center gap-3">
                  {snoozeAction}
                  <Button
                    variant="outline"
                    className="flex-1 uppercase tracking-[0.08em]"
                    disabled={isTransitionPending}
                    isLoading={isDismissing}
                    loadingLabel="Dismissing…"
                    onClick={() => onDismiss(alert.log_id)}
                  >
                    Dismiss Accident
                  </Button>
                  <Button
                    variant="primary"
                    className="flex-1 uppercase tracking-[0.08em]"
                    disabled={isTransitionPending}
                    isLoading={isConfirming}
                    loadingLabel="Confirming…"
                    onClick={() => onConfirm(alert.log_id)}
                  >
                    Confirm Accident
                  </Button>
                </div>
              ) : null}

              {alert.detection_status === "Ongoing" ? (
                <div className="flex items-center gap-3">
                  <Button
                    variant="outline"
                    className="flex-1 uppercase tracking-[0.08em]"
                    disabled={isTransitionPending}
                    isLoading={isDismissing}
                    loadingLabel="Dismissing…"
                    onClick={() => onDismiss(alert.log_id)}
                  >
                    Dismiss Accident
                  </Button>
                  <Button
                    variant="primary"
                    className="flex-1 uppercase tracking-[0.08em]"
                    disabled={isTransitionPending}
                    isLoading={isResolving}
                    loadingLabel="Resolving…"
                    onClick={() => onResolve(alert.log_id)}
                  >
                    Resolve Accident
                  </Button>
                </div>
              ) : null}

              {/*
                124:9186 draws no action buttons on a terminal incident, and
                that is a contract statement rather than a layout choice: the
                backend rejects every transition out of Dismissed or Resolved,
                so offering one would be a button that can only fail.
              */}
            </>
          ) : (
            <div className="py-12 text-center text-sm text-fg-muted">Loading alert details…</div>
          )}
        </div>
      </div>
    </Modal>
  )
}
