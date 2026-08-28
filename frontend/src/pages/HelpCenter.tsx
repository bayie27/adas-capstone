import { useMemo, useState, type AnchorHTMLAttributes, type ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"
import ReactMarkdown from "react-markdown"
import rehypeSanitize from "rehype-sanitize"
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
        <ArticleDetail
          query={articleQuery}
          onBack={() => setSelectedSlug(null)}
          onNavigateToSlug={openArticle}
        />
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
          className="flex flex-col items-start rounded-lg border border-stroke bg-surface-1 p-5 text-left transition-colors duration-150 hover:border-stroke-strong hover:bg-surface-2"
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

/**
 * A body-relative link — e.g. `[Correcting a Mistaken
 * Confirmation](correcting-a-mistaken-confirmation)`, the cross-reference
 * shape the seeded articles actually use — is a slug, not a browsable URL:
 * this SPA has no route for it, so letting the browser navigate there
 * verbatim would 404 the whole app. Anything absolute (a real external URL,
 * or `mailto:`) opens normally in a new tab instead.
 */
function isInternalSlugHref(href: string) {
  return !/^([a-z][a-z0-9+.-]*:)/i.test(href)
}

function MarkdownLink({
  href,
  children,
  onNavigateToSlug,
}: AnchorHTMLAttributes<HTMLAnchorElement> & {
  onNavigateToSlug: (slug: string) => void
}) {
  if (href && isInternalSlugHref(href)) {
    return (
      <button
        type="button"
        onClick={() => onNavigateToSlug(href)}
        className="font-medium text-fg underline underline-offset-2 hover:text-fg-body"
      >
        {children}
      </button>
    )
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-fg underline underline-offset-2 hover:text-fg-body"
    >
      {children}
    </a>
  )
}

/** Markdown element styling — this app has no Tailwind Typography plugin, so
 * each block maps onto the same tokens the rest of the app already uses
 * rather than pulling in a second styling system for one page. */
function markdownComponents(onNavigateToSlug: (slug: string) => void) {
  return {
    h1: ({ children }: { children?: ReactNode }) => (
      <h2 className="mt-6 mb-3 text-lg font-semibold text-fg first:mt-0">{children}</h2>
    ),
    h2: ({ children }: { children?: ReactNode }) => (
      <h3 className="mt-6 mb-3 text-base font-semibold text-fg first:mt-0">{children}</h3>
    ),
    h3: ({ children }: { children?: ReactNode }) => (
      <h4 className="mt-5 mb-2 text-secondary font-semibold text-fg first:mt-0">{children}</h4>
    ),
    p: ({ children }: { children?: ReactNode }) => (
      <p className="mb-4 text-secondary leading-relaxed text-fg-body last:mb-0">{children}</p>
    ),
    ul: ({ children }: { children?: ReactNode }) => (
      <ul className="mb-4 list-disc space-y-1.5 pl-5 text-secondary text-fg-body last:mb-0">
        {children}
      </ul>
    ),
    ol: ({ children }: { children?: ReactNode }) => (
      <ol className="mb-4 list-decimal space-y-1.5 pl-5 text-secondary text-fg-body last:mb-0">
        {children}
      </ol>
    ),
    li: ({ children }: { children?: ReactNode }) => <li>{children}</li>,
    strong: ({ children }: { children?: ReactNode }) => (
      <strong className="font-semibold text-fg">{children}</strong>
    ),
    blockquote: ({ children }: { children?: ReactNode }) => (
      <blockquote className="mb-4 border-l-2 border-stroke pl-4 text-fg-muted italic last:mb-0">
        {children}
      </blockquote>
    ),
    hr: () => <hr className="my-6 border-stroke" />,
    code: ({ children }: { children?: ReactNode }) => (
      <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-caption text-fg">
        {children}
      </code>
    ),
    pre: ({ children }: { children?: ReactNode }) => (
      <pre className="mb-4 overflow-x-auto rounded-md bg-surface-2 p-4 font-mono text-caption text-fg-body last:mb-0">
        {children}
      </pre>
    ),
    a: (props: AnchorHTMLAttributes<HTMLAnchorElement>) => (
      <MarkdownLink {...props} onNavigateToSlug={onNavigateToSlug} />
    ),
  }
}

function ArticleDetail({
  query,
  onBack,
  onNavigateToSlug,
}: {
  query: ReturnType<typeof useQuery<Awaited<ReturnType<typeof getHelpArticle>>>>
  onBack: () => void
  onNavigateToSlug: (slug: string) => void
}) {
  const components = useMemo(() => markdownComponents(onNavigateToSlug), [onNavigateToSlug])
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
        <article className="rounded-lg border border-stroke bg-surface-1 p-6">
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
          {/*
            rehype-sanitize strips anything outside its safe-tag allowlist
            before render. Article content is admin-authored and seeded, not
            user-generated, which lowers the XSS risk but doesn't eliminate
            it — the backend's own doc comment says as much: it never
            renders HTML from article content, so this is the only place
            that does, and it does so defensively.
          */}
          <ReactMarkdown rehypePlugins={[rehypeSanitize]} components={components}>
            {query.data.body_markdown}
          </ReactMarkdown>
        </article>
      ) : null}
    </div>
  )
}
