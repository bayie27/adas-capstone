import { useState } from "react"

/**
 * Page state for a fixed-size list. `page` is clamped at read time, so an
 * out-of-range page (e.g. after a filter shrinks the result set) never renders
 * and never fires a query with an invalid offset — the clamp is derivation, not
 * an effect that runs after a wasted render/fetch.
 */
export function usePagination(totalFiltered: number, pageSize: number) {
  const [rawPage, setRawPage] = useState(1)

  const totalPages = Math.max(1, Math.ceil(totalFiltered / pageSize))
  const page = Math.min(rawPage, totalPages)
  const offset = (page - 1) * pageSize

  return {
    page,
    totalPages,
    offset,
    rangeStart: totalFiltered === 0 ? 0 : offset + 1,
    rangeEnd: (visibleCount: number) => (totalFiltered === 0 ? 0 : offset + visibleCount),
    next: () => setRawPage(Math.min(totalPages, page + 1)),
    prev: () => setRawPage(Math.max(1, page - 1)),
    /** Jump to a page, for PaginationFooter's numbered chips. Clamped like the rest. */
    goTo: (target: number) => setRawPage(Math.min(totalPages, Math.max(1, target))),
    reset: () => setRawPage(1),
  }
}
