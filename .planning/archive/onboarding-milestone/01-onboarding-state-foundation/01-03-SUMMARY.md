---
phase: 01-onboarding-state-foundation
plan: "03"
subsystem: backend-api
tags: [onboarding, api-routes, exception-handler, tests, fastapi]
dependency_graph:
  requires:
    - "01-01"  # error hierarchy, schemas, model
    - "01-02"  # migration, service layer
  provides:
    - GET /api/onboarding/status
    - PATCH /api/onboarding/status
    - OnboardingError exception handler
  affects:
    - src/career_os/main.py
tech_stack:
  added: []
  patterns:
    - FastAPI APIRouter with query params (not path params) for profile_id
    - App-level exception handler returning structured {error, resolution} JSON
    - TestClient integration tests using db_session fixture override
key_files:
  created:
    - src/career_os/api/onboarding.py
  modified:
    - src/career_os/main.py
    - tests/test_onboarding_api.py
decisions:
  - OnboardingError exception handler placed after SlowAPI handler block using @app.exception_handler decorator pattern
  - onboarding_router import alphabetically ordered after oauth by ruff isort (oa < on)
  - Unused `import pytest` removed by ruff (no pytest.mark/raises used directly)
metrics:
  duration_seconds: 297
  duration_human: "~5 min"
  completed_date: "2026-04-20"
  tasks_completed: 3
  files_created: 1
  files_modified: 2
---

# Phase 01 Plan 03: API Routes and Test Suite Summary

**One-liner:** FastAPI GET+PATCH /api/onboarding/status wired with structured OnboardingError handler and 12-test integration suite covering INF-01/INF-02/INF-03.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create GET and PATCH /api/onboarding/status routes | 3c20f97 | src/career_os/api/onboarding.py (created) |
| 2 | Register onboarding router and exception handler in main.py | ffb2a12 | src/career_os/main.py |
| 3 | Write full test suite for INF-01, INF-02, INF-03 | 969a583 | tests/test_onboarding_api.py |

## What Was Built

**src/career_os/api/onboarding.py** — Two routes on `router = APIRouter(prefix="/api/onboarding")`:
- `GET /status?profile_id=N` — validates profile exists (404 if not), delegates to `get_onboarding_status()`. Returns synthesized empty state if no OnboardingState row exists yet.
- `PATCH /status?profile_id=N` — validates profile exists (404 if not), delegates to `mark_step_complete()`. OnboardingValidationError (unknown step) propagates to app-level handler.

**src/career_os/main.py** — Two additions:
- `from career_os.api.onboarding import router as onboarding_router` (alphabetically after oauth imports per ruff isort)
- `app.include_router(onboarding_router)` in the include_router block
- `@app.exception_handler(OnboardingError)` returning `{"error": user_message, "resolution": resolution}` JSON — no stack traces, no exception types in response body

**tests/test_onboarding_api.py** — 12 tests replacing 8 stubs:

| Test | Requirement | What it verifies |
|------|-------------|------------------|
| test_get_status_no_state | INF-03/A2 | Synthesized empty state for new profile |
| test_get_status_missing_profile | INF-03 | 404 for unknown profile |
| test_patch_step_creates_state | INF-03/D-05 | Row created, timestamp set, progress_pct > 0 |
| test_patch_step_idempotent | INF-03/D-06 | Repeat PATCH preserves original timestamp |
| test_patch_missing_profile | INF-03 | 404 for unknown profile on PATCH |
| test_patch_invalid_step_returns_422 | INF-02/D-09/D-10 | {"error","resolution"} keys, no "detail" |
| test_error_response_has_no_stack_trace | INF-02/D-10 | No Traceback in response body |
| test_patch_invalid_via_returns_422 | INF-02 | Pydantic Literal rejects "mobile" |
| test_patch_all_steps_complete | INF-01 | All 7 steps → is_complete=True, progress_pct=100 |
| test_get_reflects_patch | INF-01 | GET after PATCH shows updated state |
| test_error_fields | INF-02/D-08 | OnboardingError hierarchy field contracts |
| test_state_persisted | INF-01/D-01/D-13 | Direct service layer DB row creation |

## Test Results

```
12 passed in 0.20s  (test_onboarding_api.py)
2933 passed, 2 pre-existing failures in test_md_to_pdf.py (unrelated to this plan)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Lint] ruff isort reordered onboarding import after oauth imports**
- **Found during:** Task 2 post-commit ruff check
- **Issue:** `onboarding` placed alphabetically before `oauth` in import block, but ruff isort sorts by full module path string — `career_os.api.oauth` < `career_os.api.onboarding` because 'oa' < 'on'
- **Fix:** Ran `ruff check --fix` which reordered the import; re-committed after ruff-format hook reformatted
- **Files modified:** src/career_os/main.py

**2. [Rule 3 - Lint] Removed unused `import pytest` from test file**
- **Found during:** Task 3 ruff check
- **Issue:** Test file had `import pytest` but no direct uses of pytest API (no `pytest.mark`, `pytest.raises`, etc.)
- **Fix:** `ruff check --fix` removed the import; all 12 tests still passed

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes beyond what the plan's threat model covers (T-1-05 through T-1-10). All mitigations implemented as specified:
- T-1-05/T-1-06: Profile existence validated in both routes before service calls
- T-1-07: Exception handler returns only {error, resolution} — verified by test_error_response_has_no_stack_trace
- T-1-08: Step validation in service layer raises OnboardingValidationError
- T-1-09: Pydantic Literal["cli","web"] on via field — verified by test_patch_invalid_via_returns_422

## Known Stubs

None — all routes wired with real data, no hardcoded responses or placeholder values.

## Self-Check: PASSED
