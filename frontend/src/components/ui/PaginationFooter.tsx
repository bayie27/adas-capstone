import { RiArrowLeftSLine, RiArrowRightSLine } from "@remixicon/react"

import { cn } from "@/utils/cn"
import { focusRing } from "@/components/ui/Button"

/**
 * The pagination footer as drawn on `37:74` and `38:82`.
 *
 * The two capabilities the frames show and the old footer only mimicked are
 * opt-in, so the pages that have not adopted them yet render exactly as
 * before:
 *
 * - pass `onPageSizeChange` and the items-per-page count becomes a real
 *   selector instead of a static chip;
 * - pass `onPageChange` and the "N of M" text becomes numbered page chips.
 *
 * Both are inert until a screen phase wires them up, which keeps this
 * component's rebuild off the screenshot diff.
 */
const PAGE_SIZE_OPTIONS = [10, 25, 50, 100]

/** Windowed page list: first, last, and a run around the current page. */
function pageWindow(page: number, totalPages: number): Array<number | "gap"> {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1)
  }

  const pages: Array<number | "gap"> = [1]
  const from = Math.max(2, page - 1)
  const to = Math.min(totalPages - 1, page + 1)

  if (from > 2) pages.push("gap")
  for (let n = from; n <= to; n++) pages.push(n)
  if (to < totalPages - 1) pages.push("gap")

  pages.push(totalPages)
  return pages
}

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
  /** Opt-in: turns the page indicator into numbered chips. */
  onPageChange?: (page: number) => void
  /** Opt-in: turns the items-per-page count into a selector. */
  onPageSizeChange?: (pageSize: number) => void
  pageSizeOptions?: number[]
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
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = PAGE_SIZE_OPTIONS,
}: PaginationFooterProps) {
  const navButton = cn(
    "flex items-center gap-1 rounded-sm transition-colors duration-150 hover:text-fg",
    "disabled:cursor-not-allowed disabled:opacity-50",
    focusRing,
  )

  return (
    <div className="flex items-center justify-between border-t border-stroke px-6 py-3 text-xs text-fg-muted">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          Items per page
          {onPageSizeChange ? (
            <select
              value={pageSize}
              onChange={(event) => onPageSizeChange(Number(event.target.value))}
              aria-label="Items per page"
              className={cn(
                "rounded border border-stroke bg-surface-1 px-2 py-1 text-fg",
                "transition-colors duration-150 hover:border-stroke-strong",
                focusRing,
              )}
            >
              {pageSizeOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          ) : (
            <span className="flex items-center gap-1 rounded border border-stroke bg-surface-1 px-2 py-1 text-fg">
              {pageSize}
            </span>
          )}
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
          className={navButton}
        >
          <RiArrowLeftSLine size={14} /> Previous
        </button>

        {onPageChange ? (
          <div className="flex items-center gap-1">
            {pageWindow(page, totalPages).map((entry, index) =>
              entry === "gap" ? (
                <span key={`gap-${index}`} className="px-1">
                  …
                </span>
              ) : (
                <button
                  key={entry}
                  type="button"
                  onClick={() => onPageChange(entry)}
                  disabled={isFetching}
                  aria-current={entry === page ? "page" : undefined}
                  className={cn(
                    "flex h-6 min-w-6 items-center justify-center rounded px-2 transition-colors duration-150",
                    "disabled:cursor-not-allowed disabled:opacity-50",
                    entry === page
                      ? "bg-surface-2 font-medium text-fg"
                      : "hover:bg-surface-1 hover:text-fg",
                    focusRing,
                  )}
                >
                  {entry}
                </button>
              ),
            )}
          </div>
        ) : (
          <div className="flex items-center gap-1">
            <span className="flex h-6 min-w-6 items-center justify-center rounded bg-surface-2 px-2 font-medium text-fg">
              {page}
            </span>
            <span className="text-fg-muted">of</span>
            <span>{totalPages}</span>
          </div>
        )}

        <button
          type="button"
          disabled={page >= totalPages || isFetching}
          onClick={onNext}
          className={navButton}
        >
          Next <RiArrowRightSLine size={14} />
        </button>
      </div>
    </div>
  )
}
