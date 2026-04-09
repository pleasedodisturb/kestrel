"""Tests for the Discovery Service (Milestone 3).

Covers:
- VAL-DISC-001: Unified discovery returns results from ≥2 distinct sources
- VAL-DISC-002: Deduplication across sources
- VAL-DISC-003: Deduplication preserves richest data
- VAL-DISC-004: Saved search profile CRUD
- VAL-DISC-005: Saved search executes correctly
- VAL-DISC-006: Scheduled weekly discovery
- VAL-DISC-007: Scheduled discovery surfaces only new jobs
- VAL-DISC-008: Discovery auto-feeds pipeline as "discovered"
- VAL-DISC-009: Individual scraper failure doesn't block others
- VAL-DISC-010: Rate limit handling with backoff
- Profile scoping: two-profile negative tests
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base, get_db
from career_os.discovery.adapters import (
    RawJobResult,
    ScrapeParams,
    ScraperAdapter,
    _request_with_backoff,
)
from career_os.main import app
from career_os.models.discovery import DiscoveryRun, SearchProfile
from career_os.models.models import Application, Profile
from career_os.services.discovery import (
    ProfileNotFoundError,
    _dedup_key,
    _merge_raw_jobs,
    _normalize,
    run_discovery,
)

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    connection = engine.connect()
    test_session_cls = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = test_session_cls()

    # Seed two profiles for scoping tests
    profile_a = Profile(id=1, name="Profile A", email="a@test.com", location="Frankfurt")
    profile_b = Profile(id=2, name="Profile B", email="b@test.com", location="Berlin")
    session.add_all([profile_a, profile_b])
    session.commit()

    def override_get_db():
        yield session

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


# ---------------------------------------------------------------------------
# Mock adapter helpers
# ---------------------------------------------------------------------------


class MockAdapter(ScraperAdapter):
    """A configurable mock scraper adapter for testing."""

    def __init__(
        self,
        name: str,
        jobs: list[RawJobResult] | None = None,
        raise_error: Exception | None = None,
    ):
        self._name = name
        self._jobs = jobs or []
        self._raise_error = raise_error

    @property
    def source_name(self) -> str:
        return self._name

    async def scrape(self, params: ScrapeParams) -> list[RawJobResult]:
        if self._raise_error:
            raise self._raise_error
        return self._jobs


def _make_job(
    source: str,
    title: str = "Engineer",
    company: str = "Acme",
    location: str = "Frankfurt",
    url: str = "",
    description: str = "",
    salary_range: str = "",
    remote: bool = False,
    posted_at: datetime | None = None,
) -> RawJobResult:
    return RawJobResult(
        source=source,
        title=title,
        company=company,
        location=location,
        url=url,
        description=description,
        salary_range=salary_range,
        remote=remote,
        posted_at=posted_at,
    )


# ---------------------------------------------------------------------------
# Unit tests: Deduplication logic
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_normalize_strips_and_lowercases(self):
        assert _normalize("  Hello WORLD  ") == "hello world"

    def test_normalize_empty(self):
        assert _normalize("") == ""


class TestDedupKey:
    def test_same_job_different_case(self):
        j1 = _make_job("a", title="Senior Engineer", company="Acme", location="Berlin")
        j2 = _make_job("b", title="senior engineer", company="ACME", location="berlin")
        assert _dedup_key(j1) == _dedup_key(j2)

    def test_different_title_different_key(self):
        j1 = _make_job("a", title="Senior Engineer", company="Acme")
        j2 = _make_job("a", title="Junior Engineer", company="Acme")
        assert _dedup_key(j1) != _dedup_key(j2)


class TestMergeRawJobs:
    def test_merge_keeps_longest_description(self):
        j1 = _make_job("a", description="Short")
        j2 = _make_job("b", description="This is a much longer description with more details")
        merged = _merge_raw_jobs([j1, j2])
        assert merged["description"] == j2.description

    def test_merge_keeps_earliest_posted_date(self):
        earlier = datetime(2026, 1, 1)
        later = datetime(2026, 2, 1)
        j1 = _make_job("a", posted_at=later)
        j2 = _make_job("b", posted_at=earlier)
        merged = _merge_raw_jobs([j1, j2])
        assert merged["posted_at"] == earlier

    def test_merge_collects_all_sources(self):
        j1 = _make_job("arbeitsagentur")
        j2 = _make_job("arbeitnow")
        merged = _merge_raw_jobs([j1, j2])
        assert "arbeitsagentur" in merged["sources"]
        assert "arbeitnow" in merged["sources"]

    def test_merge_collects_all_urls(self):
        j1 = _make_job("a", url="https://a.com/job1")
        j2 = _make_job("b", url="https://b.com/job1")
        merged = _merge_raw_jobs([j1, j2])
        assert "https://a.com/job1" in merged["source_urls"]
        assert "https://b.com/job1" in merged["source_urls"]

    def test_merge_keeps_richest_salary(self):
        j1 = _make_job("a", salary_range="60k")
        j2 = _make_job("b", salary_range="60,000-80,000 EUR/year")
        merged = _merge_raw_jobs([j1, j2])
        assert merged["salary_range"] == "60,000-80,000 EUR/year"

    def test_merge_remote_flag_additive(self):
        j1 = _make_job("a", remote=False)
        j2 = _make_job("b", remote=True)
        merged = _merge_raw_jobs([j1, j2])
        assert merged["remote"] is True


# ---------------------------------------------------------------------------
# Integration tests: Discovery service
# ---------------------------------------------------------------------------


class TestDiscoveryService:
    """Tests for run_discovery with mocked adapters."""

    @pytest.mark.asyncio
    async def test_discovery_returns_results_from_multiple_sources(self, db_session):
        """VAL-DISC-001: Discovery returns jobs from ≥2 distinct sources."""
        adapter_a = MockAdapter(
            "arbeitsagentur",
            [_make_job("arbeitsagentur", title="TPM", company="CompA", location="Berlin")],
        )
        adapter_b = MockAdapter(
            "arbeitnow",
            [_make_job("arbeitnow", title="PM", company="CompB", location="Munich")],
        )

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter_a, adapter_b],
        ):
            result = await run_discovery(
                db_session,
                1,
                keywords=["engineer"],
                sources=["arbeitsagentur", "arbeitnow"],
            )

        assert result["new_jobs"] == 2
        sources_in_jobs = set()
        for job in result["jobs"]:
            for s in json.loads(job.sources):
                sources_in_jobs.add(s)
        assert len(sources_in_jobs) >= 2

    @pytest.mark.asyncio
    async def test_deduplication_merges_same_job(self, db_session):
        """VAL-DISC-002: Same job from 2 sources → 1 record with both sources."""
        job_a = _make_job(
            "arbeitsagentur",
            title="Senior TPM",
            company="Acme Corp",
            location="Frankfurt",
            url="https://aa.de/job1",
            description="Short desc",
        )
        job_b = _make_job(
            "arbeitnow",
            title="Senior TPM",
            company="Acme Corp",
            location="Frankfurt",
            url="https://arbeitnow.com/job1",
            description="A much longer and more detailed job description for this role",
        )

        adapter_a = MockAdapter("arbeitsagentur", [job_a])
        adapter_b = MockAdapter("arbeitnow", [job_b])

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter_a, adapter_b],
        ):
            result = await run_discovery(db_session, 1, keywords=["tpm"])

        # Should be 1 new job (deduplicated)
        assert result["new_jobs"] == 1
        assert len(result["jobs"]) == 1

        # The record should have both sources
        job = result["jobs"][0]
        sources = json.loads(job.sources)
        assert "arbeitsagentur" in sources
        assert "arbeitnow" in sources

    @pytest.mark.asyncio
    async def test_dedup_preserves_richest_data(self, db_session):
        """VAL-DISC-003: Merged record keeps longest description, all URLs, earliest posted."""
        earlier = datetime(2026, 1, 1)
        later = datetime(2026, 2, 1)

        job_a = _make_job(
            "arbeitsagentur",
            title="Engineer",
            company="TestCo",
            location="Berlin",
            url="https://aa.de/job",
            description="Short",
            posted_at=later,
        )
        job_b = _make_job(
            "arbeitnow",
            title="Engineer",
            company="TestCo",
            location="Berlin",
            url="https://arbeitnow.com/job",
            description="A much longer and detailed description of the engineering role",
            posted_at=earlier,
        )

        adapter_a = MockAdapter("arbeitsagentur", [job_a])
        adapter_b = MockAdapter("arbeitnow", [job_b])

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter_a, adapter_b],
        ):
            result = await run_discovery(db_session, 1, keywords=["eng"])

        job = result["jobs"][0]
        assert job.description == job_b.description  # Longest
        source_urls = json.loads(job.source_urls)
        assert "https://aa.de/job" in source_urls
        assert "https://arbeitnow.com/job" in source_urls
        assert job.posted_at == earlier  # Earliest

    @pytest.mark.asyncio
    async def test_discovery_auto_feeds_pipeline(self, db_session):
        """VAL-DISC-008: Discovered jobs auto-added to pipeline as 'discovered'."""
        adapter = MockAdapter(
            "arbeitnow",
            [_make_job("arbeitnow", title="Data Eng", company="DataCo", location="Remote")],
        )

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter],
        ):
            result = await run_discovery(db_session, 1, keywords=["data"])

        assert result["new_jobs"] == 1

        # Verify pipeline entry created
        apps = (
            db_session.query(Application)
            .filter(
                Application.profile_id == 1,
                Application.source == "discovery",
            )
            .all()
        )
        assert len(apps) == 1
        assert apps[0].status == "discovered"
        assert apps[0].company == "DataCo"
        assert apps[0].role == "Data Eng"

        # Verify discovered job has application_id
        dj = result["jobs"][0]
        assert dj.application_id == apps[0].id

    @pytest.mark.asyncio
    async def test_scraper_failure_doesnt_block_others(self, db_session):
        """VAL-DISC-009: One source failing still returns results from others."""
        adapter_ok = MockAdapter(
            "arbeitnow",
            [_make_job("arbeitnow", title="ML Eng", company="AICO", location="Berlin")],
        )
        adapter_fail = MockAdapter(
            "arbeitsagentur",
            raise_error=RuntimeError("API timeout"),
        )

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter_fail, adapter_ok],
        ):
            result = await run_discovery(db_session, 1, keywords=["ml"])

        # Should still have results from the working adapter
        assert result["new_jobs"] == 1
        assert len(result["warnings"]) >= 1
        scraper_warnings = [w for w in result["warnings"] if w["source"] == "arbeitsagentur"]
        assert len(scraper_warnings) == 1
        assert "API timeout" in scraper_warnings[0]["error"]

    @pytest.mark.asyncio
    async def test_profile_not_found_raises(self, db_session):
        """Non-existent profile raises ProfileNotFoundError."""
        with pytest.raises(ProfileNotFoundError):
            await run_discovery(db_session, 999, keywords=["test"])

    @pytest.mark.asyncio
    async def test_subsequent_discovery_deduplicates_existing(self, db_session):
        """VAL-DISC-007: Second run doesn't re-surface already discovered jobs."""
        job = _make_job("arbeitnow", title="SWE", company="TechCo", location="Frankfurt")
        adapter = MockAdapter("arbeitnow", [job])

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter],
        ):
            result1 = await run_discovery(db_session, 1, keywords=["swe"])
            assert result1["new_jobs"] == 1

            # Second run with same job
            result2 = await run_discovery(db_session, 1, keywords=["swe"])
            assert result2["new_jobs"] == 0
            assert result2["duplicates"] == 1

    @pytest.mark.asyncio
    async def test_discovery_run_logged(self, db_session):
        """VAL-DISC-006: Discovery run is logged in discovery_runs table."""
        adapter = MockAdapter("arbeitnow", [])

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter],
        ):
            await run_discovery(db_session, 1, keywords=["test"], trigger="scheduled")

        runs = db_session.query(DiscoveryRun).filter(DiscoveryRun.profile_id == 1).all()
        assert len(runs) == 1
        assert runs[0].trigger == "scheduled"
        assert runs[0].status == "completed"
        assert runs[0].completed_at is not None


