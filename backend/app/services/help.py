"""FR-20 — Help Center content: frontmatter parsing, idempotent seeding from
backend/content/help/*.md, and role-filtered FTS5 search with a LIKE fallback
(09_PKG_help_center.md).

The frontmatter format here (a handful of scalar/list/bool/int fields, no
nesting) is simple enough that a full YAML parser is unwarranted — see the
PR description for the dependency call. Hand-rolled parsing also means a
malformed file fails with a precise, local error message instead of a
generic YAML syntax error.
"""

import hashlib
import json
import logging
import re
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, col, select

from app.models import HelpArticle, UserRole

logger = logging.getLogger("uvicorn.error")

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content" / "help"

_REQUIRED_FIELDS = ("slug", "title", "category", "roles")
_VALID_ROLES = {role.value for role in UserRole}


class HelpContentError(ValueError):
    """A content file failed to parse or validate. Raised loudly (rather
    than skipping the file) so a typo'd role never silently hides an
    article from everyone who should see it."""


def _parse_scalar(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        raw = raw[1:-1]
    return raw


def _parse_list(raw: str, *, source: str) -> list[str]:
    raw = raw.strip()
    if not (raw.startswith("[") and raw.endswith("]")):
        raise HelpContentError(f"{source}: expected a bracketed list, got: {raw!r}")
    inner = raw[1:-1].strip()
    if not inner:
        return []
    return [_parse_scalar(item) for item in inner.split(",")]


def _parse_frontmatter(raw_text: str, *, source: str) -> tuple[dict, str]:
    """Split a `---`-delimited frontmatter block from its markdown body and
    parse the block into a dict of scalars/lists/bools/ints."""
    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise HelpContentError(f"{source}: missing frontmatter opening '---'")
    try:
        end_index = next(
            i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"
        )
    except StopIteration as exc:
        raise HelpContentError(f"{source}: missing frontmatter closing '---'") from exc

    meta: dict = {}
    for line in lines[1:end_index]:
        if not line.strip():
            continue
        if ":" not in line:
            raise HelpContentError(f"{source}: malformed frontmatter line: {line!r}")
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("["):
            meta[key] = _parse_list(value, source=source)
        elif value.lower() in ("true", "false"):
            meta[key] = value.lower() == "true"
        elif re.fullmatch(r"-?\d+", value):
            meta[key] = int(value)
        else:
            meta[key] = _parse_scalar(value)

    body = "\n".join(lines[end_index + 1 :]).strip("\n")
    return meta, body


def _validate_roles(roles: object, *, source: str) -> list[str]:
    if not isinstance(roles, list) or not roles:
        raise HelpContentError(f"{source}: 'roles' must be a non-empty list")
    for role in roles:
        if role not in _VALID_ROLES:
            raise HelpContentError(
                f"{source}: unknown role {role!r} — must be one of "
                f"{sorted(_VALID_ROLES)}"
            )
    return roles


def load_articles(content_dir: Path = CONTENT_DIR) -> list[dict]:
    """Parse every `*.md` file in `content_dir` into a seed-ready dict.
    Raises HelpContentError on the first malformed file — startup should
    fail loudly rather than seed a wrong or incomplete article set."""
    articles = []
    for path in sorted(content_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw, source=path.name)

        missing = [f for f in _REQUIRED_FIELDS if f not in meta]
        if missing:
            raise HelpContentError(f"{path.name}: missing required field(s): {missing}")
        if not body.strip():
            raise HelpContentError(f"{path.name}: article body is empty")

        roles = _validate_roles(meta["roles"], source=path.name)

        articles.append(
            {
                "slug": meta["slug"],
                "title": meta["title"],
                "category": meta["category"],
                "roles": roles,
                "summary": meta.get("summary"),
                "sort_order": meta.get("sort_order", 0),
                "is_faq": meta.get("is_faq", False),
                "body_markdown": body,
                "content_hash": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            }
        )
    return articles


def seed_help_articles(session: Session, content_dir: Path = CONTENT_DIR) -> None:
    """Upsert `help_article` rows by slug from `content_dir`, skipping files
    whose content_hash is unchanged, and deleting rows whose file is gone.
    Idempotent — a re-seed of unchanged content writes nothing (edge case
    10.6). The FTS5 index (app/models/help.py) stays in sync automatically
    via its insert/update/delete triggers on this table."""
    articles = load_articles(content_dir)
    seen_slugs = {article["slug"] for article in articles}

    for article in articles:
        existing = session.exec(
            select(HelpArticle).where(HelpArticle.slug == article["slug"])
        ).first()

        if existing is not None:
            if existing.content_hash == article["content_hash"]:
                continue
            existing.title = article["title"]
            existing.category = article["category"]
            existing.roles = json.dumps(article["roles"])
            existing.summary = article["summary"]
            existing.sort_order = article["sort_order"]
            existing.is_faq = article["is_faq"]
            existing.body_markdown = article["body_markdown"]
            existing.content_hash = article["content_hash"]
            session.add(existing)
        else:
            session.add(
                HelpArticle(
                    slug=article["slug"],
                    title=article["title"],
                    category=article["category"],
                    roles=json.dumps(article["roles"]),
                    summary=article["summary"],
                    sort_order=article["sort_order"],
                    is_faq=article["is_faq"],
                    body_markdown=article["body_markdown"],
                    content_hash=article["content_hash"],
                )
            )

    stale = session.exec(
        select(HelpArticle).where(col(HelpArticle.slug).not_in(seen_slugs))
        if seen_slugs
        else select(HelpArticle)
    ).all()
    for row in stale:
        session.delete(row)

    session.commit()


# ---------------------------------------------------------------------------
# Search (Step 3)
# ---------------------------------------------------------------------------

_FTS_TERM_LIMIT = 20  # bounds edge case 4.13 (a 10 KB search string)


def _role_can_view(article: HelpArticle, role: UserRole) -> bool:
    """FR-02: Admins inherit every Operator-visible article — encoded here,
    not by duplicating articles with both roles listed."""
    if role == UserRole.ADMIN:
        return True
    return role.value in json.loads(article.roles)


def _extract_terms(raw: str) -> list[str]:
    return re.findall(r"\w+", raw)[:_FTS_TERM_LIMIT]


def _fts_match_query(terms: list[str]) -> str:
    """Quote every term and treat it as a prefix match. Quoting means a
    reserved FTS5 keyword typed by a user (OR, NEAR, AND, NOT) is parsed as
    a literal token instead of query syntax (edge case 4.12) — MATCH never
    sees raw, unquoted user input."""
    return " ".join(f'"{term}"*' for term in terms)


def _fts_search(session: Session, raw_query: str) -> list[HelpArticle] | None:
    """Returns ranked articles, `[]` for no matches, or `None` if the FTS5
    virtual table is unavailable (edge case 6.17) so the caller can fall
    back to LIKE."""
    terms = _extract_terms(raw_query)
    if not terms:
        return []

    try:
        rows = session.execute(
            text(
                """
                SELECT ha.article_id
                FROM help_article_fts
                JOIN help_article ha ON ha.article_id = help_article_fts.rowid
                WHERE help_article_fts MATCH :query
                ORDER BY bm25(help_article_fts), ha.sort_order, ha.title
                """
            ),
            {"query": _fts_match_query(terms)},
        ).all()
    except OperationalError:
        logger.warning(
            "help_article_fts unavailable — falling back to LIKE search.",
            exc_info=True,
        )
        return None

    article_ids = [row[0] for row in rows]
    if not article_ids:
        return []
    articles_by_id = {
        a.article_id: a
        for a in session.exec(
            select(HelpArticle).where(col(HelpArticle.article_id).in_(article_ids))
        )
    }
    # Preserve the bm25 ranking order from the FTS query, not the id order.
    return [articles_by_id[i] for i in article_ids if i in articles_by_id]


def _like_search(session: Session, raw_query: str) -> list[HelpArticle]:
    """FTS5-unavailable fallback (edge case 6.17). ANDs every term across
    title/summary/body — a simpler ranking than bm25, but a "sensible
    result" is all the package doc requires of this path."""
    terms = _extract_terms(raw_query)
    if not terms:
        return []

    stmt = select(HelpArticle)
    for term in terms:
        stmt = stmt.where(
            col(HelpArticle.title).icontains(term)
            | col(HelpArticle.summary).icontains(term)
            | col(HelpArticle.body_markdown).icontains(term)
        )
    stmt = stmt.order_by(col(HelpArticle.sort_order), col(HelpArticle.title))
    return list(session.exec(stmt))


def search_articles(
    session: Session,
    *,
    role: UserRole,
    category: str | None = None,
    search: str | None = None,
) -> tuple[list[HelpArticle], bool]:
    """Returns (role-visible articles, whether a search term was actually
    applied). An empty/whitespace-only `search` is treated as no search at
    all (edge case 3.9) — it returns every visible article rather than an
    empty result or an error."""
    normalized_search = (search or "").strip()
    searched = bool(normalized_search)

    if searched:
        articles = _fts_search(session, normalized_search)
        if articles is None:
            articles = _like_search(session, normalized_search)
    else:
        stmt = select(HelpArticle).order_by(
            col(HelpArticle.sort_order), col(HelpArticle.title)
        )
        articles = list(session.exec(stmt))

    if category:
        articles = [
            a for a in articles if a.category.lower() == category.strip().lower()
        ]

    visible = [a for a in articles if _role_can_view(a, role)]
    return visible, searched


def list_top_faqs(
    session: Session, *, role: UserRole, limit: int = 8
) -> list[HelpArticle]:
    stmt = (
        select(HelpArticle)
        .where(col(HelpArticle.is_faq).is_(True))
        .order_by(col(HelpArticle.sort_order), col(HelpArticle.title))
    )
    visible = [a for a in session.exec(stmt) if _role_can_view(a, role)]
    return visible[:limit]


def get_article_by_slug(
    session: Session, *, slug: str, role: UserRole
) -> HelpArticle | None:
    """Returns None for both "doesn't exist" and "not visible to this
    role" — the route must 404 either way without distinguishing them
    (01_CONTRACTS.md §5.11)."""
    article = session.exec(select(HelpArticle).where(HelpArticle.slug == slug)).first()
    if article is None or not _role_can_view(article, role):
        return None
    return article
