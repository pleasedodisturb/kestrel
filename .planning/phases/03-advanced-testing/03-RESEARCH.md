# Phase 3: Advanced Testing - Research

**Researched:** 2026-04-20
**Domain:** Property-based testing, golden set regression, API contract fuzzing
**Confidence:** HIGH

## Summary

Phase 3 adds three complementary testing layers: golden set regression (catches scoring band drift), Hypothesis property-based tests (proves pipeline invariants), and Schemathesis API fuzzing (validates OpenAPI contract compliance). All three use MockProvider -- zero AI costs in CI.

The golden set fixture files already exist in `tests/fixtures/` (TPM, finance, design -- 20, ~20, ~20 cases respectively). The `regression` marker is already registered in pyproject.toml. The MockProvider returns zeroed-out demo scores (fit_score=0.0), which means golden set tests against MockProvider will always produce band [0, 0] -- this is a critical design point the planner must address. Property tests and Schemathesis are net-new additions requiring `hypothesis` and `schemathesis` as dev dependencies.

**Primary recommendation:** Add hypothesis>=6.152 and schemathesis>=4.15 to dev dependencies. Register `property` and `fuzz` markers. Golden set tests load fixtures and call `score_job()` with MockProvider. Property tests use `@given` for scoring invariants and `RuleBasedStateMachine` for state machine transitions. Schemathesis uses `from_asgi` for in-process fuzzing (no server startup needed).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Diverse job families -- include 5-8 families with 3-5 cases per band (low/medium/high). Leverages 288 job family presets from G-301.
- D-02: Band ranges, not exact scores -- each golden case defines expected range (e.g., high: 70-100). AI-driven scoring drifts between rubric versions; ranges catch gross regressions without being brittle.
- D-03: Any band-range violation fails immediately -- one failure = blocked PR.
- D-04: MockProvider with fixed responses -- tests prove the scoring PIPELINE is correct (0-100 clamping, band assignment, state transitions) without calling real AI.
- D-05: Three additional properties beyond 0-100 and determinism: band monotonicity, state machine completeness, idempotent rescoring.
- D-06: Auth disabled for fuzzing -- run Schemathesis with AUTH_ENABLED=false.
- D-07: Stateful mode on application lifecycle chain -- create profile -> create application -> update status -> add contact.
- D-08: JSON fixture files in tests/fixtures/ -- static, version-control friendly.
- D-09: Run actual scoring with MockProvider -- golden set loads job+profile data, calls real scoring pipeline, asserts output falls in expected band.
- D-10: Golden set in PR, property+fuzz nightly only.
- D-11: Excluded from default run, opt-in -- `pytest -m 'not regression and not property and not fuzz'` is the default.

### Claude's Discretion
- Specific Hypothesis strategies for property tests
- Schemathesis CLI flags and configuration
- Golden set fixture internal structure (exact JSON schema)
- How to start/stop the test server for Schemathesis in CI
- Number of cases per job family (within 3-5 range)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ADV-01 | Golden set fixtures run as functional regression tests validating actual scoring output against expected_band | Fixtures exist at `tests/fixtures/scoring_golden_set*.json`. Tests call `score_job()` with MockProvider, assert `fit_score` in `expected_band`. Marker `regression` already registered. |
| ADV-02 | Hypothesis property-based tests verify scoring 0-100, deterministic, and state machine transitions follow VALID_TRANSITIONS | Hypothesis 6.152.1 available. Use `@given` with floats/integers for scoring invariants. Use `RuleBasedStateMachine` for state machine. VALID_TRANSITIONS dict in `schemas/applications.py` is the canonical source. |
| ADV-03 | Schemathesis fuzzes all API endpoints from OpenAPI spec, including stateful mode | Schemathesis 4.15.2 available. Use `from_asgi("/openapi.json", app)` for in-process testing. Stateful mode via `schema.as_state_machine()`. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Golden set regression | Test layer (pytest) | API / Backend | Tests invoke scoring service directly via `score_job()`, not HTTP |
| Property-based scoring tests | Test layer (pytest) | API / Backend | Tests validate scoring pipeline invariants using Hypothesis strategies |
| State machine property tests | Test layer (pytest) | -- | Tests validate `VALID_TRANSITIONS` dict directly, pure logic |
| API contract fuzzing | Test layer (pytest) | API / Backend | Schemathesis tests the FastAPI app via ASGI transport (in-process) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| hypothesis | 6.152.1 | Property-based test generation | De facto standard for Python property testing [VERIFIED: pip index] |
| schemathesis | 4.15.2 | OpenAPI contract fuzzing | Purpose-built for OpenAPI/ASGI fuzzing, Hypothesis-based [VERIFIED: pip index] |
| pytest | >=8.3.0 | Test framework | Already in use, markers for regression/property/fuzz [VERIFIED: pyproject.toml] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-asyncio | >=0.25.0 | Async test support | Already installed; needed for `score_job()` which is async [VERIFIED: pyproject.toml] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| schemathesis | dredd | Schemathesis is Python-native, Hypothesis-powered, supports stateful chains; dredd is Node-based |
| hypothesis | manual fuzz loops | Hypothesis has shrinking, reproducibility, database caching -- manual loops miss edge cases |

