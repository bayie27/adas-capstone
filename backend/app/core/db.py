import logging

from fastapi import Depends, Request
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import Settings, settings
from app.core.security import get_password_hash
from app.models import UserRole

logger = logging.getLogger("uvicorn.error")


def install_sqlite_pragmas(target_engine: Engine, busy_timeout_ms: int) -> None:
    """D-005 connection policy, applied on every new DBAPI connection.

    foreign_keys=ON is the important one — SQLite defaults it off, so none
    of the existing foreign keys were enforced. Guarded by a dialect check
    so a non-SQLite DATABASE_URL doesn't blow up at connect time.
    """

    @event.listens_for(target_engine, "connect")
    def _configure_sqlite(dbapi_connection, connection_record):
        if target_engine.dialect.name != "sqlite":
            return
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=FULL")
        cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        cursor.close()


def create_db_engine(target_settings: Settings) -> Engine:
    """Build a fully configured engine for the given settings.

    A resolvable factory (rather than a single module global) so the app
    factory in main.py can bind a different engine per Settings instance —
    the real repo-root DB for the FastAPI CLI entrypoint, a throwaway one
    for tests.
    """
    is_sqlite = target_settings.DATABASE_URL.startswith("sqlite")
    target_engine = create_engine(
        target_settings.DATABASE_URL,
        echo=target_settings.SQL_ECHO,
        connect_args={"check_same_thread": False} if is_sqlite else {},
    )
    install_sqlite_pragmas(target_engine, target_settings.SQLITE_BUSY_TIMEOUT_MS)
    return target_engine


# Default engine for scripts (seed_dev_data.py, reset_db.py, ...) and the
# FastAPI CLI entrypoint, which import this directly rather than going
# through create_app()'s per-instance engine.
engine = create_db_engine(settings)


def init_db(target_engine: Engine | None = None) -> None:
    from app.models import AlarmSettings, User

    target_engine = target_engine if target_engine is not None else engine

    SQLModel.metadata.create_all(target_engine)

    # Seed the default Administrator account
    with Session(target_engine) as session:
        user_exists = session.exec(select(User)).first()

        if not user_exists:
            logger.info("No users found. Seeding default Administrator account...")
            default_admin = User(
                username="admin",
                first_name="System",
                last_name="Administrator",
                password_hash=get_password_hash(
                    settings.DEFAULT_ADMIN_PASSWORD.get_secret_value()
                ),  # Must be changed on first login!
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(default_admin)
            session.commit()
            session.refresh(default_admin)

            session.add(AlarmSettings(user_id=default_admin.user_id))
            session.commit()
            logger.info("Default Administrator account created successfully.")


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


def get_session(bound_engine: Engine = Depends(get_engine)):
    with Session(bound_engine) as session:
        yield session
