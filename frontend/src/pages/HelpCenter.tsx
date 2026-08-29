import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type AnchorHTMLAttributes,
  type ImgHTMLAttributes,
  type ReactNode,
} from "react"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { useSearchParams } from "react-router-dom"
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
import { OverlayErrorBanner } from "@/components/ui/OverlayErrorBanner"
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

/** A search term echoed back into an empty-state sentence can otherwise run
 * the full width of the page (up to the 200-char backend limit) with no
 * spaces to wrap on, e.g. a pasted string with no word breaks. Truncating
 * what's displayed (never what's actually searched) keeps that sentence
 * readable regardless of what was typed. */
function truncateForDisplay(term: string, max = 60): string {
  return term.length > max ? `${term.slice(0, max)}…` : term
}

const EMPTY_ARTICLES: HelpArticleSummary[] = []
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
function useAnimatedArticles(items: HelpArticleSummary[], leaveMs = GRID_LEAVE_MS) {
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
    // dropping out to a "Loading articles…" flash on every keystroke — the
    // grid then only ever has to animate a card in or out, never blink.
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
        <h1 className="mb-0.5 text-xl font-semibold text-fg">Help Center</h1>
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
              <p className="py-8 text-center text-caption text-fg-muted">Loading articles…</p>
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
  const buttonRefs = useRef(new Map<string, HTMLButtonElement>())
  const [indicator, setIndicator] = useState<{ left: number; width: number } | null>(null)

  // Measures synchronously before paint, so the indicator never flashes at
  // a stale position for a frame — it just slides to wherever the selected
  // tab actually is, including the first time the category list loads in
  // (which changes every button's position at once).
  useLayoutEffect(() => {
    const el = buttonRefs.current.get(optionKey(value))
    if (el) setIndicator({ left: el.offsetLeft, width: el.offsetWidth })
  }, [value, options.length])

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
        "relative inline-flex h-9 flex-wrap items-center justify-start gap-1 rounded-md bg-surface-2 p-1",
        className,
      )}
    >
      {/* One shared sliding indicator instead of each tab drawing its own
          selected-state box, so switching categories reads as one control
          moving rather than two unrelated tabs blinking off/on. */}
      {indicator ? (
        <div
          aria-hidden="true"
          className="absolute top-1 bottom-1 left-0 rounded bg-canvas shadow-sm transition-[transform,width] duration-200 ease-out"
          style={{ transform: `translateX(${indicator.left}px)`, width: indicator.width }}
        />
      ) : null}
      {options.map((option) => {
        const selected = option === value
        const Icon = option ? categoryIcon(option) : RiCompassLine
        return (
          <button
            key={optionKey(option)}
            ref={(el) => {
              if (el) buttonRefs.current.set(optionKey(option), el)
              else buttonRefs.current.delete(optionKey(option))
            }}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(option)}
            className={cn(
              "relative z-10 flex items-center justify-center gap-1.5 rounded px-3 py-1 text-caption font-medium transition-colors duration-150",
              selected ? "text-fg" : "text-fg-muted",
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

function optionKey(option: string): string {
  return option || "all"
}

function ArticleGrid({
  articles,
  onSelect,
  isLeaving,
}: {
  articles: HelpArticleSummary[]
  onSelect: (slug: string) => void
  /** Cards leaving on their way out (no longer part of the actual matched
   * set) get the leave animation and stop being interactive; everything
   * else gets the plain entrance treatment, which only visibly plays for
   * cards genuinely new to the DOM — see useAnimatedArticles. */
  isLeaving?: (slug: string) => boolean
}) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {articles.map((article) => {
        const CategoryIcon = categoryIcon(article.category)
        const leaving = isLeaving?.(article.slug) ?? false
        return (
          <button
            key={article.slug}
            type="button"
            disabled={leaving}
            aria-hidden={leaving}
            tabIndex={leaving ? -1 : 0}
            onClick={() => onSelect(article.slug)}
            className={cn(
              "flex h-full flex-col items-start rounded-lg border border-stroke bg-surface-1 p-5 text-left shadow-sm transition-all duration-150 hover:border-stroke-strong hover:bg-surface-2 hover:shadow-lg",
              leaving ? "animate-grid-item-leave pointer-events-none" : "animate-grid-item-enter",
            )}
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
              <p className="mt-2 line-clamp-2 text-caption text-fg-muted">{article.summary}</p>
            ) : null}
            <span className="mt-auto flex items-center gap-1 pt-4 text-caption font-medium text-fg-body">
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
    <div className="animate-modal-enter">
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
