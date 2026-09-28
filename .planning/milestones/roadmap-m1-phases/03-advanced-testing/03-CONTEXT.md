# Phase 3: Advanced Testing - Context

**Gathered:** 2026-04-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Prove scoring correctness and API contract stability through three complementary test types: golden set regression (catches band drift), property-based tests with Hypothesis (proves invariants), and Schemathesis API fuzzing (validates OpenAPI contract compliance). All run with MockProvider in CI — no real AI costs.

</domain>

<decisions>
## Implementation Decisions

### Golden Set Design
- **D-01:** Diverse job families — include 5-8 families (tech, finance, design, healthcare, etc.) with 3-5 cases per band (low/medium/high). Leverages the 288 job family presets from G-301. Tests that scoring rubric generalizes across domains.
- **D-02:** Band ranges, not exact scores — each golden case defines an expected range (e.g., high: 70-100). AI-driven scoring drifts between rubric versions; ranges catch gross regressions without being brittle.
- **D-03:** Any band-range violation fails immediately — one failure = blocked PR. Ranges are set wide enough that a violation is always meaningful.

### Property Test Scope
- **D-04:** MockProvider with fixed responses — tests prove the scoring PIPELINE is correct (0-100 clamping, band assignment, state transitions) without calling real AI. Fast, reproducible, CI-safe.
- **D-05:** Three additional properties beyond 0-100 and determinism:
  - Band monotonicity: if score increases, band never decreases
  - State machine completeness: every ApplicationStatus has valid transitions, no transition leads to undefined status
  - Idempotent rescoring: same job+profile with MockProvider always produces identical result

### API Fuzzing Strategy
- **D-06:** Auth disabled for fuzzing — run Schemathesis with AUTH_ENABLED=false. Tests pure API contract compliance without conflating auth failures with schema violations.
- **D-07:** Stateful mode on application lifecycle chain — chain: create profile → create application → update status → add contact. Exercises the most common user flow and state machine transitions.

### Test Data & Fixtures
- **D-08:** JSON fixture files in tests/fixtures/ — static, version-control friendly, reviewable. Named per success criteria: scoring_golden_set.json (plus per-family files like finance_golden_set.json).
- **D-09:** Run actual scoring with MockProvider — golden set loads job+profile data, calls real scoring pipeline with MockProvider, asserts output falls in expected band. Full pipeline end-to-end test.

### CI Integration
- **D-10:** Golden set in PR, property+fuzz nightly only — golden set is fast (MockProvider) so it runs on every PR and catches regressions immediately. Property tests and Schemathesis need more time/server so they run in Phase 4's nightly pipeline.

### Test Markers
- **D-11:** Excluded from default run, opt-in — `pytest -m 'not regression and not property and not fuzz'` is the default. Advanced tests only run when explicitly requested or in dedicated CI jobs. Keeps local dev fast.

### Claude's Discretion
- Specific Hypothesis strategies for property tests (how to generate profiles, scores)
- Schemathesis CLI flags and configuration (max examples, timeout, base URL)
- Golden set fixture internal structure (exact JSON schema for each case)
- How to start/stop the test server for Schemathesis in CI
- Number of cases per job family (within the 3-5 range)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scoring System
- `src/career_os/services/scoring.py` — Main scoring service (AI-powered, rubric v1.1)
- `src/career_os/schemas/ai.py` — ScoreResult schema (output format for scoring)
- `src/career_os/ai/mock_provider.py` — MockProvider implementation (for golden set and property tests)

### State Machine
- `src/career_os/schemas/applications.py` — VALID_TRANSITIONS dict (canonical state machine definition, property tests validate this)

### Test Infrastructure (from Phase 1 & 2)
- `tests/conftest.py` — Auto-marking hooks, INTEGRATION_FIXTURES, db_session fixture
- `pyproject.toml` — Pytest markers (regression, property, fuzz already registered)
- `TESTING.md` — Test quality standards (from Phase 2)

### API Contract
- `/openapi.json` endpoint — Auto-generated OpenAPI spec (Schemathesis fuzzes against this)
- `src/career_os/main.py` — FastAPI app with auto-generated docs

### Requirements
- `.planning/REQUIREMENTS.md` — ADV-01, ADV-02, ADV-03 acceptance criteria

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/career_os/ai/mock_provider.py` — MockProvider already implements `complete()` and `score()` with deterministic responses — no need to build a test double
- `tests/conftest.py` — `db_session` fixture provides isolated SQLAlchemy sessions, auto-marking hooks apply markers by directory
- `regression` marker already registered in pyproject.toml (from Phase 1) — just needs test files using it
- VALID_TRANSITIONS dict in `schemas/applications.py` — the authoritative state machine, property tests validate this directly

### Established Patterns
- AI tests use `MockProvider` (never real providers in CI) — established across 108 test files
- Scoring tests exist in `tests/test_scoring.py`, `tests/test_scoring_rubric.py` — follow these patterns for golden set
- Fixtures loaded via `conftest.py` or `@pytest.fixture` decorators — JSON fixtures should follow same pattern

### Integration Points
- `src/career_os/main.py` — FastAPI app instance for Schemathesis to target
- `pyproject.toml [tool.pytest.ini_options]` — marker registration, test configuration
- `.github/workflows/ci.yml` — golden set step goes in PR backend job; property/fuzz go in Phase 4 nightly

</code_context>

<specifics>
## Specific Ideas

- Golden set should leverage the 288 job family presets shipped in G-301 (self-calibrating scoring)
- Band ranges should be calibrated from actual scoring output during fixture creation — run scoring once, record bands, set ranges ±10 points
- Schemathesis stateful mode chains should mirror the actual user journey (discover → apply → interview → offer)
- Property tests for state machine should use Hypothesis `@rule` strategies to generate arbitrary transition sequences

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-advanced-testing*
*Context gathered: 2026-04-20*