# ---------------------------------------------------------------------------
# API tests: POST /api/discover
# ---------------------------------------------------------------------------


class TestDiscoverAPI:
    """Tests for POST /api/discover endpoint."""

    def test_discover_returns_results(self, client, db_session):
        """POST /api/discover returns results from mocked adapters."""
        adapter = MockAdapter(
            "arbeitnow",
            [_make_job("arbeitnow", title="SRE", company="CloudCo", location="Berlin")],
        )

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter],
        ):
            resp = client.post(
                "/api/discover",
                json={
                    "profile_id": 1,
                    "keywords": ["sre"],
                    "sources": ["arbeitnow"],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["new_jobs"] == 1
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["title"] == "SRE"
        assert data["jobs"][0]["company"] == "CloudCo"

    def test_discover_with_warnings(self, client, db_session):
        """POST /api/discover includes warnings for failed sources."""
        adapter_ok = MockAdapter(
            "arbeitnow",
            [_make_job("arbeitnow", title="Eng", company="Co", location="Berlin")],
        )
        adapter_fail = MockAdapter("arbeitsagentur", raise_error=RuntimeError("Network error"))

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter_fail, adapter_ok],
        ):
            resp = client.post(
                "/api/discover",
                json={"profile_id": 1, "keywords": ["eng"]},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["warnings"]) >= 1
        scraper_warnings = [w for w in data["warnings"] if w["source"] == "arbeitsagentur"]
        assert len(scraper_warnings) == 1
        assert data["new_jobs"] == 1

    def test_discover_nonexistent_profile(self, client):
        """POST /api/discover with invalid profile returns 404."""
        resp = client.post(
            "/api/discover",
            json={"profile_id": 999, "keywords": ["test"]},
        )
        assert resp.status_code == 404

    def test_discover_with_search_profile(self, client, db_session):
        """VAL-DISC-005: Discovery uses saved search profile parameters."""
        # Create a search profile first
        sp_resp = client.post(
            "/api/search-profiles",
            json={
                "profile_id": 1,
                "name": "My Search",
                "keywords": ["data engineer"],
                "locations": ["Berlin"],
                "remote_only": True,
            },
        )
        assert sp_resp.status_code == 201
        sp_id = sp_resp.json()["id"]

        adapter = MockAdapter(
            "arbeitnow",
            [
                _make_job(
                    "arbeitnow",
                    title="Data Eng",
                    company="DataCo",
                    location="Berlin",
                    remote=True,
                )
            ],
        )

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter],
        ):
            resp = client.post(
                "/api/discover",
                json={
                    "profile_id": 1,
                    "search_profile_id": sp_id,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["new_jobs"] == 1

    def test_discover_multiple_sources_in_response(self, client, db_session):
        """VAL-DISC-001: Each result has source field, ≥2 sources queried."""
        adapter_a = MockAdapter(
            "arbeitsagentur",
            [_make_job("arbeitsagentur", title="TPM", company="A", location="FF")],
        )
        adapter_b = MockAdapter(
            "arbeitnow",
            [_make_job("arbeitnow", title="PM", company="B", location="B")],
        )

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter_a, adapter_b],
        ):
            resp = client.post(
                "/api/discover",
                json={"profile_id": 1, "keywords": ["eng"]},
            )

        data = resp.json()
        assert len(data["sources_queried"]) >= 2
        # Each job has sources array
        for job in data["jobs"]:
            assert isinstance(job["sources"], list)
            assert len(job["sources"]) >= 1


