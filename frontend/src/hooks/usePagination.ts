import { useState } from "react"

/**
 * Page state for a fixed-size list. `page` is clamped at read time, so an
 * out-of-range page (e.g. after a filter shrinks the result set) never renders
 * and never fires a query with an invalid offset — the clamp is derivation, not
 * an effect that runs after a wasted render/fetch.
 */
export function usePagination(totalFiltered: number, initialPageSize: number) {
  const [rawPage, setRawPage] = useState(1)
  // Page size is state, not a constant, so `PaginationFooter`'s items-per-page
  // selector has something to drive. It was built in Phase 4 and passed by no
  // page until now.
  const [pageSize, setRawPageSize] = useState(initialPageSize)

  const totalPages = Math.max(1, Math.ceil(totalFiltered / pageSize))
  const page = Math.min(rawPage, totalPages)
  const offset = (page - 1) * pageSize

  return {
    page,
    pageSize,
    totalPages,
    offset,
    rangeStart: totalFiltered === 0 ? 0 : offset + 1,
    rangeEnd: (visibleCount: number) => (totalFiltered === 0 ? 0 : offset + visibleCount),
    next: () => setRawPage(Math.min(totalPages, page + 1)),
    prev: () => setRawPage(Math.max(1, page - 1)),
    /** Jump to a page, for PaginationFooter's numbered chips. Clamped like the rest. */
    goTo: (target: number) => setRawPage(Math.min(totalPages, Math.max(1, target))),
    /**
     * Changing the page size always returns to page 1.
     *
     * Keeping the page number would move the operator to a different set of
     * rows than the one they were reading — page 3 of 10-per-page and page 3
     * of 50-per-page start 120 rows apart — and on a growing list it can land
     * past the end. Clamp-at-read would catch the overflow, but silently
     * showing a different slice is the part that misleads.
     */
    setPageSize: (size: number) => {
      setRawPageSize(size)
      setRawPage(1)
    },
    reset: () => setRawPage(1),
  }
}
