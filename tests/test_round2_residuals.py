"""Tests for M3 scrutiny round 2 residual fixes.

Covers:
1. Salary parser k-notation (120k → 120000)
2. OpenRouter score_breakdown prompt/system prompt
3. Salary trends grouped by location
4. Market refresh returns null before first refresh
5. Scheduled discovery gates by cadence/next_run
6. SearchProfile API shows cadence/next_run fields
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.discovery import DiscoveredJob, SearchProfile
from career_os.models.models import Profile
from career_os.services.discovery import _compute_next_run, run_scheduled_discovery
from career_os.services.market import (
    _get_last_refreshed_at,
    get_salary_trends,
    refresh_market_data,
)
from career_os.services.salary import parse_salary_range, salary_midpoint

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    connection = engine.connect()
    TestSession = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = TestSession()

    # Seed a profile
    profile = Profile(
        id=1, name="Test User", email="test@example.com",
        location="Frankfurt", job_family="TPM",
    )
    session.add(profile)
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    connection.close()
    engine.dispose()
    app.dependency_overrides.clear()


@pytest.fixture
def client(db_session):
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def profile(db_session) -> Profile:
    """Get the seeded test profile."""
    return db_session.query(Profile).filter(Profile.id == 1).first()


# ---------------------------------------------------------------------------
# 1. Salary parser k-notation tests
# ---------------------------------------------------------------------------


class TestSalaryKNotation:
    """Verify k-notation salary parsing (120k → 120000)."""

    def test_k_range_eur(self):
        low, high = parse_salary_range("120k-160k EUR")
        assert low == 120000
        assert high == 160000

    def test_k_range_with_euro_symbol(self):
        low, high = parse_salary_range("€80k-€100k")
        assert low == 80000
        assert high == 100000

    def test_k_range_with_dollar_symbol(self):
        low, high = parse_salary_range("$120k-$150k")
        assert low == 120000
        assert high == 150000

    def test_k_single_value(self):
        low, high = parse_salary_range("60k")
        assert low == 60000
        assert high == 60000

    def test_k_uppercase(self):
        low, high = parse_salary_range("100K-130K")
        assert low == 100000
        assert high == 130000

    def test_full_numbers_still_work(self):
        """Existing format: full numeric values should still parse."""
        low, high = parse_salary_range("130000-160000 EUR")
        assert low == 130000
        assert high == 160000

    def test_comma_format_still_works(self):
        low, high = parse_salary_range("130,000 - 160,000")
        assert low == 130000
        assert high == 160000

    def test_midpoint_k_notation(self):
        mid = salary_midpoint("120k-160k EUR")
        assert mid == 140000

    def test_midpoint_single_k(self):
        mid = salary_midpoint("80k")
        assert mid == 80000

    def test_k_mixed_with_full(self):
        """Edge case: one k-notation, one full number."""
        low, high = parse_salary_range("80k-120000")
        assert low == 80000
        assert high == 120000

    def test_none_returns_none(self):
        low, high = parse_salary_range(None)
        assert low is None
        assert high is None

    def test_empty_returns_none(self):
        low, high = parse_salary_range("")
        assert low is None
        assert high is None


# ---------------------------------------------------------------------------
# 2. OpenRouter score_breakdown in prompts
# ---------------------------------------------------------------------------


class TestOpenRouterScoreBreakdown:
    """Verify OpenRouter provider includes score_breakdown in prompts."""

    def test_score_system_prompt_mentions_score_breakdown(self):
        """The system prompt for scoring should mention score_breakdown."""
        from career_os.ai.openrouter_provider import _system_prompt_for_feature
        from career_os.schemas.ai import AIFeature

        system_prompt = _system_prompt_for_feature(AIFeature.score)
        assert system_prompt is not None
        assert "score_breakdown" in system_prompt
        assert "≥3" in system_prompt
        assert "factor" in system_prompt
        assert "contribution" in system_prompt

    def test_score_method_prompt_contains_score_breakdown(self):
        """The user-facing prompt in score() should mention score_breakdown."""
        from career_os.ai.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider(api_key="test-key")
        import inspect
        source = inspect.getsource(provider.score)
        assert "score_breakdown" in source


# ---------------------------------------------------------------------------
# 3. Salary trends grouped by location
# ---------------------------------------------------------------------------


class TestSalaryTrendsLocationGrouping:
    """Verify salary trends include location in the grouping key."""

    def test_trends_grouped_by_location(self, db_session: Session, profile: Profile):
        """Jobs in different locations should produce separate trend entries."""
        now = datetime.now(UTC)
        db_session.add(DiscoveredJob(
            profile_id=profile.id,
            title="Senior TPM",
            company="CompA",
            location="Frankfurt",
            salary_range="120000-160000 EUR",
            title_normalized="senior tpm",
            company_normalized="compa",
            location_normalized="frankfurt",
            sources="[]",
            source_urls="[]",
            posted_at=now,
        ))
        db_session.add(DiscoveredJob(
            profile_id=profile.id,
            title="Senior TPM",
            company="CompB",
            location="Berlin",
            salary_range="100000-140000 EUR",
            title_normalized="senior tpm",
            company_normalized="compb",
            location_normalized="berlin",
            sources="[]",
            source_urls="[]",
            posted_at=now,
        ))
        db_session.commit()

        result = get_salary_trends(db_session, profile.id)
        trends = result["trends"]

        assert len(trends) >= 2
        locations = {t["location"] for t in trends}
        assert "Frankfurt" in locations
        assert "Berlin" in locations

    def test_trends_same_location_aggregated(self, db_session: Session, profile: Profile):
        """Jobs in the same location should be aggregated together."""
        now = datetime.now(UTC)
        for i in range(3):
            db_session.add(DiscoveredJob(
                profile_id=profile.id,
                title="Engineer",
                company=f"Comp{i}",
                location="Frankfurt",
                salary_range=f"{100000 + i * 10000}-{130000 + i * 10000} EUR",
                title_normalized="engineer",
                company_normalized=f"comp{i}",
                location_normalized="frankfurt",
                sources="[]",
                source_urls="[]",
                posted_at=now,
            ))
        db_session.commit()

        result = get_salary_trends(db_session, profile.id)
        trends = result["trends"]

        assert len(trends) == 1
        assert trends[0]["location"] == "Frankfurt"
        assert trends[0]["sample_size"] == 3

    def test_trend_location_field_not_empty(self, db_session: Session, profile: Profile):
        """Even without a location filter param, trends should have actual locations."""
        now = datetime.now(UTC)
        db_session.add(DiscoveredJob(
            profile_id=profile.id,
            title="TPM",
            company="TestCo",
            location="Munich",
            salary_range="120000-150000 EUR",
            title_normalized="tpm",
            company_normalized="testco",
            location_normalized="munich",
            sources="[]",
            source_urls="[]",
            posted_at=now,
        ))
        db_session.commit()

        result = get_salary_trends(db_session, profile.id)
        trends = result["trends"]
        assert len(trends) == 1
        assert trends[0]["location"] == "Munich"


# ---------------------------------------------------------------------------
# 4. Market refresh returns null before first refresh
# ---------------------------------------------------------------------------


class TestMarketRefreshNullTimestamp:
    """Verify market endpoints return null refresh timestamp before first refresh."""

    def test_no_refresh_returns_none(self, profile: Profile):
        """Profile without last_market_refreshed_at should yield None."""
        assert profile.last_market_refreshed_at is None
        result = _get_last_refreshed_at(profile)
        assert result is None

    def test_after_refresh_returns_timestamp(self, db_session: Session, profile: Profile):
        """After refresh_market_data(), should return a real timestamp."""
        result = refresh_market_data(db_session, profile.id)
        assert result["last_refreshed_at"] is not None

        db_session.refresh(profile)
        ts = _get_last_refreshed_at(profile)
        assert ts is not None
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None

    def test_salary_trends_null_before_refresh(self, db_session: Session, profile: Profile):
        """Salary trends should return null last_refreshed_at before refresh."""
        result = get_salary_trends(db_session, profile.id)
        assert result["last_refreshed_at"] is None

    def test_salary_trends_api_null_before_refresh(self, client, profile: Profile):
        """API should return null last_refreshed_at before refresh."""
        resp = client.get(f"/api/market/salary-trends?profile_id={profile.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["last_refreshed_at"] is None


# ---------------------------------------------------------------------------
# 5. Scheduled discovery gates by cadence/next_run
# ---------------------------------------------------------------------------


class TestScheduledDiscoveryGating:
    """Verify scheduled discovery respects cadence/next_run."""

    def test_compute_next_run_weekly(self):
        base = datetime(2025, 1, 1, tzinfo=UTC)
        result = _compute_next_run("weekly", base)
        assert result == datetime(2025, 1, 8, tzinfo=UTC)

    def test_compute_next_run_daily(self):
        base = datetime(2025, 1, 1, tzinfo=UTC)
        result = _compute_next_run("daily", base)
        assert result == datetime(2025, 1, 2, tzinfo=UTC)

    def test_compute_next_run_none_cadence(self):
        result = _compute_next_run(None)
        assert result is None

    def test_compute_next_run_unknown_cadence(self):
        result = _compute_next_run("monthly")
        assert result is None

    @pytest.mark.asyncio
    async def test_skips_profile_with_future_next_run(self, db_session: Session, profile: Profile):
        """Search profiles with next_run in the future should be skipped."""
        future = datetime.now(UTC) + timedelta(days=3)
        sp = SearchProfile(
            profile_id=profile.id,
            name="Test Search",
            keywords=json.dumps(["python"]),
            locations=json.dumps(["Frankfurt"]),
            remote_only=False,
            sources=json.dumps([]),
            is_active=True,
            cadence="weekly",
            next_run=future,
        )
        db_session.add(sp)
        db_session.commit()

        result = await run_scheduled_discovery(db_session, profile.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_runs_profile_with_past_next_run(self, db_session: Session, profile: Profile):
        """Search profiles with next_run in the past should run."""
        past = datetime.now(UTC) - timedelta(days=1)
        sp = SearchProfile(
            profile_id=profile.id,
            name="Test Search",
            keywords=json.dumps(["python"]),
            locations=json.dumps(["Frankfurt"]),
            remote_only=False,
            sources=json.dumps([]),
            is_active=True,
            cadence="weekly",
            next_run=past,
        )
        db_session.add(sp)
        db_session.commit()

        mock_target = (
            "career_os.services.discovery.run_discovery"
        )
        with patch(mock_target, new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "run_id": 1,
                "total_found": 0,
                "new_jobs": 0,
                "duplicates": 0,
                "jobs": [],
                "warnings": [],
                "sources_queried": [],
            }
            result = await run_scheduled_discovery(db_session, profile.id)

        assert result is not None
        mock_run.assert_called_once()

        # After execution, next_run should be updated
        db_session.refresh(sp)
        assert sp.next_run is not None
        # The next_run should be ~7 days from now (weekly cadence)
        # Normalize tz for comparison (SQLite may strip tzinfo)
        next_run = sp.next_run
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=UTC)
        past_aware = past if past.tzinfo else past.replace(tzinfo=UTC)
        assert next_run > past_aware

    @pytest.mark.asyncio
    async def test_runs_profile_with_null_next_run(self, db_session: Session, profile: Profile):
        """Search profiles with no next_run should always run."""
        sp = SearchProfile(
            profile_id=profile.id,
            name="Test Search",
            keywords=json.dumps(["python"]),
            locations=json.dumps(["Frankfurt"]),
            remote_only=False,
            sources=json.dumps([]),
            is_active=True,
            cadence="weekly",
            next_run=None,
        )
        db_session.add(sp)
        db_session.commit()

        mock_target = (
            "career_os.services.discovery.run_discovery"
        )
        with patch(mock_target, new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "run_id": 1,
                "total_found": 0,
                "new_jobs": 0,
                "duplicates": 0,
                "jobs": [],
                "warnings": [],
                "sources_queried": [],
            }
            result = await run_scheduled_discovery(db_session, profile.id)

        assert result is not None
        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# 6. SearchProfile API shows cadence/next_run fields
# ---------------------------------------------------------------------------


class TestSearchProfileCadenceExposure:
    """Verify SearchProfile API response includes cadence/next_run fields."""

    def test_create_search_profile_returns_cadence(self, client):
        resp = client.post("/api/search-profiles", json={
            "profile_id": 1,
            "name": "Weekly TPM Search",
            "keywords": ["TPM", "AI"],
            "locations": ["Frankfurt"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "cadence" in data
        assert "next_run" in data

    def test_list_search_profiles_shows_cadence(self, client):
        client.post("/api/search-profiles", json={
            "profile_id": 1,
            "name": "Daily Search",
            "keywords": ["engineer"],
        })
        resp = client.get("/api/search-profiles?profile_id=1")
        assert resp.status_code == 200
        data = resp.json()
        for sp in data["profiles"]:
            assert "cadence" in sp
            assert "next_run" in sp

    def test_get_search_profile_shows_cadence(self, client):
        create_resp = client.post("/api/search-profiles", json={
            "profile_id": 1,
            "name": "Test Search",
            "keywords": ["python"],
        })
        sp_id = create_resp.json()["id"]

        resp = client.get(f"/api/search-profiles/{sp_id}?profile_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert "cadence" in data
        assert "next_run" in data
