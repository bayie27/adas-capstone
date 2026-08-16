import { RiAlertLine } from "@remixicon/react"

import { formatDuration } from "@/utils/datetime"
import { cn } from "@/utils/cn"

/**
 * Modelled on `MaintenanceNotice.tsx`'s banner shape (a dismissable-looking
 * strip across the top of the app, warning tone by default), but this one
 * takes plain props and fetches nothing — there is no backend endpoint yet
 * that exposes the AI engine's undelivered-detection backlog (G5,
 * `ai_engine/outbox.py`). Not mounted anywhere: there is no data source to
 * drive it, and a banner permanently wired to zero would be indistinguishable
 * from one that was never built, which defeats the point of shelling it now.
 * The day G5 ships, this becomes a real `useQuery`-backed component mounted
 * in `App.tsx` alongside `MaintenanceNotice`/`DevPanelTrigger` — this file is
 * that component's presentation half, already built and already tested.
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
