import { ArticleGridSkeleton } from "./ArticleGridSkeleton"

/**
 * The route-level fallback for HelpCenter's own lazy chunk (see App.tsx) —
 * shown only on a cold visit, before that chunk has downloaded. Deliberately
 * a separate, statically-imported file rather than something exported from
 * HelpCenter.tsx itself: a Suspense fallback for a lazy import can't live
 * inside the very chunk it's standing in for.
 *
 * Mirrors the real page's shell (title block, then a toolbar-shaped row,
 * then the same grid skeleton the page uses once its data is loading) so
 * this reads as one continuous skeleton rather than a generic spinner
 * handing off to a second, differently-shaped one a moment later.
 */
export function HelpCenterPageSkeleton() {
  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6 animate-pulse space-y-2">
        <div className="h-6 w-40 rounded bg-surface-2" />
        <div className="h-4 w-72 rounded bg-surface-2" />
      </div>
      <div className="mb-6 flex flex-wrap items-center gap-2.5">
        <div className="h-9 w-60 animate-pulse rounded bg-surface-2" />
        <div className="h-9 w-96 animate-pulse rounded-md bg-surface-2" />
      </div>
      <ArticleGridSkeleton />
    </div>
  )
}
