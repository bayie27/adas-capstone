import { RiArrowLeftSLine, RiArrowRightSLine } from "@remixicon/react"

interface PaginationFooterProps {
  page: number
  totalPages: number
  rangeStart: number
  rangeEnd: number
  totalFiltered: number
  pageSize: number
  isFetching: boolean
  onPrev: () => void
  onNext: () => void
}

export function PaginationFooter({
  page,
  totalPages,
  rangeStart,
  rangeEnd,
  totalFiltered,
  pageSize,
  isFetching,
  onPrev,
  onNext,
}: PaginationFooterProps) {
  return (
    <div className="flex items-center justify-between border-t border-stroke px-6 py-3 text-xs text-fg-muted">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          Items per page
          <span className="flex items-center gap-1 rounded border border-stroke bg-surface-1 px-2 py-1 text-white">
            {pageSize}
          </span>
        </div>
        <span>
          {rangeStart}-{rangeEnd} of {totalFiltered}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={page === 1 || isFetching}
          onClick={onPrev}
          className="flex items-center gap-1 transition-colors hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RiArrowLeftSLine size={14} /> Previous
        </button>
        <div className="flex items-center gap-1">
          <span className="flex h-6 min-w-6 items-center justify-center rounded bg-surface-2 px-2 font-medium text-white">
            {page}
          </span>
          <span className="text-fg-muted">of</span>
          <span>{totalPages}</span>
        </div>
        <button
          type="button"
          disabled={page >= totalPages || isFetching}
          onClick={onNext}
          className="flex items-center gap-1 transition-colors hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          Next <RiArrowRightSLine size={14} />
        </button>
      </div>
    </div>
  )
}
