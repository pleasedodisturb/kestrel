"""Tests for OnboardingError hierarchy (INF-02, D-08, D-09).

TDD RED phase — written before implementation.
"""


def test_onboarding_error_base_fields():
    """OnboardingError has user_message, resolution, status_code=400 (D-08)."""
    from career_os.errors.onboarding import OnboardingError

    e = OnboardingError("bad step", "try again")
    assert e.user_message == "bad step"
    assert e.resolution == "try again"
    assert e.status_code == 400


def test_onboarding_error_str():
    """str(OnboardingError(...)) returns user_message."""
    from career_os.errors.onboarding import OnboardingError

    e = OnboardingError("msg", "res")
    assert str(e) == "msg"


def test_onboarding_error_is_exception():
    """OnboardingError is a subclass of Exception."""
    from career_os.errors.onboarding import OnboardingError

    e = OnboardingError("x", "y")
    assert isinstance(e, Exception)


def test_validation_error_status_code():
    """OnboardingValidationError has status_code=422 (D-09)."""
    from career_os.errors.onboarding import OnboardingValidationError

    ve = OnboardingValidationError("invalid via", "use cli or web")
    assert ve.status_code == 422


def test_validation_error_is_onboarding_error():
    """OnboardingValidationError is a subclass of OnboardingError."""
    from career_os.errors.onboarding import OnboardingError, OnboardingValidationError

    ve = OnboardingValidationError("x", "y")
    assert isinstance(ve, OnboardingError)
    assert isinstance(ve, Exception)


def test_state_error_status_code():
    """OnboardingStateError has status_code=409 (D-09)."""
    from career_os.errors.onboarding import OnboardingStateError

    se = OnboardingStateError("conflict", "check state")
    assert se.status_code == 409


def test_state_error_is_onboarding_error():
    """OnboardingStateError is a subclass of OnboardingError."""
    from career_os.errors.onboarding import OnboardingError, OnboardingStateError

    se = OnboardingStateError("x", "y")
    assert isinstance(se, OnboardingError)
    assert isinstance(se, Exception)


def test_onboarding_error_custom_status_code():
    """OnboardingError accepts custom status_code via keyword arg."""
    from career_os.errors.onboarding import OnboardingError

    e = OnboardingError("x", "y", status_code=503)
    assert e.status_code == 503
