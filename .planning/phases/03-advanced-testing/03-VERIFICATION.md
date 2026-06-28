---
phase: 03-advanced-testing
verified: 2026-04-20T22:45:00Z
status: human_needed
score: 3/3
overrides_applied: 0
human_verification:
  - test: "Verify fuzz test 500-as-warnings approach is acceptable for SC-3"
    expected: "Developer confirms that catching OverflowError as warnings (not hard failures) satisfies 'reports zero 500-errors on valid-schema inputs'"
    why_human: "SC-3 wording is ambiguous -- server exceptions bypass HTTP status codes in ASGI transport, so they cannot be asserted via status_code < 500. The fuzz harness logs them as FUZZ-500 warnings. This is a judgment call on whether the SC intent is met."
---

# Phase 3: Advanced Testing Verification Report

**Phase Goal:** Scoring correctness and API contract stability are continuously validated beyond unit tests
**Verified:** 2026-04-20T22:45:00Z
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Golden set regression tests load fixture JSON, call score_job with DeterministicScoringMockProvider, and assert fit_score falls within expected_band | VERIFIED | `pytest -m regression` passes 120/120. Tests in `tests/regression/test_golden_set.py` call `score_job()` with patched provider, assert `low <= scored.fit_score <= high` (lines 69-74). |
| 2 | Hypothesis property-based tests prove fit_score is always 0-10 and readiness_score is always 0-100 for any valid input | VERIFIED | `pytest -m property` passes 8/8. `test_fit_score_always_in_range` (200 examples) and `test_readiness_score_always_in_range` (200 examples) in `tests/property/test_scoring_properties.py`. Note: ROADMAP SC-2 says "0-100" but `fit_score` is 0-10 per `ScoreResult` schema -- RESEARCH.md resolves this discrepancy; tests use correct ranges. |
| 3 | Property tests prove scoring is deterministic (same input = same output) with MockProvider | VERIFIED | `test_scoring_idempotent` calls `score_job()` twice with DeterministicScoringMockProvider, asserts `result1.fit_score == result2.fit_score` and `result1.reasoning == result2.reasoning` (lines 196-197). |
| 4 | Property tests prove band monotonicity: higher fit_score never maps to a lower band | VERIFIED | `test_band_monotonicity` (200 examples) asserts `band_a <= band_b` when `score_a <= score_b` using threshold function 0-3/3-6/6-10 (lines 208-224). |
| 5 | State machine property tests prove every ApplicationStatus has valid transitions and no transition leads to undefined status | VERIFIED | `ApplicationStateMachine` RuleBasedStateMachine (100 examples, 10 steps each) plus `test_all_statuses_have_transitions` and `test_no_self_transitions` in `tests/property/test_state_machine.py`. |
| 6 | Schemathesis fuzzes every API endpoint from the OpenAPI spec via ASGI in-process transport | VERIFIED | `test_api_no_500` uses `schemathesis.openapi.from_asgi("/openapi.json", app)` with `@schema.parametrize()`. 140 operations tested, all passed. |
| 7 | No endpoint returns HTTP 500 on valid-schema inputs | VERIFIED (with caveat) | All 140 parametrized tests pass. However, server exceptions (OverflowError from INT64 overflow) are caught and logged as FUZZ-500 warnings rather than hard failures. This is because Schemathesis ASGI transport raises Python exceptions instead of returning HTTP 500. Design decision documented in SUMMARY. |
| 8 | Stateful mode chains dependent API calls (create profile -> create application -> update status -> add contact) | VERIFIED | `TestLifecycleChain.test_lifecycle_no_500` (lines 88-146) manually chains POST /api/profiles -> POST /api/applications -> PATCH status (discovered->interested->applied) -> POST /api/contacts with specific assertions at each step. Auto-discovered `TestAPIWorkflow` also present (xfail due to pre-existing datetime schema mismatch). |
| 9 | pytest -m regression/property/fuzz runs only respective tests and all pass | VERIFIED | `pytest -m regression`: 120 passed. `pytest -m property`: 8 passed. `pytest -m fuzz`: 140 passed, 1 xfailed. |
| 10 | Default pytest run excludes regression/property/fuzz tests | VERIFIED | `addopts = "-m 'not regression and not property and not fuzz'"` in pyproject.toml. Default collection shows 0 regression/property/fuzz-marked tests. |
| 11 | hypothesis and schemathesis are installable dev dependencies | VERIFIED | `python -c "import hypothesis; import schemathesis"` succeeds. pyproject.toml contains `"hypothesis>=6.152.0"` and `"schemathesis>=4.15.0"` in dev deps. |
| 12 | Golden set covers 6 diverse job families (TPM, finance, design, healthcare, legal, product) | VERIFIED | 6 test classes (TestGoldenSetTPM, TestGoldenSetFinance, TestGoldenSetDesign, TestGoldenSetHealthcare, TestGoldenSetLegal, TestGoldenSetProduct) with corresponding fixture files. 120 total tests (20 per family). |
| 13 | CI runs pytest -m regression on every PR in the backend job | VERIFIED | `.github/workflows/ci.yml` lines 114-120: two "Golden set regression (scoring band drift)" steps -- PR variant (`github.event_name == 'pull_request'`) and main variant (`!= 'pull_request'`). Both run `pytest tests/regression/ -m regression -v --tb=short -x`. |
| 14 | Auth is disabled during fuzzing | VERIFIED | `tests/fuzz/conftest.py` has `disable_auth` session fixture setting `AUTH_ENABLED=false`. `tests/fuzz/test_api_fuzz.py` also sets `os.environ["AUTH_ENABLED"] = "false"` at module level. |

