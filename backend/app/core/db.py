from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models import UserRole


def install_sqlite_pragmas(target_engine) -> None:
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
        cursor.execute(f"PRAGMA busy_timeout={settings.SQLITE_BUSY_TIMEOUT_MS}")
        cursor.close()


_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)
install_sqlite_pragmas(engine)


def init_db() -> None:
    from app.models import (
        User,
    )

    SQLModel.metadata.create_all(engine)

    # Seed the default Administrator account
    with Session(engine) as session:
        user_exists = session.exec(select(User)).first()

        if not user_exists:
            print("No users found. Seeding default Administrator account...")
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
            print("Default Administrator account created successfully.")


def get_session():
    with Session(engine) as session:
        yield session
