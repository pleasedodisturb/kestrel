"""Tests for `career_os.api.jobs` — search and saved-search endpoints.

Uses real DB fixtures: seeds DiscoveredJob rows so the search service runs
end-to-end against in-memory SQLite. Saved-search CRUD is exercised via
the HTTP layer with no patches needed.
"""

import pytest
from fastapi.testclient import TestClient

from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Profile


@pytest.fixture(autouse=True)
def _seed_profile(db_session):
    db_session.add(Profile(id=1, name="P", email="p@p.com"))
    db_session.commit()
    return db_session


def _seed_job(
    db,
    *,
    title: str,
    company: str,
    location: str = "Remote",
    remote: bool = True,
    salary: str | None = None,
    fit_score: float | None = None,
):
    job = DiscoveredJob(
        profile_id=1,
        title=title,
        company=company,
        location=location,
        title_normalized=title.lower(),
        company_normalized=company.lower(),
        location_normalized=location.lower(),
        remote=remote,
        salary_range=salary,
        fit_score=fit_score,
        sources='["test"]',
        source_urls="[]",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# ---------------------------------------------------------------------------
# GET /api/jobs
# ---------------------------------------------------------------------------


def test_search_jobs_empty_returns_zero(client: TestClient):
    resp = client.get("/api/jobs", params={"profile_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["jobs"] == []
    assert body["page"] == 1


def test_search_jobs_returns_seeded_rows(client: TestClient, db_session):
    _seed_job(db_session, title="AI PM", company="Mistral", fit_score=8.5)
    _seed_job(db_session, title="TPM", company="Linear", fit_score=7.0)
    _seed_job(db_session, title="Engineer", company="Acme", fit_score=5.0)

    resp = client.get("/api/jobs", params={"profile_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["jobs"]) == 3


def test_search_jobs_full_text_query(client: TestClient, db_session):
    _seed_job(db_session, title="AI PM", company="Mistral")
    _seed_job(db_session, title="TPM", company="Linear")

    resp = client.get("/api/jobs", params={"profile_id": 1, "q": "AI"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["jobs"][0]["title"] == "AI PM"


def test_search_jobs_remote_filter(client: TestClient, db_session):
    _seed_job(db_session, title="A", company="X", remote=True)
    _seed_job(db_session, title="B", company="Y", remote=False)

    resp = client.get("/api/jobs", params={"profile_id": 1, "remote": "true"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["jobs"][0]["remote"] is True


def test_search_jobs_pagination(client: TestClient, db_session):
    for i in range(5):
        _seed_job(db_session, title=f"Job{i}", company=f"Co{i}")

    resp = client.get(
        "/api/jobs",
        params={"profile_id": 1, "page": 1, "page_size": 2},
    )
    body = resp.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["jobs"]) == 2
    assert body["total_pages"] == 3


def test_search_jobs_unknown_profile_returns_404(client: TestClient):
    resp = client.get("/api/jobs", params={"profile_id": 999})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Saved searches CRUD — POST/GET/PUT/DELETE
# ---------------------------------------------------------------------------


def test_create_saved_search_returns_201(client: TestClient):
    resp = client.post(
        "/api/saved-searches",
        json={
            "profile_id": 1,
            "name": "AI Roles",
            "config": {"q": "AI", "remote": True},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "AI Roles"
    assert body["config"]["q"] == "AI"
    assert body["config"]["remote"] is True
    assert body["profile_id"] == 1


def test_create_saved_search_unknown_profile_returns_404(client: TestClient):
    resp = client.post(
        "/api/saved-searches",
        json={
            "profile_id": 999,
            "name": "X",
            "config": {},
        },
    )
    assert resp.status_code == 404


def test_list_saved_searches(client: TestClient):
    client.post(
        "/api/saved-searches",
        json={"profile_id": 1, "name": "First", "config": {}},
    )
    client.post(
        "/api/saved-searches",
        json={"profile_id": 1, "name": "Second", "config": {}},
    )

    resp = client.get("/api/saved-searches", params={"profile_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    names = {s["name"] for s in body["searches"]}
    assert names == {"First", "Second"}


def test_get_saved_search_by_id(client: TestClient):
    create = client.post(
        "/api/saved-searches",
        json={"profile_id": 1, "name": "X", "config": {"q": "abc"}},
    )
    sid = create.json()["id"]

    resp = client.get(f"/api/saved-searches/{sid}", params={"profile_id": 1})
    assert resp.status_code == 200
    assert resp.json()["name"] == "X"
    assert resp.json()["config"]["q"] == "abc"


def test_get_saved_search_unknown_id_returns_404(client: TestClient):
    resp = client.get("/api/saved-searches/9999", params={"profile_id": 1})
    assert resp.status_code == 404


def test_update_saved_search(client: TestClient):
    create = client.post(
        "/api/saved-searches",
        json={"profile_id": 1, "name": "Old", "config": {}},
    )
    sid = create.json()["id"]

    resp = client.put(
        f"/api/saved-searches/{sid}",
        params={"profile_id": 1},
        json={"name": "New Name", "config": {"q": "updated"}},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"
    assert resp.json()["config"]["q"] == "updated"


def test_update_saved_search_unknown_id_returns_404(client: TestClient):
    resp = client.put(
        "/api/saved-searches/9999",
        params={"profile_id": 1},
        json={"name": "X"},
    )
    assert resp.status_code == 404


def test_delete_saved_search_returns_204(client: TestClient):
    create = client.post(
        "/api/saved-searches",
        json={"profile_id": 1, "name": "Doomed", "config": {}},
    )
    sid = create.json()["id"]

    resp = client.delete(f"/api/saved-searches/{sid}", params={"profile_id": 1})
    assert resp.status_code == 204

    # Now it's gone
    resp = client.get(f"/api/saved-searches/{sid}", params={"profile_id": 1})
    assert resp.status_code == 404


def test_delete_saved_search_unknown_id_returns_404(client: TestClient):
    resp = client.delete("/api/saved-searches/9999", params={"profile_id": 1})
    assert resp.status_code == 404