**Installation:**
```bash
pip install hypothesis>=6.152.0 schemathesis>=4.15.0
```

Add to `pyproject.toml` under `[project.optional-dependencies] dev`:
```
"hypothesis>=6.152.0",
"schemathesis>=4.15.0",
```

## Architecture Patterns

### System Architecture Diagram

```
Golden Set Tests (ADV-01)
  tests/fixtures/scoring_golden_set*.json
       |
       v
  load_golden_fixtures() --> score_job(db, profile_id, job_desc, ...)
       |                          |
       v                          v
  assert fit_score in         MockProvider.score()
  expected_band                   |
                                  v
                              ScoreResult(fit_score=0.0, ...)

Property Tests (ADV-02)
  Hypothesis @given strategies
       |
       v
  test_scoring_invariants() --> assert 0 <= fit_score <= 10
  test_determinism()        --> assert score_a == score_b
  test_band_monotonicity()  --> assert band(higher_score) >= band(lower_score)
       |
       v
  RuleBasedStateMachine     --> validates VALID_TRANSITIONS exhaustively
       |
       v
  assert no invalid state reached

API Fuzzing (ADV-03)
  schemathesis.openapi.from_asgi("/openapi.json", app)
       |
       v
  @schema.parametrize()     --> generates random valid inputs per endpoint
       |
       v
  case.call_and_validate()  --> asserts no 500 errors on valid-schema inputs
       |
       v
  schema.as_state_machine() --> chains: create profile -> create app -> update -> add contact
```

### Recommended Project Structure
```
tests/
├── fixtures/
│   ├── scoring_golden_set.json          # TPM golden set (exists)
│   ├── scoring_golden_set_finance.json  # Finance golden set (exists)
│   ├── scoring_golden_set_design.json   # Design golden set (exists)
│   ├── scoring_golden_set_healthcare.json  # Healthcare golden set (new)
│   ├── scoring_golden_set_legal.json       # Legal golden set (new)
│   └── scoring_golden_set_product.json     # Product/PM golden set (new)
├── regression/
│   └── test_golden_set.py              # ADV-01: golden set regression
├── property/
│   ├── test_scoring_properties.py      # ADV-02: scoring invariants
│   └── test_state_machine.py           # ADV-02: state machine properties
├── fuzz/
│   └── test_api_fuzz.py                # ADV-03: Schemathesis fuzzing
└── conftest.py                          # auto-marking hooks (exists)
```

### Pattern 1: Golden Set Regression Test
**What:** Load JSON fixtures, call scoring pipeline, assert output in expected band.
**When to use:** Every PR (fast with MockProvider).

**Critical design note:** MockProvider returns `fit_score=0.0` for ALL inputs (zeroed demo mode). This means golden set tests with MockProvider will always produce the same score. Two viable approaches:

1. **Test the pipeline plumbing, not AI quality** -- Assert that `score_job()` returns a valid `ScoredJob` with fit_score in [0, 10], that the correct fixture data flows through, and that the output schema matches expectations. The `expected_band` in fixtures documents what a REAL provider should produce, serving as living documentation.

2. **Create a `GoldenSetMockProvider`** that returns deterministic but varied scores based on input hashing (similar to how `_deterministic_seed()` works in `mock_provider.py`). This would allow band assertions to be meaningful.

Approach 2 is recommended per D-09 ("run actual scoring with MockProvider... asserts output falls in expected band"). The golden set mock should return scores that vary by job description hash to make band checks meaningful.

