# Phase 1: CI Optimization - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 01-ci-optimization
**Areas discussed:** Auto-marking rules, CI job structure, PR test feedback, testmon cache, Node cache strategy, Alembic migration check, Test parallelization, CI workflow naming

---

## Auto-marking Rules

| Option | Description | Selected |
|--------|-------------|----------|
| Fixture-based | Tests using db_session/client/authenticated_client/db_engine → integration, else → unit | ✓ |
| Filename-based | Files matching *_api.py or *_service.py → integration | |
| Directory-based | Reorganize tests/ into unit/ and integration/ subdirs | |

**User's choice:** Fixture-based auto-marking
**Notes:** No file moves needed, works with the flat tests/ layout

---

| Option | Description | Selected |
|--------|-------------|----------|
| Timeout threshold | Any test exceeding 5s auto-marked slow via pytest hook | ✓ |
| Manual @pytest.mark.slow | Developers explicitly tag slow tests | |
| You decide | Claude picks | |

**User's choice:** Timeout threshold (>5s)
**Notes:** Zero manual work, adapts as tests evolve

---

| Option | Description | Selected |
|--------|-------------|----------|
| Smoke = health check only | Mark existing API smoke test as smoke (1-2 tests) | |
| Regression = golden set | Defer regression marker to Phase 3 (ADV-01) | |
| Both of the above | Smoke = health check, regression = Phase 3 | ✓ |
| You decide | Claude handles | |

**User's choice:** Both — smoke = health check only, regression deferred to Phase 3
**Notes:** Keep Phase 1 focused on unit/integration/slow

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, in pyproject.toml | Register all 5 markers with descriptions | ✓ |
| Skip registration | Don't register, accept warnings | |

**User's choice:** Register in pyproject.toml
**Notes:** Clean output, no warnings

---

## CI Job Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Keep monolithic + skip | One backend job, skip via dorny condition | ✓ |
| Split into 3 jobs | Separate lint, test, security jobs | |
| You decide | Claude picks | |

**User's choice:** Keep monolithic + skip
**Notes:** Simpler, fewer jobs to manage

---

| Option | Description | Selected |
|--------|-------------|----------|
| ci-complete gate job | Final job with if: always(), checks for failures | ✓ |
| Individual required checks | Each job as its own required check | |
| You decide | Claude picks | |

**User's choice:** ci-complete gate job
**Notes:** Only required status check in branch protection

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, skip all tests | Docs-only PRs skip backend + frontend | ✓ |
| No, always run something | Even docs PRs run at least lint | |

**User's choice:** Skip all tests for docs-only PRs

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, symmetric | Frontend skips when only backend changed | ✓ |
| No, always run frontend | Frontend tests always run | |

**User's choice:** Symmetric path filtering

---

| Option | Description | Selected |
|--------|-------------|----------|
| Shared config files | docker-compose*, ci.yml trigger both jobs | ✓ |
| Only component-specific | Strict src/ vs frontend/ separation | |

**User's choice:** Shared config files trigger both

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, full suite on main | Path filtering only for PRs | ✓ |
| Filter on main too | Apply same filtering on main pushes | |

**User's choice:** Full suite on main pushes

---

| Option | Description | Selected |
|--------|-------------|----------|
| Keep current concurrency | No changes to concurrency settings | ✓ |
| I have something specific | Custom concern | |

**User's choice:** Keep current concurrency

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, symmetric | Frontend job also gets path-filter skip | ✓ |
| No, always run frontend | Always run frontend tests | |

**User's choice:** Symmetric frontend path filtering

---

## PR Test Feedback

| Option | Description | Selected |
|--------|-------------|----------|
| Summary + failures only | Pass/fail/skip counts, expand only failures | ✓ |
| Full breakdown | Every test with status and duration | |
| Counts only | Just summary table, no failure details | |

**User's choice:** Summary + failures only

---

| Option | Description | Selected |
|--------|-------------|----------|
| Combined single comment | One comment with backend + frontend sections | ✓ |
| Separate comments | Two comments, one per component | |

**User's choice:** Combined single comment

---

| Option | Description | Selected |
|--------|-------------|----------|
| Update existing | Edit same comment on each push (marker-based upsert) | ✓ |
| New comment per push | Fresh comment per push | |

