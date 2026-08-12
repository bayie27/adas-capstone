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
    <div className="mb-4 flex items-center justify-between gap-4 rounded-md border border-[#F87171]/30 bg-[#F87171]/10 px-4 py-3">
      <p className="text-xs text-[#FCA5A5]">{getApiErrorMessage(error, fallback)}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md border border-[#333] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[#1A1A1A]"
        >
          Retry
        </button>
      )}
    </div>
  )
}
