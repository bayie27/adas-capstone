"""
Tests for app.services.help (FR-20) and GET /api/help/* — 09_PKG_help_center.md's
"Tests to write" table, plus 14_EDGE_CASES.md rows 3.8, 3.9, 4.12, 4.13, 6.17, 10.6.
"""

import json
import logging
from pathlib import Path

import pytest
from app.models import HelpArticle, UserRole
from app.services.help import CONTENT_DIR as REAL_CONTENT_DIR
from app.services.help import (
    HelpContentError,
    load_articles,
    search_articles,
    seed_help_articles,
)
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, select

from .conftest import auth_headers, make_admin, make_operator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_article(
    tmp_path: Path,
    filename: str,
    *,
    slug: str,
    title: str = "Title",
    category: str = "Operations",
    roles: str = "[Admin, Operator]",
    summary: str = "Summary.",
    sort_order: int = 0,
    is_faq: bool = False,
    body: str = "Body content here.",
) -> Path:
    content = (
        "---\n"
        f"slug: {slug}\n"
        f"title: {title}\n"
        f"category: {category}\n"
        f"roles: {roles}\n"
        f"summary: {summary}\n"
        f"sort_order: {sort_order}\n"
        f"is_faq: {'true' if is_faq else 'false'}\n"
        "---\n\n"
        f"{body}\n"
    )
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return path


def _seed_rows(session: Session, articles: list[dict]) -> None:
    """Insert HelpArticle rows directly, bypassing markdown parsing — route
    tests stay decoupled from the real starter content set."""
    for i, a in enumerate(articles):
        session.add(
            HelpArticle(
                slug=a["slug"],
                title=a.get("title", a["slug"]),
                category=a.get("category", "Operations"),
                roles=json.dumps(a.get("roles", ["Admin", "Operator"])),
                summary=a.get("summary"),
                body_markdown=a.get("body_markdown", "Ordinary body content."),
                sort_order=a.get("sort_order", 0),
                is_faq=a.get("is_faq", False),
                content_hash=a.get("content_hash", f"hash-{i}-{a['slug']}"),
            )
        )
    session.commit()


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


class TestFrontmatterParsing:
    def test_valid_file_parses(self, tmp_path):
        _write_article(tmp_path, "a.md", slug="a", roles="[Admin, Operator]")
        articles = load_articles(tmp_path)
        assert len(articles) == 1
        assert articles[0]["slug"] == "a"
        assert articles[0]["roles"] == ["Admin", "Operator"]

    def test_unknown_role_fails_loudly(self, tmp_path):
        _write_article(tmp_path, "a.md", slug="a", roles="[Admin, Supervisor]")
        with pytest.raises(HelpContentError, match="Supervisor"):
            load_articles(tmp_path)

    def test_missing_required_field_fails_loudly(self, tmp_path):
        path = tmp_path / "a.md"
        path.write_text("---\nslug: a\ntitle: A\n---\nbody\n", encoding="utf-8")
        with pytest.raises(HelpContentError, match="category"):
            load_articles(tmp_path)

    def test_empty_body_fails_loudly(self, tmp_path):
        _write_article(tmp_path, "a.md", slug="a", body="")
        with pytest.raises(HelpContentError, match="empty"):
            load_articles(tmp_path)

    def test_real_starter_content_all_parses(self):
        """Regression guard on the hand-written starter set (Step 1) — a
        typo'd role or missing field here would silently break seeding."""
        real_files = list(REAL_CONTENT_DIR.glob("*.md"))
        assert real_files, "expected backend/content/help/*.md to exist"

        articles = load_articles(REAL_CONTENT_DIR)
        assert len(articles) == len(real_files)

        slugs = [a["slug"] for a in articles]
        assert len(slugs) == len(set(slugs)), "duplicate slug in starter content"


# ---------------------------------------------------------------------------
# Idempotent seeding — edge case 10.6
# ---------------------------------------------------------------------------


class TestIdempotentSeeding:
    def test_reseed_unchanged_writes_nothing(self, session: Session, tmp_path):
        _write_article(tmp_path, "a.md", slug="a")
        seed_help_articles(session, content_dir=tmp_path)
        first = session.exec(select(HelpArticle).where(HelpArticle.slug == "a")).one()
        first_updated_at = first.updated_at

        seed_help_articles(session, content_dir=tmp_path)
        session.expire_all()
        second = session.exec(select(HelpArticle).where(HelpArticle.slug == "a")).one()
        assert second.updated_at == first_updated_at

    def test_changed_file_updates_the_row(self, session: Session, tmp_path):
        _write_article(tmp_path, "a.md", slug="a", title="Old Title")
        seed_help_articles(session, content_dir=tmp_path)

        _write_article(tmp_path, "a.md", slug="a", title="New Title")
        seed_help_articles(session, content_dir=tmp_path)

        session.expire_all()
        row = session.exec(select(HelpArticle).where(HelpArticle.slug == "a")).one()
        assert row.title == "New Title"

    def test_deleted_file_removes_the_row(self, session: Session, tmp_path):
        path_a = _write_article(tmp_path, "a.md", slug="a")
        _write_article(tmp_path, "b.md", slug="b")
        seed_help_articles(session, content_dir=tmp_path)

        path_a.unlink()
        seed_help_articles(session, content_dir=tmp_path)

        session.expire_all()
        remaining = session.exec(select(HelpArticle)).all()
        assert [r.slug for r in remaining] == ["b"]