**User's choice:** Update existing comment

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, show skip count | Include "X tests skipped by testmon" in summary | ✓ |
| No, just pass/fail | Don't mention testmon skips | |
| Show individual skipped | List every skipped test name | |

**User's choice:** Show skip count

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, upload as artifact | JUnit XML artifact with 7-day retention | ✓ |
| No, PR comment is enough | Don't store XML | |

**User's choice:** Upload as artifact

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, show duration delta | Compare against previous run | |
| No, just current duration | Show current run duration only | ✓ |

**User's choice:** Current duration only
**Notes:** Timing varies by runner load, deltas can be misleading

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, add vitest-junit-reporter | JUnit XML for frontend too | ✓ |
| Backend only for now | Only pytest JUnit XML | |

**User's choice:** Add vitest JUnit reporter

---

| Option | Description | Selected |
|--------|-------------|----------|
| No, keep it simple | Just failure message + file location | ✓ |
| Yes, add mapping hints | Cross-reference failed tests to source files | |

**User's choice:** Keep it simple

---

## testmon Cache

| Option | Description | Selected |
|--------|-------------|----------|
| Python version + deps hash | Shared across all PRs on same deps | ✓ |
| Branch-specific cache | Each PR branch gets own cache | |
| You decide | Claude picks | |

**User's choice:** Python version + deps hash

---

| Option | Description | Selected |
|--------|-------------|----------|
| Run all tests | On miss, testmon runs full suite, builds fresh cache | ✓ |
| Fall back to no-testmon | Skip testmon on miss, run pytest normally | |

**User's choice:** Run all tests on cache miss

---

| Option | Description | Selected |
|--------|-------------|----------|
| testmon on PRs, coverage on main | Mutually exclusive, clean separation | ✓ |
| Always coverage, testmon separate step | Both on PRs via two-step approach | |

**User's choice:** testmon on PRs, coverage on main

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, full venv cache | Cache .venv keyed to Python + pyproject.toml | ✓ |
| Keep pip cache only | Use setup-python's built-in pip cache | |

**User's choice:** Full venv cache

---

| Option | Description | Selected |
|--------|-------------|----------|
| Gitignored | .testmondata in CI cache and local dev only | ✓ |
| Committed | Commit to repo for shared baseline | |

**User's choice:** Gitignored

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, document it | testmon in dev deps, document local workflow | ✓ |
| CI only | testmon for CI optimization only | |

**User's choice:** Document local testmon usage

---

| Option | Description | Selected |
|--------|-------------|----------|
| No, deps-hash handles it | Old caches expire via GitHub's eviction policy | ✓ |
| Yes, add TTL or weekly purge | Force cache rebuild weekly | |

**User's choice:** No periodic purge needed

---

## Node Cache Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Keep npm cache only | setup-node's npm cache, npm ci is fast enough | ✓ |
| Full node_modules cache | Cache node_modules keyed to package-lock.json | |

**User's choice:** Keep npm cache only

---

## Alembic Migration Check

| Option | Description | Selected |
|--------|-------------|----------|
| Always run on backend | Alembic check runs whenever backend job runs | ✓ |
| Path-filter to alembic/ + models/ | Only run on migration-related changes | |

**User's choice:** Always run on backend

---

## Test Parallelization

| Option | Description | Selected |
|--------|-------------|----------|
| No, testmon only | testmon addresses root cause per PROJECT.md | ✓ |
| Add xdist too | testmon + xdist for maximum speedup | |

**User's choice:** testmon only (per PROJECT.md decision)

---

## CI Workflow Naming

| Option | Description | Selected |
|--------|-------------|----------|
| Keep ci.yml | Phase 4 adds ci-nightly.yml and ci-weekly.yml alongside | ✓ |
| Rename to ci-pr.yml | Proactive rename for consistency | |

**User's choice:** Keep ci.yml

---

## Claude's Discretion

- Implementation details of dorny/paths-filter configuration
- Exact EnricoMi/publish-unit-test-result-action configuration
- JUnit XML file paths and naming
- Vitest reporter configuration syntax
- conftest.py hook implementation details

## Deferred Ideas

- SonarCloud local pre-checks (SonarLint VS Code or SonarQube server) — noted for Phase 2 enforcement
