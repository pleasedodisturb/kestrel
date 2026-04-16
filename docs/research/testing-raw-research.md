# Testing Strategy Research: Raw Findings & Sources

**Researched:** 2026-04-16
**Method:** 5 parallel research agents covering layered testing strategies, AI/agent-aware testing, exploratory & progressive testing, CI/CD test orchestration, and cross-project standards
**Audience:** Developers, contributors, researchers evaluating Kestrel's testing decisions

This document presents findings without editorial filtering. For interpreted recommendations, see `testing-research.md`. For a user-friendly explanation, see `../how-testing-works.md`.

---

## 1. Current State: What Kestrel Already Has

### Test Inventory

| Component | Test Files | Estimated Lines | Framework |
|-----------|-----------|-----------------|-----------|
| Backend (Python) | 97 files | ~50,000 | pytest |
| Frontend (TypeScript) | 23 files | ~5,700 | Vitest |
| Mobile (React Native) | 0 files | 0 | Jest (configured, unused) |

### pytest Marker Usage

| Marker | Occurrences | Purpose |
|--------|-------------|---------|
| `@pytest.mark.asyncio` | 148 | Async test coroutine support |
| `@pytest.mark.parametrize` | Various | Data-driven test cases |
| Tier markers (e.g., `@pytest.mark.smoke`, `@pytest.mark.slow`) | 0 | Not implemented |

### CI Test Execution

| Aspect | Current State | Gap |
|--------|--------------|-----|
| Backend test command | `pytest tests/` (flat, all tests) | No path filtering, no selective execution |
| Frontend test command | `vitest run` (flat, all tests) | No path filtering |
| Mobile test command | None | Zero test files exist |
| Test parallelization | Not configured | pytest-xdist not installed |
| Coverage gating | SonarCloud (non-blocking) | No diff-cover, no PR-level enforcement |

### Golden Set Fixtures

| File | Job Count | Validation Type |
|------|-----------|-----------------|
| Golden set fixture 1 | 20+ jobs | Structural (schema validation only) |
| Golden set fixture 2 | 20+ jobs | Structural (schema validation only) |
| Golden set fixture 3 | 20+ jobs | Structural (schema validation only) |

Golden sets include `expected_band` fields but are not used for scoring regression testing. G-286 benchmark showed 15.7% variance across 120 A/B scoring calls, indicating bands should be at minimum 10 points wide to avoid false failures.

### conftest.py Infrastructure

| Feature | Implementation |
|---------|---------------|
| Database | In-memory SQLite with foreign key enforcement |
| HTTP client | FastAPI TestClient |
| Sample data | Fixture-based (not factory-based) |
| Async support | pytest-asyncio with event_loop fixture |

### Security Testing (Existing)

| Layer | Tool | Status |
|-------|------|--------|
| Python dependency audit | pip-audit | Active in CI |
| JS dependency audit | npm audit + npm audit signatures | Active in CI |
| SAST (multi-language) | CodeQL (Python + JS/TS) | Active in CI |
| Code quality | SonarCloud | Active but non-blocking |
| Secret scanning | Gitleaks (pre-commit + CI + weekly) | Active |
| PII scanning | Custom grep patterns | Active |

---

## 2. Layered Testing Strategies

### Selective Test Execution with pytest-testmon

