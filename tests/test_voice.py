"""Tests for Voice Discussion Mode API and service.

Covers:
- VAL-VOICE-001: Voice input accepted (STT-agnostic) — text accepted, response generated
- VAL-VOICE-002: Voice cover letter brainstorming — produces draft referencing profile and role
- VAL-VOICE-003: Voice coaching session — dialogue with relevant questions and feedback
- VAL-VOICE-004: Voice job evaluation — scored evaluation with pros/cons
- Profile scoping: two-profile isolation tests
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
from career_os.models.models import Application, Profile

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _db_engine():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_name = tmp.name
    url = f"sqlite:///{tmp_name}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(
        engine, "connect", lambda c, _: c.cursor().execute("PRAGMA foreign_keys=ON")
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    os.unlink(tmp_name)


@pytest.fixture
def test_db(_db_engine):
    TestSession = sessionmaker(bind=_db_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(_db_engine) -> TestClient:
    TestSession = sessionmaker(bind=_db_engine)

    def override():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def profile(test_db: Session) -> Profile:
    p = Profile(name="Test User", email="test@example.com", location="Remote", job_family="TPM")
    test_db.add(p)
    test_db.commit()
    test_db.refresh(p)
    return p


@pytest.fixture
def profile_b(test_db: Session) -> Profile:
    p = Profile(name="Other User", email="other@test.com", location="Berlin")
    test_db.add(p)
    test_db.commit()
    test_db.refresh(p)
    return p


@pytest.fixture
def application(test_db: Session, profile: Profile) -> Application:
    app_obj = Application(
        profile_id=profile.id,
        company="Stripe",
        role="Senior TPM",
        status="interested",
        salary_range="140-160k EUR",
        notes="AI-first fintech, great culture fit",
        fit_score=8.5,
    )
    test_db.add(app_obj)
    test_db.commit()
    test_db.refresh(app_obj)
    return app_obj


# ===========================================================================
# VAL-VOICE-001: Voice input accepted (STT-agnostic)
# ===========================================================================


class TestVoiceInput:
    """Text from any STT tool accepted in voice discussion interface."""

    def test_create_session_and_send_message(
        self, client: TestClient, profile: Profile
    ):
        """Create a session and send a text message → get response."""
        # Create session
        resp = client.post(
            "/api/voice/sessions",
            json={"profile_id": profile.id, "mode": "coaching"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["mode"] == "coaching"
        assert data["status"] == "active"
        assert len(data["messages"]) == 1  # welcome message
        assert data["messages"][0]["role"] == "assistant"
        session_id = data["id"]

        # Send user message (simulating STT input)
        resp = client.post(
            f"/api/voice/sessions/{session_id}/messages",
            json={
                "profile_id": profile.id,
                "content": "I want to prepare for interviews at FAANG companies",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_message"]["role"] == "user"
        assert "FAANG" in data["user_message"]["content"]
        assert data["assistant_message"]["role"] == "assistant"
        assert len(data["assistant_message"]["content"]) > 0

    def test_session_transcript_flow(
        self, client: TestClient, profile: Profile
    ):
        """Multiple messages form a conversation transcript."""
        # Create session
        resp = client.post(
            "/api/voice/sessions",
            json={"profile_id": profile.id, "mode": "coaching"},
        )
        session_id = resp.json()["id"]

        # Send multiple messages
        for msg in ["Hello", "Tell me about interview tips"]:
            resp = client.post(
                f"/api/voice/sessions/{session_id}/messages",
                json={"profile_id": profile.id, "content": msg},
            )
            assert resp.status_code == 200

        # Get full session with all messages
        resp = client.get(
            f"/api/voice/sessions/{session_id}",
            params={"profile_id": profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        # 1 welcome + 2 user + 2 assistant = 5 messages
        assert len(data["messages"]) == 5

    def test_list_sessions(self, client: TestClient, profile: Profile):
        """Can list all sessions for a profile."""
        # Create two sessions
        for mode in ["coaching", "job_evaluation"]:
            client.post(
                "/api/voice/sessions",
                json={"profile_id": profile.id, "mode": mode},
            )

        resp = client.get(
            "/api/voice/sessions",
            params={"profile_id": profile.id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_list_sessions_filter_by_mode(
        self, client: TestClient, profile: Profile
    ):
        """Can filter sessions by mode."""
        for mode in ["coaching", "coaching", "job_evaluation"]:
            client.post(
                "/api/voice/sessions",
                json={"profile_id": profile.id, "mode": mode},
            )

        resp = client.get(
            "/api/voice/sessions",
            params={"profile_id": profile.id, "mode": "coaching"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_complete_session(self, client: TestClient, profile: Profile):
        """Mark session as completed."""
        resp = client.post(
            "/api/voice/sessions",
            json={"profile_id": profile.id, "mode": "coaching"},
        )
        session_id = resp.json()["id"]

        resp = client.post(
            f"/api/voice/sessions/{session_id}/complete",
            params={"profile_id": profile.id},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_empty_message_rejected(self, client: TestClient, profile: Profile):
        """Empty message is rejected with 422."""
        resp = client.post(
            "/api/voice/sessions",
            json={"profile_id": profile.id, "mode": "coaching"},
        )
        session_id = resp.json()["id"]

        resp = client.post(
            f"/api/voice/sessions/{session_id}/messages",
            json={"profile_id": profile.id, "content": ""},
        )
        assert resp.status_code == 422


# ===========================================================================
# VAL-VOICE-002: Voice cover letter brainstorming
# ===========================================================================


class TestVoiceCoverLetter:
    """Cover letter brainstorming produces draft referencing profile and role."""

    def test_cover_letter_session_with_application(
        self, client: TestClient, profile: Profile, application: Application
    ):
        """Cover letter session references the target application."""
        # Create cover letter session
        resp = client.post(
            "/api/voice/sessions",
            json={
                "profile_id": profile.id,
                "mode": "cover_letter",
                "application_id": application.id,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["mode"] == "cover_letter"
        assert data["application_id"] == application.id
        # Welcome message references company
        welcome = data["messages"][0]["content"]
        assert "Stripe" in welcome
        assert "Senior TPM" in welcome

    def test_cover_letter_brainstorm_produces_draft(
        self, client: TestClient, profile: Profile, application: Application
    ):
        """Sending brainstorm message produces draft referencing profile strengths."""
        resp = client.post(
            "/api/voice/sessions",
            json={
                "profile_id": profile.id,
                "mode": "cover_letter",
                "application_id": application.id,
            },
        )
        session_id = resp.json()["id"]

        # Ask for a draft
        resp = client.post(
            f"/api/voice/sessions/{session_id}/messages",
            json={
                "profile_id": profile.id,
                "content": "Draft a cover letter emphasizing my AI/ML experience",
            },
        )
        assert resp.status_code == 200
        assistant_content = resp.json()["assistant_message"]["content"]
        # Mock provider references profile and role
        assert len(assistant_content) > 50
        # The mock response should reference the company/role
        assert "Stripe" in assistant_content or "leadership" in assistant_content.lower()

    def test_cover_letter_auto_title(
        self, client: TestClient, profile: Profile, application: Application
    ):
        """Session auto-generates title with company and role."""
        resp = client.post(
            "/api/voice/sessions",
            json={
                "profile_id": profile.id,
                "mode": "cover_letter",
                "application_id": application.id,
            },
        )
        title = resp.json()["title"]
        assert "Cover Letter" in title
        assert "Stripe" in title

    def test_cover_letter_requires_application_id(
        self, client: TestClient, profile: Profile
    ):
        """Cover letter mode without application_id returns 422."""
        resp = client.post(
            "/api/voice/sessions",
            json={
                "profile_id": profile.id,
                "mode": "cover_letter",
                # No application_id
            },
        )
        assert resp.status_code == 422
        assert "application_id" in resp.json()["detail"].lower()


# ===========================================================================
# VAL-VOICE-003: Voice coaching session
# ===========================================================================


class TestVoiceCoaching:
    """Coaching session runs with relevant questions and feedback."""

    def test_coaching_welcome_message(
        self, client: TestClient, profile: Profile
    ):
        """Coaching session starts with helpful welcome."""
        resp = client.post(
            "/api/voice/sessions",
            json={"profile_id": profile.id, "mode": "coaching"},
        )
        assert resp.status_code == 201
        welcome = resp.json()["messages"][0]["content"]
        assert "coaching" in welcome.lower() or "focus" in welcome.lower()

    def test_coaching_with_interview_focus(
        self, client: TestClient, profile: Profile
    ):
        """Coaching responds with interview-relevant questions."""
        resp = client.post(
            "/api/voice/sessions",
            json={"profile_id": profile.id, "mode": "coaching"},
        )
        session_id = resp.json()["id"]

        resp = client.post(
            f"/api/voice/sessions/{session_id}/messages",
            json={
                "profile_id": profile.id,
                "content": "I want to focus on interview preparation",
            },
        )
        assert resp.status_code == 200
        content = resp.json()["assistant_message"]["content"]
        # Should contain questions or coaching-relevant content
        assert len(content) > 50
        assert "interview" in content.lower() or "question" in content.lower()

    def test_coaching_with_skills_focus(
        self, client: TestClient, profile: Profile
    ):
        """Coaching responds with skills development advice."""
        resp = client.post(
            "/api/voice/sessions",
            json={"profile_id": profile.id, "mode": "coaching"},
        )
        session_id = resp.json()["id"]

        resp = client.post(
            f"/api/voice/sessions/{session_id}/messages",
            json={
                "profile_id": profile.id,
                "content": "Help me with skills development plan",
            },
        )
        assert resp.status_code == 200
        content = resp.json()["assistant_message"]["content"]
        assert len(content) > 50

    def test_coaching_multi_turn(
        self, client: TestClient, profile: Profile
    ):
        """Multiple coaching turns maintain conversational flow."""
        resp = client.post(
            "/api/voice/sessions",
            json={"profile_id": profile.id, "mode": "coaching"},
        )
        session_id = resp.json()["id"]

        messages = [
            "I want career strategy advice",
            "I'm targeting Senior TPM roles",
            "What should I prioritize?",
        ]
        for msg in messages:
            resp = client.post(
                f"/api/voice/sessions/{session_id}/messages",
                json={"profile_id": profile.id, "content": msg},
            )
            assert resp.status_code == 200
            assert len(resp.json()["assistant_message"]["content"]) > 0

        # Verify full transcript
        resp = client.get(
            f"/api/voice/sessions/{session_id}",
            params={"profile_id": profile.id},
        )
        # 1 welcome + 3 user + 3 assistant = 7
        assert len(resp.json()["messages"]) == 7


# ===========================================================================
# VAL-VOICE-004: Voice job evaluation
# ===========================================================================


class TestVoiceJobEvaluation:
    """Job evaluation produces scored assessment with pros/cons."""

    def test_job_evaluation_session(
        self, client: TestClient, profile: Profile, application: Application
    ):
        """Job evaluation session linked to application."""
        resp = client.post(
            "/api/voice/sessions",
            json={
                "profile_id": profile.id,
                "mode": "job_evaluation",
                "application_id": application.id,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["mode"] == "job_evaluation"
        assert data["application_id"] == application.id
        welcome = data["messages"][0]["content"]
        assert "Stripe" in welcome
        assert "Senior TPM" in welcome

    def test_job_evaluation_produces_scored_assessment(
        self, client: TestClient, profile: Profile, application: Application
    ):
        """Evaluation produces scored assessment with pros/cons."""
        resp = client.post(
            "/api/voice/sessions",
            json={
                "profile_id": profile.id,
                "mode": "job_evaluation",
                "application_id": application.id,
            },
        )
        session_id = resp.json()["id"]

        resp = client.post(
            f"/api/voice/sessions/{session_id}/messages",
            json={
                "profile_id": profile.id,
                "content": "What do you think about this role? Give me a full evaluation.",
            },
        )
        assert resp.status_code == 200
        content = resp.json()["assistant_message"]["content"]
        # Should contain scoring, pros, and cons
        assert "pros" in content.lower() or "pro" in content.lower()
        assert "cons" in content.lower() or "con" in content.lower()
        assert "score" in content.lower() or "/10" in content

    def test_job_evaluation_references_profile(
        self, client: TestClient, profile: Profile, application: Application
    ):
        """Evaluation references the user's profile and role details."""
        resp = client.post(
            "/api/voice/sessions",
            json={
                "profile_id": profile.id,
                "mode": "job_evaluation",
                "application_id": application.id,
            },
        )
        session_id = resp.json()["id"]

        resp = client.post(
            f"/api/voice/sessions/{session_id}/messages",
            json={
                "profile_id": profile.id,
                "content": "Evaluate this opportunity for me",
            },
        )
        assert resp.status_code == 200
        content = resp.json()["assistant_message"]["content"]
        # Should reference the company or role
        assert "Stripe" in content or "Senior TPM" in content or "TPM" in content


