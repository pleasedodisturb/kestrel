# Testing Research: Catching Bugs Before CI/CD Ships Them to Reality

**Researched:** 2026-04-16
**Status:** Research complete — pending decision & implementation
**Scope:** Kestrel-first, but designed to be reusable across all repos

---

## Philosophy: Human-First, Data-Driven

This document follows a deliberate research philosophy: we do deep, thorough research to understand the full landscape, but research findings **inform** decisions — they don't make them.

Every recommendation here weighs:

- **Developer wellbeing** — mental load, emotional cost, maintenance burden for a solo developer
- **Sustainability** — will this still be manageable in 6 months? In 2 years?
- **Real-world consequences** — for the developer, for users, for the project's future
- **Balance** — across competing concerns, not optimizing for a single metric

"Recommended" doesn't mean "optimal." It means: sane, balanced, and reflective of what we actually care about. We research deeply so we *can* make informed trade-offs. Then we make the human decision.

This is the testing counterpart to CI/CD research (G-306). CI/CD moves code into production — testing is the gate that decides whether it's *ready* for production. They're two halves of the same pipeline: testing catches bugs, CI/CD ensures what passes actually ships.

---

## Context: What We Already Have

Kestrel's test suite is substantial but unevenly distributed:

| Area | Coverage | Status |
|------|----------|--------|
| **Backend tests** | 97 files, ~50K lines (pytest, asyncio) | Strong |
| **Frontend tests** | 23 files, ~5.7K lines (Vitest) | Moderate |
| **Mobile tests** | 0 files | Gap |
| **Test markers** | Only `asyncio` and `parametrize` — zero tier markers | Gap |
| **CI execution** | Single flat run (everything on every PR) | Inefficient |
| **Golden set fixtures** | Exist but only structurally validated (schema, not behavior) | Partial |
| **Test infrastructure** | conftest.py: in-memory SQLite, TestClient, sample fixtures | Solid |
| **Security testing** | pip-audit, npm audit, CodeQL, SonarCloud, PII detection, gitleaks | Strong |

**Key gaps identified:**
- No way to run "fast tests only" or "slow tests only" — every PR runs everything
- Golden set fixtures validate structure but don't assert scoring behavior
- Zero mobile test coverage (React Native/Expo stack)
- No contract testing between frontend API calls and backend endpoints
- No mutation testing — tests exist but we don't know if they actually catch bugs
- No property-based testing for scoring logic (the most complex domain)

---

## Research Synthesis: Six Streams

### Stream 1: Selective Test Execution

**The data says:** pytest-testmon tracks which tests are affected by code changes and skips the rest — typical speedup is 2x on incremental runs. `dorny/paths-filter` in CI skips entire component test suites (40-60% savings when a PR only touches backend or frontend). Pytest markers (`@pytest.mark.slow`, `@pytest.mark.integration`) allow manual tier selection.

**The trade-off:** testmon and `--cov` are incompatible — testmon selects a subset of tests, but coverage reporting needs the full suite to be meaningful. You can have fast selective runs *or* complete coverage numbers, not both simultaneously.

**Our recommendation:** testmon on PR runs (speed), full coverage on nightly runs (accuracy). Path filtering via `dorny/paths-filter` for component-level skipping — if a PR only touches `src/career_os/`, skip frontend tests entirely. This gives us fast PR feedback without sacrificing coverage visibility.

**Other findings:**
- Nx/Turborepo "affected commands" — designed for massive monorepos, overkill for 3 components
- pytest-picked — runs tests for uncommitted files only; useful locally, not in CI
- Vitest `changedSince` — only works in watch mode, not applicable to CI runs
- Custom markers (`@pytest.mark.tier1`, `@pytest.mark.tier2`) — manual but explicit; good for separating unit vs integration tests

### Stream 2: Test Quality Assurance

**The data says:** A study of 1.2 million commits found that AI agents over-mock in 36% of generated tests — tests pass but don't actually exercise the code path they claim to test. Mutation testing (injecting small bugs and checking whether tests catch them) is the gold standard for measuring test effectiveness, not just coverage percentage.

