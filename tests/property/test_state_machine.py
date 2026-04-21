"""Hypothesis stateful property tests for application state machine.

Proves:
- RuleBasedStateMachine explores arbitrary transition sequences without
  reaching invalid states (D-05)
- Every ApplicationStatus has an entry in VALID_TRANSITIONS
- Every transition target is a valid ApplicationStatus
- No self-transitions exist in the state machine
"""

from __future__ import annotations

import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, rule

from career_os.schemas.applications import (
    VALID_TRANSITIONS,
    ApplicationStatus,
    is_valid_transition,
)

# ---------------------------------------------------------------------------
# RuleBasedStateMachine: explores arbitrary transition sequences
# ---------------------------------------------------------------------------


class ApplicationStateMachine(RuleBasedStateMachine):
    """Verify the application state machine never reaches an invalid state.

    Hypothesis generates random sequences of transition attempts. After each
    attempt (valid or invalid), we assert two invariants:
    1. Current status always has an entry in VALID_TRANSITIONS
    2. Current status is always a valid ApplicationStatus enum member
    """

    def __init__(self):
        super().__init__()
        self.current_status: ApplicationStatus | None = None
        self.transition_count: int = 0

    @initialize()
    def start(self):
        self.current_status = ApplicationStatus.discovered

    @rule(target_status=st.sampled_from(list(ApplicationStatus)))
    def attempt_transition(self, target_status: ApplicationStatus):
        valid = is_valid_transition(self.current_status.value, target_status.value)
        if valid:
            self.current_status = target_status
            self.transition_count += 1

        # Invariant 1: every status has an entry in VALID_TRANSITIONS
        assert self.current_status in VALID_TRANSITIONS, (
            f"{self.current_status} missing from VALID_TRANSITIONS after "
            f"{self.transition_count} transitions"
        )
        # Invariant 2: current status is always a valid ApplicationStatus
        assert isinstance(self.current_status, ApplicationStatus), (
            f"{self.current_status} is not a valid ApplicationStatus after "
            f"{self.transition_count} transitions"
        )


TestApplicationStateMachine = ApplicationStateMachine.TestCase
TestApplicationStateMachine.settings = settings(max_examples=100, stateful_step_count=10)
# Apply the property marker so pytest -m property picks it up
TestApplicationStateMachine = pytest.mark.property(TestApplicationStateMachine)

# ---------------------------------------------------------------------------
# Standalone property tests
# ---------------------------------------------------------------------------


@pytest.mark.property
def test_all_statuses_have_transitions() -> None:
    """Every ApplicationStatus member is a key in VALID_TRANSITIONS,
    and every transition target is a valid ApplicationStatus.
    """
    for status in ApplicationStatus:
        assert status in VALID_TRANSITIONS, f"{status} missing from VALID_TRANSITIONS"

    for status, targets in VALID_TRANSITIONS.items():
        for target in targets:
            assert isinstance(target, ApplicationStatus), (
                f"{target} in VALID_TRANSITIONS[{status}] is not ApplicationStatus"
            )


@pytest.mark.property
def test_no_self_transitions() -> None:
    """No status has a self-transition (status -> same status)."""
    for status, targets in VALID_TRANSITIONS.items():
        assert status not in targets, f"{status} has a self-transition"

    # Second meaningful assertion: all target sets are non-empty
    for status, targets in VALID_TRANSITIONS.items():
        assert len(targets) > 0, f"{status} has no valid transitions"
