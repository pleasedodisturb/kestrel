---
phase: 03-advanced-testing
plan: 02
subsystem: testing
tags: [property-testing, hypothesis, scoring, state-machine]
dependency_graph:
  requires: [golden-set-regression, deterministic-mock-provider]
  provides: [scoring-property-tests, state-machine-property-tests]
  affects: [tests/property/]
tech_stack:
  added: []
  patterns: [RuleBasedStateMachine, hypothesis-given-strategies, inline-db-session]
key_files:
  created:
    - tests/property/test_scoring_properties.py
    - tests/property/test_state_machine.py
  modified: []
decisions:
  - "Inline DB session creation instead of pytest fixture to avoid Hypothesis health check failures with function-scoped fixtures"
  - "Band monotonicity uses simple threshold function (0-3/3-6/6-10) since no band function exists in scoring.py"
metrics:
  duration: 3m
  completed: 2026-04-20
  tasks: 2
  files_created: 2
  files_modified: 0
  tests_added: 8
---

# Phase 03 Plan 02: Hypothesis Property-Based Tests Summary

Hypothesis property tests proving scoring pipeline invariants (fit_score 0-10, readiness_score 0-100, Pydantic rejection, pipeline-level idempotency, band monotonicity) and state machine completeness via RuleBasedStateMachine exploring 100 random transition sequences.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Hypothesis scoring property tests with pipeline-level idempotency | da3c239 | tests/property/test_scoring_properties.py |
| 2 | State machine property tests with RuleBasedStateMachine | 73ddf1c | tests/property/test_state_machine.py |

## What Was Built

### Scoring Property Tests (tests/property/test_scoring_properties.py)
- **test_fit_score_always_in_range**: 200 examples proving ScoreResult accepts fit_score 0-10
- **test_readiness_score_always_in_range**: 200 examples proving readiness_score 0-100
- **test_fit_score_rejects_out_of_range**: 50 examples proving Pydantic ValidationError for >10
- **test_scoring_idempotent**: 20 examples calling score_job() twice through the full async pipeline with DeterministicScoringMockProvider, asserting fit_score and reasoning are identical
- **test_band_monotonicity**: 200 examples proving higher fit_score never maps to lower band (thresholds: 0-3 low, 3-6 medium, 6-10 high)

### State Machine Property Tests (tests/property/test_state_machine.py)
- **ApplicationStateMachine (RuleBasedStateMachine)**: 100 random transition sequences of 10 steps each, asserting current_status always has a VALID_TRANSITIONS entry and is always a valid ApplicationStatus enum member
- **test_all_statuses_have_transitions**: every ApplicationStatus enum value is a key in VALID_TRANSITIONS, every transition target is a valid ApplicationStatus
- **test_no_self_transitions**: no status can transition to itself, all target sets are non-empty

### Test Quality
- All 8 tests marked `@pytest.mark.property`
- Every test has 2+ meaningful assertions (no `assert True` or bare `is not None`)
- Idempotency test uses inline DB session creation to avoid Hypothesis health check on function-scoped fixtures
- Combined run with regression: 80 passed (72 regression + 8 property)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Hypothesis health check rejects function-scoped fixture**
- **Found during:** Task 1
- **Issue:** Hypothesis raises FailedHealthCheck when a `@given` test uses a function-scoped pytest fixture, because fixtures are not reset between generated inputs
- **Fix:** Replaced the `idempotent_db_session` fixture with an inline `_create_db_session()` helper function that returns (session, cleanup_fn), called directly inside the test with try/finally cleanup
- **Files modified:** tests/property/test_scoring_properties.py
- **Commit:** da3c239

## Verification Results

```
8 passed, 0 failed (pytest tests/property/ -m property -v)
80 passed combined (pytest tests/ -m 'regression or property')
```

## Self-Check: PASSED
