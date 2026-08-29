import { useMemo, useState } from "react"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { useSearchParams } from "react-router-dom"

import { getHelpArticle, getHelpArticles } from "@/api/help"
import { OverlayErrorBanner } from "@/components/ui/OverlayErrorBanner"
import { SearchInput } from "@/components/ui/SearchInput"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { ArticleDetail } from "./help/ArticleDetail"
import { ArticleGrid } from "./help/ArticleGrid"
import { ArticleGridSkeleton } from "./help/ArticleGridSkeleton"
import { CategoryTabs } from "./help/CategoryTabs"
import { EMPTY_ARTICLES, useAnimatedArticles } from "./help/useAnimatedArticles"

const HELP_CATEGORIES_QUERY_KEY = ["help-categories"] as const

/** A search term echoed back into an empty-state sentence can otherwise run
 * the full width of the page (up to the 200-char backend limit) with no
 * spaces to wrap on, e.g. a pasted string with no word breaks. Truncating
 * what's displayed (never what's actually searched) keeps that sentence
 * readable regardless of what was typed. */
function truncateForDisplay(term: string, max = 60): string {
  return term.length > max ? `${term.slice(0, max)}…` : term
}

/**
 * No Figma frame (D-5). Follows the same list-then-detail shape as
 * Detections/Users rather than inventing a new idiom: a toolbar (search +
 * category), a card grid of articles, and a detail view that replaces the
 * grid rather than opening a modal — an article is prose meant to be read
 * at length, which a modal is the wrong shape for.
 *
 * The page itself only owns state, data-fetching, and layout — every visual
 * piece (the category tablist, the grid, an article's own reading view, and
 * their loading skeletons) lives in ./help/ as its own component, so this
 * file stays a short orchestrator rather than growing every time one of
 * those pieces gets more detailed.
 */
export default function HelpCenter() {
  const [searchTerm, setSearchTerm] = useState("")
  const [category, setCategory] = useState("")
  // The open article lives in the URL, not local state, so it gets its own
  // browser-history entry — otherwise the browser's Back button has nothing
  // of ours to pop and skips straight past the Help Center to whatever page
  // was open before it, which is the bug this fixes.
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedSlug = searchParams.get("article")
  const debouncedSearch = useDebouncedValue(searchTerm.trim(), 300)

  // Categories need the *unfiltered* population, independent of whatever
  // search/category is currently applied to the list below — otherwise a
  // category filter would prune the very options used to change it. Cheap:
  // the backend returns the full role-visible set in one call, unpaginated.
  const categoriesQuery = useQuery({
    queryKey: HELP_CATEGORIES_QUERY_KEY,
    queryFn: () => getHelpArticles({}),
    staleTime: 5 * 60_000,
  })

  const categoryValues = useMemo(
    () => [...new Set((categoriesQuery.data?.items ?? []).map((a) => a.category))].sort(),
    [categoriesQuery.data],
  )

  const listQuery = useQuery({
    queryKey: ["help-articles", debouncedSearch, category],
    queryFn: () =>
      getHelpArticles({
        search: debouncedSearch || undefined,
        category: category || undefined,
      }),
    // Keeps the previous result set on screen (and `isLoading` false) while
    // a new search or category refetches, instead of the whole grid
    // dropping out to a loading skeleton on every keystroke — the grid then
    // only ever has to animate a card in or out, never blink.
    placeholderData: keepPreviousData,
  })

  const articleQuery = useQuery({
    queryKey: ["help-article", selectedSlug],
    queryFn: () => getHelpArticle(selectedSlug as string),
    enabled: selectedSlug !== null,
  })

  const items = listQuery.data?.items ?? EMPTY_ARTICLES
  const topFaqs = listQuery.data?.top_faqs ?? EMPTY_ARTICLES
  // Mirrors the backend's own condition exactly (`searched and not articles`
  // in routes/help.py) rather than reinventing when the fallback applies —
  // it must never appear on a plain browse or a category-only filter.
  const showFaqFallback = debouncedSearch !== "" && items.length === 0 && topFaqs.length > 0
  const displayedItems = showFaqFallback ? topFaqs : items
  const animatedGrid = useAnimatedArticles(displayedItems)

  function openArticle(slug: string) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set("article", slug)
      return next
    })
  }

  function closeArticle() {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete("article")
      return next
    })
  }

  function goToCategory(nextCategory: string) {
    closeArticle()
    setCategory(nextCategory)
  }

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6">
        <h1 className="mb-0.5 text-xl font-semibold text-fg">
          {/* Clickable, not styled as a button — same "plain text that
              happens to react to a click" treatment as the breadcrumb's own
              "Help Center" crumb in ArticleDetail. Returns to the article
              list from wherever you are on the page, the way a page
              title/logo commonly does; a no-op when you're on the list
              already. */}
          <button
            type="button"
            onClick={closeArticle}
            className="text-left transition-colors duration-150 hover:text-fg-muted"
          >
            Help Center
          </button>
        </h1>
        <p className="text-xs text-fg-muted">
          Role-filtered operating guides: search, browse by category, or read an article
        </p>
      </div>

      {selectedSlug ? (
        <ArticleDetail
          key={selectedSlug}
          query={articleQuery}
          onBack={closeArticle}
          onNavigateToSlug={openArticle}
          onNavigateToCategory={goToCategory}
        />
      ) : (
        // `animate-modal-enter` plays once whenever this branch (re)mounts —
        // switching back from reading an article, or the page's first
        // load — rather than on every keystroke, since React keeps this
        // same DOM node across re-renders within the branch.
        <div className="animate-modal-enter">
          {/* One toolbar row (search + category), matching the
              search-plus-filters convention every other list page in this
              app already uses (e.g. Cameras.tsx) rather than the two
              stacked full-width rows this page used to have. */}
          <div className="mb-6 flex flex-wrap items-center gap-2.5">
            <SearchInput
              value={searchTerm}
              onChange={setSearchTerm}
              placeholder="Search articles..."
              maxLength={200}
            />
            <CategoryTabs categories={categoryValues} value={category} onChange={setCategory} />
          </div>

          {/* `relative` so a failed list query overlays this region instead
              of pushing it down and back up every time the query fails or
              recovers — see OverlayErrorBanner. */}
          <div className="relative">
            {listQuery.isError ? (
              <OverlayErrorBanner
                error={listQuery.error}
                fallback="Unable to load help articles."
                onRetry={() => listQuery.refetch()}
              />
            ) : listQuery.isLoading ? (
              <ArticleGridSkeleton />
            ) : (
              <>
                {showFaqFallback ? (
                  <p className="mb-4 break-words text-caption text-fg-muted">
                    No articles matched &ldquo;{truncateForDisplay(debouncedSearch)}&rdquo;. Here
                    are some frequently asked questions:
                  </p>
                ) : displayedItems.length === 0 ? (
                  <p className="py-8 text-center text-caption text-fg-muted">
                    No articles found for the current filters.
                  </p>
                ) : null}
                {/* Renders the outgoing set's leftover cards too (fading
                    out) alongside whatever just matched — see
                    useAnimatedArticles — so narrowing a search or category
                    reads as the grid settling into its new shape rather
                    than an instant swap. */}
                {animatedGrid.items.length > 0 ? (
                  <ArticleGrid
                    articles={animatedGrid.items}
                    onSelect={openArticle}
                    isLeaving={animatedGrid.isLeaving}
                  />
                ) : null}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
