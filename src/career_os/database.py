"""Database configuration and session management."""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from career_os.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""

    pass


def _get_database_url() -> str:
    """Resolve database URL, ensuring data directory exists."""
    url = settings.database_url
    # Extract path from sqlite URL and ensure directory exists
    if url.startswith("sqlite:///"):
        db_path = Path(url.replace("sqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return url


def _set_sqlite_pragmas(dbapi_conn, connection_record) -> None:  # noqa: ANN001
    """Enable WAL mode and foreign keys for SQLite connections."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine = create_engine(
    _get_database_url(),
    # check_same_thread=False is required for FastAPI's async request handling
    # where DB sessions may be created in one thread and used in another.
    # WAL mode (set in _set_sqlite_pragmas) makes concurrent reads safe.
    connect_args={"check_same_thread": False},
    echo=False,
)

# Enable WAL mode and foreign keys on every connection
event.listen(engine, "connect", _set_sqlite_pragmas)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Session:
    """Dependency for FastAPI: yield a database session."""
    db = SessionLocal()
    try:
        yield db  # type: ignore[misc]
    finally:
        db.close()


def create_test_engine(url: str = "sqlite:///:memory:"):
    """Create a test engine with in-memory SQLite."""
    test_engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(test_engine, "connect", _set_sqlite_pragmas)
    return test_engine