**The trade-off:** Mutation testing is slow — minutes per module, potentially hours for a full suite. Property-based testing (Hypothesis) requires thoughtful property definitions; poorly-chosen properties produce tests that are both slow and uninformative.

**Our recommendation:**
1. **Anti-mocking rules in CLAUDE.md** — explicit guidance for AI agents: "prefer real dependencies over mocks; mock only external services and time-dependent functions"
2. **Pre-commit hook for `assert True` detection** — catches the most egregious placeholder tests before they land
3. **Hypothesis for scoring and state machine logic** — the scoring module is the highest-value target for property-based testing (complex numeric logic with many edge cases)
4. **mutmut nightly on critical modules** — run mutation testing on `scoring/`, `services/`, and `ai/` modules in a scheduled workflow

**Key decisions:**
- diff-cover threshold starts at 70% and rises as the codebase matures — not 100% (leads to garbage tests)
- Mutation score target >=60% on the scoring module — this is aspirational but achievable for numeric logic
- Pre-commit hooks catch anti-patterns locally before CI even runs

### Stream 3: API & Contract Testing

**The data says:** Schemathesis reads your OpenAPI schema and generates test cases automatically — zero test authoring required. It fuzzes endpoints with valid-but-unexpected inputs, edge-case types, and boundary values. Used in production by Spotify and JetBrains. Finds real bugs that hand-written tests miss because humans don't think to send a 10,000-character string as a job title.

**The trade-off:** Schemathesis can be noisy — false positives on complex auth flows, rate-limited endpoints, and stateful multi-step operations. Stateful testing mode (testing sequences of API calls) requires OpenAPI `links` annotations that we don't currently have.

**Our recommendation:** Schemathesis in a nightly workflow. Not on every PR — too slow (minutes per endpoint), too noisy during active development. Nightly gives us continuous coverage without blocking developer flow.

**What we rejected:**
- RESTler (Microsoft) — C# toolchain, heavy setup, designed for enterprise
- Pact (consumer-driven contracts) — designed for microservices with separate teams; overkill for a monorepo where both sides of the contract live in the same repo
- Dredd — less actively maintained, Schemathesis is the clear successor in this space

### Stream 4: Exploratory & Visual Testing

**The data says:** Gremlins.js simulates random user interactions (clicks, text input, scrolling) and catches unhandled exceptions, console errors, and UI crashes. Playwright's built-in `toHaveScreenshot()` provides free visual regression testing — no SaaS required, pixel-level comparison with configurable thresholds.

**The trade-off:** Monkey testing (Gremlins.js) is inherently flaky — random interactions sometimes trigger legitimate but rare UI states that aren't bugs. Visual regression needs locked environments (exact browser version, OS, viewport) to avoid false diffs from rendering differences.

**Our recommendation:** Both in weekly workflows. Gremlins.js for the web frontend (catches unhandled exceptions and dead-end UI states). Playwright screenshots for key pages (dashboard, pipeline, scoring detail). Defer mobile visual testing until mobile v1 stabilizes — the UI is still in flux.

**What we rejected:**
- Percy ($99/mo) — Playwright's built-in screenshot comparison is free and sufficient for solo dev
- Chromatic ($149/mo) — designed for component library teams with dedicated design review workflows
- AI-powered testing tools (Testim, Mabl, etc.) — $150+/mo, built for QA teams, overkill at our scale
- Applitools — visual AI testing at enterprise pricing; solving a problem we don't have yet

### Stream 5: Security Testing Enhancement

**The data says:** Bandit (Python SAST) scans for common security issues — hardcoded passwords, SQL injection patterns, unsafe deserialization — in about 5 seconds for our codebase. ZAP baseline scan (DAST) tests a running app for OWASP Top 10 vulnerabilities in 2-5 minutes. Both are free, well-maintained, and widely adopted.

**The trade-off:** False positives need tuning — Bandit flags `assert` statements (common in tests) and `subprocess` calls (sometimes legitimate). ZAP against an in-memory SQLite test instance is less realistic than against the production Postgres/SQLite WAL setup, but still catches header misconfigurations, CORS issues, and injection vectors.

