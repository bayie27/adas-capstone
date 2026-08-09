from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api.dependencies import get_current_user
from app.core.db import get_session
from app.core.errors import AppHTTPException
from app.models import User, UserRole
from app.schemas import HelpArticleDetail, HelpArticleListResponse, HelpArticleSummary
from app.services.help import get_article_by_slug, list_top_faqs, search_articles

router = APIRouter(
    prefix="/api/help",
    tags=["Help Center"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/articles", response_model=HelpArticleListResponse)
def list_articles(
    search: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HelpArticleListResponse:
    """Role-filtered by the caller's role (01_CONTRACTS.md §5.11) — an Admin
    sees every Operator-visible article too (FR-02). `top_faqs` is only
    populated when a non-empty `search` matched nothing (UC-10's empty
    state), never for a plain unfiltered or category-only browse."""
    role = UserRole(current_user.role)
    articles, searched = search_articles(
        session, role=role, category=category, search=search
    )

    top_faqs: list[HelpArticleSummary] = []
    if searched and not articles:
        top_faqs = [
            HelpArticleSummary.model_validate(a)
            for a in list_top_faqs(session, role=role)
        ]

    return HelpArticleListResponse(
        items=[HelpArticleSummary.model_validate(a) for a in articles],
        top_faqs=top_faqs,
    )


@router.get("/articles/{slug}", response_model=HelpArticleDetail)
def get_article(
    slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HelpArticleDetail:
    """404, never 403, when the slug exists but the caller's role can't see
    it — the response must not confirm the article exists (§5.11)."""
    article = get_article_by_slug(session, slug=slug, role=UserRole(current_user.role))
    if article is None:
        raise AppHTTPException(404, "Article not found.", code="NOT_FOUND")
    return HelpArticleDetail.model_validate(article)
