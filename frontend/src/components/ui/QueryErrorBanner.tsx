import { getApiErrorMessage } from "@/api/client"
import { cn } from "@/utils/cn"
import { focusRing } from "@/components/ui/Button"

export function QueryErrorBanner({
  error,
  fallback,
  onRetry,
}: {
  error: unknown
  fallback: string
  onRetry?: () => void
}) {
  return (
    <div className="mb-4 flex items-center justify-between gap-4 rounded-md border border-danger-border bg-danger-subtle px-4 py-3">
      <p className="text-xs text-danger">{getApiErrorMessage(error, fallback)}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className={cn(
            "rounded-md border border-stroke-strong px-3 py-1.5 text-xs font-medium text-fg",
            "transition-colors duration-150 hover:bg-surface-2",
            focusRing,
          )}
        >
          Retry
        </button>
      )}
    </div>
  )
}
