---
phase: 01-ci-optimization
plan: 03
subsystem: ci-workflow
tags: [ci, github-actions, path-filtering, testmon, junit, pr-comments, gate-job]
dependency_graph:
  requires: [pytest-markers, testmon-dep, frontend-junit-xml]
  provides: [ci-path-filtering, ci-testmon-selective, ci-junit-upload, ci-pr-comments, ci-gate-job, ci-venv-cache]
  affects: [.github/workflows/ci.yml]
tech_stack:
  added: [dorny/paths-filter@v3, EnricoMi/publish-unit-test-result-action@v2, actions/cache@v4]
  patterns: [path-filtered-jobs, conditional-test-execution, venv-caching, junit-artifact-upload, gate-job]
key_files:
  created: []
  modified:
    - .github/workflows/ci.yml
decisions:
  - "D-05 through D-10: Path filtering via dorny/paths-filter with shared config triggering both jobs"
  - "D-06: ci-complete gate job as single required status check"
  - "D-12 through D-17: PR test comments via EnricoMi/publish-unit-test-result-action"
  - "D-22: testmon on PRs, --cov on main pushes (mutually exclusive)"
  - "D-23: Full venv cache replacing setup-python cache: pip"
  - "D-26: Keep npm cache via setup-node (unchanged)"
metrics:
  duration: 2m 18s
  completed: "2026-04-19T21:49:32Z"
  tasks: 1/1
  files_changed: 1
---

# Phase 01 Plan 03: CI Workflow Rewrite Summary

Full CI workflow rewrite adding dorny/paths-filter job filtering, testmon selective execution on PRs, venv caching via actions/cache@v4, JUnit XML artifact uploads, PR test result comments via EnricoMi action, and ci-complete gate job.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite ci.yml with path filtering, testmon, venv cache, JUnit XML, PR comments, gate job | 1f646d0 | .github/workflows/ci.yml |

## What Was Built

1. **Changes Job (NEW):** `dorny/paths-filter@v3` detects backend/frontend/docs_only changes. Backend filter includes `src/`, `tests/`, `pyproject.toml`, `alembic.ini`, `config/`, plus shared files (`docker-compose*`, `.github/workflows/ci.yml`). Frontend filter includes `frontend/` plus shared files. Docs-only filter uses negation patterns to exclude code directories. Only runs on `pull_request` events (D-10).

2. **Backend Job (MODIFIED):** Removed `cache: pip` from setup-python. Added full venv cache via `actions/cache@v4` with key `venv-py311-${{ hashFiles('pyproject.toml') }}`. Install step only runs on cache miss. Venv activated via `$GITHUB_PATH` injection. Two conditional pytest steps: `--testmon --junitxml` on PRs, `--cov --junitxml` on main pushes. Testmon cache with key `testmon-py311-${{ hashFiles('pyproject.toml') }}` only on PRs. Coverage upload restricted to non-PR events. JUnit XML upload with `if: always()`. If-condition uses `always()` + `needs.changes.result == 'skipped'` pattern to run unconditionally on push/merge_group and conditionally on PRs.

3. **Frontend Job (MODIFIED):** Added `needs: [changes]` dependency. Same if-condition pattern as backend using `needs.changes.outputs.frontend`. Added JUnit XML upload step for `frontend/test-results/frontend-junit.xml`. Preserved type-check/build disabled comments, npm cache via setup-node, and working-directory default.

4. **Test Results Job (NEW):** Downloads backend and frontend JUnit XML artifacts with `continue-on-error: true` (handles skipped jobs). Publishes via `EnricoMi/publish-unit-test-result-action@v2` with `comment_mode: update` for marker-based upsert. Per-job permissions: `checks: write`, `pull-requests: write`. Only runs on PRs.

5. **CI Complete Gate Job (NEW):** `if: always()`, `needs` all 6 other jobs. Logs all job results. Fails if `contains(needs.*.result, 'failure')`. Designed to be the single required status check in branch protection.

6. **SonarCloud Job (PRESERVED):** No changes to sonarcloud job -- kept exact existing implementation including pinned action SHAs, quality gate, and PR comment script.

7. **Actionlint Job (PRESERVED):** No changes -- kept exactly as-is.

## Verification Results

- YAML valid (pyyaml `safe_load` succeeds)
- All 7 jobs present: changes, backend, actionlint, frontend, test-results, sonarcloud, ci-complete
- `dorny/paths-filter`: 1 occurrence (changes job)
- `publish-unit-test-result-action`: 1 occurrence (test-results job)
- `actions/cache@v4`: 2 occurrences (venv cache + testmon cache)
- `testmon`: 5 occurrences (cache step, pytest PR step, cache key, related strings)
- `cache: pip` NOT present on setup-python
- Backend if-condition checks `needs.changes.outputs.backend`
- Frontend if-condition checks `needs.changes.outputs.frontend`
- test-results job has `checks: write` and `pull-requests: write` permissions
- No file deletions in commit

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None.

## Threat Surface Scan

No new threat surfaces beyond those documented in the plan's threat model. All mitigations implemented:
- T-01-04: venv cache key includes `hashFiles('pyproject.toml')`
- T-01-05: `checks: write` and `pull-requests: write` scoped only to test-results job
- T-01-06: No user-controlled strings in `run:` steps
- T-01-08: testmon cache key includes `hashFiles('pyproject.toml')`

## Self-Check: PASSED
