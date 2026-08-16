import { RiAlertLine } from "@remixicon/react"

import { formatDuration } from "@/utils/datetime"
import { cn } from "@/utils/cn"

/**
 * Modelled on `MaintenanceNotice.tsx`'s banner shape (a strip across the top
 * of the app, warning tone by default). This half is pure presentation —
 * plain props, no fetch of its own — because there is no backend endpoint
 * yet that exposes the AI engine's undelivered-detection backlog (G5,
 * `ai_engine/outbox.py`). The fetch lives in `useDeliveryBacklog`
 * (`hooks/useDeliveryBacklog.ts`), which always returns `null` today for
 * exactly that reason. Mounted in `App.tsx` alongside `MaintenanceNotice` —
 * same idiom: wired all the way through, renders nothing most of the time,
 * not "built but not wired in."
 *
 * Renders nothing when `pendingCount` is 0 — a backlog of zero is not a
 * warning.
 */
export function DeliveryBacklogNotice({
  pendingCount,
  oldestPendingAgeSeconds,
  quarantinedCount,
}: {
  pendingCount: number
  oldestPendingAgeSeconds: number | null
  quarantinedCount: number
}) {
  if (pendingCount <= 0) return null

  const isDanger = quarantinedCount > 0

  return (
    <div role="status" className="fixed inset-x-0 top-0 z-[9998]">
      <div
        className={cn(
          "flex items-center gap-2 border-b px-4 py-2.5 text-caption",
          isDanger
            ? "border-danger-border bg-danger-subtle text-danger"
            : "border-warning-border bg-warning-subtle text-warning",
        )}
      >
        <RiAlertLine size={15} className="shrink-0" aria-hidden="true" />
        <span>
          {pendingCount} accident detection{pendingCount === 1 ? "" : "s"} awaiting delivery to the
          backend
          {oldestPendingAgeSeconds !== null
            ? ` (oldest: ${formatDuration(oldestPendingAgeSeconds)})`
            : ""}
          .{isDanger ? ` ${quarantinedCount} quarantined and will not be retried.` : ""}
        </span>
      </div>
    </div>
  )
}
