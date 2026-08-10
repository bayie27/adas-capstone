import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# backend/ is not a package (see CLAUDE.md) — env.py runs as a standalone
# script under whatever CWD invoked `alembic`, so put backend/ on sys.path
# the same way backend/scripts/_bootstrap.py does for the dev scripts.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import every model module so SQLModel.metadata is fully populated before
# it's used as target_metadata below — SQLModel only registers a table on
# import of the module that defines it.
import app.models  # noqa: E402, F401  (populates SQLModel.metadata)
from app.core.config import settings  # noqa: E402
from app.core.db import install_sqlite_pragmas  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
#
# disable_existing_loggers=False (not the fileConfig default!) matters a
# lot here: this env.py now runs repeatedly inside the *running app*
# process — check_schema_revision's development auto-bootstrap calls
# `alembic.command.upgrade()` from app startup, not just from the `alembic`
# CLI. fileConfig's default silently disables every logger not named in
# alembic.ini's [loggers] section (app.*, uvicorn.error, pytest's caplog
# handler, ...), which is invisible until something downstream stops
# logging. This is Alembic's own documented fix for exactly that failure
# mode.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# The app's own Settings resolves DATABASE_URL (anchored to REPO_ROOT
# regardless of CWD — see 01_CONTRACTS.md §4) so migrations always target
# the same database the running app would, rather than the placeholder URL
# `alembic init` wrote into alembic.ini.
#
# app.core.migrations.get_alembic_config() (the programmatic entrypoint
# used by the startup revision check and by tests) passes a *specific*
# Settings-derived URL through config.attributes — Alembic's own
# documented mechanism for threading runtime data into env.py. That must
# win over the process-global `settings` singleton imported above: a
# caller building a Config for one particular database (a disposable test
# file, e.g.) is not asking for whatever database the current process
# would otherwise default to.
override_url = config.attributes.get("sqlalchemy_url")
config.set_main_option(
    "sqlalchemy.url",
    override_url if override_url is not None else settings.DATABASE_URL,
)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    # Same D-005 connection policy (foreign_keys=ON, WAL, busy_timeout) the
    # running app installs — SQLite's batch-mode ALTER (render_as_batch,
    # required because SQLite can't ALTER most things in place) recreates
    # tables under the hood and needs FK enforcement configured consistently
    # with production, not left at SQLite's off-by-default.
    install_sqlite_pragmas(connectable, settings.SQLITE_BUSY_TIMEOUT_MS)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