```python
# Source: project codebase patterns + Hypothesis docs
import json
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

def load_golden_set(filename: str) -> dict:
    with open(FIXTURES_DIR / filename) as f:
        return json.load(f)

@pytest.mark.regression
class TestGoldenSetTPM:
    """Golden set regression for TPM job family."""

    @pytest.fixture(autouse=True)
    def setup_golden_data(self):
        self.golden = load_golden_set("scoring_golden_set.json")

    @pytest.mark.parametrize("job_idx", range(20))
    async def test_scoring_band(self, db_session, job_idx):
        job = self.golden["jobs"][job_idx]
        profile = self.golden["profile"]
        # Setup profile in DB, call score_job(), assert band
        result = await score_job(db_session, profile_id, job["description"])
        low, high = job["expected_band"]
        assert low <= result.fit_score <= high, (
            f"Job {job['id']}: fit_score {result.fit_score} "
            f"outside expected band [{low}, {high}]"
        )
```

### Pattern 2: Hypothesis Property-Based Scoring Tests
**What:** Prove invariants hold for ALL possible inputs.
**When to use:** Nightly CI (slower, thorough).

```python
# Source: Hypothesis docs (hypothesisworks/hypothesis)
from hypothesis import given, settings, strategies as st
import pytest

@pytest.mark.property
@given(fit_score=st.floats(min_value=0, max_value=10))
@settings(max_examples=200)
def test_score_always_in_range(fit_score):
    """fit_score is always 0-10 (Pydantic enforces this)."""
    from career_os.schemas.ai import ScoreResult
    # ScoreResult has ge=0, le=10 on fit_score
    # This verifies the constraint holds for all floats in range
    result = ScoreResult(
        fit_score=fit_score,
        reasoning="test",
        estimated_salary="test",
        effort_flag="low",
        prep_level="light",
        prep_notes="test",
        readiness_score=50.0,
        career_alignment=5.0,
        score_breakdown=[
            {"factor": "test", "contribution": 1.0, "description": "test"},
            {"factor": "test2", "contribution": 1.0, "description": "test2"},
            {"factor": "test3", "contribution": 1.0, "description": "test3"},
        ],
    )
    assert 0 <= result.fit_score <= 10
```

### Pattern 3: State Machine Property Test with RuleBasedStateMachine
**What:** Prove VALID_TRANSITIONS never reaches an invalid state.
**When to use:** Nightly CI.

```python
# Source: Hypothesis docs - stateful testing
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize
from hypothesis import strategies as st
from career_os.schemas.applications import ApplicationStatus, VALID_TRANSITIONS, is_valid_transition

class ApplicationStateMachine(RuleBasedStateMachine):
    """Verify state machine never reaches invalid state."""

    def __init__(self):
        super().__init__()
        self.current_status = None

    @initialize()
    def start(self):
        self.current_status = ApplicationStatus.discovered

    @rule(target_status=st.sampled_from(list(ApplicationStatus)))
    def attempt_transition(self, target_status):
        if is_valid_transition(self.current_status, target_status):
            self.current_status = target_status
        # Invariant: current_status is always a valid ApplicationStatus
        assert self.current_status in ApplicationStatus.__members__.values()
        # Invariant: current status always has an entry in VALID_TRANSITIONS
        assert self.current_status in VALID_TRANSITIONS

TestApplicationStateMachine = ApplicationStateMachine.TestCase
```

### Pattern 4: Schemathesis API Fuzzing (ASGI in-process)
**What:** Fuzz all endpoints from OpenAPI spec without starting a server.
**When to use:** Nightly CI.

```python
# Source: Schemathesis docs (schemathesis/schemathesis) - from_asgi
import schemathesis
from hypothesis import settings
from career_os.main import app

schema = schemathesis.openapi.from_asgi("/openapi.json", app)

@pytest.mark.fuzz
@schema.parametrize()
@settings(max_examples=50)
def test_api_no_500(case):
    """No endpoint returns 500 on valid-schema inputs."""
    response = case.call_and_validate()
    assert response.status_code < 500
```

### Pattern 5: Schemathesis Stateful Mode
**What:** Chain dependent API calls (create profile -> create app -> update -> add contact).
**When to use:** Nightly CI.

```python
# Source: Schemathesis docs - stateful testing
import schemathesis
from hypothesis import settings
from career_os.main import app

schema = schemathesis.openapi.from_asgi("/openapi.json", app)

class APIWorkflow(schema.as_state_machine()):
    def setup(self):
        # Ensure clean state
        pass

TestAPIWorkflow = APIWorkflow.TestCase
TestAPIWorkflow.settings = settings(max_examples=50, stateful_step_count=5)
```

