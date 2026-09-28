# Phase 1: CI Optimization - Research

**Researched:** 2026-04-19
**Domain:** GitHub Actions CI, pytest markers, selective test execution, PR feedback
**Confidence:** HIGH

## Summary

Phase 1 transforms the existing monolithic CI workflow into a targeted, fast-feedback system. The core changes are: (1) auto-classifying 108 backend test files as unit/integration via conftest.py fixture inspection, (2) skipping irrelevant CI jobs via dorny/paths-filter, (3) running only affected tests via pytest-testmon on PRs, and (4) publishing JUnit XML results as PR comments via EnricoMi/publish-unit-test-result-action.

All four requirements are well-served by mature, widely-adopted tools. The existing CI workflow (`ci.yml`) is clean and well-structured -- modifications are additive (new jobs, new steps, new pytest config) rather than rewrites. The SonarCloud PR comment pattern already in the workflow provides a proven template for marker-based upsert comments.

**Primary recommendation:** Implement as four sequential waves: (1) pytest markers + pyproject.toml registration, (2) dorny/paths-filter + ci-complete gate job, (3) testmon + venv cache, (4) JUnit XML + PR comment action. Each wave is independently testable.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Fixture-based auto-marking in conftest.py -- tests using `db_session`, `client`, `authenticated_client`, or `db_engine` fixtures are auto-marked `integration`; all others are auto-marked `unit`. Uses `pytest_collection_modifyitems` hook.
- **D-02:** Slow tests auto-detected via timeout threshold (>5s) using `pytest_runtest_makereport` hook. No manual `@pytest.mark.slow` tagging needed.
- **D-03:** Smoke marker = health check only (1-2 tests). Regression marker = deferred to Phase 3 (ADV-01 golden set). Phase 1 focuses on unit/integration/slow.
- **D-04:** All 5 markers (unit, integration, slow, smoke, regression) registered in `pyproject.toml` `[tool.pytest.ini_options]` with descriptions to suppress warnings.
- **D-05:** Keep monolithic `backend` job -- skip entire job via dorny/paths-filter when only frontend/docs files change. No job splitting.
- **D-06:** Add `ci-complete` gate job (`if: always()`, checks for failures across all jobs). Make this the ONLY required status check in branch protection.
- **D-07:** Docs-only PRs (only .md files) skip ALL test jobs. ci-complete still runs and passes.
- **D-08:** Frontend job gets symmetric path-filter skip condition -- skips when only backend files change.
- **D-09:** Shared config files (`docker-compose*`, `.github/workflows/ci.yml`) trigger BOTH backend and frontend jobs.
- **D-10:** Main branch pushes bypass path filtering -- always run full suite. Path filtering only applies to PRs.
- **D-11:** Keep current concurrency settings as-is (cancel-in-progress on non-main branches).
- **D-12:** PR comments show summary + failures only -- pass/fail/skip counts and duration for green PRs, expanded failure details for red ones.
- **D-13:** Combined single PR comment with backend and frontend sections (not separate comments).
- **D-14:** Update existing comment on each push (marker-based upsert, same pattern as SonarCloud comment).
- **D-15:** Include testmon skip count ("X tests skipped by testmon") in summary for selective execution visibility.
- **D-16:** Upload JUnit XML as workflow artifact with standard retention (alongside coverage XML).
- **D-17:** Show current run duration only -- no duration delta comparison against previous runs.
- **D-18:** Add `@vitest/junit-reporter` to frontend dev deps for JUnit XML output feeding into the combined PR comment.
- **D-19:** No test-to-code mapping hints in failure output -- keep failure details simple (message + file location).
- **D-20:** Cache key: `testmon-py311-{hash of pyproject.toml}`. Shared across all PRs on same deps version. Invalidates when deps change.
- **D-21:** On cache miss, testmon runs full suite and builds fresh .testmondata. No special fallback logic.
- **D-22:** testmon on PRs (fast, selective), `--cov` on main pushes (full coverage report). Mutually exclusive -- never combined.
- **D-23:** Full venv cache keyed to `venv-py311-{hash of pyproject.toml}`. Skip pip install entirely on cache hit.
- **D-24:** .testmondata gitignored -- lives only in CI cache and local dev.
- **D-25:** testmon available for local dev use -- added to dev dependencies, documented as `pytest --testmon` workflow.
- **D-26:** Keep npm cache via setup-node (not full node_modules cache). npm ci is fast enough (~10s).
- **D-27:** Alembic migration check always runs when backend job runs -- no path filtering for this step.
- **D-28:** No pytest-xdist in Phase 1 -- testmon only.
- **D-29:** Keep workflow filename as `ci.yml`.