**Our recommendation:** Bandit in CI on every PR — 5 seconds, no reason not to. ZAP baseline as a weekly scheduled workflow. `eslint-plugin-security` for the frontend (catches `innerHTML`, `eval`, unsafe regex).

**What we already have right:**
- pip-audit + npm audit (dependency vulnerability scanning)
- CodeQL (deep semantic analysis, scheduled)
- SonarCloud (code quality + security hotspots)
- PII detection (custom scanner for personal data leaks)
- gitleaks (secret detection in git history)

The gap is SAST for our own code (Bandit) and DAST against a running instance (ZAP). These complement, not replace, the existing tools.

### Stream 6: Standards & Governance

**The data says:** Moving from Maturity Level 2 (tests exist, CI runs them) to Level 3 (formalized standards, enforcement, measurable quality targets) requires three enforcement layers: documentation (what the rules are), automation (hooks and CI gates that enforce them), and culture (CLAUDE.md rules that AI agents follow).

**The trade-off:** Too much enforcement slows agents down — if every commit requires 15 gates to pass, development velocity collapses. Too little enforcement lets quality drift, especially when AI agents write 80%+ of the code.

**Our recommendation:**
1. **TESTING.md** — single source of truth for test standards, naming conventions, fixture patterns, when to mock, when not to
2. **Updated CLAUDE.md** — anti-mocking rules, test quality expectations, marker requirements for new tests
3. **Pre-commit hooks** — `assert True` detection, test file naming validation, import order
4. **diff-cover in CI** — new code must meet coverage threshold (starts at 70%)

**What we rejected:**
- Extracting shared pytest plugins as a pip package — no second consumer exists yet; premature extraction adds maintenance for zero benefit
- Extracting shared npm test config as a package — same reasoning
- Custom pytest plugins for test registration/validation — the built-in marker system is sufficient

Extract cross-project tooling when a second project actually needs it, not before.

---

## Implementation Roadmap

### Phase 1: Markers + Path Filtering + Caching (2-3 hours)

Immediate ROI with zero behavior change — tests still run, just faster and smarter:

| # | Change | Effort | Impact |
|---|--------|--------|--------|
| 1 | Add pytest markers (`unit`, `integration`, `slow`, `golden`) | 1 hour | Enable selective execution |
| 2 | Add `dorny/paths-filter` to ci.yml | 30 min | Skip irrelevant component tests |
| 3 | Cache `.venv` and `node_modules` in CI | 30 min | 30-60s savings per run |
| 4 | Add marker-based CI matrix (fast on PR, full on nightly) | 30 min | Fast PR feedback loop |

### Phase 2: Standards + Anti-Pattern Enforcement (3-4 hours)

Quality floor for agent-generated code:

| # | Change | Effort | Impact |
|---|--------|--------|--------|
| 5 | Write TESTING.md (standards, conventions, examples) | 1 hour | Single source of truth |
| 6 | Update CLAUDE.md with anti-mocking rules | 15 min | AI agent quality guidance |
| 7 | Add pre-commit hook for `assert True` / empty tests | 30 min | Catch placeholder tests |
| 8 | Add diff-cover to CI (70% threshold on new code) | 30 min | Coverage floor for PRs |
| 9 | Add Bandit SAST to CI (every PR, ~5 seconds) | 30 min | Security scanning for own code |
| 10 | Add `eslint-plugin-security` to frontend | 15 min | Frontend security lint |

### Phase 3: Golden Set Regression + Hypothesis + Schemathesis (4-6 hours)

Catch real bugs in the most complex domain logic:

| # | Change | Effort | Impact |
|---|--------|--------|--------|
| 11 | Expand golden set tests from structural to behavioral | 2 hours | Scoring regression detection |
| 12 | Add Hypothesis property-based tests for scoring | 2 hours | Edge case discovery |
| 13 | Add Schemathesis nightly workflow | 1 hour | Automated API fuzzing |
| 14 | Add pytest-testmon for PR runs | 30 min | 2x speedup on incremental PRs |

