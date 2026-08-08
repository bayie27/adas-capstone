from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models import UserRole

engine = create_engine(
    settings.DATABASE_URL, echo=True, connect_args={"check_same_thread": False}
)


# Enable WAL mode for concurrent read/write support
@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


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
                    settings.DEFAULT_ADMIN_PASSWORD
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