### Claude's Discretion
- Implementation details of the dorny/paths-filter configuration
- Exact EnricoMi/publish-unit-test-result-action configuration options
- JUnit XML file paths and naming
- Vitest reporter configuration syntax
- conftest.py hook implementation details beyond the described approach

### Deferred Ideas (OUT OF SCOPE)
- SonarCloud local pre-checks -- deferred to Phase 2

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CI-01 | pytest markers (unit/integration/regression/smoke/slow) applied to all 108 backend test files with conftest.py auto-marking (G-329) | `pytest_collection_modifyitems` hook inspects fixture names; 5 markers registered in pyproject.toml; ~80 integration + ~28 unit files identified by fixture usage pattern |
| CI-02 | dorny/paths-filter detects changed components and skips unaffected CI jobs (G-330) | dorny/paths-filter@v3 (stable, v4 is Node 24 update only); outputs drive `if:` conditions on backend/frontend jobs; ci-complete gate job pattern documented |
| CI-03 | pytest-testmon runs only affected tests on PR builds with cached .testmondata (G-331) | pytest-testmon 2.2.0; cache key strategy documented; `--testmon` flag on PRs, `--cov` on main; `--testmon-nocollect` forced when running under coverage |
| CI-04 | Full venv cached, JUnit XML output, PR test result comments (G-332) | venv cache via actions/cache@v4; `--junitxml` for pytest; vitest built-in junit reporter (no separate package); EnricoMi/publish-unit-test-result-action@v2 for PR comments |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Test marker classification | Test Infrastructure (conftest.py) | -- | Fixture inspection is a pytest concern, lives in test config |
| Path-based job filtering | CI/CD (GitHub Actions) | -- | Workflow-level conditional execution |
| Selective test execution | Test Infrastructure (testmon) | CI/CD (cache) | testmon is a pytest plugin; CI provides cache persistence |
| PR test feedback | CI/CD (GitHub Actions) | -- | Workflow step using JUnit XML artifacts |
| Venv caching | CI/CD (GitHub Actions) | -- | actions/cache restores installed dependencies |
| JUnit XML generation | Test Infrastructure (pytest + vitest) | CI/CD (artifacts) | Test runners produce XML; CI uploads as artifacts |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest-testmon | 2.2.0 | Selective test execution based on changed code | Only mature pytest plugin for file-level test selection; active maintenance [VERIFIED: pypi.org] |
| dorny/paths-filter | v3 | Skip CI jobs based on changed file paths | De facto standard for GitHub Actions path filtering; v3 is stable, v4 is only a Node runtime bump [VERIFIED: github.com/dorny/paths-filter/releases] |
| EnricoMi/publish-unit-test-result-action | v2 (2.23.0) | Publish JUnit XML as PR comments | Most popular GH Action for test result reporting; auto-updates comments, supports multiple file patterns [VERIFIED: github.com/EnricoMi releases] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| actions/cache | v4 | Cache venv and testmon data between runs | Every CI run -- venv cache and testmon cache |
| vitest (built-in junit) | 4.1.x | JUnit XML output from frontend tests | Already installed; use `reporters: ['default', 'junit']` config -- NO separate package needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| dorny/paths-filter | Native `paths:` in `on.push/pull_request` | Native paths cannot be used for job-level skipping (only trigger-level); breaks required status checks when job doesn't run |
| EnricoMi/publish-unit-test-result-action | Custom github-script | Reinventing JUnit parsing, comment formatting, upsert logic -- exactly what "Don't Hand-Roll" warns against |
| pytest-testmon | pytest-xdist (parallel) | xdist runs all tests faster but doesn't skip irrelevant tests; testmon addresses root cause per PROJECT.md decision |

### CRITICAL CORRECTION: D-18

**D-18 states:** "Add `@vitest/junit-reporter` to frontend dev deps"
**Reality:** Vitest has a built-in `junit` reporter since v1.x. No separate package `@vitest/junit-reporter` exists on npm. [VERIFIED: vitest.dev/guide/reporters, npm registry]