# ===========================================================================
# Validation / Error handling
# ===========================================================================


class TestVoiceValidation:
    """Validation and error handling tests."""

    def test_invalid_mode_returns_422(
        self, client: TestClient, profile: Profile
    ):
        """Invalid session mode returns 422."""
        resp = client.post(
            "/api/voice/sessions",
            json={"profile_id": profile.id, "mode": "invalid_mode"},
        )
        assert resp.status_code == 422

    def test_nonexistent_profile_returns_404(self, client: TestClient):
        """Non-existent profile returns 404."""
        resp = client.post(
            "/api/voice/sessions",
            json={"profile_id": 9999, "mode": "coaching"},
        )
        assert resp.status_code == 404

    def test_nonexistent_application_returns_404(
        self, client: TestClient, profile: Profile
    ):
        """Non-existent application returns 404."""
        resp = client.post(
            "/api/voice/sessions",
            json={
                "profile_id": profile.id,
                "mode": "cover_letter",
                "application_id": 9999,
            },
        )
        assert resp.status_code == 404

    def test_nonexistent_session_returns_404(
        self, client: TestClient, profile: Profile
    ):
        """Non-existent session returns 404."""
        resp = client.get(
            "/api/voice/sessions/9999",
            params={"profile_id": profile.id},
        )
        assert resp.status_code == 404

    def test_send_to_nonexistent_session_returns_404(
        self, client: TestClient, profile: Profile
    ):
        """Sending to non-existent session returns 404."""
        resp = client.post(
            "/api/voice/sessions/9999/messages",
            json={"profile_id": profile.id, "content": "hello"},
        )
        assert resp.status_code == 404