### Anti-Patterns to Avoid
- **Asserting exact scores with MockProvider:** MockProvider returns 0.0 for all inputs. Either use a golden-set-specific mock that varies by input hash, or assert pipeline plumbing only.
- **Running property/fuzz tests on every PR:** They are slow. Keep them nightly per D-10.
- **Including advanced tests in default pytest run:** Per D-11, default run must exclude regression/property/fuzz markers.
- **Mocking the database in golden set tests:** Per project rules, use `db_session` fixture. Golden set tests are integration tests.
- **Hard-coding exact scores in golden fixtures:** Use band ranges per D-02 to tolerate AI drift.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Property-based input generation | Custom random generators | Hypothesis strategies | Shrinking, reproducibility, edge case discovery |
| API contract validation | Manual endpoint-by-endpoint tests | Schemathesis from_asgi | Auto-generates from OpenAPI spec, catches schema violations |
| Stateful API testing | Sequential test scripts | Schemathesis state machine | Automatic dependency chaining from OpenAPI links |
| Test case serialization | Custom fixture loaders | pytest parametrize + JSON | Built-in, debuggable, CI-friendly |

## Common Pitfalls

### Pitfall 1: MockProvider Returns Constant Scores
**What goes wrong:** MockProvider returns `fit_score=0.0` for ALL inputs. Golden set band assertions become meaningless -- every test passes or every test fails.
**Why it happens:** MockProvider is designed for UI development, not scoring differentiation.
**How to avoid:** Create a `GoldenSetMockProvider` or monkey-patch MockProvider's `_handle_score` in golden set tests to return scores derived from input hash (e.g., hash(job_description) % 10).
**Warning signs:** All golden set tests pass with identical scores; band assertions never trigger.

### Pitfall 2: Hypothesis Database Accumulation
**What goes wrong:** Hypothesis stores its example database in `.hypothesis/` by default. This can grow large and cause issues if committed to git.
**Why it happens:** Hypothesis persists interesting examples for replay.
**How to avoid:** Add `.hypothesis/` to `.gitignore`. In CI, set `HYPOTHESIS_DATABASE_BACKEND=none` or use `settings(database=None)`.
**Warning signs:** `.hypothesis/` directory in git status, slow test startup.

### Pitfall 3: Schemathesis Hitting Auth Endpoints
**What goes wrong:** Schemathesis generates requests that fail on auth before reaching the actual endpoint logic, producing false 401/403 reports.
**Why it happens:** API has optional auth (`AUTH_ENABLED` flag).
**How to avoid:** Per D-06, run with `AUTH_ENABLED=false`. Set this as an environment variable in the test fixture or conftest.
**Warning signs:** Mass 401 errors in Schemathesis output.

### Pitfall 4: Marker Exclusion Not Working
**What goes wrong:** Advanced tests run in the default `pytest` invocation, slowing down local dev.
**Why it happens:** Markers registered but not excluded in default config.
**How to avoid:** Add `addopts = "-m 'not regression and not property and not fuzz'"` to `[tool.pytest.ini_options]` in pyproject.toml.
**Warning signs:** Test count jumps unexpectedly, `pytest` takes much longer than expected.

### Pitfall 5: Schemathesis Stateful Mode Requires API Links
**What goes wrong:** `schema.as_state_machine()` produces no transitions because the OpenAPI spec lacks `links` or response references.
**Why it happens:** Stateful mode relies on OpenAPI links to chain operations.
**How to avoid:** Either add OpenAPI links to the FastAPI app, or manually define the state machine transitions in a custom class inheriting from the generated one. Use `before_call` / `after_call` hooks to extract IDs from responses and inject into subsequent requests.
**Warning signs:** Stateful test runs but explores zero transitions.

### Pitfall 6: Async Score Job in Sync Tests
**What goes wrong:** `score_job()` is an async function. Calling it from sync test code fails.
**Why it happens:** Golden set tests may be written as sync functions.
**How to avoid:** Use `@pytest.mark.asyncio` on golden set tests, or use `pytest-asyncio` with `asyncio_mode = "auto"` (already configured in pyproject.toml).
**Warning signs:** `RuntimeError: cannot be called from a running event loop` or similar.

## Code Examples