**Correct approach:** Add `reporters: ['default', ['junit', { outputFile: 'test-results/frontend-junit.xml' }]]` to `vitest.config.ts` test config. Zero new dependencies needed.

**Installation (backend only):**
```bash
# Add to pyproject.toml [project.optional-dependencies] dev section
pip install pytest-testmon>=2.2.0
```

## Architecture Patterns

### System Architecture Diagram

```
PR Push Event
    |
    v
[ci.yml workflow triggers]
    |
    v
[changes job] -- dorny/paths-filter
    |--- outputs.backend: true/false
    |--- outputs.frontend: true/false
    |--- outputs.docs_only: true/false
    |
    +---> [backend job] (if: backend == 'true' OR github.ref == main)
    |       |
    |       +-> Restore venv cache (actions/cache, key: venv-py311-{hash})
    |       +-> pip install (skip on cache hit)
    |       +-> Lint (ruff)
    |       +-> Alembic migration check
    |       +-> pytest --testmon --junitxml (PR) OR pytest --cov (main)
    |       +-> Upload JUnit XML artifact
    |       +-> API smoke test
    |       +-> Security audit + PII check
    |
    +---> [frontend job] (if: frontend == 'true' OR github.ref == main)
    |       |
    |       +-> npm ci
    |       +-> Lint (eslint)
    |       +-> vitest run (with junit reporter) --coverage
    |       +-> Upload JUnit XML artifact
    |       +-> Security audit
    |
    +---> [actionlint job] (always runs)
    |
    +---> [test-results job] (needs: backend, frontend; if: always())
    |       |
    |       +-> Download JUnit XML artifacts
    |       +-> EnricoMi/publish-unit-test-result-action (PR comment)
    |
    +---> [sonarcloud job] (needs: backend, frontend)
    |
    +---> [ci-complete job] (needs: all jobs; if: always())
            |
            +-> Check all job results, fail if any failed
            +-> This is the ONLY required status check
```

### Recommended Changes to Existing Files

```
.github/workflows/ci.yml    # Major modifications: add changes job, ci-complete job,
                             #   test-results job, modify backend/frontend jobs
pyproject.toml               # Add markers + testmon to dev deps
tests/conftest.py            # Add pytest_collection_modifyitems + pytest_runtest_makereport hooks
frontend/vitest.config.ts    # Add junit reporter config
.gitignore                   # Add .testmondata
```

### Pattern 1: Auto-Marking via Fixture Inspection

**What:** `pytest_collection_modifyitems` hook inspects each test's fixture names and adds markers automatically
**When to use:** When test classification can be derived from infrastructure dependencies (fixtures) rather than manual tagging

```python
# Source: pytest docs (hook reference) + project-specific fixture names
INTEGRATION_FIXTURES = frozenset({"db_session", "client", "authenticated_client", "db_engine"})

def pytest_collection_modifyitems(items):
    """Auto-mark tests as unit or integration based on fixture usage."""
    for item in items:
        # Skip items that already have explicit markers
        if any(item.get_closest_marker(m) for m in ("unit", "integration", "smoke")):
            continue
        fixture_names = set(getattr(item, "fixturenames", []))
        if fixture_names & INTEGRATION_FIXTURES:
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)
```

**Key detail:** `item.fixturenames` includes indirect fixtures. A test using `profile` fixture (which depends on `db_session`) WILL have `db_session` in its `fixturenames` list because pytest resolves the full fixture dependency chain. This means the auto-marking correctly classifies tests that transitively depend on integration fixtures. [VERIFIED: pytest docs on fixturenames resolution]

### Pattern 2: Slow Test Detection via Runtime Hook

**What:** `pytest_runtest_makereport` hook records actual test duration and marks slow tests after execution
**When to use:** When slow thresholds should be data-driven rather than manually tagged

```python
# Source: pytest hook documentation
def pytest_runtest_makereport(item, call):
    """Mark tests that exceed the slow threshold after execution."""
    if call.when == "call" and call.duration > 5.0:
        item.add_marker(pytest.mark.slow)
```

**Important caveat:** This hook fires AFTER the test runs, so `pytest -m slow` cannot select slow tests before execution. The slow marker is informational for reporting purposes. If pre-selection is needed later, a JSON manifest from a previous run would be required. For Phase 1, the slow marker is used for visibility in test reports only. [ASSUMED]