# ---------------------------------------------------------------------------
# API tests: Search Profiles CRUD
# ---------------------------------------------------------------------------


class TestSearchProfileCRUD:
    """Tests for /api/search-profiles CRUD operations."""

    def test_create_search_profile(self, client):
        """VAL-DISC-004: Create search profile with name, keywords, locations, filters."""
        resp = client.post(
            "/api/search-profiles",
            json={
                "profile_id": 1,
                "name": "Frankfurt TPM",
                "keywords": ["TPM", "Program Manager"],
                "locations": ["Frankfurt", "Remote"],
                "remote_only": False,
                "sources": ["arbeitsagentur", "arbeitnow"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Frankfurt TPM"
        assert data["keywords"] == ["TPM", "Program Manager"]
        assert data["locations"] == ["Frankfurt", "Remote"]
        assert data["profile_id"] == 1

    def test_list_search_profiles(self, client):
        """VAL-DISC-004: List search profiles."""
        # Create two
        client.post(
            "/api/search-profiles",
            json={"profile_id": 1, "name": "Search A", "keywords": ["AI"]},
        )
        client.post(
            "/api/search-profiles",
            json={"profile_id": 1, "name": "Search B", "keywords": ["ML"]},
        )

        resp = client.get("/api/search-profiles?profile_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["profiles"]) == 2

    def test_get_search_profile(self, client):
        """VAL-DISC-004: Read single search profile."""
        create_resp = client.post(
            "/api/search-profiles",
            json={"profile_id": 1, "name": "Test", "keywords": ["test"]},
        )
        sp_id = create_resp.json()["id"]

        resp = client.get(f"/api/search-profiles/{sp_id}?profile_id=1")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test"

    def test_update_search_profile(self, client):
        """VAL-DISC-004: Update search profile."""
        create_resp = client.post(
            "/api/search-profiles",
            json={"profile_id": 1, "name": "Old Name", "keywords": ["old"]},
        )
        sp_id = create_resp.json()["id"]

        resp = client.put(
            f"/api/search-profiles/{sp_id}?profile_id=1",
            json={"name": "New Name", "keywords": ["new", "updated"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New Name"
        assert data["keywords"] == ["new", "updated"]

    def test_delete_search_profile(self, client):
        """VAL-DISC-004: Delete search profile."""
        create_resp = client.post(
            "/api/search-profiles",
            json={"profile_id": 1, "name": "To Delete", "keywords": []},
        )
        sp_id = create_resp.json()["id"]

        resp = client.delete(f"/api/search-profiles/{sp_id}?profile_id=1")
        assert resp.status_code == 204

        # Verify deleted
        resp = client.get(f"/api/search-profiles/{sp_id}?profile_id=1")
        assert resp.status_code == 404

    def test_create_nonexistent_profile(self, client):
        """Create search profile for nonexistent profile returns 404."""
        resp = client.post(
            "/api/search-profiles",
            json={"profile_id": 999, "name": "Test", "keywords": []},
        )
        assert resp.status_code == 404

    def test_get_nonexistent_profile(self, client):
        """Get nonexistent search profile returns 404."""
        resp = client.get("/api/search-profiles/999?profile_id=1")
        assert resp.status_code == 404

    def test_update_nonexistent(self, client):
        """Update nonexistent search profile returns 404."""
        resp = client.put(
            "/api/search-profiles/999?profile_id=1",
            json={"name": "New"},
        )
        assert resp.status_code == 404

    def test_delete_nonexistent(self, client):
        """Delete nonexistent search profile returns 404."""
        resp = client.delete("/api/search-profiles/999?profile_id=1")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API tests: Discovery Runs
# ---------------------------------------------------------------------------


class TestDiscoveryRuns:
    def test_list_discovery_runs(self, client, db_session):
        """List discovery runs after a sweep."""
        adapter = MockAdapter("arbeitnow", [])

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter],
        ):
            client.post(
                "/api/discover",
                json={"profile_id": 1, "keywords": ["test"]},
            )

        resp = client.get("/api/discovery-runs?profile_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["status"] == "completed"

    def test_get_latest_discovery_run_returns_most_recent_completed(self, client, db_session):
        """GET /api/discovery-runs/latest returns the most recent completed run, not a pending one."""
        from datetime import UTC, timedelta

        now = datetime.now(UTC)

        # Older completed run
        older_run = DiscoveryRun(
            profile_id=1,
            trigger="manual",
            status="completed",
            total_found=10,
            new_jobs=5,
            duplicates=5,
            started_at=now - timedelta(hours=2),
            completed_at=now - timedelta(hours=2),
        )
        # Most recent completed run
        newer_run = DiscoveryRun(
            profile_id=1,
            trigger="scheduled",
            status="completed",
            total_found=8,
            new_jobs=3,
            duplicates=5,
            started_at=now - timedelta(hours=1),
            completed_at=now - timedelta(hours=1),
        )
        # Pending run (should not be returned)
        pending_run = DiscoveryRun(
            profile_id=1,
            trigger="manual",
            status="running",
            total_found=0,
            new_jobs=0,
            duplicates=0,
            started_at=now,
            completed_at=None,
        )
        db_session.add_all([older_run, newer_run, pending_run])
        db_session.commit()
        newer_run_id = newer_run.id

        resp = client.get("/api/discovery-runs/latest?profile_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data is not None
        assert data["id"] == newer_run_id
        assert data["status"] == "completed"
        assert data["trigger"] == "scheduled"

    def test_get_latest_discovery_run_no_runs_returns_null(self, client, db_session):
        """GET /api/discovery-runs/latest returns null when no runs exist for the profile."""
        resp = client.get("/api/discovery-runs/latest?profile_id=1")
        assert resp.status_code == 200
        assert resp.json() is None

    def test_get_latest_discovery_run_only_pending_returns_null(self, client, db_session):
        """GET /api/discovery-runs/latest returns null when only pending runs exist."""
        from datetime import UTC

        pending_run = DiscoveryRun(
            profile_id=1,
            trigger="manual",
            status="running",
            total_found=0,
            new_jobs=0,
            duplicates=0,
            started_at=datetime.now(UTC),
            completed_at=None,
        )
        db_session.add(pending_run)
        db_session.commit()

        resp = client.get("/api/discovery-runs/latest?profile_id=1")
        assert resp.status_code == 200
        assert resp.json() is None


# ---------------------------------------------------------------------------
# Profile scoping tests
# ---------------------------------------------------------------------------


class TestProfileScoping:
    """Two-profile negative tests for discovery resources."""

    def test_profile_b_cannot_see_profile_a_search_profiles(self, client):
        """Profile B cannot list Profile A's search profiles."""
        client.post(
            "/api/search-profiles",
            json={"profile_id": 1, "name": "A's Search", "keywords": ["ai"]},
        )

        resp = client.get("/api/search-profiles?profile_id=2")
        data = resp.json()
        assert data["total"] == 0

    def test_profile_b_cannot_read_profile_a_search_profile(self, client):
        """Profile B cannot get Profile A's search profile by ID."""
        create_resp = client.post(
            "/api/search-profiles",
            json={"profile_id": 1, "name": "A's Search", "keywords": ["ai"]},
        )
        sp_id = create_resp.json()["id"]

        resp = client.get(f"/api/search-profiles/{sp_id}?profile_id=2")
        assert resp.status_code == 404

    def test_profile_b_cannot_update_profile_a_search_profile(self, client):
        """Profile B cannot update Profile A's search profile."""
        create_resp = client.post(
            "/api/search-profiles",
            json={"profile_id": 1, "name": "A's Search", "keywords": ["ai"]},
        )
        sp_id = create_resp.json()["id"]

        resp = client.put(
            f"/api/search-profiles/{sp_id}?profile_id=2",
            json={"name": "Hacked"},
        )
        assert resp.status_code == 404

    def test_profile_b_cannot_delete_profile_a_search_profile(self, client):
        """Profile B cannot delete Profile A's search profile."""
        create_resp = client.post(
            "/api/search-profiles",
            json={"profile_id": 1, "name": "A's Search", "keywords": ["ai"]},
        )
        sp_id = create_resp.json()["id"]

        resp = client.delete(f"/api/search-profiles/{sp_id}?profile_id=2")
        assert resp.status_code == 404

    def test_discovery_scoped_to_profile(self, client, db_session):
        """Discovery results for profile A not visible to profile B."""
        adapter = MockAdapter(
            "arbeitnow",
            [_make_job("arbeitnow", title="AI Eng", company="AIco", location="Remote")],
        )

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter],
        ):
            resp = client.post(
                "/api/discover",
                json={"profile_id": 1, "keywords": ["ai"]},
            )
        assert resp.json()["new_jobs"] == 1

        # Profile B's discovery runs should be empty
        resp = client.get("/api/discovery-runs?profile_id=2")
        assert len(resp.json()) == 0


# ---------------------------------------------------------------------------
# Rate limit / backoff tests
# ---------------------------------------------------------------------------


class TestRateLimitBackoff:
    """VAL-DISC-010: Rate limit handling with exponential backoff."""

    @pytest.mark.asyncio
    async def test_backoff_on_429(self):
        """HTTP 429 triggers retry with backoff, then succeeds."""
        import httpx

        call_count = 0

        async def mock_request(method, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                resp = httpx.Response(429, request=httpx.Request("GET", url))
                raise httpx.HTTPStatusError("rate limited", request=resp.request, response=resp)
            return httpx.Response(200, json={"data": []}, request=httpx.Request("GET", url))

        client = AsyncMock()
        client.request = mock_request

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            resp = await _request_with_backoff(
                client,
                "GET",
                "https://example.com/api",
                max_retries=3,
                initial_backoff=0.01,
            )

        assert resp.status_code == 200
        assert call_count == 3  # 2 retries + 1 success
        # Sleep called twice with exponential backoff
        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_backoff_exhausted_raises(self):
        """After max retries, raises the error."""
        import httpx

        async def mock_request(method, url, **kwargs):
            resp = httpx.Response(429, request=httpx.Request("GET", url))
            raise httpx.HTTPStatusError("rate limited", request=resp.request, response=resp)

        client = AsyncMock()
        client.request = mock_request

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await _request_with_backoff(
                client,
                "GET",
                "https://example.com/api",
                max_retries=2,
                initial_backoff=0.01,
            )


# ---------------------------------------------------------------------------
# Scheduled discovery tests
# ---------------------------------------------------------------------------


class TestScheduledDiscovery:
    """VAL-DISC-006: Scheduled discovery runs on configured cadence."""

    @pytest.mark.asyncio
    async def test_scheduled_discovery_with_active_profiles(self, db_session):
        """Scheduled discovery runs for active search profiles with cadence."""
        from datetime import UTC, timedelta

        from career_os.services.discovery import run_scheduled_discovery

        # Create an active search profile with explicit cadence
        sp = SearchProfile(
            profile_id=1,
            name="Weekly AI Search",
            keywords=json.dumps(["AI Engineer"]),
            locations=json.dumps(["Berlin"]),
            remote_only=False,
            is_active=True,
            cadence="weekly",
            next_run=datetime.now(UTC) - timedelta(hours=1),
        )
        db_session.add(sp)
        db_session.commit()

        adapter = MockAdapter(
            "arbeitnow",
            [_make_job("arbeitnow", title="AI Eng", company="AIco", location="Berlin")],
        )

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter],
        ):
            result = await run_scheduled_discovery(db_session, 1)

        assert result is not None
        assert result["new_jobs"] == 1

        # Verify discovery run logged with trigger="scheduled"
        runs = db_session.query(DiscoveryRun).filter(DiscoveryRun.trigger == "scheduled").all()
        assert len(runs) == 1

    @pytest.mark.asyncio
    async def test_scheduled_discovery_no_active_profiles(self, db_session):
        """Scheduled discovery returns None when no active profiles."""
        from career_os.services.discovery import run_scheduled_discovery

        result = await run_scheduled_discovery(db_session, 1)
        assert result is None


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_discover_empty_results(self, client, db_session):
        """Discovery with no results returns empty list."""
        adapter = MockAdapter("arbeitnow", [])

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter],
        ):
            resp = client.post(
                "/api/discover",
                json={"profile_id": 1, "keywords": ["nonexistent"]},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["new_jobs"] == 0
        assert data["jobs"] == []

    def test_discover_all_sources_fail(self, client, db_session):
        """When all sources fail, returns empty results with warnings."""
        adapter = MockAdapter("arbeitsagentur", raise_error=RuntimeError("API down"))

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter],
        ):
            resp = client.post(
                "/api/discover",
                json={"profile_id": 1, "keywords": ["test"]},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["new_jobs"] == 0
        assert len(data["warnings"]) >= 1

    def test_search_profile_with_filters(self, client):
        """Search profile can include custom filters."""
        resp = client.post(
            "/api/search-profiles",
            json={
                "profile_id": 1,
                "name": "Custom",
                "keywords": ["AI"],
                "filters": {"min_salary": 80000, "exclude_agencies": True},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["filters"]["min_salary"] == 80000
        assert data["filters"]["exclude_agencies"] is True

    def test_search_profile_toggle_active(self, client):
        """Search profile can be deactivated and reactivated."""
        create_resp = client.post(
            "/api/search-profiles",
            json={"profile_id": 1, "name": "Toggle", "keywords": []},
        )
        sp_id = create_resp.json()["id"]

        # Deactivate
        resp = client.put(
            f"/api/search-profiles/{sp_id}?profile_id=1",
            json={"is_active": False},
        )
        assert resp.json()["is_active"] is False

        # Filter active only
        resp = client.get("/api/search-profiles?profile_id=1&active_only=true")
        assert resp.json()["total"] == 0

        # Reactivate
        resp = client.put(
            f"/api/search-profiles/{sp_id}?profile_id=1",
            json={"is_active": True},
        )
        assert resp.json()["is_active"] is True


# ---------------------------------------------------------------------------
# Bug fix tests: m3-fix-ut-crud-schedule-search
# ---------------------------------------------------------------------------


class TestDeleteSearchProfileWithDiscoveryRuns:
    """VAL-DISC-004 regression: DELETE /api/search-profiles/{id} must return 204
    even when discovery_runs reference the profile (FK SET NULL)."""

    def test_delete_profile_with_linked_discovery_run(self, client, db_session):
        """Delete search profile that has associated discovery runs.

        Previously returned 500 due to FK constraint; now FK has
        ondelete='SET NULL' so the run's search_profile_id is set to NULL.
        """
        # Create search profile
        create_resp = client.post(
            "/api/search-profiles",
            json={"profile_id": 1, "name": "With Runs", "keywords": ["AI"]},
        )
        assert create_resp.status_code == 201
        sp_id = create_resp.json()["id"]

        # Create a discovery run referencing this search profile
        run = DiscoveryRun(
            profile_id=1,
            search_profile_id=sp_id,
            trigger="manual",
            status="completed",
            total_found=5,
            new_jobs=3,
            duplicates=2,
        )
        db_session.add(run)
        db_session.commit()
        run_id = run.id

        # Delete the search profile — should succeed (204), not 500
        resp = client.delete(f"/api/search-profiles/{sp_id}?profile_id=1")
        assert resp.status_code == 204

        # Verify GET returns 404
        resp = client.get(f"/api/search-profiles/{sp_id}?profile_id=1")
        assert resp.status_code == 404

        # Verify discovery run still exists but search_profile_id is NULL
        db_session.expire_all()
        updated_run = db_session.query(DiscoveryRun).filter(DiscoveryRun.id == run_id).first()
        assert updated_run is not None
        assert updated_run.search_profile_id is None


class TestScheduledDiscoverySkipsNullCadence:
    """VAL-DISC-006 regression: Scheduled discovery must skip profiles
    with cadence=None."""

    @pytest.mark.asyncio
    async def test_skips_profiles_without_cadence(self, db_session):
        """Profiles with cadence=None should be skipped entirely."""
        from career_os.services.discovery import run_scheduled_discovery

        # Create an active profile with NO cadence (cadence=None)
        sp = SearchProfile(
            profile_id=1,
            name="No Cadence",
            keywords=json.dumps(["AI"]),
            locations=json.dumps(["Berlin"]),
            remote_only=False,
            is_active=True,
            cadence=None,
            next_run=None,
        )
        db_session.add(sp)
        db_session.commit()

        adapter = MockAdapter(
            "arbeitnow",
            [_make_job("arbeitnow", title="AI Eng", company="AIco", location="Berlin")],
        )

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter],
        ):
            result = await run_scheduled_discovery(db_session, 1)

        # Should return None — profile was skipped
        assert result is None

        # Verify no discovery runs were created
        runs = db_session.query(DiscoveryRun).filter(DiscoveryRun.trigger == "scheduled").all()
        assert len(runs) == 0

    @pytest.mark.asyncio
    async def test_runs_profiles_with_explicit_cadence(self, db_session):
        """Profiles with cadence='weekly' and next_run <= now should run."""
        from datetime import UTC, timedelta

        from career_os.services.discovery import run_scheduled_discovery

        # Create an active profile WITH cadence
        sp = SearchProfile(
            profile_id=1,
            name="Weekly Search",
            keywords=json.dumps(["engineer"]),
            locations=json.dumps(["Frankfurt"]),
            remote_only=False,
            is_active=True,
            cadence="weekly",
            next_run=datetime.now(UTC) - timedelta(hours=1),  # past due
        )
        db_session.add(sp)
        db_session.commit()

        adapter = MockAdapter(
            "arbeitnow",
            [_make_job("arbeitnow", title="Eng", company="Co", location="Frankfurt")],
        )

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter],
        ):
            result = await run_scheduled_discovery(db_session, 1)

        assert result is not None
        assert result["new_jobs"] == 1

    @pytest.mark.asyncio
    async def test_mixed_cadence_only_runs_configured(self, db_session):
        """Only profiles with cadence set should be scheduled; others skipped."""
        from datetime import UTC, timedelta

        from career_os.services.discovery import run_scheduled_discovery

        # Profile with cadence=None (should skip)
        sp_no_cadence = SearchProfile(
            profile_id=1,
            name="No Cadence",
            keywords=json.dumps(["AI"]),
            is_active=True,
            cadence=None,
        )
        # Profile with cadence="weekly" (should run)
        sp_weekly = SearchProfile(
            profile_id=1,
            name="Weekly",
            keywords=json.dumps(["TPM"]),
            is_active=True,
            cadence="weekly",
            next_run=datetime.now(UTC) - timedelta(hours=1),
        )
        db_session.add_all([sp_no_cadence, sp_weekly])
        db_session.commit()

        adapter = MockAdapter(
            "arbeitnow",
            [_make_job("arbeitnow", title="TPM", company="Corp", location="Berlin")],
        )

        with patch(
            "career_os.services.discovery.get_available_adapters",
            return_value=[adapter],
        ):
            result = await run_scheduled_discovery(db_session, 1)

        # Only the weekly profile should have run
        assert result is not None
        assert result["new_jobs"] == 1

        runs = db_session.query(DiscoveryRun).filter(DiscoveryRun.trigger == "scheduled").all()
        assert len(runs) == 1
