import { RiArrowRightSLine, RiQuestionLine } from "@remixicon/react"

import type { HelpArticleSummary } from "@/api/help"
import { Badge } from "@/components/ui/Badge"
import { cn } from "@/utils/cn"
import { categoryIcon } from "./categoryIcons"

export function ArticleGrid({
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
