import api from "@/api/client"

export interface HelpArticleSummary {
  slug: string
  title: string
  category: string
  summary: string | null
  is_faq: boolean
}

export interface HelpArticleListResponse {
  items: HelpArticleSummary[]
  /**
   * Populated **only** when a non-empty `search` matched nothing — the
   * empty-state fallback, not a "featured" list. Empty on a plain browse
   * and on a category-only filter, even when `items` is also empty.
   */
  top_faqs: HelpArticleSummary[]
}

export interface HelpArticleDetail extends HelpArticleSummary {
  /** Raw markdown. The backend never renders HTML — sanitize before display. */
  body_markdown: string
}

export interface GetHelpArticlesParams {
  search?: string
  category?: string
}

export async function getHelpArticles(params: GetHelpArticlesParams = {}) {
  const { data } = await api.get<HelpArticleListResponse>("/help/articles", { params })
  return data
}

/**
 * 404, never 403, when the slug exists but the caller's role can't see it —
 * the response must not confirm the article exists. Callers should render
 * the 404 message as-is rather than softening it into "you don't have
 * access to this".
 */
export async function getHelpArticle(slug: string) {
  const { data } = await api.get<HelpArticleDetail>(`/help/articles/${slug}`)
  return data
}
