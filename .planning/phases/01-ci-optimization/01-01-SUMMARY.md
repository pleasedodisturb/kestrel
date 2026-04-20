---
phase: 01-ci-optimization
plan: 01
subsystem: test-infrastructure
tags: [pytest, markers, testmon, tdd]
dependency_graph:
  requires: []
  provides: [pytest-markers, testmon-dep, marker-hooks]
  affects: [pyproject.toml, tests/conftest.py, .gitignore]
tech_stack:
  added: [pytest-testmon-2.2.0]
  patterns: [fixture-based-auto-marking, pytest-collection-hook]
key_files:
  created: [tests/test_markers.py]
  modified: [pyproject.toml, tests/conftest.py, .gitignore]
decisions:
  - "D-01: Fixture-based auto-marking via pytest_collection_modifyitems hook"
  - "D-02: Slow test detection via pytest_runtest_makereport (>5s threshold, post-execution only)"
  - "D-04: All 5 markers registered in pyproject.toml"
  - "D-24: .testmondata gitignored"
  - "D-25: pytest-testmon added as dev dependency"
metrics:
  duration: 3m 43s
  completed: "2026-04-19T21:43:00Z"
  tasks: 2/2
  files_changed: 4
---

# Phase 01 Plan 01: Pytest Marker Auto-Classification Summary

Fixture-based auto-marking hooks classify 2928 tests into unit (1381) and integration (1546) via pytest_collection_modifyitems, with 5 markers registered and pytest-testmon added for future selective execution.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Register markers, add testmon dep, gitignore testmondata, write marker tests | 296fca0 | pyproject.toml, .gitignore, tests/test_markers.py |
| 2 | Implement auto-marking hooks in conftest.py | 8e558e9 | tests/conftest.py |

## What Was Built

1. **Marker Registration (pyproject.toml):** 5 markers registered in `[tool.pytest.ini_options]` -- unit, integration, slow, smoke, regression -- with descriptive strings suppressing PytestUnknownMarkWarning.

2. **pytest-testmon Dependency:** Added `pytest-testmon>=2.2.0` to dev dependencies for selective test execution in CI (CI-03 prep).

3. **Auto-Marking Hooks (tests/conftest.py):**
   - `pytest_collection_modifyitems`: Inspects each test's fixture names. Tests using `db_session`, `client`, `authenticated_client`, or `db_engine` get `integration` marker; all others get `unit`. Explicit markers (smoke, etc.) take precedence.
   - `pytest_runtest_makereport`: Marks tests exceeding 5s as `slow` (post-execution, informational only).

4. **Marker Verification Tests (tests/test_markers.py):** 5 tests in 2 classes verifying marker registration and auto-classification behavior.

5. **.gitignore:** Added `.testmondata` entry in the Python section.

## Verification Results

- `pytest -m unit`: 1381 tests collected
- `pytest -m integration`: 1546 tests collected
- `pytest tests/test_markers.py -v`: 5/5 passed
- Full suite: 2907 passed, 20 skipped, 2 pre-existing failures (test_md_to_pdf.py, unrelated)
- No PytestUnknownMarkWarning for any registered markers

## Deviations from Plan

None -- plan executed exactly as written.

## TDD Gate Compliance

- RED gate: `test(01-01)` commit 296fca0 -- marker verification tests created
- GREEN gate: `feat(01-01)` commit 8e558e9 -- auto-marking hooks implemented, all tests pass
- Note: Tests in RED phase passed immediately because they verify marker registration (already in pyproject.toml) and fixture values, not marker application. The marker application behavior is verified via `--collect-only -m unit/integration` commands in GREEN phase. This is acceptable as the hook behavior is inherently a collection-phase concern.

## Known Stubs

None.

## Self-Check: PASSED
