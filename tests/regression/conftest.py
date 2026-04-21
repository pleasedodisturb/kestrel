"""Fixtures for golden set regression tests.

Provides:
- DeterministicScoringMockProvider: hash-based scoring for varied but reproducible results
- db_session: in-memory SQLite with a seeded Profile
- golden_set_provider: patches get_ai_provider to use the deterministic mock
- load_golden_set(): loads JSON fixtures from tests/fixtures/
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.ai.base import AIProvider, ComplexityTier
from career_os.database import Base
from career_os.models.models import Profile
from career_os.schemas.ai import (
    AIFeature,
    AIResponse,
    ATSKeyword,
    DimensionalScores,
    ScoreBreakdownFactor,
    ScoreResult,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Deterministic seed (same algo as mock_provider.py)
# ---------------------------------------------------------------------------


def _deterministic_seed(text: str) -> int:
    """Produce a deterministic integer seed from input text."""
    return int(hashlib.md5(text.encode()).hexdigest()[:8], 16)


# ---------------------------------------------------------------------------
# DeterministicScoringMockProvider
# ---------------------------------------------------------------------------


class DeterministicScoringMockProvider(AIProvider):
    """Mock provider that returns varied, deterministic scores based on input hash.

    Uses _deterministic_seed() to hash the job_description, then maps the seed
    to a fit_score in [0.0, 9.99] via ``(seed % 1000) / 100.0``. This makes
    golden set band assertions meaningful -- different job descriptions produce
    different scores, but the same description always produces the same score.
    """

    @property
    def name(self) -> str:
        return "deterministic-mock"

    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        tier: ComplexityTier | None = None,
        **kwargs: object,
    ) -> AIResponse:
        return AIResponse(
            content=f"Deterministic mock response to: {prompt[:80]}",
            provider=self.name,
            feature=feature,
            structured=None,
            model="deterministic-mock-v1",
        )

    async def score(
        self,
        job_description: str,
        profile_data: dict,
        *,
        tier: ComplexityTier | None = None,
        **kwargs: object,
    ) -> AIResponse:
        seed = _deterministic_seed(job_description)
        fit_score = round((seed % 1000) / 100.0, 2)

        # Derive other scores from the same seed for variety
        readiness = round((seed % 100), 1)
        career_align = round((seed % 1000) / 100.0, 1)

        structured = ScoreResult(
            fit_score=fit_score,
            reasoning=f"Deterministic score based on description hash (seed={seed}).",
            estimated_salary="Deterministic mock -- not estimated",
            effort_flag="medium",
            prep_level="moderate",
            prep_notes="Deterministic mock -- no real prep notes.",
            readiness_score=readiness,
            career_alignment=min(career_align, 10.0),
            score_breakdown=[
                ScoreBreakdownFactor(
                    factor="Hash-based technical fit",
                    contribution=round(fit_score * 0.4, 2),
                    description="Derived from description hash",
                ),
                ScoreBreakdownFactor(
                    factor="Hash-based role alignment",
                    contribution=round(fit_score * 0.35, 2),
                    description="Derived from description hash",
                ),
                ScoreBreakdownFactor(
                    factor="Hash-based domain fit",
                    contribution=round(fit_score * 0.25, 2),
                    description="Derived from description hash",
                ),
            ],
            dimensional_scores=DimensionalScores(
                technical_fit=fit_score,
                seniority_alignment=min(fit_score + 0.5, 10.0),
                compensation_fit=min(fit_score + 1.0, 10.0),
                location_fit=7.0,
                career_trajectory=min(career_align, 10.0),
                company_fit=min(fit_score + 0.5, 10.0),
            ),
            ats_keywords=[
                ATSKeyword(keyword="deterministic", category="technical", matched=True),
            ],
            desire_score=fit_score,
            desire_reasoning="Deterministic mock desire score.",
        )

        return AIResponse(
            content=structured.reasoning,
            provider=self.name,
            feature=AIFeature.score,
            structured=structured,
            model="deterministic-mock-v1",
        )

    async def embed(self, text: str, **kwargs: object) -> list[float]:
        return [0.0] * 768


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def load_golden_set(filename: str) -> dict:
    """Load a golden set fixture JSON file from tests/fixtures/."""
    filepath = FIXTURES_DIR / filename
    with open(filepath) as f:
        return json.load(f)


@pytest.fixture()
def db_session():
    """Create a fresh in-memory database for golden set regression tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    connection = engine.connect()
    test_session_cls = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = test_session_cls()

    # Default profile -- tests may override via golden set profile data
    profile = Profile(
        id=1,
        name="Golden Set Test User",
        email="golden@test.example.com",
        location="Berlin, Germany",
        job_family="TPM",
    )
    session.add(profile)
    session.commit()

    yield session
    session.close()
    connection.close()
    engine.dispose()


@pytest.fixture()
def golden_set_provider():
    """Patch get_ai_provider to return DeterministicScoringMockProvider."""
    provider = DeterministicScoringMockProvider()
    with patch("career_os.services.scoring.get_ai_provider", return_value=provider):
        yield provider
