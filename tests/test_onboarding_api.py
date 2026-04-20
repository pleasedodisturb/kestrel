"""Tests for /api/onboarding/status endpoints.

Covers INF-01 (state persistence), INF-02 (error hierarchy), INF-03 (GET/PATCH endpoints).
All tests use the shared client/db_session/profile fixtures from conftest.py.
"""


# ---------------------------------------------------------------------------
# INF-03: GET /api/onboarding/status
# ---------------------------------------------------------------------------


def test_get_status_no_state(client, db_session, profile):
    """GET returns synthesized empty state for profile with no onboarding row (A2 assumption)."""
    response = client.get(f"/api/onboarding/status?profile_id={profile.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["is_complete"] is False
    assert data["progress_pct"] == 0
    assert data["next_step"] == "profile_started"
    assert data["profile_id"] == profile.id
    assert data["profile_completed_at"] is None


def test_get_status_missing_profile(client, db_session):
    """GET returns 404 for non-existent profile."""
    response = client.get("/api/onboarding/status?profile_id=9999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# INF-03: PATCH /api/onboarding/status
# ---------------------------------------------------------------------------


def test_patch_step_creates_state(client, db_session, profile):
    """PATCH creates OnboardingState row on first call and marks step complete."""
    payload = {"step": "profile_completed", "via": "cli"}
    response = client.patch(f"/api/onboarding/status?profile_id={profile.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["profile_completed_at"] is not None
    assert data["profile_completed_via"] == "cli"
    assert data["progress_pct"] > 0


def test_patch_step_idempotent(client, db_session, profile):
    """PATCH same step twice preserves original timestamp (D-06)."""
    payload = {"step": "profile_completed", "via": "cli"}
    r1 = client.patch(f"/api/onboarding/status?profile_id={profile.id}", json=payload)
    assert r1.status_code == 200
    ts1 = r1.json()["profile_completed_at"]

    r2 = client.patch(f"/api/onboarding/status?profile_id={profile.id}", json=payload)
    assert r2.status_code == 200
    ts2 = r2.json()["profile_completed_at"]

    assert ts1 == ts2, f"Timestamp changed on repeat PATCH: {ts1} -> {ts2}"


def test_patch_missing_profile(client, db_session):
    """PATCH returns 404 for non-existent profile."""
    payload = {"step": "profile_completed", "via": "web"}
    response = client.patch("/api/onboarding/status?profile_id=9999", json=payload)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# INF-02: Error hierarchy and exception handler (D-08, D-09, D-10)
# ---------------------------------------------------------------------------


def test_patch_invalid_step_returns_422(client, db_session, profile):
    """PATCH with unknown step name returns 422 with structured error body (D-10)."""
    payload = {"step": "nonexistent_step", "via": "cli"}
    response = client.patch(f"/api/onboarding/status?profile_id={profile.id}", json=payload)
    assert response.status_code == 422
    data = response.json()
    # Must have "error" and "resolution" keys (not Pydantic's default "detail" format)
    assert "error" in data, f"Expected 'error' key, got: {list(data.keys())}"
    assert "resolution" in data, f"Expected 'resolution' key, got: {list(data.keys())}"
    assert "detail" not in data, f"Should not have 'detail' key (that's Pydantic format): {data}"
    assert "nonexistent_step" in data["error"]


def test_error_response_has_no_stack_trace(client, db_session, profile):
    """Error response body does not contain traceback or exception type strings."""
    payload = {"step": "bad_step", "via": "cli"}
    response = client.patch(f"/api/onboarding/status?profile_id={profile.id}", json=payload)
    assert response.status_code == 422
    body = response.text
    assert "Traceback" not in body
    assert "Exception" not in body or "OnboardingValidationError" not in body


def test_patch_invalid_via_returns_422(client, db_session, profile):
    """PATCH with via='mobile' returns 422 (Pydantic Literal validation)."""
    payload = {"step": "profile_completed", "via": "mobile"}
    response = client.patch(f"/api/onboarding/status?profile_id={profile.id}", json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# INF-01: State persistence and completion (timestamps, not booleans)
# ---------------------------------------------------------------------------


def test_patch_all_steps_complete(client, db_session, profile):
    """Patching all steps leads to is_complete=True and progress_pct=100."""
    from career_os.services.onboarding import STEP_ORDER

    for step in STEP_ORDER:
        payload = {"step": step, "via": "web"}
        r = client.patch(f"/api/onboarding/status?profile_id={profile.id}", json=payload)
        assert r.status_code == 200, f"Failed on step {step}: {r.text}"

    final = client.get(f"/api/onboarding/status?profile_id={profile.id}")
    assert final.status_code == 200
    data = final.json()
    assert data["is_complete"] is True
    assert data["progress_pct"] == 100
    assert data["next_step"] is None


def test_get_reflects_patch(client, db_session, profile):
    """GET after PATCH reflects the updated state (INF-01: survives within session)."""
    payload = {"step": "demo_seeded", "via": "cli"}
    patch_r = client.patch(f"/api/onboarding/status?profile_id={profile.id}", json=payload)
    assert patch_r.status_code == 200

    get_r = client.get(f"/api/onboarding/status?profile_id={profile.id}")
    assert get_r.status_code == 200
    data = get_r.json()
    assert data["demo_seeded_at"] is not None
    assert data["demo_seeded_via"] == "cli"


# ---------------------------------------------------------------------------
# INF-02: OnboardingError hierarchy (D-08, D-09) — unit tests
# ---------------------------------------------------------------------------


def test_error_fields():
    """INF-02: OnboardingError has user_message, resolution, status_code (D-08)."""
    from career_os.errors.onboarding import (
        OnboardingError,
        OnboardingStateError,
        OnboardingValidationError,
    )

    base = OnboardingError("base message", "base resolution", status_code=400)
    assert base.user_message == "base message"
    assert base.resolution == "base resolution"
    assert base.status_code == 400

    validation_err = OnboardingValidationError("bad step", "Valid steps are: ...")
    assert validation_err.status_code == 422
    assert validation_err.user_message == "bad step"

    state_err = OnboardingStateError("already complete", "No action needed")
    assert state_err.status_code == 409


# ---------------------------------------------------------------------------
# INF-01: Direct service layer test (state persistence)
# ---------------------------------------------------------------------------


def test_state_persisted(client, db_session, profile):
    """INF-01: OnboardingState row persisted in DB after first mark_step_complete call (D-01, D-13)."""
    from career_os.models.onboarding import OnboardingState
    from career_os.services.onboarding import mark_step_complete

    # No row exists before first PATCH
    before = db_session.query(OnboardingState).filter_by(profile_id=profile.id).first()
    assert before is None

    # After mark_step_complete, row exists with timestamp set
    result = mark_step_complete("profile_started", "cli", profile.id, db_session)
    after = db_session.query(OnboardingState).filter_by(profile_id=profile.id).first()
    assert after is not None
    assert after.profile_started_at is not None
    assert after.profile_started_via == "cli"
    assert result.profile_started_at is not None
