"""Structured error hierarchy for onboarding with user-facing fields.

All onboarding errors carry user_message (what happened), resolution (what to do),
and status_code (HTTP response code). The FastAPI exception handler in main.py
converts these to {"error": user_message, "resolution": resolution} JSON responses
without exposing stack traces (D-10).
"""


class OnboardingError(Exception):
    """Base onboarding error with user-facing fields (D-08).

    Attributes:
        user_message: Human-readable description of what went wrong.
        resolution: Actionable step the user can take to resolve it.
        status_code: HTTP status code for the API response (default 400).
    """

    def __init__(self, user_message: str, resolution: str, status_code: int = 400) -> None:
        self.user_message = user_message
        self.resolution = resolution
        self.status_code = status_code
        super().__init__(user_message)


class OnboardingValidationError(OnboardingError):
    """Raised for bad input (422 Unprocessable Entity) (D-09).

    Examples: invalid step name, invalid via surface.
    """

    def __init__(self, user_message: str, resolution: str) -> None:
        super().__init__(user_message, resolution, status_code=422)


class OnboardingStateError(OnboardingError):
    """Raised for invalid state transitions (409 Conflict) (D-09).

    Reserved for future state machine enforcement if D-07 is ever relaxed.
    """

    def __init__(self, user_message: str, resolution: str) -> None:
        super().__init__(user_message, resolution, status_code=409)