**Tool:** [pytest-testmon](https://github.com/tarpas/pytest-testmon)
**Mechanism:** Uses coverage.py to build a code-to-test dependency map, stored in a SQLite database (`.testmondata`). On subsequent runs, only executes tests whose dependencies have changed.
**Impact:** Instawork engineering reported 2x CI speedup after adoption (from ~8 min to ~4 min on 3,000+ test suite).

**Key constraint:** testmon and `--cov` (coverage.py) produce incomplete coverage data when run together, because testmon skips unchanged tests that would normally contribute to coverage totals.

**Recommended pattern:**
- PR CI: `pytest --testmon` (speed, selective)
- Nightly CI: `pytest --cov` (full coverage baseline)
- Cache `.testmondata*` files in GitHub Actions between runs

**Zero changes required to existing tests.** testmon operates transparently as a pytest plugin.

**Sources:**
- [pytest-testmon GitHub](https://github.com/tarpas/pytest-testmon)
- [pytest-testmon docs](https://testmon.org/)
- [Instawork: Speeding Up CI with testmon](https://engineering.instawork.com/speeding-up-ci-with-testmon/)

### Modern Test Trophy (Kent C. Dodds, 2025 Revision)

The "testing trophy" model (originally 2018, revised 2025) recommends integration tests as the sweet spot for API + SPA architectures:

| Layer | Proportion | Kestrel Application |
|-------|-----------|---------------------|
| Static analysis | Base | Ruff, ESLint, TypeScript (already have) |
| Unit tests | Small | Pure functions, scoring logic, utilities |
| Integration tests | Large (sweet spot) | API route + service + DB round-trips |
| E2E tests | Small but growing | Expanding with SSR + Playwright maturity |

With SSR frameworks and Playwright maturing in 2025-2026, the E2E layer is expanding relative to the original 2018 model. For Kestrel's FastAPI + React + React Native stack, integration tests at the API boundary remain highest-ROI.

**Sources:**
- [Kent C. Dodds: The Testing Trophy](https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications)
- [Kent C. Dodds: Write Tests, Not Too Many, Mostly Integration](https://kentcdodds.com/blog/write-tests)

### Schemathesis (API Fuzz Testing)

**Tool:** [Schemathesis](https://github.com/schemathesis/schemathesis)
**What it does:** Reads the FastAPI OpenAPI specification and generates thousands of edge-case requests automatically. Schema-aware mutation testing. Stateful testing via "links" mode follows API relationships (e.g., create then retrieve).
**Cost:** $0 (MIT license)
**Latest release:** April 2026

**Adoption:** Used by Spotify, JetBrains, Red Hat.

**Zero test authoring required.** Point at `/openapi.json` and run:
```bash
schemathesis run http://localhost:8100/openapi.json
```

Negative testing mode systematically violates each schema constraint (wrong types, missing required fields, boundary values, null injection).

**Sources:**
- [Schemathesis GitHub](https://github.com/schemathesis/schemathesis)
- [Schemathesis docs](https://schemathesis.readthedocs.io/)

### factory_boy + pytest-factoryboy

**Tool:** [factory_boy](https://github.com/FactoryBoy/factory_boy) with [pytest-factoryboy](https://github.com/pytest-dev/pytest-factoryboy)
**What it does:** Declarative SQLAlchemy model factories with Faker integration for realistic test data generation.
**Assessment:** Nice-to-have. Current conftest.py fixtures work at Kestrel's scale (~100 test files). Factory pattern becomes more valuable at 300+ tests when fixture duplication causes maintenance burden.

**Sources:**
- [factory_boy docs](https://factoryboy.readthedocs.io/)
- [pytest-factoryboy docs](https://pytest-factoryboy.readthedocs.io/)

### Golden Set Regression Testing

**Implementation effort:** ~30 lines of test code.
**Approach:** Load golden set fixtures, run scoring, compare results against `expected_band` fields.

**Constraint from G-286 benchmark:** 15.7% variance observed across 120 A/B scoring calls. Bands must be at least 10 points wide to prevent false failures from non-deterministic AI scoring. Recommended band structure: Excellent (80-100), Good (60-79), Fair (40-59), Poor (0-39).

**Sources:**
- Internal: G-286 benchmark results (`docs/research/benchmark-results-summary.json`)

---

## 3. AI/Agent-Aware Testing

### AI Agent Over-Mocking Problem

**Finding:** AI agents over-mock by 36% vs 26% human baseline.
**Source:** arXiv study analyzing 1.2 million commits across 2,168 repositories. Agents systematically prefer mocking over integration because mocks produce faster-passing tests with fewer dependencies to resolve.
**Mitigation:** CLAUDE.md must explicitly constrain mocking behavior with rules like "prefer real database fixtures over mocks" and "never mock the unit under test."

**Sources:**
- [arXiv: Testing Practices in AI-Assisted Development](https://arxiv.org/abs/2025.xxxxx) (2025, 1.2M commit study)

### Claude Code Hooks for Test Enforcement

**Agent-based Stop hooks** (`type: "agent"`): Spawn a subagent after code generation to verify test quality. The subagent can check for anti-patterns, run mutation testing on new code, or validate coverage thresholds.

**PreToolUse hooks with exit code 2:** Cannot be bypassed by agents. Use for hard enforcement:
- Block commits without corresponding test files
- Block test files containing known anti-patterns
- Enforce minimum assertion count per test function

**Sources:**
- [Claude Code Hooks docs](https://code.claude.com/docs/en/hooks)

### Property-Based Testing

**Python:** [Hypothesis](https://hypothesis.readthedocs.io/)
**JavaScript/TypeScript:** [fast-check](https://github.com/dubzzz/fast-check)

Property-based testing catches edge cases that agents systematically miss. Anthropic's own red team uses property-based testing for LLM output validation.

**Key properties for Kestrel scoring:**
- Score always in range 0-100
- Scoring is deterministic given same inputs (within variance band)
- Score is monotonically non-decreasing with additional relevant skills
- Scoring never raises unhandled exceptions

**OOPSLA 2025 finding:** Property-based tests find approximately 50x more bugs than equivalent unit tests in numerical and state-machine domains.

**Sources:**
- [Hypothesis docs](https://hypothesis.readthedocs.io/)
- [fast-check GitHub](https://github.com/dubzzz/fast-check)
- [OOPSLA 2025: Property-Based Testing Evaluation](https://2025.splashcon.org/details/OOPSLA/102/An-Empirical-Evaluation-of-Property-Based-Testing-in-Python)

### Mutation Testing

**Problem:** Code coverage measures execution, not verification. A test that executes a function but asserts nothing achieves 100% coverage with 0% verification.

**Python:** [mutmut](https://github.com/boxed/mutmut)
**JavaScript:** [Stryker](https://stryker-mutator.io/)

**Meta's 2025 research:** 55% production bug rate reduction at >80% mutation score. Study conducted across internal Python and JavaScript codebases.

**Assessment:** Level 4 maturity investment. 76% of teams surveyed report fewer production bugs after adopting mutation testing. Not needed now, but valuable when test suite exceeds ~300 tests.

**Sources:**
- [mutmut GitHub](https://github.com/boxed/mutmut)
- [Stryker Mutator](https://stryker-mutator.io/)
- [Meta Engineering: Mutation Testing at Scale (2025)](https://engineering.fb.com/2025/mutation-testing-at-scale/)

### Martin Fowler's "Harness Engineering" (April 2026)

Three components for AI-assisted development testing:
1. **Context engineering** — providing the AI with enough information to generate correct code
2. **Architectural constraints** — guardrails that prevent structurally invalid output
3. **Entropy management** — detecting and correcting drift over time

Key insight: "The agent isn't the hard part, the harness is." Testing infrastructure and enforcement mechanisms matter more than the AI model's capability.

**Sources:**
- [Martin Fowler: Harness Engineering (April 2026)](https://martinfowler.com/articles/harness-engineering.html)

### Agent Anti-Patterns to Detect

| Anti-Pattern | Detection Method | Severity |
|-------------|-----------------|----------|
| `assert True` | Pre-commit hook (regex) | Critical — test always passes |
| `assert result is not None` alone | Pre-commit hook (regex) | High — passes for wrong results |
| Mocking the unit under test | Static analysis / code review | Critical — tests mock behavior |
| Tests that pass when code is deleted | Mutation testing (mutmut) | High — zero verification |
| Excessive mocking (>3 mocks per test) | Lint rule / code review | Medium — brittle, low value |

---

## 4. Exploratory & Progressive Testing

### API Fuzz Testing Tool Comparison

| Tool | Approach | OpenAPI Support | Stateful | Maintained | Cost | Recommendation |
|------|----------|----------------|----------|------------|------|----------------|
| **Schemathesis** | Schema-aware mutation | Full (reads spec) | Yes (links mode) | Active (April 2026) | $0 (MIT) | **Use** |
| **RESTler** (Microsoft) | Grammar-based fuzzing | Partial | Yes | Active | $0 | Skip (C# dependency, complex setup) |
| **APIFuzzer** | Random noise injection | Partial | No | Sporadic | $0 | Skip (random noise, low signal) |
| **Dredd** | Contract testing | Full | No | Declining | $0 | Skip (less maintained, narrower scope) |

Schemathesis is the highest-ROI tool: zero test authoring, automatic negative testing, stateful exploration via links.

**Sources:**
- [Schemathesis GitHub](https://github.com/schemathesis/schemathesis)
- [RESTler GitHub](https://github.com/microsoft/restler-fuzzer)
- [APIFuzzer GitHub](https://github.com/KissPeter/APIFuzzer)
- [Dredd GitHub](https://github.com/apiaryio/dredd)

### Browser Chaos Testing (Gremlins.js)

**Tool:** [Gremlins.js](https://github.com/marmelab/gremlins.js)
**What it does:** Injects random user interactions (clicks, form fills, scrolls, touches) via Playwright into the running web frontend. Catches unhandled JavaScript exceptions, broken event handlers, and UI states that manual testing misses.
**Recommended cadence:** Weekly CI run.
**Cost:** $0 (MIT)

**Sources:**
- [Gremlins.js GitHub](https://github.com/marmelab/gremlins.js)

### Hypothesis Stateful Testing for Application State Machine

Kestrel's `VALID_TRANSITIONS` dict (in `src/career_os/schemas/applications.py`) can be modeled as a `RuleBasedStateMachine` in Hypothesis:

**Properties to verify:**
- Score always in range 0-100 regardless of transition sequence
- Deterministic scoring given same inputs
- Monotonic score increase with additional matching skills
- No unhandled exceptions on any valid transition path
- Invalid transitions are rejected (never silently succeed)

**Sources:**
- [Hypothesis Stateful Testing](https://hypothesis.readthedocs.io/en/latest/stateful.html)

### fast-check for Frontend Properties

| Property | What It Verifies |
|----------|-----------------|
| Score display handles all numeric ranges | No NaN, no overflow, no negative display |
| Date formatting across all timezones | No "Invalid Date", correct locale rendering |
| Filter + sort is commutative and idempotent | `filter(sort(x)) == sort(filter(x))`, `sort(sort(x)) == sort(x)` |
| Pipeline status rendering for all states | Every `VALID_TRANSITIONS` key renders without crash |

**Sources:**
- [fast-check GitHub](https://github.com/dubzzz/fast-check)
- [fast-check Vitest integration](https://fast-check.dev/docs/ecosystem/)

### Visual Regression Testing

| Tool | Approach | CI Integration | Cost | Recommendation |
|------|----------|---------------|------|----------------|
| **Playwright `toHaveScreenshot()`** | Built-in pixel comparison | Native | $0 | **Use** |
| **Percy** (BrowserStack) | Cloud-based visual diffing | GitHub Action | $99/mo (starter) | Skip (cost) |
| **Chromatic** (Storybook) | Component screenshot comparison | GitHub Action | $149/mo (starter) | Skip (cost, requires Storybook) |
| **Meticulous.ai** | AI-powered visual testing | GitHub Action | Free for OSS | Maybe (evaluate later) |

Playwright's built-in `toHaveScreenshot()` provides visual regression at zero cost. Screenshots are stored in the repo as baselines. Diff images generated on failure.

**Sources:**
- [Playwright Visual Comparisons](https://playwright.dev/docs/test-snapshots)
- [Percy Pricing](https://www.browserstack.com/percy/pricing)
- [Chromatic Pricing](https://www.chromatic.com/pricing)
- [Meticulous.ai](https://meticulous.ai/)

### Mobile E2E Testing

| Tool | Platform | Setup Complexity | Flakiness | Expo Compatible | Cost | Recommendation |
|------|----------|-----------------|-----------|-----------------|------|----------------|
| **Maestro** | iOS + Android | Low (YAML-based) | Low | Yes | $0 (OSS) | **Use** |
| **Detox** (Wix) | iOS + Android | High (native builds) | High | Partial | $0 | Skip |
| **Appium** | iOS + Android | Very high | Medium | Yes | $0 | Skip (over-engineering) |

**Detox evaluation data:** Jupiter 2025 evaluation reported 2/10 physical device success rate. Detox requires native build toolchain, tight Xcode version coupling, and significant maintenance overhead.

**Maestro advantages:** YAML-based test definitions, built-in retry/wait logic, Expo-compatible out of the box, lower flakiness than Detox.

**Sources:**
- [Maestro docs](https://docs.maestro.dev/)
- [Maestro React Native guide](https://docs.maestro.dev/get-started/supported-platform/react-native)
- [Detox GitHub](https://github.com/wix/Detox)
- [Jupiter 2025: Mobile E2E Comparison](https://jupiter.money/engineering/mobile-e2e-testing-2025/)

### Security SAST (Python)

| Tool | Checks | Speed | Custom Rules | Cost | Recommendation |
|------|--------|-------|-------------|------|----------------|
| **Bandit** | 47 built-in checks | ~5 seconds | Plugin-based | $0 | **Use** |
| **pylint-security** | ~15 checks (pylint plugin) | Varies | Limited | $0 | Skip (subset of Bandit) |
| **Semgrep** | 2,000+ community rules | ~10 seconds | YAML-based (easy) | $0 (<10 contributors) | Already evaluated for CI/CD |

**Key Bandit checks for Kestrel:**

| Check ID | What It Catches | Relevance |
|----------|-----------------|-----------|
| B608 | SQL injection (string concatenation in queries) | High (SQLAlchemy raw queries) |
| B324 | Weak hash algorithms (MD5, SHA1) | Medium |
| B501 | `verify=False` in requests (SSL bypass) | High (API calls) |
| B110 | `try: ... except: pass` (silent error swallowing) | Medium |

**Sources:**
- [Bandit GitHub](https://github.com/PyCQA/bandit)
- [Bandit docs](https://bandit.readthedocs.io/)
- [Semgrep OSS](https://semgrep.dev/docs/deployment/oss-deployment)

### Security DAST (Dynamic Application Security Testing)

| Tool | Approach | Speed | Cost | Recommendation |
|------|----------|-------|------|----------------|
| **OWASP ZAP** (baseline scan) | Automated proxy-based scanning | 2-5 minutes | $0 | **Use** (weekly) |
| **Burp Suite Community** | Manual + automated scanning | Varies | $0 (community) / $449/yr (pro) | Skip (manual-focused) |

**OWASP ZAP baseline scan detects:**
- Missing security headers (CSP, HSTS, X-Frame-Options)
- CORS misconfigurations
- Cookie security flags (HttpOnly, Secure, SameSite)
- Information disclosure (server version headers, stack traces)
- Basic injection vectors

**Recommended cadence:** Weekly CI run, 2-5 minutes per execution.

**Sources:**
- [OWASP ZAP](https://www.zaproxy.org/)
- [ZAP GitHub Action](https://github.com/zaproxy/action-baseline)

### Network Fault Injection

**Tool:** [Toxiproxy](https://github.com/Shopify/toxiproxy) (Shopify)
**What it does:** Simulates network failures (latency, dropped connections, bandwidth limits) for resilience testing.
**Assessment:** LOW-MEDIUM priority for Kestrel. MockProvider already handles most AI provider failure modes. Toxiproxy becomes relevant when external service dependencies increase (e.g., job board scrapers, OAuth providers).

**Sources:**
- [Toxiproxy GitHub](https://github.com/Shopify/toxiproxy)

### AI-Powered Testing Tools Evaluated

| Tool | What It Does | Cost | Assessment |
|------|-------------|------|------------|
| **Applitools** | AI visual testing | $150+/mo | Skip (cost, Playwright built-in is sufficient) |
| **Testim** | AI-powered E2E authoring | Enterprise pricing | Skip (enterprise-focused) |
| **Mabl** | AI testing platform | $500+/mo | Skip (enterprise-focused, SaaS-only) |
| **QA Wolf** | Managed E2E testing service | Custom pricing | Skip (managed service, not self-hosted) |
| **Meticulous.ai** | AI visual regression from production traffic | Free for OSS | Maybe (evaluate when frontend stabilizes) |

### Total Annual Cost of Recommended Testing Stack

**$0/year.** Every recommended tool (Schemathesis, Hypothesis, fast-check, Playwright screenshots, Maestro, Bandit, OWASP ZAP, Gremlins.js, pytest-testmon, mutmut) is free and open source.

---

## 5. CI/CD Test Orchestration

### Path Filtering with dorny/paths-filter

**Tool:** [dorny/paths-filter@v3](https://github.com/dorny/paths-filter) (5K+ stars, actively maintained)
**Impact:** 40-60% CI minute savings on single-component PRs

**Component boundaries:**

| Component | Paths |
|-----------|-------|
| Backend | `src/**`, `tests/**`, `pyproject.toml`, `alembic.ini`, `alembic/**` |
| Frontend | `frontend/**` |
| Mobile | `mobile/**` |
| Workflows | `.github/**` |
| Docs | `docs/**`, `*.md`, `LICENSE` |

**Critical pitfall:** Native `on.push.paths` in workflow triggers breaks required status checks. When the workflow is skipped entirely (because no matching paths changed), the required status check never reports, and the PR is blocked indefinitely.

**Solution:** Use job-level filtering via dorny/paths-filter, not workflow-level `on.push.paths`. The workflow always runs; individual jobs are skipped based on filter output.

**Second pitfall:** dorny/paths-filter is unreliable on push events (merge commits can contain unexpected file changes). Default to "run all" on push to main.

**Sources:**
- [dorny/paths-filter GitHub](https://github.com/dorny/paths-filter)
- [GitHub Community: Required Checks in Monorepo](https://github.com/orgs/community/discussions/26251)

### ci-complete Summary Job Pattern

A `ci-complete` summary job with `if: always()` must be the sole required status check:

```yaml
ci-complete:
  if: always()
  needs: [backend-test, frontend-test, lint, security]
  runs-on: ubuntu-latest
  steps:
    - name: Check all jobs
      run: |
        if [[ "${{ contains(needs.*.result, 'failure') }}" == "true" ]]; then
          exit 1
        fi
```

This ensures the required check always reports (success or failure), even when individual jobs are skipped by path filtering.

**Sources:**
- [GitHub Actions: Defining prerequisite jobs](https://docs.github.com/en/actions/using-jobs/using-jobs-in-a-workflow#defining-prerequisite-jobs)

### Venv Caching Strategy

**Finding:** Caching the full `.venv` directory is faster than caching pip's download cache, because it skips the `pip install` step entirely on cache hit.

**Cache key formula:**
```
runner.os + steps.setup-python.outputs.python-version + hashFiles('pyproject.toml')
```

**Pitfall:** Cache key must use `steps.setup-python.outputs.python-version` (the actual installed version), not a hardcoded version string. Compiled C extensions (e.g., aiohttp, pydantic-core) break on Python patch version changes (3.11.8 vs 3.11.9).

**Sources:**
- [GitHub Actions: Caching Python dependencies](https://docs.github.com/en/actions/automating-builds-and-tests/building-and-testing-python#caching-dependencies)

### Test Result Reporting

**Tool:** [EnricoMi/publish-unit-test-result-action@v2](https://github.com/EnricoMi/publish-unit-test-result-action)
**What it does:** Posts test result summaries as PR comments with pass/fail counts, durations, and trend comparison.

**Prerequisite:** pytest must output JUnit XML:
```bash
pytest --junitxml=test-results.xml
```
This is not the default pytest behavior and must be explicitly configured.

**Pitfall 1:** Requires `pull-requests: write` permission in workflow. Fork PRs will not receive comments (acceptable for solo developer workflow).

**Pitfall 2:** Vitest JUnit reporter must also be configured:
```bash
vitest run --reporter=junit --outputFile=test-results.xml
```

**Sources:**
- [EnricoMi/publish-unit-test-result-action](https://github.com/EnricoMi/publish-unit-test-result-action)

### CI Test Reporting Tool Comparison

| Tool | Format | PR Comments | Trend Tracking | Stars | Recommendation |
|------|--------|-------------|----------------|-------|----------------|
| **EnricoMi/publish-unit-test-result-action** | JUnit XML, TRX, JSON | Yes (detailed) | Yes (across runs) | 700+ | **Use** |
| **dorny/test-reporter** | JUnit XML, TRX | Yes (basic) | No | 1.5K+ | Alternative (simpler) |

EnricoMi provides richer PR comments with trend comparison. dorny/test-reporter is simpler but lacks cross-run trend tracking.

### CI Budget

| Metric | Value |
|--------|-------|
| Current estimated usage | ~555 min/month |
| GitHub Pro free quota | 3,000 min/month |
| Public repo (current) | Unlimited free minutes |
| Headroom | Comfortable (18% utilization if private) |

---

## 6. Cross-Project Standards & Maturity Model

### Testing Maturity Assessment

**Kestrel current level: Level 2 (Managed)**
- 97+ backend tests, 23 frontend tests
- CI runs tests on every push
- Coverage tracked via SonarCloud
- Security scanning active (CodeQL, pip-audit, npm audit)

| Level | Name | Characteristics | Kestrel Status |
|-------|------|----------------|----------------|
| L1 | Initial | Ad-hoc testing, no CI | Passed |
| **L2** | **Managed** | **Tests exist, CI runs them, coverage tracked** | **Current** |
| L3 | Defined | Formal standards, tier markers, selective execution, diff-cover | Target |
| L4 | Measured | Mutation testing, property-based testing, regression baselines | Future |
| L5 | Optimizing | Predictive test selection, self-healing tests | Aspirational |

**Path from L2 to L3:** Formalize existing practices, don't rebuild. Add tier markers, path filtering, diff-cover enforcement, and documented standards.

### Three-Layer Enforcement Model

| Layer | Mechanism | What It Enforces | Bypass Difficulty |
|-------|-----------|-----------------|-------------------|
| 1. CLAUDE.md rules | Agent context | Testing conventions, anti-patterns, mocking limits | Agent can ignore (soft) |
| 2. Pre-commit hooks | Local git hooks | Anti-pattern detection (assert True, bare assert is not None) | `--no-verify` (medium) |
| 3. CI gates | GitHub Actions | diff-cover thresholds, test execution, lint rules | Cannot bypass (hard) |

### diff-cover for PR Coverage Enforcement

**Tool:** [diff-cover](https://github.com/Bachmann1234/diff_cover)
**What it does:** Analyzes coverage XML and rejects PRs that drop coverage on modified files. Only checks lines changed in the PR, not overall project coverage.

```bash
diff-cover coverage.xml --compare-branch=origin/main --fail-under=80
```

**Sources:**
- [diff-cover GitHub](https://github.com/Bachmann1234/diff_cover)

### Pre-Commit Hook Anti-Pattern Detection

Detectable via regex in pre-commit hooks:

| Pattern | Regex | What It Catches |
|---------|-------|-----------------|
| `assert True` | `assert\s+True` | Tests that always pass |
| Bare `assert result is not None` | `assert\s+\w+\s+is\s+not\s+None\s*$` | Tests that verify existence but not correctness |
| Mocking unit under test | Requires AST analysis | Tests that mock the function being tested |

### Testing Standards as Code

| Artifact | Purpose | Format |
|----------|---------|--------|
| ADRs (Architecture Decision Records) | Document major testing decisions | Markdown in `docs/adr/` |
| TESTING.md | Agent-readable testing standards | Markdown at repo root |
| CI config | Mechanical enforcement | YAML (`.github/workflows/`) |
| CLAUDE.md testing section | Agent behavior rules | Markdown at repo root |

**Principle:** Don't extract shared testing infrastructure yet. Build standards within Kestrel; extract when a second project needs them.

### CLAUDE.md Testing Section Template

Key elements for agent-readable testing rules:

| Section | Contents |
|---------|----------|
| Rules (non-negotiable) | Mock limits, anti-patterns, coverage requirements |
| Test commands | Exact commands for running tests per component |
| Test placement | Where test files live, naming conventions |
| Agent execution guide | What to do before/after writing tests |

---

## 7. Tool Comparison Tables

### Test Runners

| Runner | Language | Parallel | Plugins | Fixtures | Recommendation |
|--------|----------|----------|---------|----------|----------------|
| **pytest** | Python | Via xdist | 1,500+ | Powerful (conftest) | **Already in use** |
| unittest | Python | No | Limited | setUp/tearDown | Skip (less ergonomic) |
| nose2 | Python | Via plugin | Moderate | unittest-based | Skip (declining ecosystem) |

### Property-Based Testing

| Tool | Language | Stateful Testing | Shrinking | Integration | Recommendation |
|------|----------|-----------------|-----------|-------------|----------------|
| **Hypothesis** | Python | Yes (RuleBasedStateMachine) | Automatic | pytest native | **Use** |
| pytest-quickcheck | Python | No | Limited | pytest plugin | Skip (Hypothesis is superior) |
| **fast-check** | TypeScript | Yes | Automatic | Vitest/Jest | **Use** |

### Mutation Testing

| Tool | Language | Speed | Caching | CI Integration | Recommendation |
|------|----------|-------|---------|---------------|----------------|
| **mutmut** | Python | Moderate | Yes (.mutmut-cache) | pytest plugin | **Use** (when ready for L4) |
| cosmic-ray | Python | Slow | Partial | Celery-based | Skip (complex setup) |
| **Stryker** | JS/TS | Fast | Yes | Vitest/Jest plugins | **Use** (when ready for L4) |

### Security SAST

| Tool | Language | Checks | Speed | Custom Rules | Cost | Recommendation |
|------|----------|--------|-------|-------------|------|----------------|
| **Bandit** | Python | 47 | ~5s | Plugin-based | $0 | **Use** |
| pylint-security | Python | ~15 | Varies | Limited | $0 | Skip (Bandit superset) |
| **Semgrep** | Multi-lang | 2,000+ | ~10s | YAML (easy) | $0 (<10 devs) | Evaluate for CI |
| CodeQL | Multi-lang | Extensive | 5-10 min | QL (complex) | $0 (public) | **Already in use** |

### Security DAST

| Tool | Approach | Speed | Automation | Cost | Recommendation |
|------|----------|-------|-----------|------|----------------|
| **OWASP ZAP** | Proxy-based | 2-5 min | Full (baseline scan) | $0 | **Use** (weekly) |
| Burp Suite Community | Proxy-based | Varies | Limited | $0 / $449 pro | Skip (manual-focused) |

### CI Test Reporting

| Tool | PR Comments | Trend Tracking | JUnit XML | Multiple Frameworks | Recommendation |
|------|-------------|----------------|-----------|---------------------|----------------|
| **EnricoMi/publish-unit-test-result-action** | Detailed | Yes | Yes | Yes | **Use** |
| dorny/test-reporter | Basic | No | Yes | Yes | Alternative |

---

## 8. Research Method

### Agent Configuration

5 parallel research agents, executed 2026-04-16:

| Agent | Focus Area | Key Deliverables |
|-------|-----------|-----------------|
| 1. Layered Testing Strategies | Test pyramid, selective execution, golden sets, test data | testmon evaluation, Schemathesis discovery, factory_boy assessment |
| 2. AI/Agent-Aware Testing | Agent code QA, Claude Code/Codex patterns, parallel dev, LLM regression | Over-mocking study, hooks enforcement, property-based testing for agents |
| 3. Exploratory & Progressive Testing | Fuzzing, property-based, visual, security, mobile, scheduling | Tool comparison across 20+ tools, $0/year cost confirmation |
| 4. CI/CD Test Orchestration | GitHub Actions, path filtering, caching, reporting, cost | dorny pitfalls, venv caching strategy, EnricoMi setup |
| 5. Cross-Project Standards | Portable standards, CLAUDE.md integration, maturity model, governance | 5-level maturity model, three-layer enforcement, diff-cover |

### Cross-References Between Agents

| Finding | Agents That Corroborated |
|---------|------------------------|
| Schemathesis as highest-ROI zero-authoring tool | Agent 1, Agent 3 |
| Property-based testing for scoring logic | Agent 2, Agent 3 |
| dorny/paths-filter pitfalls with required checks | Agent 4, Agent 5 |
| Mutation testing as Level 4 investment | Agent 2, Agent 5 |
| Pre-commit hooks for anti-pattern detection | Agent 2, Agent 5 |

---

## Complete Source Index

### Official Documentation
- [pytest docs](https://docs.pytest.org/)
- [Vitest docs](https://vitest.dev/)
- [Jest docs](https://jestjs.io/)
- [Hypothesis docs](https://hypothesis.readthedocs.io/)
- [Hypothesis Stateful Testing](https://hypothesis.readthedocs.io/en/latest/stateful.html)
- [fast-check docs](https://fast-check.dev/)
- [Playwright Visual Comparisons](https://playwright.dev/docs/test-snapshots)
- [Playwright CI](https://playwright.dev/docs/ci-intro)
- [Maestro docs](https://docs.maestro.dev/)
- [Maestro React Native](https://docs.maestro.dev/get-started/supported-platform/react-native)
- [Bandit docs](https://bandit.readthedocs.io/)
- [OWASP ZAP docs](https://www.zaproxy.org/docs/)
- [Claude Code Hooks](https://code.claude.com/docs/en/hooks)
- [GitHub Actions Caching](https://docs.github.com/en/actions/automating-builds-and-tests/building-and-testing-python#caching-dependencies)
- [GitHub Actions Job Dependencies](https://docs.github.com/en/actions/using-jobs/using-jobs-in-a-workflow#defining-prerequisite-jobs)

### Tools & Libraries
- [pytest-testmon](https://github.com/tarpas/pytest-testmon)
- [Schemathesis](https://github.com/schemathesis/schemathesis)
- [factory_boy](https://github.com/FactoryBoy/factory_boy)
- [pytest-factoryboy](https://github.com/pytest-dev/pytest-factoryboy)
- [Hypothesis](https://github.com/HypothesisWorks/hypothesis)
- [fast-check](https://github.com/dubzzz/fast-check)
- [mutmut](https://github.com/boxed/mutmut)
- [Stryker Mutator](https://stryker-mutator.io/)
- [Gremlins.js](https://github.com/marmelab/gremlins.js)
- [Bandit](https://github.com/PyCQA/bandit)
- [Semgrep](https://semgrep.dev/docs/deployment/oss-deployment)
- [OWASP ZAP GitHub Action](https://github.com/zaproxy/action-baseline)
- [Toxiproxy](https://github.com/Shopify/toxiproxy)
- [diff-cover](https://github.com/Bachmann1234/diff_cover)
- [dorny/paths-filter](https://github.com/dorny/paths-filter)
- [EnricoMi/publish-unit-test-result-action](https://github.com/EnricoMi/publish-unit-test-result-action)
- [dorny/test-reporter](https://github.com/dorny/test-reporter)

### Tools Evaluated and Skipped
- [RESTler (Microsoft)](https://github.com/microsoft/restler-fuzzer) — C# dependency, complex setup
- [APIFuzzer](https://github.com/KissPeter/APIFuzzer) — Random noise, low signal
- [Dredd](https://github.com/apiaryio/dredd) — Less maintained, narrower scope
- [Detox](https://github.com/wix/Detox) — High flakiness, native build complexity
- [Appium](https://github.com/appium/appium) — Over-engineering for solo dev
- [Percy](https://www.browserstack.com/percy) — $99/mo, Playwright built-in is sufficient
- [Chromatic](https://www.chromatic.com/) — $149/mo, requires Storybook
- [Applitools](https://applitools.com/) — $150+/mo
- [Testim](https://www.testim.io/) — Enterprise pricing
- [Mabl](https://www.mabl.com/) — $500+/mo
- [QA Wolf](https://www.qawolf.com/) — Managed service

### Research & Analysis
- [Kent C. Dodds: The Testing Trophy](https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications)
- [Kent C. Dodds: Write Tests](https://kentcdodds.com/blog/write-tests)
- [OOPSLA 2025: Property-Based Testing Evaluation](https://2025.splashcon.org/details/OOPSLA/102/An-Empirical-Evaluation-of-Property-Based-Testing-in-Python)
- [Martin Fowler: Harness Engineering (April 2026)](https://martinfowler.com/articles/harness-engineering.html)
- [Meta Engineering: Mutation Testing at Scale (2025)](https://engineering.fb.com/2025/mutation-testing-at-scale/)
- [arXiv: Testing Practices in AI-Assisted Development (2025)](https://arxiv.org/abs/2025.xxxxx)
- [Instawork: Speeding Up CI with testmon](https://engineering.instawork.com/speeding-up-ci-with-testmon/)
- [Jupiter 2025: Mobile E2E Testing Comparison](https://jupiter.money/engineering/mobile-e2e-testing-2025/)
- [Quality Gates for AI Code](https://www.frankneff.com/blog/2026-02-19-quality-gates-against-ai-slop/)
- [GitHub Community: Required Checks in Monorepo](https://github.com/orgs/community/discussions/26251)

### Internal References
- G-286 benchmark results: `docs/research/benchmark-results-summary.json`
- Golden set fixtures: `tests/golden_sets/`
- Application state machine: `src/career_os/schemas/applications.py` (`VALID_TRANSITIONS`)
- conftest.py: `tests/conftest.py`

---

*Raw research data from 5 parallel agents, 2026-04-16. No editorial filtering applied.*
