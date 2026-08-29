import {
  useMemo,
  useRef,
  useState,
  type AnchorHTMLAttributes,
  type ImgHTMLAttributes,
  type ReactNode,
} from "react"
import { useQuery } from "@tanstack/react-query"
import ReactMarkdown from "react-markdown"
import rehypeSanitize from "rehype-sanitize"
import {
  RiArrowRightSLine,
  RiBookOpenLine,
  RiCompassLine,
  RiPulseLine,
  RiQuestionLine,
  RiShieldUserLine,
  RiToolsLine,
} from "@remixicon/react"
import type { RemixiconComponentType } from "@remixicon/react"

import { getHelpArticle, getHelpArticles } from "@/api/help"
import type { HelpArticleSummary } from "@/api/help"
import { Badge } from "@/components/ui/Badge"
import { focusRing } from "@/components/ui/Button"
import { QueryErrorBanner } from "@/components/ui/QueryErrorBanner"
import { SearchInput } from "@/components/ui/SearchInput"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { getApiErrorMessage } from "@/api/client"
import { cn } from "@/utils/cn"

const HELP_CATEGORIES_QUERY_KEY = ["help-categories"] as const

/** Best-effort icon per category, echoing the icons the sidebar already uses
 * for the same concepts (System Health's RiPulseLine, etc.) — falls back to
 * the page's own book icon for a category this map doesn't know about, so a
 * newly-added category never renders with no icon at all. */
const CATEGORY_ICONS: Record<string, RemixiconComponentType> = {
  "Getting Started": RiCompassLine,
  Operations: RiToolsLine,
  Monitoring: RiPulseLine,
  Administration: RiShieldUserLine,
  FAQ: RiQuestionLine,
}

function categoryIcon(category: string): RemixiconComponentType {
  return CATEGORY_ICONS[category] ?? RiBookOpenLine
}

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

  function goToCategory(nextCategory: string) {
    setSelectedSlug(null)
    setCategory(nextCategory)
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
          onNavigateToCategory={goToCategory}
        />
      ) : (
        <>
          <div className="mb-5">
            <SearchInput
              value={searchTerm}
              onChange={setSearchTerm}
              placeholder="Search articles..."
            />
          </div>

          <CategoryTabs
            categories={categoryValues}
            value={category}
            onChange={setCategory}
            className="mb-6"
          />

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

/**
 * A local chip tablist rather than the shared `Tabs` component: `Tabs`'
 * `label` prop is a plain string, and a category needs an icon alongside it.
 * Styled to match `Tabs`' `chip` variant exactly (§2.8) so it reads as the
 * same control family without widening a shared component's props for one
 * caller.
 */
function CategoryTabs({
  categories,
  value,
  onChange,
  className,
}: {
  categories: string[]
  value: string
  onChange: (value: string) => void
  className?: string
}) {
  const options = ["", ...categories]

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const index = options.findIndex((option) => option === value)
    if (index === -1) return

    let next: number
    if (event.key === "ArrowRight") next = (index + 1) % options.length
    else if (event.key === "ArrowLeft") next = (index - 1 + options.length) % options.length
    else if (event.key === "Home") next = 0
    else if (event.key === "End") next = options.length - 1
    else return

    event.preventDefault()
    onChange(options[next])
  }

  return (
    <div
      role="tablist"
      aria-label="Help article categories"
      onKeyDown={onKeyDown}
      className={cn(
        "inline-flex flex-wrap items-center justify-start gap-1 rounded-md bg-surface-2 p-1",
        className,
      )}
    >
      {options.map((option) => {
        const selected = option === value
        const Icon = option ? categoryIcon(option) : RiCompassLine
        return (
          <button
            key={option || "all"}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(option)}
            className={cn(
              "flex items-center justify-center gap-1.5 rounded px-3 py-2 text-caption font-medium transition-all duration-150",
              selected ? "bg-canvas text-fg shadow-sm" : "bg-transparent text-fg-muted",
              focusRing,
            )}
          >
            <Icon size={14} className="shrink-0" />
            {option || "All"}
          </button>
        )
      })}
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
      {articles.map((article) => {
        const CategoryIcon = categoryIcon(article.category)
        return (
          <button
            key={article.slug}
            type="button"
            onClick={() => onSelect(article.slug)}
            className="flex flex-col items-start rounded-lg border border-stroke bg-surface-1 p-5 text-left transition-colors duration-150 hover:border-stroke-strong hover:bg-surface-2"
          >
            <div className="mb-3 flex w-full items-center justify-between gap-2">
              <Badge variant="subtle" tone="neutral">
                <CategoryIcon size={12} className="mr-1 inline shrink-0 -translate-y-px" />
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
        )
      })}
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
    // A screenshot reads as a captured frame of the app rather than a
    // floating image: bordered and rounded like the `Card` primitive the
    // rest of the app already uses, with the markdown alt text doubling as
    // a caption underneath (the same way a figure caption works anywhere
    // else) rather than introducing a second image-with-caption syntax.
    img: ({ src, alt }: ImgHTMLAttributes<HTMLImageElement>) => (
      <figure className="mb-4 last:mb-0">
        <img
          src={src}
          alt={alt ?? ""}
          loading="lazy"
          className="w-full rounded-lg border border-stroke"
        />
        {alt ? <figcaption className="mt-2 text-caption text-fg-muted">{alt}</figcaption> : null}
      </figure>
    ),
  }
}

