# Phase 1: CI Optimization - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver fast, targeted CI test feedback on PRs by adding pytest markers, path-based job filtering, selective test execution via testmon, venv caching, JUnit XML output, and PR test result comments. No test behavior changes — only reorganization and speedup of existing CI.

</domain>

<decisions>
## Implementation Decisions

### Auto-marking Strategy
- **D-01:** Fixture-based auto-marking in conftest.py — tests using `db_session`, `client`, `authenticated_client`, or `db_engine` fixtures are auto-marked `integration`; all others are auto-marked `unit`. Uses `pytest_collection_modifyitems` hook.
- **D-02:** Slow tests auto-detected via timeout threshold (>5s) using `pytest_runtest_makereport` hook. No manual `@pytest.mark.slow` tagging needed.
- **D-03:** Smoke marker = health check only (1-2 tests). Regression marker = deferred to Phase 3 (ADV-01 golden set). Phase 1 focuses on unit/integration/slow.
- **D-04:** All 5 markers (unit, integration, slow, smoke, regression) registered in `pyproject.toml` `[tool.pytest.ini_options]` with descriptions to suppress warnings.

### CI Job Structure
- **D-05:** Keep monolithic `backend` job — skip entire job via dorny/paths-filter when only frontend/docs files change. No job splitting.
- **D-06:** Add `ci-complete` gate job (`if: always()`, checks for failures across all jobs). Make this the ONLY required status check in branch protection.
- **D-07:** Docs-only PRs (only .md files) skip ALL test jobs. ci-complete still runs and passes.
- **D-08:** Frontend job gets symmetric path-filter skip condition — skips when only backend files change.
- **D-09:** Shared config files (`docker-compose*`, `.github/workflows/ci.yml`) trigger BOTH backend and frontend jobs.
- **D-10:** Main branch pushes bypass path filtering — always run full suite. Path filtering only applies to PRs.
- **D-11:** Keep current concurrency settings as-is (cancel-in-progress on non-main branches).

### PR Test Feedback
- **D-12:** PR comments show summary + failures only — pass/fail/skip counts and duration for green PRs, expanded failure details for red ones.
- **D-13:** Combined single PR comment with backend and frontend sections (not separate comments).
- **D-14:** Update existing comment on each push (marker-based upsert, same pattern as SonarCloud comment).
- **D-15:** Include testmon skip count ("X tests skipped by testmon") in summary for selective execution visibility.
- **D-16:** Upload JUnit XML as workflow artifact with standard retention (alongside coverage XML).
- **D-17:** Show current run duration only — no duration delta comparison against previous runs.
- **D-18:** Add `@vitest/junit-reporter` to frontend dev deps for JUnit XML output feeding into the combined PR comment.
- **D-19:** No test-to-code mapping hints in failure output — keep failure details simple (message + file location).

### testmon Cache
- **D-20:** Cache key: `testmon-py311-{hash of pyproject.toml}`. Shared across all PRs on same deps version. Invalidates when deps change.
- **D-21:** On cache miss, testmon runs full suite and builds fresh .testmondata. No special fallback logic.
- **D-22:** testmon on PRs (fast, selective), `--cov` on main pushes (full coverage report). Mutually exclusive — never combined.
- **D-23:** Full venv cache keyed to `venv-py311-{hash of pyproject.toml}`. Skip pip install entirely on cache hit.
- **D-24:** .testmondata gitignored — lives only in CI cache and local dev.
- **D-25:** testmon available for local dev use — added to dev dependencies, documented as `pytest --testmon` workflow.

### Additional Decisions
- **D-26:** Keep npm cache via setup-node (not full node_modules cache). npm ci is fast enough (~10s).
- **D-27:** Alembic migration check always runs when backend job runs — no path filtering for this step.
- **D-28:** No pytest-xdist in Phase 1 — testmon only (addresses root cause of running irrelevant tests, per PROJECT.md decision).
- **D-29:** Keep workflow filename as `ci.yml` — Phase 4 will add `ci-nightly.yml` and `ci-weekly.yml` alongside it.

### Claude's Discretion
- Implementation details of the dorny/paths-filter configuration
- Exact EnricoMi/publish-unit-test-result-action configuration options
- JUnit XML file paths and naming
- Vitest reporter configuration syntax
- conftest.py hook implementation details beyond the described approach

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### CI Configuration
- `.github/workflows/ci.yml` — Current CI workflow to be modified (monolithic backend job, frontend job, sonarcloud, actionlint)
- `pyproject.toml` — pytest config (`[tool.pytest.ini_options]`) where markers will be registered

### Test Infrastructure
- `tests/conftest.py` — Shared fixtures (db_engine, db_session, client, authenticated_client) — these define the integration marker boundary
- `tests/profile_data.py` — Shared test data constants

### Codebase Maps
- `.planning/codebase/TESTING.md` — Comprehensive testing patterns analysis (108 backend files, 22 frontend files, fixture patterns, mocking conventions)
- `.planning/codebase/CONVENTIONS.md` — Coding conventions including commit message format

### Project Context
- `.planning/PROJECT.md` — Key decisions: testmon over xdist, dorny over native path filters, three-layer enforcement
- `.planning/REQUIREMENTS.md` — CI-01 through CI-04 requirement definitions with Linear ticket references (G-329 through G-332)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/conftest.py` — Already defines all integration-indicator fixtures (db_session, client, db_engine, authenticated_client). Auto-marking hook can inspect these directly.
- `.github/workflows/ci.yml` — Existing concurrency config, artifact upload pattern, and SonarCloud comment upsert pattern can be reused for test result comments.
- `frontend/vitest.config.ts` — Existing coverage reporter config; JUnit reporter adds alongside it.

### Established Patterns
- CI uses `actions/upload-artifact@v7` for coverage reports — same pattern for JUnit XML
- SonarCloud PR comment uses marker-based upsert (`<!-- sonarcloud-issues -->`) — test results comment should use same pattern
- `pytest-timeout` already installed with 30s default — slow marker hook can leverage the existing timeout infrastructure

### Integration Points
- `pyproject.toml [tool.pytest.ini_options]` — marker registration goes here
- `tests/conftest.py` — `pytest_collection_modifyitems` and `pytest_runtest_makereport` hooks go here
- `.github/workflows/ci.yml` — dorny/paths-filter, testmon, venv cache, JUnit XML, PR comment, ci-complete job all modify this file
- `.gitignore` — add .testmondata entry

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches for all implementation details.

</specifics>

<deferred>
## Deferred Ideas

- **SonarCloud local pre-checks** — Run SonarLint in VS Code or SonarQube server locally to catch known issues before pushing. Better fit for Phase 2 (Agent-Aware Enforcement) since it's about pre-commit/pre-push quality gates.

</deferred>

---

*Phase: 01-ci-optimization*
*Context gathered: 2026-04-19*