### Pattern 3: dorny/paths-filter Job Conditionals

**What:** A dedicated `changes` job outputs boolean flags consumed by downstream jobs
**When to use:** When different CI jobs should run based on which files changed

```yaml
# Source: dorny/paths-filter README (github.com/dorny/paths-filter)
jobs:
  changes:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: read
    outputs:
      backend: ${{ steps.filter.outputs.backend }}
      frontend: ${{ steps.filter.outputs.frontend }}
      docs_only: ${{ steps.filter.outputs.docs_only }}
    steps:
      - uses: actions/checkout@v6
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            backend:
              - 'src/**'
              - 'tests/**'
              - 'pyproject.toml'
              - 'alembic.ini'
              - 'config/**'
            frontend:
              - 'frontend/**'
            shared:
              - 'docker-compose*'
              - '.github/workflows/ci.yml'
            docs_only:
              - '**/*.md'
              - 'docs/**'
              - '!frontend/**'
              - '!src/**'
              - '!tests/**'
```

**Version note:** Use `@v3` not `@v4`. v4 only updates the Node runtime to 24; v3 is functionally identical and more widely tested. The v4 release (March 2023) has no new features. [VERIFIED: github.com/dorny/paths-filter/releases]

### Pattern 4: ci-complete Gate Job

**What:** A job that always runs, checks all other jobs for failures, and serves as the single required status check

```yaml
# Source: GitHub Actions documentation pattern
ci-complete:
  name: CI Complete
  runs-on: ubuntu-latest
  if: always()
  needs: [changes, backend, frontend, actionlint, sonarcloud, test-results]
  steps:
    - name: Check job results
      run: |
        if [[ "${{ contains(needs.*.result, 'failure') }}" == "true" ]]; then
          echo "::error::One or more CI jobs failed"
          exit 1
        fi
        echo "All CI jobs passed or were skipped"
```

### Pattern 5: Full venv Cache

**What:** Cache the entire `.venv` directory to skip pip install on cache hit

```yaml
# Source: actions/cache documentation
- name: Cache venv
  id: cache-venv
  uses: actions/cache@v4
  with:
    path: .venv
    key: venv-py311-${{ hashFiles('pyproject.toml') }}

- name: Install dependencies
  if: steps.cache-venv.outputs.cache-hit != 'true'
  run: |
    python -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade 'pip>=26.0'
    pip install -e ".[dev]"
```

### Anti-Patterns to Avoid

- **Caching pip download cache instead of venv:** `setup-python`'s `cache: pip` caches downloaded wheels but still runs `pip install` (dependency resolution + installation). Caching the full venv skips everything. D-23 explicitly requires full venv cache.
- **Using `@v4` of dorny/paths-filter without testing:** v4 bumps to Node 24 which may have compatibility issues with older action runners. Stick with v3.
- **Combining testmon and coverage:** `--testmon-nocollect` is forced when running under coverage, meaning testmon won't update its data. D-22 makes them mutually exclusive for this reason.
- **Running testmon on main branch:** Main pushes should always run the full suite with coverage. testmon is PR-only (D-10, D-22).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JUnit XML parsing + PR comments | Custom github-script parsing XML | EnricoMi/publish-unit-test-result-action@v2 | Handles multiple formats, comment upsert, skipped/failed counting, duration tracking |
| Path-based job filtering | Manual `git diff` + shell conditionals | dorny/paths-filter@v3 | Handles merge bases, PR vs push events, glob patterns, multiple outputs |
| Test selection by changed files | Custom pytest plugin tracking imports | pytest-testmon | Maintains dependency graph via coverage, handles transitive dependencies |
| Vitest JUnit output | Custom test result transformer | Vitest built-in `junit` reporter | Zero config, maintained by vitest team |

**Key insight:** Every tool in this phase is a mature, single-purpose solution. The complexity is in orchestrating them correctly in the workflow, not in any individual component.

## Common Pitfalls

### Pitfall 1: dorny/paths-filter and Required Status Checks

**What goes wrong:** When a job is skipped via `if:` condition, its status check never reports. If that job is a required status check, the PR is permanently blocked.
**Why it happens:** GitHub requires all listed status checks to report a conclusion. Skipped jobs report no conclusion.
**How to avoid:** D-06 addresses this: use a `ci-complete` gate job as the ONLY required status check. It always runs (`if: always()`) and checks `needs.*.result` for failures.
**Warning signs:** PRs stuck in "pending" with no CI activity on a specific check.

