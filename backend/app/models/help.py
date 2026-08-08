import logging
from datetime import UTC, datetime

from sqlalchemy import event, text
from sqlmodel import Field, SQLModel

from app.core.types import UtcDateTime

logger = logging.getLogger("uvicorn.error")


class HelpArticle(SQLModel, table=True):
    """FR-20 — Help Center content, searched via the help_article_fts
    external-content FTS5 table created right after this one."""

    __tablename__ = "help_article"

    article_id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(unique=True)
    title: str
    category: str
    roles: str  # JSON array, e.g. '["Admin","Operator"]'
    summary: str | None = Field(default=None)
    body_markdown: str
    sort_order: int = Field(default=0)
    is_faq: bool = Field(default=False)
    content_hash: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=UtcDateTime
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=UtcDateTime
    )


_FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS help_article_fts USING fts5(
    title, summary, body_markdown,
    content='help_article', content_rowid='article_id'
);
"""

_FTS_SYNC_TRIGGERS = [
    """
    CREATE TRIGGER IF NOT EXISTS trg_help_article_fts_insert AFTER INSERT ON help_article
    BEGIN
        INSERT INTO help_article_fts(rowid, title, summary, body_markdown)
        VALUES (new.article_id, new.title, new.summary, new.body_markdown);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_help_article_fts_update AFTER UPDATE ON help_article
    BEGIN
        INSERT INTO help_article_fts(help_article_fts, rowid, title, summary, body_markdown)
        VALUES ('delete', old.article_id, old.title, old.summary, old.body_markdown);
        INSERT INTO help_article_fts(rowid, title, summary, body_markdown)
        VALUES (new.article_id, new.title, new.summary, new.body_markdown);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_help_article_fts_delete AFTER DELETE ON help_article
    BEGIN
        INSERT INTO help_article_fts(help_article_fts, rowid, title, summary, body_markdown)
        VALUES ('delete', old.article_id, old.title, old.summary, old.body_markdown);
    END;
    """,
]


def _create_help_article_fts(target, connection, **kw) -> None:
    """Create the FTS5 virtual table + sync triggers after help_article exists.

    Guarded rather than raw DDL: some SQLite builds ship without FTS5
    compiled in (edge case 6.17). When that happens, log a warning and let
    the rest of schema creation continue — help search falls back to LIKE.
    """
    try:
        connection.execute(text(_FTS_DDL))
        for trigger_sql in _FTS_SYNC_TRIGGERS:
            connection.execute(text(trigger_sql))
    except Exception:
        logger.warning(
            "help_article_fts (FTS5) could not be created — this SQLite build "
            "likely lacks FTS5 support. Help search will need to fall back to LIKE.",
            exc_info=True,
        )


event.listen(HelpArticle.__table__, "after_create", _create_help_article_fts)