### Golden Set Fixture Schema (verified from existing files)
```json
{
  "profile": {
    "job_family": "TPM",
    "location": "Berlin, Germany",
    "key_skills": ["Python", "AI/ML", "Program Management"]
  },
  "jobs": [
    {
      "id": "gs-01",
      "category": "reject",
      "expected_band": [1, 3],
      "title": "Senior .NET Developer",
      "company": "SAP SE",
      "location": "Walldorf, Germany",
      "description": "Build enterprise ERP modules in C#/.NET 8..."
    }
  ]
}
```
Source: `tests/fixtures/scoring_golden_set.json` [VERIFIED: codebase]

### ScoreResult Schema (verified)
```python
class ScoreResult(BaseModel):
    fit_score: float = Field(..., ge=0, le=10)  # 0-10 scale, NOT 0-100
    reasoning: str
    estimated_salary: str
    effort_flag: str
    prep_level: str
    prep_notes: str
    readiness_score: float = Field(..., ge=0, le=100)  # 0-100 scale
    career_alignment: float = Field(..., ge=0, le=10)  # 0-10 scale
    score_breakdown: list[ScoreBreakdownFactor]
    dimensional_scores: DimensionalScores | None
    ats_keywords: list[ATSKeyword]
    desire_score: float | None = Field(default=None, ge=0, le=10)
    desire_reasoning: str | None
```
Source: `src/career_os/schemas/ai.py` [VERIFIED: codebase]

**IMPORTANT NOTE:** The success criteria says "scoring output is always 0-100" but `fit_score` is actually 0-10, while `readiness_score` is 0-100. Property tests must use the correct ranges.

### VALID_TRANSITIONS (verified)
```python
VALID_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.discovered: {interested, ghosted},
    ApplicationStatus.interested: {discovered, applied, ghosted},
    ApplicationStatus.applied: {interested, discovered, interviewing, ghosted},
    ApplicationStatus.interviewing: {applied, interested, discovered, offer, ghosted},
    ApplicationStatus.offer: {interviewing, accepted, rejected, ghosted},
    ApplicationStatus.accepted: {discovered},
    ApplicationStatus.rejected: {discovered},
    ApplicationStatus.ghosted: {discovered},
}
```
Source: `src/career_os/schemas/applications.py` [VERIFIED: codebase]

### Pytest Marker Configuration (current)
```toml
markers = [
    "unit: Pure logic tests (auto-applied)",
    "integration: Tests using database/API (auto-applied)",
    "slow: Tests exceeding 5s (auto-detected)",
    "smoke: Health check tests (manual)",
    "regression: Golden set regression tests (Phase 3, ADV-01)",
]
```
Source: `pyproject.toml` [VERIFIED: codebase]

Note: `property` and `fuzz` markers are NOT yet registered. Must be added.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual API testing scripts | Schemathesis from_asgi (in-process) | schemathesis 3.x+ | No server startup needed, faster, more reliable |
| Random testing | Hypothesis with shrinking | Stable since 2016 | Automatic minimal failing example discovery |
| dredd for API testing | Schemathesis | 2020+ | Python-native, better stateful support |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | GoldenSetMockProvider approach will produce meaningful band variation via input hashing | Architecture Patterns | If hash-based scoring is too uniform, band assertions become meaningless -- need to calibrate hash function |
| A2 | Schemathesis stateful mode can chain operations even without explicit OpenAPI links | Common Pitfalls | If links are required, must either add them to FastAPI app or use custom state machine class |
| A3 | `addopts` marker exclusion in pyproject.toml will not conflict with CI marker selection | Pitfalls | If CI override doesn't work correctly, tests may be skipped unintentionally |

## Open Questions (RESOLVED)

1. **MockProvider scoring strategy for golden set** (RESOLVED)
   - What we know: MockProvider returns fit_score=0.0 for all inputs. Golden set fixtures have expected_band ranges.
   - Resolution: Create a `DeterministicScoringMockProvider` that hashes the job description via `_deterministic_seed()` to produce varied but reproducible scores. Implemented in Plan 03-01 Task 2 conftest.py. Score formula: `(seed % 1000) / 100.0` maps to 0.0-9.99 range.

2. **Schemathesis OpenAPI links for stateful mode** (RESOLVED)
   - What we know: FastAPI auto-generates OpenAPI spec at `/openapi.json`. Stateful mode works best with links.
   - Resolution: Check during implementation (Plan 03-03 Task 1). If no OpenAPI links present, fall back to a manual lifecycle chain test (POST profile -> POST application -> PATCH status -> POST contact). Covered in Plan 03-03 action with skipif fallback.

