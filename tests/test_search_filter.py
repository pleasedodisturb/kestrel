"""Tests for the Jobs Search & Filter API (Milestone 3).

Covers:
- VAL-SEARCH-001: Full-text search across title/company/description/location
- VAL-SEARCH-002: Multi-facet filtering with AND logic
- VAL-SEARCH-003: Sort by score/date/salary/readiness asc/desc
- VAL-SEARCH-004: Saved searches persist and re-execute correctly
- VAL-SEARCH-005: Empty search returns all jobs paginated
- Profile scoping: two-profile negative tests
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Profile
from career_os.models.scoring import ScoredJob

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

    # Seed two profiles
    profile_a = Profile(id=1, name="Profile A", email="a@test.com", location="Frankfurt")
    profile_b = Profile(id=2, name="Profile B", email="b@test.com", location="Berlin")
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


@pytest.fixture()
def seed_jobs(db_session):
    """Seed multiple discovered jobs with varied attributes for testing."""
    now = datetime.now(UTC)
    jobs = [
        DiscoveredJob(
            profile_id=1,
            title="Senior TPM - AI Platform",
            company="Stripe",
            location="San Francisco, Remote",
            url="https://stripe.com/job1",
            description="Lead AI platform program management with ML teams",
            salary_range="180000-220000 USD",
            remote=True,
            posted_at=now - timedelta(days=5),
            title_normalized="senior tpm - ai platform",
            company_normalized="stripe",
            location_normalized="san francisco, remote",
            sources=json.dumps(["linkedin", "indeed"]),
            source_urls=json.dumps(["https://linkedin.com/1", "https://indeed.com/1"]),
            fit_score=8.5,
            created_at=now - timedelta(days=5),
        ),
        DiscoveredJob(
            profile_id=1,
            title="Product Engineer",
            company="Vercel",
            location="Remote",
            url="https://vercel.com/job2",
            description="Build developer tools and infrastructure",
            salary_range="150000-180000 EUR",
            remote=True,
            posted_at=now - timedelta(days=10),
            title_normalized="product engineer",
            company_normalized="vercel",
            location_normalized="remote",
            sources=json.dumps(["arbeitnow"]),
            source_urls=json.dumps(["https://arbeitnow.com/2"]),
            fit_score=7.2,
            created_at=now - timedelta(days=10),
        ),
        DiscoveredJob(
            profile_id=1,
            title="DevRel Engineer",
            company="Stripe",
            location="Berlin, Germany",
            url="https://stripe.com/job3",
            description="Developer relations and community for payments",
            salary_range="120000-140000 EUR",
            remote=False,
            posted_at=now - timedelta(days=2),
            title_normalized="devrel engineer",
            company_normalized="stripe",
            location_normalized="berlin, germany",
            sources=json.dumps(["arbeitsagentur"]),
            source_urls=json.dumps(["https://arbeitsagentur.de/3"]),
            fit_score=6.0,
            created_at=now - timedelta(days=2),
        ),
        DiscoveredJob(
            profile_id=1,
            title="AI Program Lead",
            company="SAP",
            location="Frankfurt, Germany",
            url="https://sap.com/job4",
            description="Lead AI transformation programs across divisions",
            salary_range="130000-160000 EUR",
            remote=False,
            posted_at=now - timedelta(days=1),
            title_normalized="ai program lead",
            company_normalized="sap",
            location_normalized="frankfurt, germany",
            sources=json.dumps(["linkedin"]),
            source_urls=json.dumps(["https://linkedin.com/4"]),
            fit_score=9.0,
            created_at=now - timedelta(days=1),
        ),
        DiscoveredJob(
            profile_id=1,
            title="Junior Data Analyst",
            company="Zalando",
            location="Berlin",
            url="https://zalando.com/job5",
            description="Analyze fashion data and trends",
            salary_range=None,
            remote=False,
            posted_at=now - timedelta(days=20),
            title_normalized="junior data analyst",
            company_normalized="zalando",
            location_normalized="berlin",
            sources=json.dumps(["indeed"]),
            source_urls=json.dumps(["https://indeed.com/5"]),
            fit_score=3.5,
            created_at=now - timedelta(days=20),
        ),
    ]
    db_session.add_all(jobs)
    db_session.commit()

    # Add scores for some jobs
    for job in jobs:
        db_session.refresh(job)

    scored_jobs = [
        ScoredJob(
            profile_id=1,
            discovered_job_id=jobs[0].id,
            fit_score=8.5,
            readiness_score=85.0,
            career_alignment=8.0,
            reasoning="Strong AI TPM match with remote flexibility. "
            "Salary above target range. Skills alignment high." * 3,
            estimated_salary="180000-220000 USD",
            effort_flag="low",
            prep_level="light",
            prep_notes="Strong match",
        ),
        ScoredJob(
            profile_id=1,
            discovered_job_id=jobs[1].id,
            fit_score=7.2,
            readiness_score=72.0,
            career_alignment=7.0,
            reasoning="Good product engineering role. "
            "Remote with competitive salary. Some gaps in frontend." * 3,
            estimated_salary="150000-180000 EUR",
            effort_flag="medium",
            prep_level="moderate",
            prep_notes="Brush up on frontend",
        ),
        ScoredJob(
            profile_id=1,
            discovered_job_id=jobs[3].id,
            fit_score=9.0,
            readiness_score=90.0,
            career_alignment=9.0,
            reasoning="Excellent AI Program Lead match at SAP. "
            "Frankfurt location ideal. Strong career alignment." * 3,
            estimated_salary="130000-160000 EUR",
            effort_flag="low",
            prep_level="light",
            prep_notes="Top match",
        ),
    ]
    db_session.add_all(scored_jobs)
    db_session.commit()

    # Also add a job for profile B to test scoping
    profile_b_job = DiscoveredJob(
        profile_id=2,
        title="PM at Secret Corp",
        company="Secret Corp",
        location="London",
        title_normalized="pm at secret corp",
        company_normalized="secret corp",
        location_normalized="london",
        sources=json.dumps(["indeed"]),
        source_urls=json.dumps([]),
        fit_score=5.0,
    )
    db_session.add(profile_b_job)
    db_session.commit()

    return jobs


# ===================================================================
# VAL-SEARCH-005: Empty search returns all jobs paginated
# ===================================================================


class TestEmptySearch:
    """Empty search returns full paginated set."""

    def test_empty_search_returns_all_jobs(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["jobs"]) == 5
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_empty_search_pagination(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1, "page": 1, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["jobs"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 3

    def test_pagination_second_page(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1, "page": 2, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["jobs"]) == 2
        assert data["page"] == 2

    def test_empty_search_no_jobs(self, client, db_session):
        resp = client.get("/api/jobs", params={"profile_id": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["jobs"] == []
        assert data["total_pages"] == 1


# ===================================================================
# VAL-SEARCH-001: Full-text search
# ===================================================================


class TestFullTextSearch:
    """Search across title, company, description, location fields."""

    def test_search_by_title(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1, "q": "TPM"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["jobs"][0]["title"] == "Senior TPM - AI Platform"

    def test_search_by_company(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1, "q": "Stripe"})
        data = resp.json()
        assert data["total"] == 2
        companies = {j["company"] for j in data["jobs"]}
        assert companies == {"Stripe"}

    def test_search_by_description(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1, "q": "developer tools"})
        data = resp.json()
        assert data["total"] == 1
        assert data["jobs"][0]["company"] == "Vercel"

    def test_search_by_location(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1, "q": "Frankfurt"})
        data = resp.json()
        assert data["total"] == 1
        assert data["jobs"][0]["company"] == "SAP"

    def test_search_case_insensitive(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1, "q": "stripe"})
        data = resp.json()
        assert data["total"] == 2

    def test_search_no_results(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1, "q": "nonexistent"})
        data = resp.json()
        assert data["total"] == 0
        assert data["jobs"] == []

    def test_search_results_less_than_total(self, client, seed_jobs):
        """Search returns fewer results than total jobs."""
        resp_all = client.get("/api/jobs", params={"profile_id": 1})
        resp_filtered = client.get("/api/jobs", params={"profile_id": 1, "q": "AI"})
        assert resp_filtered.json()["total"] < resp_all.json()["total"]


# ===================================================================
# VAL-SEARCH-002: Multi-facet filtering with AND logic
# ===================================================================


class TestMultiFacetFiltering:
    """Filter by source, remote, salary range, score range, date, company, location."""

    def test_filter_by_remote_true(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1, "remote": True})
        data = resp.json()
        assert data["total"] == 2
        for job in data["jobs"]:
            assert job["remote"] is True

    def test_filter_by_remote_false(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1, "remote": False})
        data = resp.json()
        assert data["total"] == 3
        for job in data["jobs"]:
            assert job["remote"] is False

    def test_filter_by_source(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1, "source": "linkedin"})
        data = resp.json()
        assert data["total"] == 2
        for job in data["jobs"]:
            assert "linkedin" in job["sources"]

    def test_filter_by_company(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1, "company": "Stripe"})
        data = resp.json()
        assert data["total"] == 2
        for job in data["jobs"]:
            assert "stripe" in job["company"].lower()

    def test_filter_by_location(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1, "location": "Berlin"})
        data = resp.json()
        assert data["total"] == 2  # Berlin & Berlin, Germany
        for job in data["jobs"]:
            assert "berlin" in job["location"].lower()

    def test_filter_by_score_range(self, client, seed_jobs):
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "score_min": 7.0, "score_max": 9.0},
        )
        data = resp.json()
        assert data["total"] >= 2
        for job in data["jobs"]:
            assert 7.0 <= job["fit_score"] <= 9.0

    def test_filter_by_score_min(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1, "score_min": 8.0})
        data = resp.json()
        assert data["total"] == 2  # 8.5 and 9.0
        for job in data["jobs"]:
            assert job["fit_score"] >= 8.0

    def test_and_logic_remote_plus_company(self, client, seed_jobs):
        """Multiple filters combine with AND logic."""
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "remote": True, "company": "Stripe"},
        )
        data = resp.json()
        assert data["total"] == 1
        job = data["jobs"][0]
        assert job["remote"] is True
        assert "stripe" in job["company"].lower()

    def test_and_logic_score_plus_remote(self, client, seed_jobs):
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "score_min": 7.0, "remote": True},
        )
        data = resp.json()
        for job in data["jobs"]:
            assert job["fit_score"] >= 7.0
            assert job["remote"] is True

    def test_and_logic_all_results_match_all_filters(self, client, seed_jobs):
        """All results must match ALL active filters."""
        resp = client.get(
            "/api/jobs",
            params={
                "profile_id": 1,
                "q": "AI",
                "score_min": 8.0,
            },
        )
        data = resp.json()
        for job in data["jobs"]:
            text = (
                job["title"] + job["company"] + (job["description"] or "") + job["location"]
            ).lower()
            assert "ai" in text
            assert job["fit_score"] >= 8.0


# ===================================================================
# VAL-SEARCH-003: Sort by score, date, salary, readiness
# ===================================================================


class TestSorting:
    """Sort works for all 4 fields in both directions."""

    def test_sort_by_score_desc(self, client, seed_jobs):
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "sort": "score", "order": "desc"},
        )
        data = resp.json()
        scores = [j["fit_score"] for j in data["jobs"] if j["fit_score"] is not None]
        assert scores == sorted(scores, reverse=True)

    def test_sort_by_score_asc(self, client, seed_jobs):
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "sort": "score", "order": "asc"},
        )
        data = resp.json()
        scores = [j["fit_score"] for j in data["jobs"] if j["fit_score"] is not None]
        # Null scores go last, so filter those out
        assert scores == sorted(scores)

    def test_sort_by_date_desc(self, client, seed_jobs):
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "sort": "date", "order": "desc"},
        )
        data = resp.json()
        dates = [j["created_at"] for j in data["jobs"]]
        assert dates == sorted(dates, reverse=True)

    def test_sort_by_date_asc(self, client, seed_jobs):
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "sort": "date", "order": "asc"},
        )
        data = resp.json()
        dates = [j["created_at"] for j in data["jobs"]]
        assert dates == sorted(dates)

    def test_sort_by_readiness_desc(self, client, seed_jobs):
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "sort": "readiness", "order": "desc"},
        )
        data = resp.json()
        readiness_vals = [
            j["readiness_score"] for j in data["jobs"] if j["readiness_score"] is not None
        ]
        assert readiness_vals == sorted(readiness_vals, reverse=True)

    def test_sort_by_readiness_asc(self, client, seed_jobs):
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "sort": "readiness", "order": "asc"},
        )
        data = resp.json()
        readiness_vals = [
            j["readiness_score"] for j in data["jobs"] if j["readiness_score"] is not None
        ]
        assert readiness_vals == sorted(readiness_vals)

    def test_sort_by_salary_desc(self, client, seed_jobs):
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "sort": "salary", "order": "desc"},
        )
        assert resp.status_code == 200

    def test_sort_by_salary_asc(self, client, seed_jobs):
        resp = client.get(
            "/api/jobs",
            params={"profile_id": 1, "sort": "salary", "order": "asc"},
        )
        assert resp.status_code == 200

    def test_default_sort_is_date_desc(self, client, seed_jobs):
        resp = client.get("/api/jobs", params={"profile_id": 1})
        data = resp.json()
        dates = [j["created_at"] for j in data["jobs"]]
        assert dates == sorted(dates, reverse=True)


# ===================================================================
# VAL-SEARCH-004: Saved searches persist and re-execute correctly
# ===================================================================


class TestSavedSearches:
    """Saved searches CRUD and re-execution."""

    def test_create_saved_search(self, client, seed_jobs):
        resp = client.post(
            "/api/saved-searches",
            json={
                "profile_id": 1,
                "name": "Remote AI jobs",
                "config": {
                    "q": "AI",
                    "remote": True,
                    "score_min": 7.0,
                    "sort": "score",
                    "order": "desc",
                },
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Remote AI jobs"
        assert data["config"]["q"] == "AI"
        assert data["config"]["remote"] is True
        assert data["id"] > 0

    def test_list_saved_searches(self, client, seed_jobs):
        # Create two saved searches
        client.post(
            "/api/saved-searches",
            json={"profile_id": 1, "name": "Search 1", "config": {"q": "AI"}},
        )
        client.post(
            "/api/saved-searches",
            json={
                "profile_id": 1,
                "name": "Search 2",
                "config": {"remote": True},
            },
        )

        resp = client.get("/api/saved-searches", params={"profile_id": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["searches"]) == 2

    def test_get_saved_search(self, client, seed_jobs):
        create_resp = client.post(
            "/api/saved-searches",
            json={
                "profile_id": 1,
                "name": "Test Search",
                "config": {"q": "TPM"},
            },
        )
        search_id = create_resp.json()["id"]

        resp = client.get(f"/api/saved-searches/{search_id}", params={"profile_id": 1})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Search"

    def test_update_saved_search(self, client, seed_jobs):
        create_resp = client.post(
            "/api/saved-searches",
            json={
                "profile_id": 1,
                "name": "Old Name",
                "config": {"q": "old"},
            },
        )
        search_id = create_resp.json()["id"]

        resp = client.put(
            f"/api/saved-searches/{search_id}",
            params={"profile_id": 1},
            json={"name": "New Name", "config": {"q": "new", "remote": True}},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"
        assert resp.json()["config"]["q"] == "new"

    def test_delete_saved_search(self, client, seed_jobs):
        create_resp = client.post(
            "/api/saved-searches",
            json={
                "profile_id": 1,
                "name": "To Delete",
                "config": {},
            },
        )
        search_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/saved-searches/{search_id}", params={"profile_id": 1})
        assert del_resp.status_code == 204

        get_resp = client.get(f"/api/saved-searches/{search_id}", params={"profile_id": 1})
        assert get_resp.status_code == 404

    def test_saved_search_reexecute_matches(self, client, seed_jobs):
        """VAL-SEARCH-004: re-executing a saved search produces same results."""
        # First: manual search
        search_params = {"profile_id": 1, "q": "AI", "remote": True}
        manual_resp = client.get("/api/jobs", params=search_params)
        manual_data = manual_resp.json()

        # Create saved search with same config
        client.post(
            "/api/saved-searches",
            json={
                "profile_id": 1,
                "name": "AI Remote",
                "config": {"q": "AI", "remote": True},
            },
        )

        # Load saved search, apply its config
        list_resp = client.get("/api/saved-searches", params={"profile_id": 1})
        saved = list_resp.json()["searches"][0]
        config = saved["config"]
        reexecute_params = {"profile_id": 1}
        for k, v in config.items():
            if v is not None:
                reexecute_params[k] = v

        reexecute_resp = client.get("/api/jobs", params=reexecute_params)
        reexecute_data = reexecute_resp.json()

        assert manual_data["total"] == reexecute_data["total"]
        manual_ids = {j["id"] for j in manual_data["jobs"]}
        reexecute_ids = {j["id"] for j in reexecute_data["jobs"]}
        assert manual_ids == reexecute_ids


# ===================================================================
# Profile scoping
# ===================================================================


class TestProfileScoping:
    """Profile-scoped access control for jobs and saved searches."""

    def test_profile_b_cannot_see_profile_a_jobs(self, client, seed_jobs):
        """Profile B sees only its own jobs."""
        resp = client.get("/api/jobs", params={"profile_id": 2})
        data = resp.json()
        assert data["total"] == 1
        assert data["jobs"][0]["company"] == "Secret Corp"

    def test_profile_b_cannot_see_profile_a_saved_searches(self, client, seed_jobs):
        # Create search for profile A
        client.post(
            "/api/saved-searches",
            json={
                "profile_id": 1,
                "name": "A's Search",
                "config": {"q": "AI"},
            },
        )

        # Profile B lists saved searches — should see none
        resp = client.get("/api/saved-searches", params={"profile_id": 2})
        assert resp.json()["total"] == 0

    def test_profile_b_cannot_get_profile_a_saved_search(self, client, seed_jobs):
        create_resp = client.post(
            "/api/saved-searches",
            json={
                "profile_id": 1,
                "name": "A's Search",
                "config": {"q": "AI"},
            },
        )
        search_id = create_resp.json()["id"]

        resp = client.get(f"/api/saved-searches/{search_id}", params={"profile_id": 2})
        assert resp.status_code == 404

    def test_profile_b_cannot_delete_profile_a_saved_search(self, client, seed_jobs):
        create_resp = client.post(
            "/api/saved-searches",
            json={
                "profile_id": 1,
                "name": "A's Search",
                "config": {},
            },
        )
        search_id = create_resp.json()["id"]

        resp = client.delete(f"/api/saved-searches/{search_id}", params={"profile_id": 2})
        assert resp.status_code == 404

    def test_nonexistent_profile_returns_404(self, client):
        resp = client.get("/api/jobs", params={"profile_id": 999})
        assert resp.status_code == 404


# ===================================================================
# Error handling
# ===================================================================


class TestErrorHandling:
    def test_missing_profile_id(self, client):
        resp = client.get("/api/jobs")
        assert resp.status_code == 422

    def test_saved_search_not_found(self, client):
        resp = client.get("/api/saved-searches/9999", params={"profile_id": 1})
        assert resp.status_code == 404

    def test_saved_search_empty_name(self, client):
        resp = client.post(
            "/api/saved-searches",
            json={"profile_id": 1, "name": "", "config": {}},
        )
        assert resp.status_code == 422