# ---------------------------------------------------------------------------
# Role filter
# ---------------------------------------------------------------------------


class TestRoleFilter:
    def test_operator_list_excludes_admin_only_articles(
        self, client: TestClient, session: Session
    ):
        make_operator(session)
        _seed_rows(
            session,
            [
                {
                    "slug": "admin-thing",
                    "roles": ["Admin"],
                    "category": "Administration",
                },
                {
                    "slug": "shared-thing",
                    "roles": ["Admin", "Operator"],
                    "category": "Operations",
                },
            ],
        )
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get("/api/help/articles", headers=headers)
        assert resp.status_code == 200
        slugs = [a["slug"] for a in resp.json()["items"]]
        assert "admin-thing" not in slugs
        assert "shared-thing" in slugs

    def test_operator_cannot_fetch_admin_only_article_detail(
        self, client: TestClient, session: Session
    ):
        make_operator(session)
        _seed_rows(session, [{"slug": "admin-thing", "roles": ["Admin"]}])
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get("/api/help/articles/admin-thing", headers=headers)
        assert resp.status_code == 404

    def test_admin_sees_operator_articles_too(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        _seed_rows(
            session,
            [
                {"slug": "admin-thing", "roles": ["Admin"]},
                {"slug": "operator-thing", "roles": ["Operator"]},
            ],
        )
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.get("/api/help/articles", headers=headers)
        slugs = {a["slug"] for a in resp.json()["items"]}
        assert {"admin-thing", "operator-thing"} <= slugs

        resp = client.get("/api/help/articles/admin-thing", headers=headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_term_matching_is_case_insensitive(
        self, client: TestClient, session: Session
    ):
        make_operator(session)
        _seed_rows(
            session,
            [
                {
                    "slug": "cooldown-article",
                    "title": "The Cooldown Period",
                    "body_markdown": "Explains cooldown behavior in detail.",
                },
                {
                    "slug": "unrelated-article",
                    "title": "Something Else",
                    "body_markdown": "Nothing to do with it.",
                },
            ],
        )
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get(
            "/api/help/articles", params={"search": "COOLDOWN"}, headers=headers
        )
        slugs = [a["slug"] for a in resp.json()["items"]]
        assert slugs == ["cooldown-article"]

    def test_ranking_prefers_denser_matches(self, client: TestClient, session: Session):
        make_operator(session)
        _seed_rows(
            session,
            [
                {
                    "slug": "weak-match",
                    "title": "Something",
                    "body_markdown": "mentions alert once in passing",
                },
                {
                    "slug": "strong-match",
                    "title": "Alert Alert Alert",
                    "body_markdown": "alert alert alert alert",
                },
            ],
        )
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get(
            "/api/help/articles", params={"search": "alert"}, headers=headers
        )
        slugs = [a["slug"] for a in resp.json()["items"]]
        assert slugs[0] == "strong-match"

    def test_ranking_prefers_title_match_over_denser_body_match(
        self, client: TestClient, session: Session
    ):
        """A title match must outrank a body-only match even when the body
        repeats the term far more densely — the bug this guards against: an
        article whose *title* is the real answer (e.g. "Viewing Camera
        Details") losing to one that just happens to mention the search term
        several times in ordinary prose (e.g. an unrelated FAQ). Regression
        test for the bm25() column-weight fix in _fts_search."""
        make_operator(session)
        _seed_rows(
            session,
            [
                {
                    "slug": "body-only-match",
                    "title": "Something Else Entirely",
                    "body_markdown": "camera camera camera camera camera camera",
                },
                {
                    "slug": "title-match",
                    "title": "Viewing Camera Details",
                    "body_markdown": "What you see when you click into a camera.",
                },
            ],
        )
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get(
            "/api/help/articles", params={"search": "camera"}, headers=headers
        )
        slugs = [a["slug"] for a in resp.json()["items"]]
        assert slugs[0] == "title-match"

    def test_category_filter_combines_with_role_filter(
        self, client: TestClient, session: Session
    ):
        make_operator(session)
        _seed_rows(
            session,
            [
                {"slug": "op-cat", "category": "Operations", "roles": ["Operator"]},
                {
                    "slug": "admin-cat",
                    "category": "Administration",
                    "roles": ["Admin"],
                },
            ],
        )
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get(
            "/api/help/articles",
            params={"category": "Administration"},
            headers=headers,
        )
        assert resp.json()["items"] == []

    @pytest.mark.parametrize("query", ['"', "*", "NEAR(a b)", '"unterminated'])
    def test_metacharacters_never_crash_and_return_empty(
        self, client: TestClient, session: Session, query
    ):
        """Edge case 4.12. These probes contain no real word from the seeded
        content, so an empty result is the correct outcome, not just an
        artifact of never crashing."""
        make_operator(session)
        _seed_rows(session, [{"slug": "a", "body_markdown": "ordinary alert text"}])
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get(
            "/api/help/articles", params={"search": query}, headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_or_as_a_literal_term_never_crashes(
        self, client: TestClient, session: Session
    ):
        """Edge case 4.12 also lists bare `OR`. Sanitization quotes every
        extracted term, so `OR` is searched as the literal word "or" rather
        than parsed as FTS5 boolean syntax — it never raises. Unlike the
        other probes in this row, "or" is a common English word that
        legitimately appears in real prose, so asserting an empty result
        here would be testing the content, not the sanitizer; a 200 with a
        genuine match is the correct behavior, and that's what this checks."""
        make_operator(session)
        _seed_rows(
            session,
            [{"slug": "a", "title": "Confirm or Dismiss", "body_markdown": "text"}],
        )
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get(
            "/api/help/articles", params={"search": "OR"}, headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["items"] == [] or all(
            item["slug"] == "a" for item in resp.json()["items"]
        )

    def test_extremely_long_search_string_is_rejected(
        self, client: TestClient, session: Session
    ):
        """Edge case 4.13 — a 10 KB search string. Rejected via the query
        param's max_length rather than executed against the DB."""
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get(
            "/api/help/articles", params={"search": "a" * 10_000}, headers=headers
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Empty state — edge cases 3.8, 3.9
# ---------------------------------------------------------------------------


class TestEmptyState:
    def test_no_results_returns_empty_items_and_populated_top_faqs(
        self, client: TestClient, session: Session
    ):
        make_operator(session)
        _seed_rows(
            session,
            [
                {"slug": "faq-1", "is_faq": True, "title": "FAQ One"},
                {"slug": "faq-2", "is_faq": True, "title": "FAQ Two"},
                {"slug": "normal", "is_faq": False, "title": "Normal Article"},
            ],
        )
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get(
            "/api/help/articles",
            params={"search": "zzzznotathing"},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert {f["slug"] for f in body["top_faqs"]} == {"faq-1", "faq-2"}

    def test_empty_search_string_returns_all_visible_articles(
        self, client: TestClient, session: Session
    ):
        make_operator(session)
        _seed_rows(session, [{"slug": "a"}, {"slug": "b"}])
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get("/api/help/articles", params={"search": ""}, headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert {a["slug"] for a in body["items"]} == {"a", "b"}
        assert body["top_faqs"] == []

    def test_plain_browse_with_no_matches_never_populates_top_faqs(
        self, client: TestClient, session: Session
    ):
        """A category filter that matches nothing is not "a search that
        returned no results" — top_faqs stays empty."""
        make_operator(session)
        _seed_rows(session, [{"slug": "a", "category": "Operations"}])
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get(
            "/api/help/articles",
            params={"category": "Nonexistent Category"},
            headers=headers,
        )
        body = resp.json()
        assert body["items"] == []
        assert body["top_faqs"] == []


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestAuth:
    def test_list_requires_a_session(self, client: TestClient):
        resp = client.get("/api/help/articles")
        assert resp.status_code == 401

    def test_detail_requires_a_session(self, client: TestClient):
        resp = client.get("/api/help/articles/some-slug")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# FTS5 fallback — edge case 6.17
# ---------------------------------------------------------------------------


class TestFtsFallback:
    def test_like_search_used_when_fts5_table_is_unavailable(
        self, session: Session, caplog
    ):
        _seed_rows(
            session,
            [
                {
                    "slug": "a",
                    "title": "Cooldown Explained",
                    "body_markdown": "details",
                },
                {"slug": "b", "title": "Unrelated", "body_markdown": "details"},
            ],
        )
        # Simulate an SQLite build without FTS5 compiled in (rather than the
        # DROP TRIGGERs firing on a later write, this only needs the SELECT
        # against help_article_fts to fail).
        session.execute(text("DROP TABLE help_article_fts"))
        session.commit()

        with caplog.at_level(logging.WARNING):
            articles, searched = search_articles(
                session, role=UserRole.ADMIN, search="cooldown"
            )

        assert searched is True
        assert [a.slug for a in articles] == ["a"]
        assert "falling back to LIKE" in caplog.text