3. **Score range correction in success criteria** (RESOLVED)
   - What we know: Success criteria says "0-100" but `fit_score` is 0-10 (Pydantic enforced). `readiness_score` IS 0-100.
   - Resolution: Test both ranges. Property tests (Plan 03-02) assert `fit_score` 0-10 AND `readiness_score` 0-100 separately. Plans use correct ranges throughout.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with hypothesis 6.152 and schemathesis 4.15 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `pytest tests/regression/ -m regression -v --tb=short` |
| Full suite command | `pytest tests/ -v --tb=short -m 'regression or property or fuzz'` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADV-01 | Golden set scoring bands validated | regression | `pytest tests/regression/test_golden_set.py -m regression -x` | Wave 0 |
| ADV-02a | Scoring always 0-10 and deterministic | property | `pytest tests/property/test_scoring_properties.py -m property -x` | Wave 0 |
| ADV-02b | State machine transitions valid | property | `pytest tests/property/test_state_machine.py -m property -x` | Wave 0 |
| ADV-03a | No 500 errors on valid inputs | fuzz | `pytest tests/fuzz/test_api_fuzz.py -m fuzz -x` | Wave 0 |
| ADV-03b | Stateful API lifecycle chain | fuzz | `pytest tests/fuzz/test_api_fuzz.py::TestAPIWorkflow -m fuzz -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/regression/ -m regression -v --tb=short`
- **Per wave merge:** `pytest tests/ -v -m 'regression or property or fuzz'`
- **Phase gate:** Full advanced suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/regression/` directory and `__init__.py`
- [ ] `tests/regression/test_golden_set.py` -- covers ADV-01
- [ ] `tests/property/` directory and `__init__.py`
- [ ] `tests/property/test_scoring_properties.py` -- covers ADV-02a
- [ ] `tests/property/test_state_machine.py` -- covers ADV-02b
- [ ] `tests/fuzz/` directory and `__init__.py`
- [ ] `tests/fuzz/test_api_fuzz.py` -- covers ADV-03
- [ ] `property` and `fuzz` markers in pyproject.toml
- [ ] `hypothesis>=6.152.0` and `schemathesis>=4.15.0` in dev dependencies
- [ ] `.hypothesis/` added to `.gitignore`
- [ ] `addopts` updated in pyproject.toml to exclude regression/property/fuzz from default run

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Auth disabled for fuzzing per D-06 |
| V3 Session Management | no | Not applicable to test infrastructure |
| V4 Access Control | no | Tests run with no auth |
| V5 Input Validation | yes | Schemathesis validates API accepts/rejects inputs per OpenAPI schema |
| V6 Cryptography | no | Not applicable |

### Known Threat Patterns for Test Infrastructure

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Schemathesis finds 500 on malformed input | Tampering | Fix endpoint validation, add Pydantic schema constraints |
| Property test finds out-of-range score | Tampering | Fix scoring pipeline clamping logic |
| State machine finds invalid transition | Elevation | Fix VALID_TRANSITIONS or transition validation code |

## Sources

### Primary (HIGH confidence)
- `/hypothesisworks/hypothesis` Context7 -- stateful testing, strategies, pytest integration [VERIFIED: Context7]
- `/schemathesis/schemathesis` Context7 -- from_asgi, parametrize, stateful mode, FastAPI integration [VERIFIED: Context7]
- `tests/fixtures/scoring_golden_set*.json` -- existing fixture files [VERIFIED: codebase]
- `src/career_os/schemas/ai.py` -- ScoreResult schema with field constraints [VERIFIED: codebase]
- `src/career_os/schemas/applications.py` -- VALID_TRANSITIONS dict [VERIFIED: codebase]
- `src/career_os/ai/mock_provider.py` -- MockProvider returns fit_score=0.0 [VERIFIED: codebase]
- `pyproject.toml` -- existing markers and pytest config [VERIFIED: codebase]

### Secondary (MEDIUM confidence)
- hypothesis 6.152.1 latest on PyPI [VERIFIED: pip index]
- schemathesis 4.15.2 latest on PyPI [VERIFIED: pip index]

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- hypothesis and schemathesis are mature, well-documented, verified via Context7 and PyPI
- Architecture: HIGH -- patterns directly from official docs and existing codebase
- Pitfalls: HIGH -- MockProvider behavior verified by reading source code, marker config verified in pyproject.toml

**Research date:** 2026-04-20
**Valid until:** 2026-05-20 (stable libraries, 30-day validity)
