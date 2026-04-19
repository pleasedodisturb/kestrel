---
phase: 01-ci-optimization
plan: 03
subsystem: ci-workflow
tags: [ci, github-actions, path-filtering, testmon, junit, pr-comments]
dependency_graph:
  requires: [pytest-markers, testmon-dep, frontend-junit-xml]
  provides: [ci-path-filtering, ci-testmon, ci-junit-upload, ci-pr-comments, ci-gate-job]
  affects: [.github/workflows/ci.yml]
tech_stack:
  added: [dorny/paths-filter@v3, EnricoMi/publish-unit-test-result-action@v2, actions/cache@v4]
  patterns: [path-based-job-filtering, venv-caching, conditional-test-execution, gate-job]
key_files:
  created: []
  modified:
    - .github/workflows/ci.yml
decisions:
  - "D-05/D-08: Backend and frontend jobs skip via dorny/paths-filter when only unrelated files change"
  - "D-06: ci-complete gate job is the single required status check"
  - "D-07: Docs-only PRs skip both backend and frontend jobs"
  - "D-09: Shared config files (docker-compose*, ci.yml) listed in both backend and frontend filters"
  - "D-10: Main pushes and merge_group bypass path filtering (changes job only runs on PRs)"
  - "D-22: testmon on PRs, coverage on main (mutually exclusive)"
  - "D-23: Full venv cache replaces setup-python cache:pip"
  - "D-12-D-17: PR comments via EnricoMi/publish-unit-test-result-action with combined backend+frontend results"
metrics:
  duration: 2m 53s
  completed: "2026-04-19T21:50:41Z"
  tasks: 1/1
  files_changed: 1
---

# Phase 01 Plan 03: CI Workflow Rewrite Summary

Complete CI workflow overhaul with dorny/paths-filter for job skipping, full venv caching via actions/cache@v4, conditional testmon (PRs) vs coverage (main), JUnit XML artifacts, and EnricoMi/publish-unit-test-result-action for PR test result comments.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add changes job, restructure backend with venv cache + testmon, add JUnit XML upload, test-results job, ci-complete gate | b7ea5c1 | .github/workflows/ci.yml |

## What Was Built

1. **Changes Job (NEW):** Uses `dorny/paths-filter@v3` to detect backend/frontend/docs_only file changes. Only runs on `pull_request` events. Shared config files (`docker-compose*`, `.github/workflows/ci.yml`) listed in both backend and frontend filters so they trigger both jobs (D-09).

2. **Backend Job (MODIFIED):**
   - Path filtering: `if: always() && (needs.changes.result == 'skipped' || needs.changes.outputs.backend == 'true') && (needs.changes.result == 'skipped' || needs.changes.outputs.docs_only != 'true')` -- runs unconditionally on push/merge_group (changes job skipped), conditionally on PRs.
   - Venv caching: `actions/cache@v4` with key `venv-py311-${{ hashFiles('pyproject.toml') }}`. Removed `cache: pip` from `setup-python`. On cache hit, pip install is skipped entirely. Venv activated via `GITHUB_PATH`.
   - Testmon: `actions/cache@v4` for `.testmondata` (PR only). Conditional test steps: `pytest --testmon --junitxml` on PRs, `pytest --cov --junitxml` on main.
   - JUnit XML: `--junitxml=test-results/backend-junit.xml` in both pytest commands, uploaded via `actions/upload-artifact@v7`.
   - Coverage upload: Now conditional on non-PR events only (coverage only generated on main).

3. **Frontend Job (MODIFIED):** Same path filtering pattern as backend using `needs.changes.outputs.frontend`. Added JUnit XML upload step for `frontend/test-results/frontend-junit.xml` (produced by vitest config from Plan 02).

4. **Test Results Job (NEW):** Downloads backend and frontend JUnit XML artifacts (with `continue-on-error: true` for skipped suites), publishes combined PR comment via `EnricoMi/publish-unit-test-result-action@v2` with `comment_mode: update`. Per-job permissions: `checks: write`, `pull-requests: write`.

5. **CI Complete Gate Job (NEW):** `if: always()`, depends on all jobs, checks `contains(needs.*.result, 'failure')`. Logs all job results for debugging. Designed to be the single required status check in branch protection.

6. **Preserved Unchanged:** `actionlint` job, `sonarcloud` job (with full SonarCloud PR comment script and pinned action hashes).

## Verification Results

- YAML validation: passed (js-yaml)
- All 7 jobs present: changes, backend, actionlint, frontend, test-results, sonarcloud, ci-complete
- dorny/paths-filter@v3: present
- publish-unit-test-result-action@v2: present
- actions/cache@v4: present (venv + testmon)
- testmon in PR test step: present
- JUnit XML in both pytest commands: present
- No `cache: pip` on setup-python: confirmed
- Backend if-condition with changes.outputs.backend: present
- Frontend if-condition with changes.outputs.frontend: present
- test-results job permissions (checks:write, pull-requests:write): present

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None.

## Threat Surface Scan

No new threat surfaces beyond those documented in the plan's threat model. All permissions are scoped to specific jobs (test-results gets checks:write and pull-requests:write; sonarcloud retains its existing pull-requests:write). No user-controlled strings flow into `run:` steps.

## Self-Check: PASSED
