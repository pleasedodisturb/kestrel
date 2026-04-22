"""Shared test fixtures."""

import os
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Application, Profile

# Ensure tools/ is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

# ---------------------------------------------------------------------------
# Test isolation: force mock AI provider and blank all real API keys
# ---------------------------------------------------------------------------

# Set before any career_os imports that read settings so the pydantic-settings
# singleton picks up mock values when first constructed.
os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("TOGETHER_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("GROQ_API_KEY", "")
os.environ.setdefault("XAI_API_KEY", "")
os.environ.setdefault("GOOGLE_API_KEY", "")

# Real AI provider domains — any HTTP request to these during tests is a bug.
_BLOCKED_AI_DOMAINS = [
    "openrouter.ai",
    "api.anthropic.com",
    "api.together.xyz",
    "api.openai.com",
    "api.groq.com",
    "api.x.ai",
    "generativelanguage.googleapis.com",
]


@pytest.fixture(autouse=True)
def block_real_ai_calls(monkeypatch):
    """Fail fast if any test tries to hit a real AI provider.

    Intercepts all httpx.AsyncClient.send calls and raises immediately if the
    target host matches a known AI provider domain. This prevents accidental
    API charges when tests are run with real credentials in the environment.
    """
    original_send = httpx.AsyncClient.send

    async def guarded_send(self, request, **kwargs):
        host = request.url.host
        for domain in _BLOCKED_AI_DOMAINS:
            if domain in host:
                raise RuntimeError(
                    f"TEST ISOLATION VIOLATION: attempted real HTTP call to {host}. "
                    f"Tests must use AI_PROVIDER=mock. "
                    f"Check conftest.py and .env — a real API key may be leaking in."
                )
        return await original_send(self, request, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", guarded_send)


from tests.profile_data import DEFAULT_PROFILE_KWARGS, SECOND_PROFILE_KWARGS  # noqa: F401


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Shared database fixtures for M6+ tests
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine():
    """Create a fresh in-memory SQLite engine with FK enforcement."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Session:
    """Yield a database session on a shared connection.

    Uses a single connection so both test code and the FastAPI app
    see the same in-memory tables when dependency is overridden.
    """
    connection = db_engine.connect()
    test_session_cls = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = test_session_cls()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    connection.close()
    app.dependency_overrides.clear()


@pytest.fixture
def profile(db_session: Session) -> Profile:
    """Seed a default test profile."""
    p = Profile(id=1, **DEFAULT_PROFILE_KWARGS)
    db_session.add(p)
    db_session.commit()
    return p


@pytest.fixture
def application(db_session: Session, profile: Profile) -> Application:
    """Seed a default test application linked to the test profile."""
    a = Application(
        profile_id=profile.id,
        company="Acme Corp",
        role="Senior Engineer",
        status="discovered",
    )
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


@pytest.fixture
def authenticated_client(db_session: Session) -> TestClient:
    """FastAPI test client with auth header pre-set."""
    return TestClient(app, headers={"Authorization": "Bearer test-token"})


@pytest.fixture
def sample_jobs():
    """Sample job dicts for testing pipeline steps."""
    return [
        {
            "title": "Senior AI Product Manager",
            "company": "Mistral AI",
            "location": "Remote, EU",
            "url": "https://mistral.ai/careers/pm",
            "source": "remotive",
            "description": "Build AI products with autonomy. ML platform team.",
            "posted": "2026-03-10",
            "remote": True,
            "salary": "130-160k EUR",
            "tags": ["ai", "product"],
            "fit_score": 9,
            "fit_reasoning": "Strong AI focus, remote, builder role",
            "estimated_salary": "130-160k EUR",
            "effort_flag": "sweet-spot",
            "prep_level": 2,
            "prep_notes": "Brush up on LLM deployment",
        },
        {
            "title": "Technical Program Manager",
            "company": "Linear",
            "location": "Remote",
            "url": "https://linear.app/jobs/tpm",
            "source": "weworkremotely",
            "description": "Coordinate technical programs for developer tools.",
            "posted": "2026-03-09",
            "remote": True,
            "salary": "",
            "tags": ["tpm"],
            "fit_score": 7,
            "fit_reasoning": "Good company, builder culture",
            "estimated_salary": "120-140k EUR",
            "effort_flag": "moderate",
            "prep_level": 2,
            "prep_notes": "Study Linear's product",
        },
        {
            "title": "PMO Coordinator",
            "company": "Big Corp AG",
            "location": "Munich, Germany",
            "url": "https://bigcorp.de/jobs/pmo",
            "source": "arbeitsagentur",
            "description": "PMBOK-based project coordination. Administrative tasks.",
            "posted": "2026-03-08",
            "remote": False,
            "salary": "",
            "tags": [],
            "fit_score": 2,
            "fit_reasoning": "PMBOK-heavy, no AI, not remote",
            "estimated_salary": "70-85k EUR",
            "effort_flag": "high-intensity",
            "prep_level": 1,
            "prep_notes": "N/A",
        },
        {
            "title": "AI Engineer",
            "company": "Startup GmbH",
            "location": "Berlin, Germany",
            "url": "https://startup.de/ai",
            "source": "germantechjobs",
            "description": "Founding AI engineer. Build ML pipelines.",
            "posted": "2026-03-10",
            "remote": False,
            "salary": "90-110k EUR",
            "tags": ["ai", "ml", "founding"],
            "fit_score": 6,
            "fit_reasoning": "AI focus, founding team, but not remote",
            "estimated_salary": "90-110k EUR",
            "effort_flag": "moderate",
            "prep_level": 4,
            "prep_notes": "Need to ramp up on MLOps",
        },
    ]


@pytest.fixture
def tmp_tracking_dir(tmp_path):
    """Create a temporary tracking directory with sample CSV."""
    tracking = tmp_path / "tracking"
    tracking.mkdir()

    csv_content = (
        "date_applied,company,role,url,source,status,salary_range,contact,next_step,notes,fit_score\n"
        '2026-03-01,Existing Co,Senior PM,https://example.com,linkedin,interested,"100-120k",,,Good fit,7/10\n'
        '2026-03-05,Another Inc,AI Lead,https://another.com,indeed,applied,"130-150k",,,Strong AI,8/10\n'
    )
    (tracking / "applications.csv").write_text(csv_content)

    return tracking