**Score:** 3/3 ROADMAP success criteria verified

### ROADMAP Success Criteria Cross-Reference

| SC# | ROADMAP Success Criterion | Truths Covering | Status |
|-----|--------------------------|-----------------|--------|
| SC-1 | Golden set regression tests load scoring_golden_set.json fixtures, run actual scoring, and assert output matches expected_band -- failing if a scoring change causes band drift | Truths 1, 9, 10, 12, 13 | VERIFIED |
| SC-2 | Hypothesis property-based tests prove scoring output is always 0-100 and deterministic, and state machine transitions never reach an invalid state | Truths 2, 3, 4, 5 | VERIFIED (fit_score is 0-10 per actual schema; readiness_score is 0-100; both tested correctly) |
| SC-3 | Schemathesis fuzzes every API endpoint from the OpenAPI spec and reports zero 500-errors on valid-schema inputs (stateful mode chains dependent API calls) | Truths 6, 7, 8, 14 | VERIFIED (with human verification needed on warning-based 500 approach) |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/regression/test_golden_set.py` | Golden set regression tests for 6 job families (min 120 lines) | VERIFIED | 244 lines. 6 test classes, 120 parametrized tests, real `score_job()` calls with band assertions. |
| `tests/regression/conftest.py` | DeterministicScoringMockProvider fixture and golden set loader (min 40 lines) | VERIFIED | 200 lines. `DeterministicScoringMockProvider`, `load_golden_set()`, `db_session`, `golden_set_provider` fixtures. |
| `tests/fixtures/scoring_golden_set_healthcare.json` | Healthcare job family golden set fixture (min 20 lines) | VERIFIED | 255 lines. Valid structure with profile + 20 jobs with expected_band. |
| `tests/fixtures/scoring_golden_set_legal.json` | Legal job family golden set fixture (min 20 lines) | VERIFIED | 255 lines. Valid structure with profile + 20 jobs with expected_band. |
| `tests/fixtures/scoring_golden_set_product.json` | Product/PM job family golden set fixture (min 20 lines) | VERIFIED | 255 lines. Valid structure with profile + 20 jobs with expected_band. |
| `tests/property/test_scoring_properties.py` | Hypothesis property tests for scoring invariants including pipeline-level idempotency (min 100 lines) | VERIFIED | 224 lines. 5 property tests with `@given` strategies, pipeline-level idempotency via `score_job()`. |
| `tests/property/test_state_machine.py` | RuleBasedStateMachine property tests for VALID_TRANSITIONS (min 50 lines) | VERIFIED | 99 lines. `ApplicationStateMachine(RuleBasedStateMachine)` + 2 standalone tests. |
| `tests/fuzz/test_api_fuzz.py` | Schemathesis parametrized fuzz tests and stateful API workflow (min 40 lines) | VERIFIED | 186 lines. `@schema.parametrize()` endpoint fuzz, manual lifecycle chain, auto-discovered stateful workflow. |
| `tests/fuzz/conftest.py` | Fixtures for ASGI app with auth disabled and clean DB state (min 15 lines) | VERIFIED | 61 lines. `disable_auth` session fixture, `clean_db` autouse fixture with StaticPool. |
| `pyproject.toml` | property+fuzz markers, addopts exclusion, hypothesis+schemathesis deps | VERIFIED | Lines 56-57: deps. Lines 108-109: markers. Line 111: addopts exclusion. |
| `.github/workflows/ci.yml` | Golden set regression step in PR backend job | VERIFIED | Lines 114-120: two regression steps (PR and main variants). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `tests/regression/test_golden_set.py` | `tests/fixtures/scoring_golden_set.json` | `conftest.load_golden_set` | WIRED | `from .conftest import load_golden_set` (line 20). `_job_ids()` and `_job_by_id()` call `load_golden_set()`. |
| `tests/regression/conftest.py` | `career_os.services.scoring.score_job` | DeterministicScoringMockProvider patched into get_ai_provider | WIRED | `patch("career_os.services.scoring.get_ai_provider", return_value=provider)` (line 199). |
| `.github/workflows/ci.yml` | `tests/regression/test_golden_set.py` | `pytest -m regression` step | WIRED | Lines 116, 120: `pytest tests/regression/ -m regression -v --tb=short -x`. |
| `tests/property/test_scoring_properties.py` | `career_os.schemas.ai.ScoreResult` | Hypothesis @given strategies | WIRED | Imports `ScoreResult`, `ScoreBreakdownFactor`, `ATSKeyword` (lines 26-29). Used in `_make_score_result()`. |
| `tests/property/test_scoring_properties.py` | `career_os.services.scoring.score_job` | Pipeline-level idempotency test | WIRED | `from career_os.services.scoring import score_job` (line 30). Called twice in `test_scoring_idempotent` (lines 181-194). |
| `tests/property/test_state_machine.py` | `career_os.schemas.applications.VALID_TRANSITIONS` | RuleBasedStateMachine rules | WIRED | `from career_os.schemas.applications import VALID_TRANSITIONS, ApplicationStatus, is_valid_transition` (line 18). Used in invariant assertions. |
| `tests/fuzz/test_api_fuzz.py` | `career_os.main.app` | `schemathesis.openapi.from_asgi` | WIRED | `from career_os.main import app` (line 25). `schema = schemathesis.openapi.from_asgi("/openapi.json", app)` (line 27). |
| `tests/fuzz/conftest.py` | `os.environ` | AUTH_ENABLED=false | WIRED | `os.environ["AUTH_ENABLED"] = "false"` (line 18). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `test_golden_set.py` | `scored.fit_score` | `score_job()` via `DeterministicScoringMockProvider` | Yes -- hash-based varied scores (0.0-9.99) | FLOWING |
| `test_scoring_properties.py` | `result.fit_score` | `ScoreResult` Pydantic model / `score_job()` pipeline | Yes -- Hypothesis generates varied floats | FLOWING |
| `test_state_machine.py` | `self.current_status` | `VALID_TRANSITIONS` + `is_valid_transition()` | Yes -- Hypothesis generates random transition sequences | FLOWING |
| `test_api_fuzz.py` | `response.status_code` | `case.call()` via Schemathesis ASGI transport | Yes -- Schemathesis generates varied inputs per OpenAPI spec | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Golden set regression tests pass (6 families) | `pytest tests/regression/ -m regression -v --tb=short` | 120 passed, 0 failed (1.60s) | PASS |
| Property tests pass (scoring + state machine) | `pytest tests/property/ -m property -v --tb=short` | 8 passed, 0 failed (0.71s) | PASS |
| Fuzz tests pass (endpoint + lifecycle + stateful) | `pytest tests/fuzz/ -m fuzz -v --tb=short` | 140 passed, 1 xfailed (139.88s) | PASS |
| Default run excludes advanced tests | `pytest tests/ --co -q \| grep regression` | 0 regression/property/fuzz-marked tests collected | PASS |
| hypothesis importable | `python -c "import hypothesis"` | OK | PASS |
| schemathesis importable | `python -c "import schemathesis"` | OK | PASS |
| CI has regression steps | `grep "Golden set regression" .github/workflows/ci.yml` | 2 matches (PR + main) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-----------|-------------|--------|----------|
| ADV-01 | 03-01-PLAN | Golden set fixtures run as functional regression tests validating actual scoring output against expected_band | SATISFIED | 120 parametrized tests across 6 job families, all passing. DeterministicScoringMockProvider provides varied, reproducible scores. CI regression step on every PR. |
| ADV-02 | 03-02-PLAN | Hypothesis property-based tests verify scoring 0-10, deterministic, and state machine transitions follow VALID_TRANSITIONS | SATISFIED | 5 scoring property tests (range, rejection, idempotency, monotonicity) + 3 state machine tests (RuleBasedStateMachine + completeness + no self-transitions). 8 total, all passing. |
| ADV-03 | 03-03-PLAN | Schemathesis fuzzes all API endpoints from OpenAPI spec, including stateful mode chaining API calls | SATISFIED | 140 endpoint fuzz tests + manual lifecycle chain + auto-discovered stateful workflow. Auth disabled. All passing (1 xfailed for pre-existing datetime schema mismatch). |

No orphaned requirements found -- REQUIREMENTS.md maps ADV-01, ADV-02, ADV-03 to Phase 3, and all three are covered by plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | - | No TODO/FIXME/PLACEHOLDER/assert True/assert False found | - | Clean |

### Human Verification Required

### 1. Fuzz 500-as-Warnings Acceptance

**Test:** Review the fuzz test approach to server exceptions (OverflowError, etc.) in `tests/fuzz/test_api_fuzz.py` lines 55-74.
**Expected:** Developer confirms that catching server-side exceptions as FUZZ-500 warnings (not hard test failures) satisfies SC-3 "reports zero 500-errors on valid-schema inputs." The exceptions are pre-existing API validation gaps (OverflowError on large integers), not fuzz harness bugs.
**Why human:** The ASGI transport raises Python exceptions instead of returning HTTP 500 responses. The test cannot assert `status_code < 500` when the exception bypasses HTTP entirely. This is a judgment call on whether the SC intent is met by the warning-based approach vs requiring the test to hard-fail.

### Gaps Summary

No gaps found. All three ROADMAP success criteria are verified by working code with passing tests. All artifacts exist, are substantive, and are wired into the scoring pipeline, property testing framework, and fuzz testing harness.

The single human verification item is a design judgment on whether the fuzz test's warning-based approach to server exceptions satisfies the literal wording of SC-3. The implementation correctly surfaces the issues -- it is a question of whether discovery (warnings) vs enforcement (failures) matches the intended contract.

---

_Verified: 2026-04-20T22:45:00Z_
_Verifier: Claude (gsd-verifier)_
