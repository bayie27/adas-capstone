import {
  useMemo,
  useRef,
  type AnchorHTMLAttributes,
  type ImgHTMLAttributes,
  type ReactNode,
} from "react"
import { useQuery } from "@tanstack/react-query"
import ReactMarkdown from "react-markdown"
import rehypeSanitize from "rehype-sanitize"
import { RiArrowRightSLine, RiBookOpenLine } from "@remixicon/react"

import { getApiErrorMessage } from "@/api/client"
import { getHelpArticle } from "@/api/help"
import { Badge } from "@/components/ui/Badge"
import { cn } from "@/utils/cn"
import { ArticleDetailSkeleton } from "./ArticleDetailSkeleton"

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
 * `scrollToOutlineEntry`) rather than by DOM id, since rehype-sanitize's
 * allowlist is not guaranteed to keep an `id` attribute on a heading. */
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

export function ArticleDetail({
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
        <ArticleDetailSkeleton />
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
