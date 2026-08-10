"""D-005 / 10_PKG_migration_evidence.md Step 1 — the startup revision check.

"Ordinary application startup never silently changes the production
schema." A production database's Alembic revision must already match the
running code's head — provisioned or upgraded beforehand by an operator
running `alembic upgrade head`, never by the app itself. Development is
more forgiving: a mismatch only warns, and a genuinely fresh/uninitialized
database (no `alembic_version` row at all — the common case for a
throwaway test or reset-and-reseed dev database) is bootstrapped
automatically, since D-005 treats those as disposable by design.
"""

import logging
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine

from app.core.config import Settings

logger = logging.getLogger("uvicorn.error")

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI_PATH = REPO_ROOT / "alembic.ini"


class SchemaRevisionError(RuntimeError):
    """Raised when a production database's schema revision cannot be
    trusted to match the running code — startup must refuse."""


def get_alembic_config(settings: Settings) -> Config:
    """Builds a Config bound to a *specific* Settings instance's
    DATABASE_URL — not necessarily the process-global `settings` singleton
    backend/alembic/env.py falls back to otherwise. `config.attributes` is
    Alembic's own documented mechanism for threading extra data into
    env.py (see its "programmatic use" cookbook); `set_main_option` alone
    doesn't survive here because env.py unconditionally recomputes
    "sqlalchemy.url" from the app's Settings when this isn't present."""
    cfg = Config(str(ALEMBIC_INI_PATH))
    cfg.attributes["sqlalchemy_url"] = settings.DATABASE_URL
    return cfg


def get_code_head_revision(settings: Settings) -> str | None:
    script = ScriptDirectory.from_config(get_alembic_config(settings))
    return script.get_current_head()


def get_database_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        return context.get_current_revision()


def is_known_schema_revision(settings: Settings, revision: str) -> bool:
    """True if `revision` is somewhere in the code's migration chain
    (base..head) — i.e. a schema that is behind, not foreign/corrupt.

    Also used by app.maintenance.restore to reject restoring a backup
    whose recorded schema_revision this codebase's migration chain
    doesn't recognize (10_PKG_migration_evidence.md Step 1 — "wire the
    revision into backups... make restore validation reject a backup
    whose revision is incompatible with the running code")."""
    script = ScriptDirectory.from_config(get_alembic_config(settings))
    known = {rev.revision for rev in script.walk_revisions(base="base", head="heads")}
    return revision in known


def check_schema_revision(engine: Engine, settings: Settings) -> None:
    """The startup gate. Called once from the app lifespan, before any
    seeding or route traffic.

    - revision matches head → nothing to do.
    - no revision at all (fresh DB): production refuses; development
      bootstraps automatically via `alembic upgrade head` (this is the
      "reset the DB via Alembic now, not by deleting the file" workflow —
      CLAUDE.md).
    - revision present but stale or unrecognized: production refuses;
      development logs a warning and continues.
    """
    from alembic import command

    cfg = get_alembic_config(settings)
    script = ScriptDirectory.from_config(cfg)
    head_rev = script.get_current_head()
    current_rev = get_database_revision(engine)

    if current_rev == head_rev:
        return

    is_production = settings.ENVIRONMENT == "production"

    if current_rev is None:
        message = (
            "Database has no Alembic schema. Run `uv run alembic upgrade head` "
            "before starting the backend."
        )
        if is_production:
            raise SchemaRevisionError(message)
        logger.warning(
            "%s Development database — applying migrations automatically.",
            message,
        )
        command.upgrade(cfg, "head")
        return

    if is_known_schema_revision(settings, current_rev):
        message = (
            f"Database schema ({current_rev}) is older than the application "
            f"code ({head_rev}). Run `uv run alembic upgrade head` before "
            "starting the backend."
        )
    else:
        message = (
            f"Database schema ({current_rev}) is not a recognized ancestor of "
            f"the application code's head ({head_rev}) — it may be newer or "
            "from an incompatible build. Refusing to start against it."
        )

    if is_production:
        raise SchemaRevisionError(message)
    logger.warning(message)
