"""Tests for discovery/search salary and dedup fixes (m3-fix-discovery-salary).

Covers:
1. Discovery dedup profile-scoped: same job for different profiles creates separate rows
2. Saved search filters applied during discovery execution
3. Salary filtering uses numeric comparison (not string matching)
4. Salary sort produces correct numeric ordering
5. Salary parsing utility
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base, get_db
from career_os.discovery.adapters import RawJobResult, ScrapeParams, ScraperAdapter
from career_os.main import app
from career_os.models.discovery import DiscoveredJob, SearchProfile
from career_os.models.models import Profile
from career_os.services.discovery import _passes_sp_filters, run_discovery
from career_os.services.salary import parse_salary_range, salary_midpoint

# ---------------------------------------------------------------------------
# Test database setup
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

    # Seed two profiles
    profile_a = Profile(
        id=1, name="Profile A", email="a@test.com", location="Frankfurt"
    )
    profile_b = Profile(
        id=2, name="Profile B", email="b@test.com", location="Berlin"
    )
    session.add_all([profile_a, profile_b])
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield session
    app.dependency_overrides.clear()
    session.close()
    connection.close()


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# 1. Salary Parsing Utility Tests
# ---------------------------------------------------------------------------


class TestSalaryParsing:
    """Test the shared salary parsing utility."""

    def test_parse_range_eur(self):
        low, high = parse_salary_range("130000-160000 EUR")
        assert low == 130000
        assert high == 160000

    def test_parse_range_with_commas(self):
        low, high = parse_salary_range("130,000 - 160,000 USD")
        assert low == 130000
        assert high == 160000

    def test_parse_single_value(self):
        low, high = parse_salary_range("150000 EUR")
        assert low == 150000
        assert high == 150000

    def test_parse_none(self):
        low, high = parse_salary_range(None)
        assert low is None
        assert high is None

    def test_parse_empty_string(self):
        low, high = parse_salary_range("")
        assert low is None
        assert high is None

    def test_parse_no_numbers(self):
        low, high = parse_salary_range("Competitive salary")
        assert low is None
        assert high is None

    def test_midpoint_calculation(self):
        mid = salary_midpoint("120000-160000 EUR")
        assert mid == 140000.0

    def test_midpoint_none_for_unparseable(self):
        mid = salary_midpoint("TBD")
        assert mid is None


# ---------------------------------------------------------------------------
# 2. Discovery Dedup Profile-Scoped
# ---------------------------------------------------------------------------


class TestDedupProfileScoped:
    """Same job discovered by different profiles creates separate rows."""

    @pytest.mark.asyncio
    async def test_same_job_different_profiles_creates_separate_rows(self, db_session):
        """Dedup constraint includes profile_id — same job for two profiles = two rows."""

        class MockAdapter(ScraperAdapter):
            source_name = "mock_source"

            async def scrape(self, params: ScrapeParams) -> list[RawJobResult]:
                return [
                    RawJobResult(
                        title="Senior TPM",
                        company="Acme Corp",
                        location="Berlin",
                        url="https://example.com/job1",
                        description="A great role",
                        salary_range="130000-160000 EUR",
                        remote=True,
                        posted_at=datetime.now(UTC),
                        source="mock_source",
                    ),
                ]

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[MockAdapter()],
        ):
            # Discover for profile A
            result_a = await run_discovery(db_session, profile_id=1)
            assert result_a["new_jobs"] == 1

            # Discover for profile B — same job should create a NEW row
            result_b = await run_discovery(db_session, profile_id=2)
            assert result_b["new_jobs"] == 1

        # Both profiles have their own row
        jobs_a = (
            db_session.query(DiscoveredJob)
            .filter(DiscoveredJob.profile_id == 1)
            .all()
        )
        jobs_b = (
            db_session.query(DiscoveredJob)
            .filter(DiscoveredJob.profile_id == 2)
            .all()
        )
        assert len(jobs_a) == 1
        assert len(jobs_b) == 1
        assert jobs_a[0].id != jobs_b[0].id

    @pytest.mark.asyncio
    async def test_same_profile_same_job_is_deduped(self, db_session):
        """Same job for the same profile is deduplicated (not duplicated)."""

        class MockAdapter(ScraperAdapter):
            source_name = "mock_source"

            async def scrape(self, params: ScrapeParams) -> list[RawJobResult]:
                return [
                    RawJobResult(
                        title="Senior TPM",
                        company="Acme Corp",
                        location="Berlin",
                        url="https://example.com/job1",
                        description="A great role",
                        salary_range="130000-160000 EUR",
                        remote=True,
                        posted_at=None,  # avoid tz-aware/naive comparison
                        source="mock_source",
                    ),
                ]

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[MockAdapter()],
        ):
            result1 = await run_discovery(db_session, profile_id=1)
            assert result1["new_jobs"] == 1

            result2 = await run_discovery(db_session, profile_id=1)
            assert result2["new_jobs"] == 0
            assert result2["duplicates"] == 1

        # Only one row for profile A
        jobs = (
            db_session.query(DiscoveredJob)
            .filter(DiscoveredJob.profile_id == 1)
            .all()
        )
        assert len(jobs) == 1


# ---------------------------------------------------------------------------
# 3. Saved Search Filters Applied During Discovery
# ---------------------------------------------------------------------------


class TestSavedSearchFiltersApplied:
    """sp.filters JSON is read and applied during discovery execution."""

    @pytest.mark.asyncio
    async def test_salary_min_filter_excludes_low_salary_jobs(self, db_session):
        """Jobs below salary_min are filtered out during discovery."""

        class MockAdapter(ScraperAdapter):
            source_name = "mock_source"

            async def scrape(self, params: ScrapeParams) -> list[RawJobResult]:
                return [
                    RawJobResult(
                        title="Junior Dev",
                        company="SmallCo",
                        location="Berlin",
                        url="https://example.com/low",
                        description="Low pay role",
                        salary_range="50000-60000 EUR",
                        remote=False,
                        posted_at=datetime.now(UTC),
                        source="mock_source",
                    ),
                    RawJobResult(
                        title="Senior TPM",
                        company="BigCo",
                        location="Frankfurt",
                        url="https://example.com/high",
                        description="High pay role",
                        salary_range="150000-180000 EUR",
                        remote=True,
                        posted_at=datetime.now(UTC),
                        source="mock_source",
                    ),
                ]

        # Create search profile with salary_min filter
        sp = SearchProfile(
            profile_id=1,
            name="High Salary Only",
            keywords=json.dumps(["dev"]),
            locations=json.dumps(["Germany"]),
            remote_only=False,
            sources=json.dumps(["mock_source"]),
            filters=json.dumps({"salary_min": 100000}),
        )
        db_session.add(sp)
        db_session.commit()
        db_session.refresh(sp)

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[MockAdapter()],
        ):
            result = await run_discovery(
                db_session,
                profile_id=1,
                search_profile_id=sp.id,
            )

        # Only the high-salary job should be saved
        assert result["new_jobs"] == 1
        jobs = (
            db_session.query(DiscoveredJob)
            .filter(DiscoveredJob.profile_id == 1)
            .all()
        )
        assert len(jobs) == 1
        assert jobs[0].company == "BigCo"

    @pytest.mark.asyncio
    async def test_remote_filter_applied_during_discovery(self, db_session):
        """Remote filter from sp.filters is applied during discovery."""

        class MockAdapter(ScraperAdapter):
            source_name = "mock_source"

            async def scrape(self, params: ScrapeParams) -> list[RawJobResult]:
                return [
                    RawJobResult(
                        title="On-site Dev",
                        company="OfficeCo",
                        location="Munich",
                        url="https://example.com/onsite",
                        description="On-site role",
                        salary_range="100000-120000 EUR",
                        remote=False,
                        posted_at=datetime.now(UTC),
                        source="mock_source",
                    ),
                    RawJobResult(
                        title="Remote Dev",
                        company="RemoteCo",
                        location="Remote",
                        url="https://example.com/remote",
                        description="Remote role",
                        salary_range="120000-140000 EUR",
                        remote=True,
                        posted_at=datetime.now(UTC),
                        source="mock_source",
                    ),
                ]

        sp = SearchProfile(
            profile_id=1,
            name="Remote Only",
            keywords=json.dumps([]),
            locations=json.dumps([]),
            remote_only=False,
            sources=json.dumps(["mock_source"]),
            filters=json.dumps({"remote": True}),
        )
        db_session.add(sp)
        db_session.commit()
        db_session.refresh(sp)

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[MockAdapter()],
        ):
            result = await run_discovery(
                db_session,
                profile_id=1,
                search_profile_id=sp.id,
            )

        assert result["new_jobs"] == 1
        jobs = (
            db_session.query(DiscoveredJob)
            .filter(DiscoveredJob.profile_id == 1)
            .all()
        )
        assert len(jobs) == 1
        assert jobs[0].company == "RemoteCo"

    @pytest.mark.asyncio
    async def test_no_filters_passes_all_jobs(self, db_session):
        """When no filters are set, all jobs pass through."""

        class MockAdapter(ScraperAdapter):
            source_name = "mock_source"

            async def scrape(self, params: ScrapeParams) -> list[RawJobResult]:
                return [
                    RawJobResult(
                        title="Job 1",
                        company="Co1",
                        location="Berlin",
                        url="https://example.com/1",
                        description="desc",
                        salary_range="50000",
                        remote=False,
                        posted_at=datetime.now(UTC),
                        source="mock_source",
                    ),
                    RawJobResult(
                        title="Job 2",
                        company="Co2",
                        location="Munich",
                        url="https://example.com/2",
                        description="desc",
                        salary_range="200000",
                        remote=True,
                        posted_at=datetime.now(UTC),
                        source="mock_source",
                    ),
                ]

        sp = SearchProfile(
            profile_id=1,
            name="No Filters",
            keywords=json.dumps([]),
            locations=json.dumps([]),
            remote_only=False,
            sources=json.dumps(["mock_source"]),
            filters=None,  # no filters
        )
        db_session.add(sp)
        db_session.commit()
        db_session.refresh(sp)

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[MockAdapter()],
        ):
            result = await run_discovery(
                db_session,
                profile_id=1,
                search_profile_id=sp.id,
            )

        assert result["new_jobs"] == 2


# ---------------------------------------------------------------------------
# 4. Salary Filtering Uses Numeric Comparison (Search API)
# ---------------------------------------------------------------------------


@pytest.fixture()
def seed_salary_jobs(db_session):
    """Seed jobs with varied salary ranges for numeric testing."""
    now = datetime.now(UTC)
    jobs = [
        DiscoveredJob(
            profile_id=1,
            title="Low Pay",
            company="Co A",
            location="Berlin",
            salary_range="50000-60000 EUR",
            remote=False,
            title_normalized="low pay",
            company_normalized="co a",
            location_normalized="berlin",
            sources=json.dumps(["indeed"]),
            source_urls=json.dumps([]),
            fit_score=5.0,
            created_at=now - timedelta(days=5),
        ),
        DiscoveredJob(
            profile_id=1,
            title="Mid Pay",
            company="Co B",
            location="Frankfurt",
            salary_range="120000-140000 EUR",
            remote=True,
            title_normalized="mid pay",
            company_normalized="co b",
            location_normalized="frankfurt",
            sources=json.dumps(["linkedin"]),
            source_urls=json.dumps([]),
            fit_score=7.0,
            created_at=now - timedelta(days=3),
        ),
        DiscoveredJob(
            profile_id=1,
            title="High Pay",
            company="Co C",
            location="Remote",
            salary_range="180000-220000 USD",
            remote=True,
            title_normalized="high pay",
            company_normalized="co c",
            location_normalized="remote",
            sources=json.dumps(["arbeitnow"]),
            source_urls=json.dumps([]),
            fit_score=9.0,
            created_at=now - timedelta(days=1),
        ),
        DiscoveredJob(
            profile_id=1,
            title="No Salary",
            company="Co D",
            location="Munich",
            salary_range=None,
            remote=False,
            title_normalized="no salary",
            company_normalized="co d",
            location_normalized="munich",
            sources=json.dumps(["indeed"]),
            source_urls=json.dumps([]),
            fit_score=6.0,
            created_at=now - timedelta(days=2),
        ),
        DiscoveredJob(
            profile_id=1,
            title="Text Salary",
            company="Co E",
            location="Hamburg",
            salary_range="Competitive",
            remote=False,
            title_normalized="text salary",
            company_normalized="co e",
            location_normalized="hamburg",
            sources=json.dumps(["indeed"]),
            source_urls=json.dumps([]),
            fit_score=4.0,
            created_at=now - timedelta(days=4),
        ),
    ]
    db_session.add_all(jobs)
    db_session.commit()
    return jobs


class TestSalaryFilterNumeric:
    """Salary filtering uses numeric comparison, not string matching."""

    def test_salary_min_filter(self, client, seed_salary_jobs):
        """salary_min=100000 excludes 50k-60k job but includes 120k-140k and 180k-220k."""
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "salary_min": 100000},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Only jobs with parseable salary >= 100k midpoint
        # Mid Pay: midpoint 130k ✓, High Pay: midpoint 200k ✓
        # Low Pay: midpoint 55k ✗, No Salary: None ✗, Text Salary: None ✗
        assert data["total"] == 2
        companies = {j["company"] for j in data["jobs"]}
        assert companies == {"Co B", "Co C"}

    def test_salary_max_filter(self, client, seed_salary_jobs):
        """salary_max=150000 includes 50k-60k and 120k-140k but excludes 180k-220k."""
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "salary_max": 150000},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Low Pay: midpoint 55k ✓, Mid Pay: midpoint 130k ✓
        # High Pay: midpoint 200k ✗
        assert data["total"] == 2
        companies = {j["company"] for j in data["jobs"]}
        assert companies == {"Co A", "Co B"}

    def test_salary_min_and_max_combined(self, client, seed_salary_jobs):
        """Combined salary_min and salary_max produces a range."""
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "salary_min": 100000, "salary_max": 150000},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Only Mid Pay: midpoint 130k
        assert data["total"] == 1
        assert data["jobs"][0]["company"] == "Co B"

    def test_salary_filter_excludes_unparseable(self, client, seed_salary_jobs):
        """Jobs with unparseable salary (None, 'Competitive') are excluded by salary filters."""
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "salary_min": 0},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Only jobs with parseable numeric salaries pass
        # Low Pay (55k), Mid Pay (130k), High Pay (200k) — all >= 0
        # No Salary and Text Salary excluded (no parseable salary)
        assert data["total"] == 3


# ---------------------------------------------------------------------------
# 5. Salary Sort Produces Correct Numeric Ordering
# ---------------------------------------------------------------------------


class TestSalarySortNumeric:
    """Salary sort uses numeric midpoint, not lexicographic string comparison."""

    def test_salary_sort_desc(self, client, seed_salary_jobs):
        """Sort by salary desc: highest numeric salary first."""
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "sort": "salary", "order": "desc"},
        )
        assert resp.status_code == 200
        data = resp.json()
        jobs = data["jobs"]

        # Jobs with salary should be sorted by numeric midpoint descending
        # High Pay (200k) > Mid Pay (130k) > Low Pay (55k) > No Salary, Text Salary
        salary_jobs = [j for j in jobs if j["salary_range"] and j["salary_range"] != "Competitive"]
        assert len(salary_jobs) >= 3
        # First 3 should be in order: High Pay, Mid Pay, Low Pay
        assert salary_jobs[0]["company"] == "Co C"  # 200k
        assert salary_jobs[1]["company"] == "Co B"  # 130k
        assert salary_jobs[2]["company"] == "Co A"  # 55k

    def test_salary_sort_asc(self, client, seed_salary_jobs):
        """Sort by salary asc: lowest numeric salary first."""
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "sort": "salary", "order": "asc"},
        )
        assert resp.status_code == 200
        data = resp.json()
        jobs = data["jobs"]

        # Jobs with salary should be sorted by numeric midpoint ascending
        salary_jobs = [j for j in jobs if j["salary_range"] and j["salary_range"] != "Competitive"]
        assert len(salary_jobs) >= 3
        assert salary_jobs[0]["company"] == "Co A"  # 55k
        assert salary_jobs[1]["company"] == "Co B"  # 130k
        assert salary_jobs[2]["company"] == "Co C"  # 200k

    def test_salary_sort_nulls_last(self, client, seed_salary_jobs):
        """Jobs without parseable salary appear after those with salary."""
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "sort": "salary", "order": "desc"},
        )
        data = resp.json()
        jobs = data["jobs"]

        # Last entries should have None or unparseable salary
        # The last two jobs should be the ones without parseable salary
        last_two = jobs[-2:]
        for j in last_two:
            mid = salary_midpoint(j["salary_range"])
            assert mid is None


# ---------------------------------------------------------------------------
# _passes_sp_filters unit tests
# ---------------------------------------------------------------------------


class TestPassesSpFilters:
    """Unit tests for the _passes_sp_filters helper."""

    @staticmethod
    def _make_merged(**overrides) -> dict:
        """Build a merged job dict with defaults for filter tests."""
        base = {
            "salary_range": None,
            "remote": False,
            "company": "Co",
            "location": "Berlin",
            "sources": [],
        }
        base.update(overrides)
        return base

    def test_empty_filters_passes(self):
        merged = self._make_merged(
            salary_range="50000", sources=["indeed"]
        )
        assert _passes_sp_filters(merged, {}) is True

    def test_salary_min_passes(self):
        merged = self._make_merged(
            salary_range="130000-160000 EUR"
        )
        assert _passes_sp_filters(
            merged, {"salary_min": 100000}
        ) is True

    def test_salary_min_fails(self):
        merged = self._make_merged(salary_range="50000 EUR")
        assert _passes_sp_filters(
            merged, {"salary_min": 100000}
        ) is False

    def test_salary_max_passes(self):
        merged = self._make_merged(salary_range="50000 EUR")
        assert _passes_sp_filters(
            merged, {"salary_max": 100000}
        ) is True

    def test_salary_max_fails(self):
        merged = self._make_merged(salary_range="200000 EUR")
        assert _passes_sp_filters(
            merged, {"salary_max": 100000}
        ) is False

    def test_no_salary_fails_min_filter(self):
        merged = self._make_merged()
        assert _passes_sp_filters(
            merged, {"salary_min": 100000}
        ) is False

    def test_remote_filter_true(self):
        merged = self._make_merged(
            remote=True, location="Remote"
        )
        assert _passes_sp_filters(
            merged, {"remote": True}
        ) is True

    def test_remote_filter_false(self):
        merged = self._make_merged(remote=False)
        assert _passes_sp_filters(
            merged, {"remote": True}
        ) is False

    def test_company_filter(self):
        merged = self._make_merged(company="Stripe Inc")
        assert _passes_sp_filters(
            merged, {"company": "stripe"}
        ) is True
        assert _passes_sp_filters(
            merged, {"company": "Google"}
        ) is False

    def test_location_filter(self):
        merged = self._make_merged(
            location="Frankfurt, Germany"
        )
        assert _passes_sp_filters(
            merged, {"location": "Frankfurt"}
        ) is True
        assert _passes_sp_filters(
            merged, {"location": "Berlin"}
        ) is False
