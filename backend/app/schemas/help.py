from sqlmodel import SQLModel


class HelpArticleSummary(SQLModel):
    slug: str
    title: str
    category: str
    summary: str | None = None
    is_faq: bool


class HelpArticleListResponse(SQLModel):
    items: list[HelpArticleSummary]
    top_faqs: list[HelpArticleSummary]


class HelpArticleDetail(SQLModel):
    slug: str
    title: str
    category: str
    summary: str | None = None
    is_faq: bool
    # Raw markdown — the frontend renders and sanitizes it before display.
    # This backend never renders HTML from article content.
    body_markdown: str
