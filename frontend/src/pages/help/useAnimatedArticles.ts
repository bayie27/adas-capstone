import { useEffect, useRef, useState } from "react"

import type { HelpArticleSummary } from "@/api/help"

/** A stable empty-array reference, so a component reading `data?.items ??
 * EMPTY_ARTICLES` doesn't create a new array identity on every render while
 * loading — that would otherwise retrigger effects keyed on that value for
 * no real reason. */
export const EMPTY_ARTICLES: HelpArticleSummary[] = []

const EMPTY_SLUGS: ReadonlySet<string> = new Set()
const GRID_LEAVE_MS = 200

/**
 * A search or category change swaps the entire result set at once (it's a
 * new server query, not a client-side filter), so React would otherwise
 * unmount the cards that no longer match instantly rather than letting them
 * fade out. This keeps a just-removed card mounted (in `.animate-grid-item-
 * leave`, matched to GRID_LEAVE_MS) until its exit animation has actually
 * played, then drops it. Cards that stay or arrive need no equivalent
 * "entering" bookkeeping — they either keep their existing DOM node (key
 * unchanged, animation already played, doesn't replay) or are genuinely new
 * (key unchanged from unmounted, plays `.animate-grid-item-enter` on mount
 * for free) — React's own keyed reconciliation already does the right thing
 * for both.
 */
export function useAnimatedArticles(items: HelpArticleSummary[], leaveMs = GRID_LEAVE_MS) {
  const [rendered, setRendered] = useState(items)
  const [leaving, setLeaving] = useState<ReadonlySet<string>>(EMPTY_SLUGS)
  const renderedRef = useRef(items)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const nextSlugs = new Set(items.map((a) => a.slug))
    const removed = renderedRef.current.filter((a) => !nextSlugs.has(a.slug))

    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }

    if (removed.length === 0) {
      renderedRef.current = items
      setRendered(items)
      setLeaving(EMPTY_SLUGS)
      return
    }

    const merged = [...items, ...removed]
    renderedRef.current = merged
    setRendered(merged)
    setLeaving(new Set(removed.map((a) => a.slug)))

    timeoutRef.current = setTimeout(() => {
      renderedRef.current = items
      setRendered(items)
      setLeaving(EMPTY_SLUGS)
      timeoutRef.current = null
    }, leaveMs)
  }, [items, leaveMs])

  useEffect(
    () => () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    },
    [],
  )

  return { items: rendered, isLeaving: (slug: string) => leaving.has(slug) }
}
