import { getApiErrorMessage } from "@/api/client"
import { cn } from "@/utils/cn"
import { focusRing } from "@/components/ui/Button"

/**
 * Same content and props as QueryErrorBanner, but floats above whatever
 * it's layered over instead of occupying flow space — a failed query
 * shouldn't shove the rest of the page down every time it fires, then snap
 * back up the moment it recovers.
 *
 * Positioned `absolute inset-x-0 top-0`, so the caller must give it a
 * `relative`-positioned ancestor to overlay against — deliberately not
 * `fixed`, since a page-level query error should stay scoped to the
 * region it's actually about (the toolbar and title above it are still
 * valid) rather than floating over the entire viewport the way an
 * app-wide notice like MaintenanceNotice does.
 */
export function OverlayErrorBanner({
  error,
  fallback,
  onRetry,
}: {
  error: unknown
  fallback: string
  onRetry?: () => void
}) {
  return (
    <div className="absolute inset-x-0 top-0 z-10">
      <div className="flex items-center justify-between gap-4 rounded-md border border-danger-border bg-danger-subtle px-4 py-3 shadow-lg">
        <p className="text-xs text-danger">{getApiErrorMessage(error, fallback)}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className={cn(
              "shrink-0 rounded-md border border-stroke-strong px-3 py-1.5 text-xs font-medium text-fg",
              "transition-colors duration-150 hover:bg-surface-2",
              focusRing,
            )}
          >
            Retry
          </button>
        )}
      </div>
    </div>
  )
}
