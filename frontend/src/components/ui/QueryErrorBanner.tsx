import { getApiErrorMessage } from "@/utils/api"

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
          className="rounded-md border border-stroke-strong px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-surface-1"
        >
          Retry
        </button>
      )}
    </div>
  )
}
