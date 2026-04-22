---
phase: 01-onboarding-state-foundation
plan: "01"
subsystem: onboarding
tags: [errors, models, schemas, sqlalchemy, pydantic, tdd]
dependency_graph:
  requires: ["01-00"]
  provides: ["errors/onboarding.py", "models/onboarding.py", "schemas/onboarding.py"]
  affects: ["01-02", "01-03"]
tech_stack:
  added: []
  patterns: ["structured error hierarchy", "SQLAlchemy Mapped[] ORM", "Pydantic v2 Literal validation"]
key_files:
  created:
    - src/career_os/errors/__init__.py
    - src/career_os/errors/onboarding.py
    - src/career_os/models/onboarding.py
    - src/career_os/schemas/onboarding.py
    - tests/test_onboarding_errors.py
  modified:
    - src/career_os/models/models.py
decisions:
  - "Used # noqa: F821 on cross-module forward references (OnboardingState, Profile) consistent with existing patterns in models.py for Skill/Goal/CoachingSuggestion"
  - "Did not add from __future__ import annotations to models.py — it was absent before and adding it triggered UP037 on all pre-existing quoted annotations"
  - "Step name validation (invalid step → 422 OnboardingValidationError) deferred to service layer per plan — OnboardingStepUpdate.step is plain str for user-friendly errors"
metrics:
  duration: "9 min"
  completed_date: "2026-04-20"
  tasks_completed: 3
  files_changed: 5
---

# Phase 1 Plan 01: Onboarding State Foundation — Contracts Summary

One-liner: Three pure-definition foundation files — error hierarchy (D-08/D-09), SQLAlchemy model with 14 per-step columns (D-01/D-02), and Pydantic schemas with Literal via validation (D-04/D-05).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (TDD) | OnboardingError hierarchy | d520359 (RED), eb8f9a2 (GREEN) | errors/__init__.py, errors/onboarding.py, tests/test_onboarding_errors.py |
| 2 | OnboardingState SQLAlchemy model | e663e51 | models/onboarding.py, models/models.py |
| 3 | Pydantic schemas | eaf6f35 | schemas/onboarding.py |

## What Was Built

**Error hierarchy** (`src/career_os/errors/onboarding.py`): Three exception classes — `OnboardingError` (base, 400), `OnboardingValidationError` (422), `OnboardingStateError` (409). All carry `user_message`, `resolution`, and `status_code` for structured FastAPI error responses (D-08/D-09/D-10).

**SQLAlchemy model** (`src/career_os/models/onboarding.py`): `OnboardingState(Base)` with `__tablename__ = "onboarding_states"`. Contains 7 step `_at` timestamp columns (D-01), 7 step `_via` string columns (D-02), `current_step` for resume (D-03), `profile_id` FK with `unique=True` (one-to-one per D-11), and `created_at`/`updated_at` audit columns. Profile backref added to `models.py` (`uselist=False`).

**Pydantic schemas** (`src/career_os/schemas/onboarding.py`): `VALID_STEPS` list (7 entries), `OnboardingStepUpdate` with `via: Literal["cli", "web"]` rejecting invalid surfaces at schema validation time (T-1-00 STRIDE mitigation), `OnboardingStatusResponse` with all 14 per-step fields plus computed `next_step`/`is_complete`/`progress_pct` (populated by service layer).

## TDD Gate Compliance

Task 1 followed full RED/GREEN cycle:
- RED commit: `d520359` — 8 tests failing with `ModuleNotFoundError`
- GREEN commit: `eb8f9a2` — 8 tests passing

No REFACTOR phase needed (implementation matched specification exactly).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed spurious `from __future__ import annotations` from models.py**
- **Found during:** Task 2 ruff check
- **Issue:** Adding `from __future__ import annotations` to models.py triggered UP037 on all 18 pre-existing quoted forward references in that file, introducing new lint violations
- **Fix:** Did not add the import (plan says "Add if not present; if already present, no change needed" — it was absent and adding it caused regressions)
- **Files modified:** `src/career_os/models/models.py`
- **Commit:** e663e51

**2. [Rule 2 - Consistency] Used `# noqa: F821` instead of `# type: ignore[name-defined]` on forward references**
- **Found during:** Task 2 ruff check
- **Issue:** `# type: ignore[name-defined]` suppresses mypy but not ruff F821; ruff still reported the undefined name
- **Fix:** Used `# noqa: F821` (same pattern as existing `Skill`/`Goal`/`CoachingSuggestion` forward refs in models.py)
- **Files modified:** `src/career_os/models/models.py`, `src/career_os/models/onboarding.py`
- **Commit:** e663e51

## Known Stubs

None — Plan 01 is pure definitions with no data flow to UI.

## SQLAlchemy Mapper Note

The `Profile.onboarding_state` backref raises `InvalidRequestError` in test sessions that load `career_os.main` without also importing `career_os.models.onboarding`. This is expected and will be resolved in Plan 02 when `onboarding.py` is imported in `alembic/env.py` and registered in the app. The `test_onboarding_api.py` stubs (from Wave 0) fail/error as expected until Plans 02-03.

## Threat Flags

None — Plan 01 creates pure definitions with no network, DB, or request handling.

## Self-Check: PASSED

Files exist:
- FOUND: src/career_os/errors/__init__.py
- FOUND: src/career_os/errors/onboarding.py
- FOUND: src/career_os/models/onboarding.py
- FOUND: src/career_os/schemas/onboarding.py
- FOUND: tests/test_onboarding_errors.py

Commits exist:
- d520359 (RED test)
- eb8f9a2 (GREEN implementation)
- e663e51 (model)
- eaf6f35 (schemas)
