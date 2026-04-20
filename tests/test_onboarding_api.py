"""Wave 0: Failing test stubs for Phase 1 onboarding state foundation.

These stubs define the test contract before implementation. Each test
imports the target module and fails until Plans 01-03 ship the code.

Requirements covered: INF-01, INF-02, INF-03
Decision traceability: D-01 through D-13
"""

import pytest

# ---------------------------------------------------------------------------
# INF-01: OnboardingState persistence (timestamps not booleans)
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


def test_state_survives_restart(client, db_session, profile):
    """INF-01: State is DB-backed; GET after PATCH reflects persisted state."""
    pytest.importorskip("career_os.models.onboarding")
    pytest.importorskip("career_os.api.onboarding")
    pytest.fail("stub — implement in Plan 03 Task 3 (test_get_reflects_patch covers this)")


# ---------------------------------------------------------------------------
# INF-02: OnboardingError hierarchy (D-08, D-09, D-10)
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


def test_error_response_format(client, db_session, profile):
    """INF-02: Exception handler returns {error, resolution} JSON, no stack trace (D-10)."""
    pytest.importorskip("career_os.api.onboarding")
    pytest.importorskip("career_os.errors.onboarding")
    pytest.fail("stub — implement in Plan 03 Task 2 + Task 3")


# ---------------------------------------------------------------------------
# INF-03: GET /api/onboarding/status (D-04)
# ---------------------------------------------------------------------------


def test_get_status(client, db_session, profile):
    """INF-03: GET returns full state with next_step, is_complete, progress_pct (D-04)."""
    pytest.importorskip("career_os.api.onboarding")
    pytest.fail("stub — implement in Plan 03 Task 3")


# ---------------------------------------------------------------------------
# INF-03: PATCH /api/onboarding/status (D-05, D-06, D-07)
# ---------------------------------------------------------------------------


def test_patch_step(client, db_session, profile):
    """INF-03: PATCH marks step complete with server-set timestamp (D-05)."""
    pytest.importorskip("career_os.api.onboarding")
    pytest.fail("stub — implement in Plan 03 Task 3")


def test_patch_idempotent(client, db_session, profile):
    """INF-03: PATCH same step twice preserves original timestamp (D-06)."""
    pytest.importorskip("career_os.api.onboarding")
    pytest.fail("stub — implement in Plan 03 Task 3")


def test_patch_invalid_step(client, db_session, profile):
    """INF-03 + D-09: Invalid step name returns 422 with structured error body."""
    pytest.importorskip("career_os.api.onboarding")
    pytest.fail("stub — implement in Plan 03 Task 3")


def test_patch_missing_profile(client, db_session):
    """INF-03: PATCH with non-existent profile_id returns 404."""
    pytest.importorskip("career_os.api.onboarding")
    pytest.fail("stub — implement in Plan 03 Task 3")
