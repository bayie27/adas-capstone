import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  RiArrowLeftLine,
  RiArrowRightSLine,
  RiBookOpenLine,
  RiQuestionLine,
} from "@remixicon/react"

import { getHelpArticle, getHelpArticles } from "@/api/help"
import type { HelpArticleSummary } from "@/api/help"
import { Badge } from "@/components/ui/Badge"
import { FilterSelect } from "@/components/ui/FilterSelect"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { SearchInput } from "@/components/ui/SearchInput"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { getApiErrorMessage } from "@/api/client"

const HELP_CATEGORIES_QUERY_KEY = ["help-categories"] as const

/**
 * No Figma frame (D-5). Follows the same list-then-detail shape as
 * Detections/Users rather than inventing a new idiom: a toolbar (search +
 * category), a card grid of articles, and a detail view that replaces the
 * grid rather than opening a modal — an article is prose meant to be read
 * at length, which a modal is the wrong shape for.
 */
export default function HelpCenter() {
  const [searchTerm, setSearchTerm] = useState("")
  const [category, setCategory] = useState("")
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null)
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

  const categoryOptions = useMemo(() => {
    const unique = [...new Set((categoriesQuery.data?.items ?? []).map((a) => a.category))].sort()
    return [
      { value: "", label: "All categories" },
      ...unique.map((name) => ({ value: name, label: name })),
    ]
  }, [categoriesQuery.data])

  const listQuery = useQuery({
    queryKey: ["help-articles", debouncedSearch, category],
    queryFn: () =>
      getHelpArticles({
        search: debouncedSearch || undefined,
        category: category || undefined,
      }),
  })

  const articleQuery = useQuery({
    queryKey: ["help-article", selectedSlug],
    queryFn: () => getHelpArticle(selectedSlug as string),
    enabled: selectedSlug !== null,
  })

  const items = listQuery.data?.items ?? []
  const topFaqs = listQuery.data?.top_faqs ?? []
  // Mirrors the backend's own condition exactly (`searched and not articles`
  // in routes/help.py) rather than reinventing when the fallback applies —
  // it must never appear on a plain browse or a category-only filter.
  const showFaqFallback = debouncedSearch !== "" && items.length === 0 && topFaqs.length > 0

  function openArticle(slug: string) {
    setSelectedSlug(slug)
  }

  return (
    <div className="mx-auto max-w-[1400px] p-8">
      <div className="mb-6">
        <h1 className="mb-0.5 text-xl font-semibold text-fg">Help Center</h1>
        <p className="text-xs text-fg-muted">
          Role-filtered operating guides — search, browse by category, or read an article
        </p>
      </div>

      {selectedSlug ? (
        <ArticleDetail query={articleQuery} onBack={() => setSelectedSlug(null)} />
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-center gap-2.5">
            <SearchInput
              value={searchTerm}
              onChange={setSearchTerm}
              placeholder="Search articles..."
            />
            <FilterSelect value={category} options={categoryOptions} onChange={setCategory} />
          </div>

          {listQuery.isError ? (
            <QueryErrorBanner
              error={listQuery.error}
              fallback="Unable to load help articles."
              onRetry={() => listQuery.refetch()}
            />
          ) : null}

          {listQuery.isLoading ? (
            <p className="py-8 text-center text-caption text-fg-muted">Loading articles…</p>
          ) : showFaqFallback ? (
            <div>
              <p className="mb-4 text-caption text-fg-muted">
                No articles matched &ldquo;{debouncedSearch}&rdquo;. Here are some frequently asked
                questions:
              </p>
              <ArticleGrid articles={topFaqs} onSelect={openArticle} />
            </div>
          ) : items.length === 0 ? (
            <p className="py-8 text-center text-caption text-fg-muted">
              No articles found for the current filters.
            </p>
          ) : (
            <ArticleGrid articles={items} onSelect={openArticle} />
          )}
        </>
      )}
    </div>
  )
}

function ArticleGrid({
  articles,
  onSelect,
}: {
  articles: HelpArticleSummary[]
  onSelect: (slug: string) => void
}) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {articles.map((article) => (
        <button
          key={article.slug}
          type="button"
          onClick={() => onSelect(article.slug)}
          className="flex flex-col items-start rounded-xl border border-stroke bg-surface-1 p-5 text-left transition-colors duration-150 hover:border-stroke-strong hover:bg-surface-2"
        >
          <div className="mb-3 flex w-full items-center justify-between gap-2">
            <Badge variant="subtle" tone="neutral">
              {article.category}
            </Badge>
            {article.is_faq ? (
              <RiQuestionLine size={15} className="shrink-0 text-fg-muted" aria-label="FAQ" />
            ) : null}
          </div>
          <h3 className="text-secondary font-semibold text-fg">{article.title}</h3>
          {article.summary ? (
            <p className="mt-2 text-caption text-fg-muted">{article.summary}</p>
          ) : null}
          <span className="mt-4 flex items-center gap-1 text-caption font-medium text-fg-body">
            Read article <RiArrowRightSLine size={14} />
          </span>
        </button>
      ))}
    </div>
  )
}

function ArticleDetail({
  query,
  onBack,
}: {
  query: ReturnType<typeof useQuery<Awaited<ReturnType<typeof getHelpArticle>>>>
  onBack: () => void
}) {
  return (
    <div>
      <button
        type="button"
        onClick={onBack}
        className="mb-6 flex items-center gap-1.5 text-caption font-medium text-fg-muted transition-colors duration-150 hover:text-fg"
      >
        <RiArrowLeftLine size={14} />
        Back to articles
      </button>

      {query.isLoading ? (
        <p className="py-8 text-center text-caption text-fg-muted">Loading article…</p>
      ) : query.isError ? (
        // A restricted slug 404s rather than 403ing, specifically so this
        // response can never confirm the article exists. Render the
        // backend's own message verbatim — softening it into "you don't
        // have access to this" would undo that.
        <p className="py-8 text-center text-caption text-danger">
          {getApiErrorMessage(query.error, "Unable to load this article.")}
        </p>
      ) : query.data ? (
        <article className="rounded-xl border border-stroke bg-surface-1 p-6">
          <div className="mb-4 flex items-center gap-2">
            <Badge variant="subtle" tone="neutral">
              {query.data.category}
            </Badge>
            {query.data.is_faq ? (
              <Badge variant="outline" tone="neutral">
                FAQ
              </Badge>
            ) : null}
          </div>
          <h2 className="mb-2 flex items-center gap-2 text-lg font-semibold text-fg">
            <RiBookOpenLine size={18} className="shrink-0 text-fg-muted" />
            {query.data.title}
          </h2>
          {query.data.summary ? (
            <p className="mb-6 text-caption text-fg-muted">{query.data.summary}</p>
          ) : null}
          {/* TODO(feat/fe-15-help-center): rendered as sanitised markdown
              in the next commit. Placeholder so the detail view is wired
              and testable before the renderer lands. */}
          <div className="whitespace-pre-wrap text-secondary leading-relaxed text-fg-body">
            {query.data.body_markdown}
          </div>
        </article>
      ) : null}
    </div>
  )
}