### Pitfall 2: testmon Cache Invalidation Timing

**What goes wrong:** testmon uses stale `.testmondata` after dependency changes, potentially skipping tests that should run.
**Why it happens:** If cache key doesn't include dependency hash, testmon's dependency graph becomes inaccurate after package updates.
**How to avoid:** D-20 addresses this: cache key includes `hashFiles('pyproject.toml')` so any dependency change invalidates the testmon cache entirely.
**Warning signs:** Tests passing in CI but failing locally after a dependency update.

### Pitfall 3: venv Cache Path Mismatch

**What goes wrong:** Cached venv created with one Python path but restored on a runner with a different Python path, causing import failures.
**Why it happens:** venv shebangs and `pyvenv.cfg` contain absolute paths. If `setup-python` installs Python to a different path on different runner images, the cached venv breaks.
**How to avoid:** Include Python version in cache key (D-23: `venv-py311-{hash}`). The `setup-python` action is deterministic about installation paths within the same major.minor version.
**Warning signs:** `ModuleNotFoundError` or `No such file or directory` errors on pip commands after cache restore.

### Pitfall 4: Permissions for PR Comments

**What goes wrong:** publish-unit-test-result-action fails silently or with permission errors when posting PR comments.
**Why it happens:** The action requires `checks: write` and `pull-requests: write` permissions. The current workflow has `permissions: contents: read` at the top level.
**How to avoid:** Add required permissions to the test-results job specifically, or expand the top-level permissions.
**Warning signs:** "Resource not accessible by integration" error in CI logs.

### Pitfall 5: testmon + pytest-timeout Interaction

**What goes wrong:** testmon may not correctly track test dependencies if a test is killed by pytest-timeout.
**Why it happens:** When pytest-timeout kills a test via signal, the coverage collection that testmon relies on may not flush properly.
**How to avoid:** The existing 30s timeout (pyproject.toml) is generous enough that legitimate tests should complete. Monitor for flaky testmon behavior on timeout-killed tests.
**Warning signs:** Previously-passing tests getting re-run every time despite no code changes.

### Pitfall 6: `pytest_runtest_makereport` Slow Marker Limitation

**What goes wrong:** Attempting `pytest -m slow` to select slow tests -- this selects nothing because the slow marker is applied after execution.
**Why it happens:** The `pytest_runtest_makereport` hook runs during/after test execution, not during collection.
**How to avoid:** Document that the slow marker is for reporting/visibility only in Phase 1. If pre-selection is needed, a separate mechanism would be required (not in scope).
**Warning signs:** `pytest -m slow` returns 0 tests collected.

## Code Examples

### conftest.py: Full Hook Implementation

```python
# Source: pytest hook documentation + D-01, D-02
import pytest

INTEGRATION_FIXTURES = frozenset({
    "db_session", "client", "authenticated_client", "db_engine"
})

def pytest_collection_modifyitems(items):
    """Auto-mark tests as unit or integration based on fixture usage.

    Tests using database/client fixtures are integration tests.
    Everything else is a unit test. Explicit markers take precedence.
    """
    for item in items:
        if any(item.get_closest_marker(m) for m in ("unit", "integration", "smoke")):
            continue
        fixture_names = set(getattr(item, "fixturenames", []))
        if fixture_names & INTEGRATION_FIXTURES:
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)


def pytest_runtest_makereport(item, call):
    """Mark tests exceeding 5s as slow (informational, post-execution)."""
    if call.when == "call" and call.duration > 5.0:
        item.add_marker(pytest.mark.slow)
```

### pyproject.toml: Marker Registration

```toml
# Source: D-04
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
timeout = 30
markers = [
    "unit: Pure logic tests with no external dependencies (auto-applied)",
    "integration: Tests using database, API client, or external fixtures (auto-applied)",
    "slow: Tests exceeding 5s runtime (auto-detected)",
    "smoke: Health check tests (manually applied, 1-2 tests)",
    "regression: Golden set regression tests (Phase 3, ADV-01)",
]
```

### vitest.config.ts: JUnit Reporter

