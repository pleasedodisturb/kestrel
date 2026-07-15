"""Drive the REAL production scorer over a golden-set fixture (G-1336).

The one rule that motivated this whole ticket: the eval exercises
``career_os.services.scoring.score_job`` — the real production entrypoint —
never a reimplementation. It runs with the deterministic **MockProvider** (the
default ``AI_PROVIDER=mock``) so there are zero paid LLM calls and the output is
reproducible in CI. "Production path, mock provider."

Shared by the eval tests and the baseline generator so both score identically.
"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base
from career_os.models.models import Profile
from career_os.services.scoring import score_job
from tests.eval.label_store import load_fixture


def make_memory_session() -> Session:
    """Create a fresh in-memory SQLite session with FK enforcement + a profile."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_pragma(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    session.add(
        Profile(
            id=1,
            name="Eval User",
            email="eval@test.example.com",
            location="Remote",
            job_family="TPM",
        )
    )
    session.commit()
    return session


async def score_fixture(db: Session, fixture_name: str, *, profile_id: int = 1) -> dict[str, float]:
    """Score every job in a fixture through the real ``score_job``.

    Aligns the seeded profile to the fixture's job family/location so the run is
    faithful, then returns ``{job_id: fit_score}``.
    """
    fixture = load_fixture(fixture_name)
    profile = db.get(Profile, profile_id)
    profile.job_family = fixture["profile"]["job_family"]
    profile.location = fixture["profile"]["location"]
    db.commit()

    scores: dict[str, float] = {}
    for job in fixture["jobs"]:
        scored = await score_job(
            db,
            profile_id,
            job["description"],
            job_title=job["title"],
            job_company=job["company"],
        )
        scores[job["id"]] = scored.fit_score
    return scores