/** One entry per `##`/`###` line in the raw markdown, in document order —
 * matched up with the rendered h2/h3 elements by that same order (see
 * `ArticleOutline`) rather than by DOM id, since rehype-sanitize's allowlist
 * is not guaranteed to keep an `id` attribute on a heading. */
interface OutlineEntry {
  text: string
  depth: 2 | 3
}

function extractOutline(markdown: string): OutlineEntry[] {
  const entries: OutlineEntry[] = []
  for (const line of markdown.split("\n")) {
    const h2 = /^##\s+(.+)$/.exec(line)
    const h3 = /^###\s+(.+)$/.exec(line)
    if (h2) entries.push({ text: h2[1].trim(), depth: 2 })
    else if (h3) entries.push({ text: h3[1].trim(), depth: 3 })
  }
  return entries
}

function ArticleDetail({
  query,
  onBack,
  onNavigateToSlug,
  onNavigateToCategory,
}: {
  query: ReturnType<typeof useQuery<Awaited<ReturnType<typeof getHelpArticle>>>>
  onBack: () => void
  onNavigateToSlug: (slug: string) => void
  onNavigateToCategory: (category: string) => void
}) {
  const components = useMemo(() => markdownComponents(onNavigateToSlug), [onNavigateToSlug])
  const articleRef = useRef<HTMLElement>(null)
  const article = query.data
  const outline = useMemo(() => (article ? extractOutline(article.body_markdown) : []), [article])

  function scrollToOutlineEntry(index: number) {
    const heading = articleRef.current?.querySelectorAll("h3, h4")[index]
    heading?.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  return (
    <div>
      <nav
        aria-label="Breadcrumb"
        className="mb-6 flex flex-wrap items-center gap-1.5 text-caption font-medium text-fg-muted"
      >
        <button
          type="button"
          onClick={onBack}
          className="transition-colors duration-150 hover:text-fg"
        >
          Help Center
        </button>
        {article ? (
          <>
            <RiArrowRightSLine size={12} className="shrink-0" />
            <button
              type="button"
              onClick={() => onNavigateToCategory(article.category)}
              className="transition-colors duration-150 hover:text-fg"
            >
              {article.category}
            </button>
            <RiArrowRightSLine size={12} className="shrink-0" />
            <span className="text-fg-body">{article.title}</span>
          </>
        ) : null}
      </nav>

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
      ) : article ? (
        <div className="flex items-start gap-6">
          <article
            ref={articleRef}
            className="min-w-0 flex-1 rounded-lg border border-stroke bg-surface-1 p-6"
          >
            <div className="mb-4 flex items-center gap-2">
              <Badge variant="subtle" tone="neutral">
                {article.category}
              </Badge>
              {article.is_faq ? (
                <Badge variant="outline" tone="neutral">
                  FAQ
                </Badge>
              ) : null}
            </div>
            <h2 className="mb-2 flex items-center gap-2 text-lg font-semibold text-fg">
              <RiBookOpenLine size={18} className="shrink-0 text-fg-muted" />
              {article.title}
            </h2>
            {article.summary ? (
              <p className="mb-6 text-caption text-fg-muted">{article.summary}</p>
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
              {article.body_markdown}
            </ReactMarkdown>
          </article>

          {/* Only worth the space once an article actually has enough
              sections to get lost in — a two-heading article reads fine
              top to bottom without a map of itself. */}
          {outline.length >= 3 ? (
            <nav
              aria-label="On this page"
              className="sticky top-8 hidden w-52 shrink-0 rounded-lg border border-stroke bg-surface-1 p-4 lg:block"
            >
              <p className="mb-2 text-caption font-semibold text-fg">On this page</p>
              <ul className="space-y-1.5">
                {outline.map((entry, index) => (
                  <li key={`${entry.depth}-${entry.text}`}>
                    <button
                      type="button"
                      onClick={() => scrollToOutlineEntry(index)}
                      className={cn(
                        "text-left text-caption text-fg-muted transition-colors duration-150 hover:text-fg",
                        entry.depth === 3 && "pl-3",
                      )}
                    >
                      {entry.text}
                    </button>
                  </li>
                ))}
              </ul>
            </nav>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