```typescript
// Source: vitest.dev/guide/reporters (built-in junit reporter)
export default defineConfig({
  // ... existing config ...
  test: {
    // ... existing test config ...
    reporters: ['default', ['junit', {
      outputFile: 'test-results/frontend-junit.xml',
      suiteName: 'Kestrel Frontend',
    }]],
  },
});
```

### ci.yml: testmon with Cache (backend job excerpt)

```yaml
# Source: actions/cache docs + pytest-testmon docs
- name: Cache testmon data
  if: github.event_name == 'pull_request'
  uses: actions/cache@v4
  with:
    path: .testmondata
    key: testmon-py311-${{ hashFiles('pyproject.toml') }}

- name: Run tests (PR - selective)
  if: github.event_name == 'pull_request'
  run: |
    source .venv/bin/activate
    pytest tests/ -v --tb=short --testmon --junitxml=test-results/backend-junit.xml

- name: Run tests (main - full coverage)
  if: github.ref == 'refs/heads/main'
  run: |
    source .venv/bin/activate
    pytest tests/ -v --tb=short --cov=src/career_os --cov-report=xml --junitxml=test-results/backend-junit.xml
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `setup-python` `cache: pip` | Full venv caching via `actions/cache` | 2024+ | Eliminates pip install time entirely on cache hit (~30-60s savings) |
| Custom `git diff` for path detection | dorny/paths-filter action | v3 stable since 2022 | Reliable path detection across PR/push/merge events |
| Manual `@pytest.mark.X` tagging | conftest.py auto-marking hooks | Standard pytest pattern | Zero maintenance burden, impossible to forget |
| testmon.net (hosted service) | Self-hosted .testmondata caching | testmon 2.2.0 | testmon.net is optional SaaS; local caching works fine for single-runner CI |

**Deprecated/outdated:**
- `syphar/restore-virtualenv` action: Outdated per testmon blog; use `actions/cache@v4` directly
- dorny/paths-filter v2: v3 has been stable for years, v2 is unmaintained
- `@vitest/junit-reporter` package: Never existed as a separate package; vitest has built-in junit reporter

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pytest_runtest_makereport` slow marker is post-execution only and cannot be used for pre-selection | Pitfall 6, Pattern 2 | Low -- slow marker is for reporting only in Phase 1; pre-selection not in scope |
| A2 | dorny/paths-filter v3 works correctly with `merge_group` event type | Pattern 3 | Medium -- if it doesn't, merge queue PRs might not get path filtering; ci-complete gate still protects |
| A3 | venv cache restores correctly across ubuntu-latest runner updates when Python major.minor matches | Pitfall 3 | Low -- actions/setup-python is deterministic within major.minor; cache key includes version |

## Open Questions

1. **testmon + merge_group event**
   - What we know: The workflow triggers on `merge_group` events. testmon caching is designed for PR events.
   - What's unclear: Whether testmon cache should be shared with merge_group runs or if merge_group should always run full suite.
   - Recommendation: Treat `merge_group` like `push` to main -- always run full suite. The merge queue is a final gate and should not rely on selective execution.

2. **publish-unit-test-result-action and fork PRs**
   - What we know: Fork PRs have limited permissions by default (no `pull-requests: write`).
   - What's unclear: Whether the project accepts external PRs that would need this.
   - Recommendation: Use `comment_mode: off` for fork PRs or accept that fork PR comments will fail silently. The action handles this gracefully.

3. **venv cache size and retention**
   - What we know: GitHub Actions cache has a 10GB limit per repository. Full venvs can be 200-500MB.
   - What's unclear: How many cache entries (branches x Python versions) will accumulate.
   - Recommendation: Single Python version (3.11) and single cache key pattern limits exposure. Monitor cache usage after rollout.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pytest-testmon | CI-03 (selective execution) | Not installed locally | -- | Add to pyproject.toml dev deps |
| dorny/paths-filter | CI-02 (job filtering) | GitHub Actions marketplace | v3 | No fallback needed (CI-only) |
| EnricoMi/publish-unit-test-result-action | CI-04 (PR comments) | GitHub Actions marketplace | v2 | No fallback needed (CI-only) |
| actions/cache | CI-03, CI-04 (caching) | GitHub Actions built-in | v4 | No fallback needed (CI-only) |
| vitest junit reporter | CI-04 (frontend XML) | Built into vitest 4.1.x | Built-in | No fallback needed |