### Phase 4: Nightly & Weekly Workflows (3-4 hours)

Deep automated testing that runs on a schedule, not on every PR:

| # | Change | Effort | Impact |
|---|--------|--------|--------|
| 15 | Add mutmut nightly on scoring/services/ai modules | 1 hour | Mutation testing for test quality |
| 16 | Add Gremlins.js weekly for web frontend | 30 min | Random interaction bug discovery |
| 17 | Add Playwright visual regression weekly | 1 hour | Screenshot-based UI regression |
| 18 | Add ZAP baseline weekly | 30 min | DAST for OWASP Top 10 |
| 19 | Add full coverage nightly (no testmon) | 30 min | Accurate coverage numbers |

### Phase 5: Documentation + Cross-Project Playbook (2-3 hours)

Deferred until a second project needs it:

| # | Change | Effort | Impact |
|---|--------|--------|--------|
| 20 | Publish testing research as blog post / open-source guide | 1 hour | Community contribution |
| 21 | Extract reusable CI workflow templates | 1 hour | Cross-project reuse |
| 22 | Create pytest plugin skeleton (if second project emerges) | 1 hour | Shared test infrastructure |

---

## Decision Matrix

Key decisions across all streams, with the reasoning:

| Decision | Choice | Runner-Up | Why This Choice |
|----------|--------|-----------|-----------------|
| Selective execution | testmon + path filtering | Nx affected | Simpler, sufficient for 3 components |
| Coverage enforcement | diff-cover (70% new code) | Codecov / 100% gate | Realistic threshold, no SaaS dependency |
| Mutation testing | mutmut (nightly) | cosmic-ray | Better maintained, simpler config, pytest-native |
| Property-based testing | Hypothesis | fast-check (TS) | Python scoring module is the target; Hypothesis is the standard |
| API fuzzing | Schemathesis (nightly) | RESTler | Python-native, reads existing OpenAPI, zero authoring |
| Contract testing | Skip (monorepo) | Pact | Both sides of the contract are in the same repo |
| Visual regression | Playwright built-in | Percy / Chromatic | Free, no SaaS dependency, sufficient for solo dev |
| Monkey testing | Gremlins.js (weekly) | Custom scripts | Battle-tested, configurable, catches real UI bugs |
| SAST (own code) | Bandit (every PR) | Semgrep rules | 5-second scans, Python-specific, zero config |
| DAST | ZAP baseline (weekly) | Nuclei | OWASP standard, better documentation, Docker image |
| Test quality gate | Pre-commit + diff-cover | Custom CI checks | Catches issues before CI, faster feedback |
| Standards enforcement | TESTING.md + CLAUDE.md | Custom linter | Documentation + AI guidance vs brittle tooling |
| Mobile testing | Defer (0 test files) | Start now | UI is still in flux; tests would churn constantly |
| E2E web | Playwright (deferred) | Cypress | Faster, lighter, already used for visual regression |
| E2E mobile | Maestro (deferred) | Detox | YAML-based, Expo-native, simpler setup |

---

## Cost Summary

### Testing Tools (Annual)

| Tool | Cost | Notes |
|------|------|-------|
| pytest-testmon | $0 | OSS, pip install |
| Hypothesis | $0 | OSS, pip install |
| mutmut | $0 | OSS, pip install |
| Schemathesis | $0 | OSS, pip install |
| Bandit | $0 | OSS, pip install |
| ZAP | $0 | OSS, Docker image |
| Gremlins.js | $0 | OSS, npm install |
| Playwright screenshots | $0 | Built into Playwright |
| diff-cover | $0 | OSS, pip install |
| eslint-plugin-security | $0 | OSS, npm install |
| **Total tools** | **$0/year** | All open-source |

### CI Minutes Impact (Monthly)

