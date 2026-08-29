/** One placeholder card, sized to match ArticleGrid's real card shape (same
 * container, same badge/title/summary/footer slots) so the grid never jumps
 * when real content swaps in. `animate-pulse` on the outer card, not each
 * bar individually, is the standard skeleton technique — every bar fades in
 * and out together as one shape rather than flickering independently. */
function ArticleCardSkeleton() {
  return (
    <div
      aria-hidden="true"
      className="flex h-full animate-pulse flex-col rounded-lg border border-stroke bg-surface-1 p-5 shadow-sm"
    >
      <div className="mb-3 h-5 w-24 rounded bg-surface-2" />
      <div className="h-4 w-3/4 rounded bg-surface-2" />
      <div className="mt-2 h-3 w-full rounded bg-surface-2" />
      <div className="mt-1.5 h-3 w-2/3 rounded bg-surface-2" />
      <div className="mt-auto h-3 w-20 rounded bg-surface-2 pt-4" />
    </div>
  )
}

/** Shown only while the list has never loaded anything at all — `listQuery`
 * keeps its previous results on screen for every later search or category
 * change (see `placeholderData: keepPreviousData` in HelpCenter.tsx), so
 * this is really just the very first paint of the page. */
export function ArticleGridSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading articles"
      className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
    >
      {Array.from({ length: 6 }, (_, index) => (
        <ArticleCardSkeleton key={index} />
      ))}
    </div>
  )
}
