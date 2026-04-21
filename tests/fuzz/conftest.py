"""Fuzz test fixtures -- auth disabled, clean DB state for Schemathesis."""

import os

import pytest
from sqlalchemy import create_engine, event, pool
from sqlalchemy.orm import sessionmaker

import career_os.models as _models  # noqa: F401 — register all ORM tables on Base
from career_os.database import Base, get_db
from career_os.main import app


@pytest.fixture(autouse=True, scope="session")
def disable_auth():
    """Disable API-key auth for the entire fuzz session (D-06).

    AUTH_ENABLED must be ``"false"`` *before* any request so the
    ``APIKeyAuthMiddleware`` skips verification.  We restore the
    original value (if any) after the session.
    """
    original = os.environ.get("AUTH_ENABLED")
    os.environ["AUTH_ENABLED"] = "false"
    yield
    if original is None:
        os.environ.pop("AUTH_ENABLED", None)
    else:
        os.environ["AUTH_ENABLED"] = original


@pytest.fixture(autouse=True)
def clean_db():
    """Provide an isolated in-memory database for each fuzz test.

    Overrides the FastAPI ``get_db`` dependency so every generated
    request hits a fresh SQLite instance with all tables created.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=pool.StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session_cls = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = session_cls()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    engine.dispose()
    app.dependency_overrides.clear()