| Workflow | Current | After Optimization | Change |
|----------|---------|-------------------|--------|
| PR runs (with path filtering + testmon) | ~555 min | ~400 min | -28% |
| Nightly (full coverage + mutmut + Schemathesis) | 0 min | ~60 min | +60 min |
| Weekly (ZAP + Gremlins.js + visual regression) | 0 min | ~30 min | +30 min |
| **Monthly total** | **~555 min** | **~490 min** | **-12% net** |

All within the 3,000 min/month free budget for public repos. Net reduction because PR savings outweigh new scheduled workflows.

### Effort Estimate

| Phase | Hours | Timeline |
|-------|-------|----------|
| Phase 1: Markers + filtering | 2-3 | Week 1 |
| Phase 2: Standards + enforcement | 3-4 | Week 1-2 |
| Phase 3: Golden set + Hypothesis + Schemathesis | 4-6 | Week 2-3 |
| Phase 4: Nightly/weekly workflows | 3-4 | Week 3-4 |
| Phase 5: Documentation + extraction | 2-3 | When needed |
| **Total** | **~40-60 hours** | **~4 weeks** |

---

## What We Explicitly Chose NOT to Do

These came up in research but were rejected for good reasons:

| Rejected Approach | Why |
|-------------------|-----|
| Percy / Chromatic (visual testing SaaS) | $99-149/mo. Playwright's built-in `toHaveScreenshot()` is free and sufficient |
| Detox (React Native E2E) | Requires native builds, notoriously flaky. Maestro is simpler, YAML-based, Expo-native |
| Shared pytest plugins (pip package) | Premature extraction — no second consumer exists. Extract when needed |
| Shared npm test config (npm package) | Same reasoning as pytest plugins |
| AI-powered testing tools (Testim, Mabl, etc.) | $150+/mo, built for QA teams, overkill for solo dev |
| Chaos testing (Toxiproxy) | LOW priority — MockProvider already covers most failure modes for AI calls |
| Time-based test cadences | Feature-driven execution is better for solo dev; don't create artificial pressure |
| 100% coverage gates | Leads to garbage tests written to hit a number. 70% on new code is the sweet spot |
| Pact (contract testing) | Designed for microservices with separate teams. Monorepo doesn't need it |
| RESTler (API fuzzing) | C# toolchain, heavy setup. Schemathesis is Python-native and reads our existing OpenAPI |
| Dredd (API testing) | Less actively maintained. Schemathesis is the clear successor |
| Custom pytest plugins for validation | Built-in marker system + pre-commit hooks are sufficient |
| Device farm services (BrowserStack, etc.) | Simulator testing catches 95% of issues. Not worth the cost for solo dev |
| Codecov / Coveralls (SaaS coverage) | diff-cover is free, local, no SaaS dependency. SonarCloud already shows coverage trends |

---

## Detailed Research Files

The raw research from each stream is preserved in `.planning/research/`:

| File | Stream | Content |
|------|--------|---------|
| `testing_selective_execution.md` | Selective test execution | testmon, path filtering, markers, affected commands |
| `testing_quality_assurance.md` | Test quality assurance | Mutation testing, anti-mocking, Hypothesis, diff-cover |
| `testing_api_contracts.md` | API & contract testing | Schemathesis, RESTler, Pact, OpenAPI fuzzing |
| `testing_exploratory_visual.md` | Exploratory & visual testing | Gremlins.js, Playwright screenshots, monkey testing |
| `testing_security.md` | Security testing enhancement | Bandit, ZAP, eslint-plugin-security, gap analysis |
| `testing_standards.md` | Standards & governance | TESTING.md, maturity levels, enforcement layers |

---

## Next Steps

1. **Review this document** — flag anything that feels wrong or doesn't match your priorities
2. **Linear epic created** — individual tickets for each actionable item, ordered by phase
3. **Start with Phase 1 markers + filtering** — 2-3 hours of work for immediate, tangible improvement
4. **Phase 2-4 as separate sprints** — each phase is a natural stopping point

This research is designed to be reusable. When we set up testing for other repos, we start from these decisions and adapt only where the project differs.

---

*Research conducted 2026-04-16 across 6 parallel research streams. Raw data in `.planning/research/testing_*.md`. Philosophy: human-first, data-driven.*
