/** Mirrors the real article's layout (category badge, title, summary line,
 * body paragraphs) rather than a generic bar-of-text, so the page's shape
 * doesn't shift once the real article renders in its place. Shown on every
 * article open, not just the first — `articleQuery`'s key changes per
 * slug, so switching articles always refetches. */
export function ArticleDetailSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading article"
      className="min-w-0 flex-1 animate-pulse rounded-lg border border-stroke bg-surface-1 p-6"
    >
      <div className="mb-4 h-5 w-28 rounded bg-surface-2" />
      <div className="mb-2 h-6 w-2/3 rounded bg-surface-2" />
      <div className="mb-6 h-4 w-1/2 rounded bg-surface-2" />
      <div className="space-y-3">
        <div className="h-4 w-full rounded bg-surface-2" />
        <div className="h-4 w-full rounded bg-surface-2" />
        <div className="h-4 w-5/6 rounded bg-surface-2" />
        <div className="h-4 w-3/4 rounded bg-surface-2" />
      </div>
    </div>
  )
}
