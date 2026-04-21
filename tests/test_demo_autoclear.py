"""Tests for demo data auto-clear behavior (D-13)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base
from career_os.models.models import Application, Profile
from career_os.migration.demo_seed import seed_demo_data
from career_os.services.applications import _auto_clear_demo_data


def _set_sqlite_pragmas(dbapi_conn, connection_record) -> None:  # noqa: ANN001
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture()
def db_session(tmp_path):
    """Create a temporary SQLite database with tables and a default profile."""
    db_path = tmp_path / "test.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _set_sqlite_pragmas)
    Base.metadata.create_all(bind=engine)
    testing_session_cls = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    session = testing_session_cls()
    profile = Profile(id=1, name="Test User", email="test@test.com", location="Frankfurt")
    session.add(profile)
    session.commit()

    yield session
    session.close()
    engine.dispose()


class TestAutoClearDemoData:
    """D-13: Auto-clear demo data when first real job arrives."""

    def test_autoclear_on_real_job(self, db_session) -> None:
        """All demo records deleted after auto-clear."""
        seed_demo_data(db_session, profile_id=1)
        assert db_session.query(Application).filter(Application.is_demo.is_(True)).count() == 10

        deleted = _auto_clear_demo_data(db_session, profile_id=1)
        assert deleted == 10
        assert db_session.query(Application).filter(Application.is_demo.is_(True)).count() == 0

    def test_autoclear_no_demo_is_noop(self, db_session) -> None:
        """No error when no demo records exist."""
        deleted = _auto_clear_demo_data(db_session, profile_id=1)
        assert deleted == 0

    def test_autoclear_preserves_real_jobs(self, db_session) -> None:
        """Real applications (is_demo=False) are NOT deleted."""
        seed_demo_data(db_session, profile_id=1)
        # Add a real job
        real_app = Application(
            profile_id=1,
            company="Real Corp",
            role="Real Role",
            source="manual",
            status="discovered",
            is_demo=False,
        )
        db_session.add(real_app)
        db_session.commit()

        _auto_clear_demo_data(db_session, profile_id=1)

        remaining = db_session.query(Application).filter(Application.profile_id == 1).all()
        assert len(remaining) == 1
        assert remaining[0].company == "Real Corp"
        assert remaining[0].is_demo is False

    def test_autoclear_preserves_ghost_seeds(self, db_session) -> None:
        """Ghost seed records (source='seed', is_demo=False) are NOT deleted (Pitfall 5)."""
        seed_demo_data(db_session, profile_id=1)
        # Add a ghost seed record
        ghost = Application(
            profile_id=1,
            company="GhostCo",
            role="Ghost Role",
            source="seed",
            status="applied",
            is_demo=False,
        )
        db_session.add(ghost)
        db_session.commit()

        _auto_clear_demo_data(db_session, profile_id=1)

        remaining = db_session.query(Application).filter(
            Application.profile_id == 1, Application.is_demo.is_(False)
        ).all()
        assert len(remaining) == 1
        assert remaining[0].source == "seed"
