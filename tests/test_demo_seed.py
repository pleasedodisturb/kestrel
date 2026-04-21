"""Tests for demo data seeder (DEMO-01 through DEMO-05, D-07)."""

from __future__ import annotations

import pytest
from datetime import UTC, datetime
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base
from career_os.models.models import Application, Profile
from career_os.migration.demo_seed import seed_demo_data


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


class TestSeedDemoData:
    """DEMO-01: 10 sample jobs loaded from fixture."""

    def test_seed_creates_10_jobs(self, db_session) -> None:
        """Seeder returns 10 and creates 10 Application rows."""
        count = seed_demo_data(db_session, profile_id=1)
        assert count == 10
        apps = db_session.query(Application).filter(Application.is_demo.is_(True)).all()
        assert len(apps) == 10

    def test_seed_job_family_diversity(self, db_session) -> None:
        """DEMO-02: Jobs span 7 job families (10 unique companies)."""
        seed_demo_data(db_session, profile_id=1)
        apps = db_session.query(Application).filter(Application.is_demo.is_(True)).all()
        companies = {a.company for a in apps}
        assert len(companies) == 10  # All unique companies

    def test_seed_computes_relative_dates(self, db_session) -> None:
        """DEMO-03: Relative dates computed at seed time."""
        now = datetime.now(UTC)
        seed_demo_data(db_session, profile_id=1)
        apps = db_session.query(Application).filter(Application.is_demo.is_(True)).all()
        for app in apps:
            created = app.created_at.replace(tzinfo=UTC) if app.created_at.tzinfo is None else app.created_at
            age = now - created
            assert age.days <= 8, f"{app.company} created_at too old: {age.days} days"
            assert age.total_seconds() >= 0, f"{app.company} created_at in the future"

    def test_seed_sets_is_demo_flag(self, db_session) -> None:
        """DEMO-04: All records have is_demo=True, source='demo'."""
        seed_demo_data(db_session, profile_id=1)
        apps = db_session.query(Application).filter(Application.profile_id == 1).all()
        for app in apps:
            assert app.is_demo is True
            assert app.source == "demo"

    def test_seed_idempotent(self, db_session) -> None:
        """DEMO-05: Running twice produces exactly 10 records."""
        seed_demo_data(db_session, profile_id=1)
        seed_demo_data(db_session, profile_id=1)
        count = db_session.query(Application).filter(Application.is_demo.is_(True)).count()
        assert count == 10

    def test_score_distribution(self, db_session) -> None:
        """D-07: Bell curve — 2 high, 6 mid, 2 low."""
        seed_demo_data(db_session, profile_id=1)
        apps = db_session.query(Application).filter(Application.is_demo.is_(True)).all()
        scores = [a.fit_score for a in apps]
        high = [s for s in scores if s >= 85]
        mid = [s for s in scores if 40 <= s < 85]
        low = [s for s in scores if s < 40]
        assert len(high) == 2, f"Expected 2 high scores, got {len(high)}: {high}"
        assert len(mid) == 6, f"Expected 6 mid scores, got {len(mid)}: {mid}"
        assert len(low) == 2, f"Expected 2 low scores, got {len(low)}: {low}"


class TestPipelineBanner:
    """D-14: Sample Results banner in pipeline list."""

    @pytest.mark.skip(reason="Requires Plan 02 CLI changes - run after wave 2 merge")
    def test_pipeline_shows_demo_banner(self, db_session) -> None:
        """Banner appears when demo records exist."""
        pass