# ===========================================================================
# Profile scoping: two-profile isolation
# ===========================================================================


class TestVoiceProfileScoping:
    """Profile B cannot access Profile A's voice sessions."""

    def test_profile_b_cannot_read_a_session(
        self,
        client: TestClient,
        profile: Profile,
        profile_b: Profile,
    ):
        """Profile B gets 404 when reading profile A's session."""
        resp = client.post(
            "/api/voice/sessions",
            json={"profile_id": profile.id, "mode": "coaching"},
        )
        session_id = resp.json()["id"]

        resp = client.get(
            f"/api/voice/sessions/{session_id}",
            params={"profile_id": profile_b.id},
        )
        assert resp.status_code == 404

    def test_profile_b_cannot_send_to_a_session(
        self,
        client: TestClient,
        profile: Profile,
        profile_b: Profile,
    ):
        """Profile B gets 404 when sending to profile A's session."""
        resp = client.post(
            "/api/voice/sessions",
            json={"profile_id": profile.id, "mode": "coaching"},
        )
        session_id = resp.json()["id"]

        resp = client.post(
            f"/api/voice/sessions/{session_id}/messages",
            json={"profile_id": profile_b.id, "content": "hello"},
        )
        assert resp.status_code == 404

    def test_profile_b_cannot_complete_a_session(
        self,
        client: TestClient,
        profile: Profile,
        profile_b: Profile,
    ):
        """Profile B cannot complete profile A's session."""
        resp = client.post(
            "/api/voice/sessions",
            json={"profile_id": profile.id, "mode": "coaching"},
        )
        session_id = resp.json()["id"]

        resp = client.post(
            f"/api/voice/sessions/{session_id}/complete",
            params={"profile_id": profile_b.id},
        )
        assert resp.status_code == 404

    def test_profile_sessions_isolated(
        self,
        client: TestClient,
        profile: Profile,
        profile_b: Profile,
    ):
        """Each profile only sees their own sessions."""
        client.post(
            "/api/voice/sessions",
            json={"profile_id": profile.id, "mode": "coaching"},
        )
        client.post(
            "/api/voice/sessions",
            json={"profile_id": profile_b.id, "mode": "coaching"},
        )

        resp_a = client.get(
            "/api/voice/sessions",
            params={"profile_id": profile.id},
        )
        resp_b = client.get(
            "/api/voice/sessions",
            params={"profile_id": profile_b.id},
        )
        assert resp_a.json()["total"] == 1
        assert resp_b.json()["total"] == 1

    def test_profile_b_cannot_use_a_application(
        self,
        client: TestClient,
        profile: Profile,
        profile_b: Profile,
        application: Application,
    ):
        """Profile B cannot create session with profile A's application."""
        resp = client.post(
            "/api/voice/sessions",
            json={
                "profile_id": profile_b.id,
                "mode": "cover_letter",
                "application_id": application.id,
            },
        )
        assert resp.status_code == 404
