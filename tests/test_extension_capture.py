"""Tests for the real extension capture + promote surface (G-1391 / Part B).

Covers the ``services.extension_capture`` orchestration and the wired
``/api/extension/capture`` + ``/api/extension/promote`` routes: structured and
raw-text (LLM-fallback) scoring, dedupe, the size cap (413), profile-incomplete
(422), token gating (401), and idempotent promote. AI_PROVIDER=mock is enforced
by conftest; the raw-text path patches the extraction provider only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from career_os.config import settings
from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Application, Profile
from career_os.models.scoring import ScoredJob
from career_os.services import extension_pairing

_MIGRATIONS_DIR = (
    Path(__file__).resolve().parent.parent / "src" / "career_os" / "_alembic" / "versions"
)


@pytest.fixture(autouse=True)
def _extension_env(monkeypatch, tmp_path):
    """Pin the extension secret, isolate the pairing/rate-limit state per test.

    Mirrors the autouse fixture in test_extension_api.py — the shared oauth
    limiter must be reset around each test or unrelated /pair throttling leaks in.
    """
    from career_os.api.oauth import limiter as _oauth_limiter

    monkeypatch.setenv("EXTENSION_TOKEN_SECRET", "test-extension-secret-000")
    monkeypatch.setattr(extension_pairing.settings, "data_dir", tmp_path)
    extension_pairing.reset_secret_cache()
    _oauth_limiter.reset()
    yield
    extension_pairing.reset_secret_cache()
    _oauth_limiter.reset()


def _auth_headers() -> dict:
    """A valid Bearer extension token header."""
    return {"Authorization": f"Bearer {extension_pairing.mint_extension_token()}"}


_STRUCTURED_PAYLOAD = {
    "url": "https://example.com/job/1",
    "title": "Senior Backend Engineer",
    "company": "Acme Corp",
    "description": "Build distributed systems in Python. Kubernetes, Go a plus.",
    "location": "Remote",
    "salary": "150-180k",
}


# ---------------------------------------------------------------------------
# Structured capture → real score
# ---------------------------------------------------------------------------


class TestStructuredCapture:
    def test_structured_capture_scores_and_persists(
        self, client: TestClient, db_session: Session, profile: Profile
    ):
        resp = client.post(
            "/api/extension/capture", json=_STRUCTURED_PAYLOAD, headers=_auth_headers()
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["scored"] is True
        assert body["status"] == "scored"
        assert isinstance(body["fit_score"], int | float)
        assert body["discovered_job_id"] is not None
        assert isinstance(body["gap"], str) and body["gap"]
        assert body["letter_grade"]

        djs = db_session.query(DiscoveredJob).filter(DiscoveredJob.profile_id == 1).all()
        assert len(djs) == 1
        assert djs[0].id == body["discovered_job_id"]
        scored = db_session.query(ScoredJob).filter(ScoredJob.discovered_job_id == djs[0].id).all()
        assert len(scored) >= 1

    def test_recapture_same_job_dedupes_to_one_discovered_job(
        self, client: TestClient, db_session: Session, profile: Profile
    ):
        first = client.post(
            "/api/extension/capture", json=_STRUCTURED_PAYLOAD, headers=_auth_headers()
        )
        second = client.post(
            "/api/extension/capture", json=_STRUCTURED_PAYLOAD, headers=_auth_headers()
        )
        assert first.status_code == 200 and second.status_code == 200
        # Same DiscoveredJob reused (dedupe on normalized title/company/location).
        assert first.json()["discovered_job_id"] == second.json()["discovered_job_id"]
        djs = db_session.query(DiscoveredJob).filter(DiscoveredJob.profile_id == 1).all()
        assert len(djs) == 1

    def test_oversize_description_returns_413(
        self, client: TestClient, db_session: Session, profile: Profile
    ):
        payload = {
            **_STRUCTURED_PAYLOAD,
            "description": "x" * (settings.extension_max_jd_chars + 1),
        }
        resp = client.post("/api/extension/capture", json=payload, headers=_auth_headers())
        assert resp.status_code == 413
        # No DiscoveredJob/ScoredJob created — the cap trips before any DB write.
        assert db_session.query(DiscoveredJob).count() == 0
        assert db_session.query(ScoredJob).count() == 0

    def test_profile_incomplete_returns_422(self, client: TestClient, db_session: Session):
        # A profile that exists but lacks job_family/location → ProfileIncompleteError.
        db_session.add(Profile(id=1, name="Incomplete", email="i@example.com"))
        db_session.commit()
        resp = client.post(
            "/api/extension/capture", json=_STRUCTURED_PAYLOAD, headers=_auth_headers()
        )
        assert resp.status_code == 422

    def test_capture_without_token_returns_401(self, client: TestClient):
        resp = client.post("/api/extension/capture", json=_STRUCTURED_PAYLOAD)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Raw-text capture → single LLM extraction, then score
# ---------------------------------------------------------------------------


class _StubExtractionProvider:
    """A stub AI provider whose ``complete`` returns fixed JSON and counts calls."""

    def __init__(self, content: str):
        self._content = content
        self.calls = 0

    async def complete(self, prompt, *, feature=None, **kwargs):
        self.calls += 1

        class _Resp:
            content = self._content

        return _Resp()


class TestRawTextCapture:
    def test_raw_text_runs_one_extraction_then_scores(
        self, client: TestClient, db_session: Session, profile: Profile, monkeypatch
    ):
        extracted = json.dumps(
            {
                "company": "Globex",
                "title": "Platform Engineer",
                "description": "Own the CI/CD platform. Terraform, Go.",
                "location": "Berlin",
                "salary": "",
            }
        )
        stub = _StubExtractionProvider(extracted)
        monkeypatch.setattr(
            "career_os.services.extension_capture.get_ai_provider", lambda *a, **k: stub
        )

        resp = client.post(
            "/api/extension/capture",
            json={"url": "https://example.com/job/raw", "raw_text": "Globex is hiring..."},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["scored"] is True
        # Exactly ONE extraction provider call (cost/DoS bound).
        assert stub.calls == 1

        dj = db_session.query(DiscoveredJob).filter(DiscoveredJob.profile_id == 1).one()
        assert dj.company == "Globex"
        assert dj.title == "Platform Engineer"


# ---------------------------------------------------------------------------
# Promote — add captured job to pipeline (idempotent)
# ---------------------------------------------------------------------------


class TestPromote:
    def _capture(self, client: TestClient) -> int:
        resp = client.post(
            "/api/extension/capture", json=_STRUCTURED_PAYLOAD, headers=_auth_headers()
        )
        assert resp.status_code == 200
        return resp.json()["discovered_job_id"]

    def test_promote_creates_linked_application(
        self, client: TestClient, db_session: Session, profile: Profile
    ):
        dj_id = self._capture(client)
        resp = client.post(
            "/api/extension/promote", json={"discovered_job_id": dj_id}, headers=_auth_headers()
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "discovered"
        app = db_session.query(Application).filter(Application.id == body["application_id"]).one()
        assert app.source == "extension"
        # The DiscoveredJob↔Application link is DiscoveredJob.application_id.
        dj = db_session.query(DiscoveredJob).filter(DiscoveredJob.id == dj_id).one()
        assert dj.application_id == app.id

    def test_promote_is_idempotent(self, client: TestClient, db_session: Session, profile: Profile):
        dj_id = self._capture(client)
        first = client.post(
            "/api/extension/promote", json={"discovered_job_id": dj_id}, headers=_auth_headers()
        )
        second = client.post(
            "/api/extension/promote", json={"discovered_job_id": dj_id}, headers=_auth_headers()
        )
        assert first.status_code == 200 and second.status_code == 200
        assert first.json()["application_id"] == second.json()["application_id"]
        assert db_session.query(Application).count() == 1

    def test_promote_without_token_returns_401(self, client: TestClient):
        resp = client.post("/api/extension/promote", json={"discovered_job_id": 1})
        assert resp.status_code == 401

    def test_promote_missing_job_returns_404(
        self, client: TestClient, db_session: Session, profile: Profile
    ):
        resp = client.post(
            "/api/extension/promote", json={"discovered_job_id": 9999}, headers=_auth_headers()
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# No schema drift: this plan adds ZERO Alembic migrations
# ---------------------------------------------------------------------------


def test_no_new_alembic_migration_added():
    """Part B reuses existing tables only — this branch may add no migration file.

    The link column ``DiscoveredJob.application_id`` already exists; capture and
    promote write only to existing tables. Compare the versions/ dir against the
    branch merge-base with main so this stays correct even as unrelated migrations
    land on main. Skips cleanly if git isn't available (e.g. an sdist test run).
    """
    import subprocess

    assert _MIGRATIONS_DIR.is_dir()
    repo_root = _MIGRATIONS_DIR.parents[3]
    try:
        base = subprocess.run(
            ["git", "merge-base", "HEAD", "main"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        changed = subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                f"{base}..HEAD",
                "--",
                "src/career_os/_alembic/versions/",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("git unavailable — migration-leak guard runs in CI")
    assert not changed, f"Part B must add no migration; changed: {changed}"
