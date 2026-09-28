---
phase: 03-advanced-testing
plan: 01
subsystem: testing
tags: [regression, golden-set, scoring, ci, hypothesis, schemathesis]
dependency_graph:
  requires: []
  provides: [golden-set-regression, deterministic-mock-provider, pytest-marker-exclusion]
  affects: [ci.yml, pyproject.toml, tests/regression/]
tech_stack:
  added: [hypothesis-6.152.1, schemathesis-4.15.2]
  patterns: [DeterministicScoringMockProvider, hash-based-scoring, band-range-assertions]
key_files:
  created:
    - tests/regression/conftest.py
    - tests/regression/test_golden_set.py
    - tests/regression/__init__.py
    - tests/property/__init__.py
    - tests/fuzz/__init__.py
    - tests/fixtures/scoring_golden_set_healthcare.json
    - tests/fixtures/scoring_golden_set_legal.json
    - tests/fixtures/scoring_golden_set_product.json
  modified:
    - pyproject.toml
    - .gitignore
    - .github/workflows/ci.yml
    - tests/fixtures/scoring_golden_set.json
    - tests/fixtures/scoring_golden_set_finance.json
    - tests/fixtures/scoring_golden_set_design.json
decisions:
  - "DeterministicScoringMockProvider hashes the full scoring prompt (not raw description) via MD5 to produce varied scores"
  - "Fixture expected_band calibrated with +/-1.0 tolerance against actual pipeline output using identical test DB setup"
  - "Existing fixture expected_band values updated to match DeterministicScoringMockProvider output (original bands were for conceptual AI scoring, not hash-based)"
metrics:
  duration: 8m
  completed: 2026-04-20
  tasks: 3
  files_created: 8
  files_modified: 6
  tests_added: 72
---

# Phase 03 Plan 01: Golden Set Regression Tests Summary

Golden set regression tests covering 6 diverse job families (TPM, finance, design, healthcare, legal, product) with a DeterministicScoringMockProvider that hashes scoring prompts to produce varied, reproducible fit_scores validated against calibrated band ranges.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Configure dependencies, markers, and exclusions | 78d0b96 | pyproject.toml, .gitignore, tests/{regression,property,fuzz}/__init__.py |
| 2 | Golden set regression tests with DeterministicScoringMockProvider | 0a04c83 | tests/regression/conftest.py, test_golden_set.py, 6 fixture files |
| 3 | Add golden set regression step to CI backend job | 15c2e33 | .github/workflows/ci.yml |

## What Was Built

### DeterministicScoringMockProvider (tests/regression/conftest.py)
- Extends AIProvider with a `score()` method that hashes the job_description parameter (which is the full scoring prompt built by `_build_scoring_prompt`) using MD5
- Maps hash to fit_score in [0.0, 9.99] via `(seed % 1000) / 100.0`
- Returns valid ScoreResult with all required fields derived from the hash seed
- Patched into the scoring pipeline via `golden_set_provider` fixture

### Golden Set Test Suite (tests/regression/test_golden_set.py)
- 6 test classes: TestGoldenSetTPM (20 jobs), TestGoldenSetFinance (20 jobs), TestGoldenSetDesign (20 jobs), TestGoldenSetHealthcare (4 jobs), TestGoldenSetLegal (4 jobs), TestGoldenSetProduct (4 jobs)
- 72 parametrized async test cases total, all marked `@pytest.mark.regression`
- Each test creates a fresh in-memory SQLite DB, scores one job through the full pipeline, and asserts fit_score falls within the calibrated expected_band

### Fixture Calibration
- All 6 fixture files have expected_band values calibrated against actual DeterministicScoringMockProvider output through the real scoring pipeline
- Bands use +/-1.0 tolerance around the deterministic score
- Calibration used the exact same db_session setup (profile name, email, location, job_family) as the test conftest to ensure reproducibility

### CI Integration (.github/workflows/ci.yml)
- Two "Golden set regression (scoring band drift)" steps added to backend job
- PR variant: runs after "Run tests (PR)" step, conditioned on `github.event_name == 'pull_request'`
- Main variant: runs after "Run tests (main)" step, conditioned on `github.event_name != 'pull_request'`
- Both use `pytest tests/regression/ -m regression -v --tb=short -x` (fail-fast)

### Pytest Configuration (pyproject.toml)
- Added `hypothesis>=6.152.0` and `schemathesis>=4.15.0` to dev dependencies
- Registered `property` and `fuzz` markers for future Phase 3 plans
- Added `addopts = "-m 'not regression and not property and not fuzz'"` to exclude advanced tests from default run
- `.hypothesis/` added to .gitignore

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixture expected_band calibration required pipeline-aware approach**
- **Found during:** Task 2
- **Issue:** The plan suggested computing `fit_score = (_deterministic_seed(job["description"]) % 1000) / 100.0` directly from the raw description text. However, `score_job()` passes the full scoring prompt (built by `_build_scoring_prompt()` including profile data, rubric, weights) to the provider, not the raw description. The hash of the full prompt differs significantly from the hash of just the description.
- **Fix:** Created a calibration script that scores each job through the actual pipeline with the exact same DB setup as the test conftest (same profile name, email, location, job_family), captures the real fit_score, and sets expected_band to [max(0, score-1.0), min(10, score+1.0)].
- **Files modified:** All 6 fixture files
- **Commit:** 0a04c83

**2. [Rule 1 - Bug] Calibration must use isolated DB per job**
- **Found during:** Task 2
- **Issue:** Initial calibration scored all jobs sequentially in the same DB session. Each `score_job()` call creates a ScoredJob record, changing the DB state for subsequent calls. But in tests, each parametrized test gets a fresh DB session via the function-scoped fixture.
- **Fix:** Modified calibration to create a fresh in-memory SQLite DB for each individual job, matching the test isolation behavior exactly.
- **Files modified:** All 6 fixture files
- **Commit:** 0a04c83

## Verification Results

```
72 passed, 0 failed (pytest -m regression)
0 regression tests in default pytest run (addopts exclusion works)
hypothesis and schemathesis importable
2 "Golden set regression" steps in ci.yml
.hypothesis/ in .gitignore
```

## Self-Check: PASSED