**Missing dependencies with no fallback:** None -- all dependencies are either marketplace actions (available by reference) or pip-installable.

**Missing dependencies with fallback:** pytest-testmon needs to be added to `pyproject.toml` dev dependencies (straightforward addition).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.x (backend), vitest 4.1.x (frontend) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`, `frontend/vitest.config.ts` |
| Quick run command | `pytest tests/ -v --tb=short -x` |
| Full suite command | `pytest tests/ -v --tb=short --cov=src/career_os` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CI-01 | `pytest -m unit` runs only unit tests; `pytest -m integration` runs only integration tests; all 108 files marked | manual + smoke | `pytest --collect-only -m unit -q \| tail -1` (verify count) | No -- Wave 0 |
| CI-01 | Auto-marking assigns correct marker based on fixture usage | unit | `pytest tests/test_parse_scoring_response.py --collect-only -q` (verify marker) | No -- Wave 0 |
| CI-02 | Backend job skipped when only frontend files change (CI log check) | manual | Requires a PR with frontend-only changes | N/A (CI behavior) |
| CI-03 | testmon runs subset of tests when single file changed | smoke | `pytest tests/ --testmon --collect-only -q` (after initial run) | No -- Wave 0 |
| CI-04 | JUnit XML produced by pytest and vitest | smoke | `pytest tests/ --junitxml=/tmp/test.xml -x && test -f /tmp/test.xml` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -v --tb=short -x` (fail fast on first error)
- **Per wave merge:** `pytest tests/ -v --tb=short` (full suite, no coverage)
- **Phase gate:** Full suite green + CI workflow runs successfully on a test PR

### Wave 0 Gaps
- [ ] `tests/test_conftest_markers.py` -- verify auto-marking assigns correct markers to known fixtures
- [ ] Verification script to count unit vs integration markers across all 108 files
- [ ] CI workflow syntax validation: `actionlint .github/workflows/ci.yml` (already in CI, run locally too)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | -- |
| V3 Session Management | No | -- |
| V4 Access Control | Yes (CI permissions) | Minimal permissions per job; `pull-requests: write` only on test-results job |
| V5 Input Validation | No | -- |
| V6 Cryptography | No | -- |

### Known Threat Patterns for CI/CD

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Workflow injection via PR title/body | Tampering | No user-controlled strings in `run:` steps; dorny/paths-filter is read-only |
| Overly permissive GITHUB_TOKEN | Elevation of Privilege | Per-job `permissions:` blocks with minimal scope |
| Cache poisoning (malicious venv) | Tampering | Cache key includes `hashFiles('pyproject.toml')` -- attacker cannot inject arbitrary packages without modifying tracked file |
| Fork PR with `pull-requests: write` | Elevation of Privilege | Fork PRs use `pull_request` event which restricts token scope by default |

## Sources

### Primary (HIGH confidence)
- [pypi.org/project/pytest-testmon](https://pypi.org/project/pytest-testmon/) -- version 2.2.0, Python >=3.10, released 2025-12-01
- [github.com/dorny/paths-filter](https://github.com/dorny/paths-filter) -- v3 stable, v4 is Node 24 bump only
- [github.com/EnricoMi/publish-unit-test-result-action](https://github.com/EnricoMi/publish-unit-test-result-action) -- v2.23.0, permissions documented
- [vitest.dev/guide/reporters](https://vitest.dev/guide/reporters) -- built-in junit reporter, no separate package
- Existing codebase: `.github/workflows/ci.yml`, `tests/conftest.py`, `pyproject.toml`, `frontend/vitest.config.ts`

### Secondary (MEDIUM confidence)
- [testmon.org](https://www.testmon.org/) -- CI usage patterns, `--testmon-nocollect` under coverage
- [testmon.org/blog](https://www.testmon.org/blog/better-github-actions-caching/) -- outdated caching article, confirms actions/cache@v4 is current approach

### Tertiary (LOW confidence)
- testmon + merge_group interaction (no documentation found, recommendation based on reasoning)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all tools verified against registries and official docs
- Architecture: HIGH -- patterns derived from official documentation and existing codebase patterns
- Pitfalls: HIGH -- well-documented issues with established solutions (especially required status checks + path filtering)

**Research date:** 2026-04-19
**Valid until:** 2026-05-19 (stable tools, 30-day window appropriate)
