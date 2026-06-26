# CI/CD Testing Strategy Research

**Project:** Kestrel
**Researched:** 2026-04-16
**Overall confidence:** HIGH (based on existing CI analysis + current ecosystem research)

## Executive Summary

Kestrel already has a solid CI foundation: backend pytest with coverage, frontend Vitest with coverage, SonarCloud analysis, pip-audit, npm audit + signature verification, PII scanning, Alembic migration checks, and an API smoke test. The existing pipeline is well-structured but has clear optimization opportunities: tests run serially, there are no E2E tests, no flaky test management, coverage gates are informational only (not blocking), and mobile has zero CI presence.

This research identifies specific, incremental improvements ordered by impact-per-effort for a solo developer doing AI-assisted development. The key principle: fast feedback on every PR, thorough checks nightly or pre-release.

---

## 1. Test Pyramid in CI

### Current State
- **102 backend test files** (~50K lines of test code) -- all run on every PR
- **20+ frontend test files** -- all run on every PR
- **0 mobile test files** -- no CI at all
- **0 E2E tests** -- no browser or API integration tests beyond the smoke check
- **1 API smoke test** -- health endpoint only

### Recommended Distribution

| Layer | What | When | Time Budget |
|-------|------|------|-------------|
| Unit tests | pytest, Vitest, Jest | Every PR | < 3 min each |
| Integration tests | API route tests with DB | Every PR | < 2 min |
| API smoke test | Health + critical endpoints | Every PR | < 30 sec |
| E2E (web) | Playwright critical paths | Nightly + pre-release | < 5 min |
| E2E (mobile) | Maestro smoke flows | Pre-release only | < 10 min |
| Security scans | pip-audit, npm audit, SonarCloud | Every PR (already done) | < 2 min |
| Performance | Bundle size check, Lighthouse | Every PR (lightweight) | < 1 min |

### PR Pipeline Target: Under 8 Minutes Total
Currently the backend job does lint + migration check + tests + smoke + security + PII sequentially. Frontend does lint + tests + audit. Both jobs run in parallel (good). Target: keep total wall-clock under 8 minutes.

**Confidence:** HIGH -- based on direct analysis of existing CI config.

---

## 2. Test Speed Optimization

### Backend: pytest-xdist

**Recommendation:** Add `pytest-xdist` with `-n auto` for parallel test execution.

**Why:** With 102 test files and ~50K lines, serial execution will only get slower. pytest-xdist provides 3-5x speedup on GitHub Actions runners (2-core) and up to 8x on larger runners.

**Configuration:**
```ini
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
timeout = 30
addopts = "-n auto --dist loadfile"
```

**Key detail:** Use `--dist loadfile` (not `loadscope` or `loadgroup`) because Kestrel's tests use in-memory SQLite per fixture -- each file's tests share a fixture session. `loadfile` keeps entire files on one worker, avoiding cross-worker DB conflicts.

**Prerequisite:** Ensure every test file creates its own `db_session` fixture (already done via conftest.py's in-memory SQLite pattern). Verify no tests write to shared filesystem paths.

**CI change:**
```yaml
- name: Run tests
  run: pytest tests/ -v --tb=short -n auto --dist loadfile --cov=src/career_os --cov-report=xml
```

**Confidence:** HIGH -- pytest-xdist is mature (10+ years), and Kestrel's test isolation pattern (in-memory SQLite per fixture) is ideal for parallelization.

### Frontend: Vitest (Already Fast)

Vitest is already fast by default (native ESM, no transform overhead). With 20 test files, parallelization isn't a bottleneck yet. No changes needed.

**Future:** When frontend tests exceed 50 files, consider Vitest's `--shard` flag for splitting across CI matrix jobs:
```yaml
strategy:
  matrix:
    shard: [1/2, 2/2]
steps:
  - run: npx vitest run --shard ${{ matrix.shard }}
```

### Mobile: Jest (When Tests Exist)

Jest parallelizes by default (one worker per file). For React Native/Expo, the main bottleneck is transform time (Babel/Metro). Use `--maxWorkers=2` on CI to match runner cores.

### Test Impact Analysis

**Skip for now.** Test impact analysis (Nx, Turborepo, Datadog TIA) is designed for monorepos with hundreds of packages. Kestrel has 3 components that don't share code. The simpler approach:

- Use GitHub Actions path filters to skip jobs when irrelevant files change:
```yaml
backend:
  if: |
    github.event_name == 'push' ||
    contains(github.event.pull_request.changed_files_url, 'src/') ||
    contains(github.event.pull_request.changed_files_url, 'tests/')
```

- Better: use `dorny/paths-filter` action for reliable path-based job skipping:
```yaml
- uses: dorny/paths-filter@v3
  id: changes
  with:
    filters: |
      backend:
        - 'src/**'
        - 'tests/**'
        - 'pyproject.toml'
      frontend:
        - 'frontend/**'
      mobile:
        - 'mobile/**'
```

**Confidence:** HIGH -- path filtering is battle-tested and trivial to implement.

---

## 3. E2E Testing in CI

### Web: Playwright

**Recommendation:** Add Playwright for critical path E2E tests, but run nightly, NOT on every PR.

**Setup:**
```yaml
e2e-web:
  name: E2E (Playwright)
  runs-on: ubuntu-latest
  if: github.event_name == 'schedule' || contains(github.event.pull_request.labels.*.name, 'e2e')
  steps:
    - uses: actions/checkout@v6
    - uses: actions/setup-node@v6
      with:
        node-version: "22"
    - run: cd frontend && npm ci --legacy-peer-deps
    - run: npx playwright install --with-deps chromium
    - uses: actions/setup-python@v6
      with:
        python-version: "3.11"
    - run: pip install -e ".[dev]"
    - run: |
        uvicorn career_os.main:app --port 8100 &
        cd frontend && npm run dev &
        npx playwright test
```

**What to test (5-10 tests max):**
- Login/onboarding flow
- Pipeline kanban view loads with data
- Application detail page renders scores
- Discovery page loads and filters work
- Settings page saves preferences

**Cost estimate:** ~2-3 min per run on GitHub Actions Linux. $0 if run nightly within free tier (2,000 min/month for private repos). Chromium only (skip Firefox/Safari for solo dev).

**Maintenance burden:** LOW if you stick to 5-10 happy-path tests. HIGH if you try to cover edge cases (don't).

### Mobile: Maestro

**Recommendation:** Maestro for mobile E2E, but defer until mobile v1 is feature-complete.

**Why Maestro over Detox:**
- YAML-based test definitions (no code to maintain)
- First-class Expo support (works with Expo Go and dev builds)
- Maestro Cloud integrates directly with EAS Workflows
- Detox requires native builds and complex setup -- overkill for solo dev

**When to add:** After mobile has 3+ completed screens with real API integration. Before that, Jest component tests are sufficient.

**Cost:** Maestro CLI is free. Maestro Cloud starts at ~$212/month -- skip this. Run Maestro locally in EAS custom builds or on a macOS GitHub Actions runner ($0.08/min) for iOS simulator tests.

**Confidence:** HIGH for Playwright recommendation. MEDIUM for Maestro (depends on mobile app maturity).

### API Integration Tests

**Already partially covered** by the smoke test. Expand to a dedicated integration test job:

```python
# tests/integration/test_critical_paths.py
"""API integration tests that run against a real (in-memory) server."""

async def test_full_application_lifecycle(client, db_session, profile):
    """Create app -> score -> update status -> verify transitions."""
    # POST /api/applications
    # POST /api/applications/{id}/score
    # PATCH /api/applications/{id} (status change)
    # GET /api/applications/{id} (verify final state)
```

These are cheaper than E2E and catch most API regressions. Run on every PR.

---

## 4. Flaky Test Management

### Current Risk Assessment
With 102 backend test files running against in-memory SQLite, flakiness risk is LOW. Common flaky test sources (network calls, timing, shared state) are mostly avoided by Kestrel's mock-based AI provider pattern.

### Detection Strategy

**Recommendation:** Use `pytest-rerunfailures` for automatic retry + detection.

```ini
# pyproject.toml
[tool.pytest.ini_options]
addopts = "-n auto --dist loadfile --reruns 2 --reruns-delay 1"
```

Any test that passes on rerun is flagged as flaky. Track these via CI output parsing.

**For frontend:** Vitest has built-in retry:
```typescript
// vitest.config.ts
export default defineConfig({
  test: {
    retry: 2, // retry failed tests up to 2 times
  },
});
```

### Quarantine Strategy (When Needed)

For a solo developer, formal quarantine is overkill. Instead:
1. If a test fails intermittently 3+ times, mark it with `@pytest.mark.flaky` (custom marker)
2. Add a `# FLAKY: <reason> <date>` comment
3. Create a Linear ticket to fix it within 2 weeks
4. If not fixed in 2 weeks, delete the test and create a proper replacement

**Do NOT use:** Trunk.io, Buildkite test analytics, or any SaaS flaky test dashboard. These are team tools. For solo dev, grep CI logs for rerun counts monthly.

**Confidence:** HIGH -- simple strategy matching project scale.

---

## 5. Coverage as a Gate

### Current State
- Backend: `--cov=src/career_os --cov-report=xml` (collected, uploaded as artifact)
- Frontend: `npx vitest run --coverage` (collected, uploaded)
- SonarCloud: Consumes both reports, runs quality gate (informational, not blocking)

### Recommended Thresholds

**Make SonarCloud quality gate blocking** (currently `continue-on-error: true`):
```yaml
- name: Wait for SonarCloud quality gate
  if: github.event_name == 'pull_request'
  uses: SonarSource/sonarqube-quality-gate-action@v1.2.0
  timeout-minutes: 5
  # Remove continue-on-error to make it blocking
  env:
    SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
```

**SonarCloud quality gate settings (recommended):**
| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| New code coverage | >= 70% | Realistic for AI-assisted dev; forces tests for new code |
| Overall coverage | >= 60% | Don't retroactively require coverage for old code |
| Duplicated lines on new code | <= 3% | Prevent copy-paste |
| Maintainability rating | A | Keep technical debt low |
| Reliability rating | A | No new bugs |
| Security rating | A | No new vulnerabilities |

**Why 70% on new code, not 80%:** AI-generated code often includes boilerplate (models, schemas, config) that doesn't benefit from 80% coverage. 70% ensures business logic is tested without gaming the metric.

**Differential coverage is the real win:** SonarCloud already does this by default -- it evaluates new code separately from overall. Just make the gate blocking.

### Coverage Trend Tracking
SonarCloud provides this for free. No additional tooling needed. Check the dashboard monthly.

**Confidence:** HIGH -- leverages existing SonarCloud setup, just needs config changes.

---

## 6. Security Testing in CI

### Current State (Already Good)
- `pip-audit` for Python dependency vulnerabilities (with ignore list)
- `npm audit --audit-level=moderate` for frontend deps
- `npm audit signatures` for supply chain verification
- SonarCloud SAST (informational)
- PII leak check (custom grep-based)
- CodeQL (GitHub Advanced Security -- check if enabled on repo)

### Recommended Additions

**1. Semgrep (replace or complement SonarCloud for SAST):**
- Scans in ~10 seconds vs SonarCloud's minutes
- Free for solo developers (<10 contributors)
- Better custom rule support (YAML-based, writable in 30 min)
- Can gate PRs directly (SonarCloud gates are async/delayed)

```yaml
- name: Semgrep SAST
  uses: semgrep/semgrep-action@v1
  with:
    config: >-
      p/python
      p/typescript
      p/react
      p/security-audit
      p/owasp-top-ten
```

**Verdict:** Add Semgrep as a fast, blocking SAST gate. Keep SonarCloud for code quality metrics (duplication, complexity, maintainability). They serve different purposes.

**2. Trivy for Docker container scanning:**
Since Kestrel has Dockerfiles, add Trivy to scan the production image:

```yaml
- name: Build Docker image
  run: docker build -t kestrel:ci .
- name: Trivy vulnerability scan
  uses: aquasecurity/trivy-action@0.33.1
  with:
    image-ref: 'kestrel:ci'
    severity: 'CRITICAL,HIGH'
    exit-code: '1'
```

Run this nightly or on release branches only (Docker build is slow, ~2-3 min).

**3. Secret scanning:**
GitHub already provides secret scanning for public repos. For private repos, consider `gitleaks` as a pre-commit hook or CI step:

```yaml
- name: Gitleaks
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Confidence:** HIGH for Semgrep and Trivy. MEDIUM for gitleaks (GitHub's built-in may suffice).

---

## 7. Performance Testing

### Bundle Size Tracking (Frontend)

**Recommendation:** `size-limit` -- lightweight, posts size changes on PRs.

```json
// frontend/package.json
{
  "size-limit": [
    { "path": "dist/assets/*.js", "limit": "200 kB" }
  ]
}
```

```yaml
- name: Bundle size check
  uses: andresz1/size-limit-action@v1
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    directory: frontend
```

This adds a PR comment showing bundle size delta. Takes ~15 seconds. Run on every PR.

### Lighthouse CI (Web Frontend)

**Recommendation:** Add but run nightly only. Not on every PR (too slow, requires full server startup).

```yaml
lighthouse:
  if: github.event_name == 'schedule'
  steps:
    - uses: treosh/lighthouse-ci-action@v12
      with:
        urls: http://localhost:8101
        budgetPath: ./frontend/lighthouse-budget.json
        uploadArtifacts: true
```

Set budgets for LCP < 2.5s, CLS < 0.1, TBT < 200ms.

### API Benchmark Tests

**Skip for now.** With SQLite and a single-user self-hosted model, API performance bottlenecks are AI provider latency (not the API itself). If/when migrating to Postgres or adding concurrent users, add `pytest-benchmark` or `locust` load tests.

**Confidence:** HIGH for bundle size. MEDIUM for Lighthouse (useful but low priority for self-hosted app).

---

## 8. Test Data Management

### Current Approach (Good)
- In-memory SQLite per test via `db_engine` fixture
- Shared connection pattern (`db_session`) ensures test code and FastAPI app see same data
- Manual factory pattern in `conftest.py` (profile, application fixtures)
- `sample_jobs` fixture for pipeline test data
- Complete isolation: each test gets fresh DB, no cleanup needed

### Recommended Improvements

**1. Move to Factory Boy for complex test data:**
When test data needs grow beyond 5-6 entity types, the manual fixture approach in conftest.py gets unwieldy. Factory Boy + `pytest-factoryboy` auto-registers factories as fixtures:

```python
# tests/factories.py
import factory
from career_os.models.models import Application, Profile

class ProfileFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Profile
        sqlalchemy_session_persistence = "commit"

    name = factory.Faker("name")
    email = factory.Faker("email")

class ApplicationFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Application
        sqlalchemy_session_persistence = "commit"

    profile = factory.SubFactory(ProfileFactory)
    company = factory.Faker("company")
    role = factory.Faker("job")
    status = "discovered"
```

**When to adopt:** When you have 10+ entities needing test data, or when tests start duplicating fixture patterns. Not urgent now.

**2. Keep the in-memory SQLite pattern:**
It is perfect for CI -- no external dependencies, no cleanup, fast. Don't switch to testcontainers or real Postgres until the app actually requires Postgres-specific features.

**Confidence:** HIGH -- current approach is solid; Factory Boy is a future optimization.

---

## 9. Visual Regression Testing

### Recommendation: Skip for Now, Use Playwright Screenshots Later

**Why skip:**
- Kestrel is a self-hosted tool, not a design-heavy consumer product
- Solo developer -- no design team to review visual diffs
- Tailwind CSS changes rarely cause subtle visual regressions (utility classes are explicit)
- SonarCloud catches duplication issues in component code

**When to add:**
If Kestrel gets a public marketing site or component library, add Playwright's built-in `toHaveScreenshot()`:

```typescript
// No external service needed
test('dashboard renders correctly', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page).toHaveScreenshot('dashboard.png', {
    maxDiffPixelRatio: 0.01,
  });
});
```

**Avoid:** Chromatic ($149/mo), Percy ($399/mo), Applitools -- all designed for teams, not solo devs.

**Lightweight alternative if needed:** BackstopJS (free, open-source, Docker-based). But still overkill for current project stage.

**Confidence:** HIGH -- clear skip with defined trigger for when to reconsider.

---

## 10. AI-Specific Testing Concerns

### Testing AI-Generated Code Quality

Kestrel uses AI-assisted development extensively. Specific concerns:

**1. Mutation Testing with mutmut:**
Measures how good your tests actually are (not just coverage). Mutmut changes code and checks if tests catch the change.

```bash
pip install mutmut
mutmut run --paths-to-mutate=src/career_os/services/scoring.py
```

**When to use:** On critical business logic (scoring engine, status transitions, AI provider routing). NOT on every PR -- too slow. Run monthly or before major releases on high-risk modules.

**2. Property-Based Testing with Hypothesis:**
Each property-based test finds ~50x as many bugs as a typical unit test (OOPSLA 2025 study). Perfect for:
- Score calculation logic (any valid input should produce score in 0-100 range)
- Status transition validation (no invalid transition should succeed)
- API input validation (any valid JSON matching schema should not crash)

```python
from hypothesis import given, strategies as st

@given(st.integers(min_value=0, max_value=100), st.integers(min_value=0, max_value=100))
def test_score_combination_always_valid(skill_score, experience_score):
    result = combine_scores(skill_score, experience_score)
    assert 0 <= result <= 100
```

**Recommendation:** Add Hypothesis for scoring logic and API validation. Use `@settings(max_examples=50)` in CI (fast) and `@settings(max_examples=500)` locally (thorough).

**3. Snapshot Testing:**
Vitest and Jest both support snapshots. Use sparingly:
- YES for API response shapes (catch accidental schema changes)
- YES for component render output (catch structural changes)
- NO for large objects (snapshots become noise, auto-updated without review)

**4. AI Output Testing:**
For the AI scoring/coaching features that use MockProvider in CI:
- Test that the AI provider abstraction works (mock returns expected format)
- Test that scoring logic handles edge cases (empty response, timeout, malformed JSON)
- Do NOT test actual AI quality in CI -- that is a separate benchmark concern (already done via G-286)

**Confidence:** HIGH for Hypothesis, MEDIUM for mutmut (useful but niche).

---

## 11. Mobile Testing in CI

### Current State
Zero mobile CI. No test files exist yet.

### Phased Approach

**Phase 1: Jest Unit Tests (Now)**
Add Jest to CI as soon as mobile test files exist:

```yaml
mobile:
  name: Mobile (React Native)
  runs-on: ubuntu-latest
  if: needs.changes.outputs.mobile == 'true'
  defaults:
    run:
      working-directory: mobile
  steps:
    - uses: actions/checkout@v6
    - uses: actions/setup-node@v6
      with:
        node-version: "22"
        cache: npm
        cache-dependency-path: mobile/package-lock.json
    - run: npm ci
    - run: npx jest --ci --coverage --maxWorkers=2
    - name: Type check
      run: npx tsc --noEmit
```

**Phase 2: Maestro E2E on EAS (When Mobile v1 Ships)**
Use Expo's EAS Workflows with Maestro:

```yaml
# eas.json build profile
"test": {
  "developmentClient": true,
  "distribution": "internal",
  "ios": { "simulator": true }
}
```

Maestro test file (YAML, not code):
```yaml
# .maestro/smoke.yaml
appId: com.kestrel.app
---
- launchApp
- assertVisible: "Connect to Kestrel"
- tapOn: "Server URL"
- inputText: "http://localhost:8100"
- tapOn: "Connect"
- assertVisible: "Pipeline"
```

**Phase 3: Device Farm (Defer Indefinitely)**
BrowserStack/AWS Device Farm free tiers exist but are not worth the setup complexity for a solo dev. Simulator/emulator testing catches 95%+ of issues.

### Cost

| Approach | Cost | When |
|----------|------|------|
| Jest on GitHub Actions | $0 (free tier) | Now |
| EAS Build (free plan) | 30 builds/month free | Mobile v1 |
| Maestro CLI (local) | $0 | Mobile v1 |
| Maestro Cloud | ~$212/mo | Never (for solo dev) |
| macOS runner for iOS sim | $0.08/min | Only if iOS-specific bugs emerge |

**Confidence:** HIGH for Jest CI. MEDIUM for Maestro (depends on mobile maturity).

---

## Implementation Priority (Ordered by Impact/Effort)

| Priority | Change | Effort | Impact | When |
|----------|--------|--------|--------|------|
| 1 | Add `dorny/paths-filter` to skip irrelevant jobs | 30 min | Saves 3-4 min on non-full-stack PRs | Now |
| 2 | Add `pytest-xdist` parallel testing | 1 hour | 2-3x faster backend tests | Now |
| 3 | Make SonarCloud quality gate blocking | 15 min | Enforces coverage on new code | Now |
| 4 | Add `pytest-rerunfailures` for flaky detection | 15 min | Prevents flaky tests from blocking PRs | Now |
| 5 | Add Semgrep SAST (fast, blocking) | 30 min | 10-second security scan on every PR | Now |
| 6 | Add `size-limit` bundle size check | 30 min | Catch frontend bloat on PRs | Now |
| 7 | Add mobile Jest CI job | 30 min | Catch mobile regressions | When tests exist |
| 8 | Add Hypothesis property-based tests | 2 hours | Stronger scoring/validation tests | Next sprint |
| 9 | Add Playwright E2E (nightly) | 2 hours | Catch integration regressions | After web stabilizes |
| 10 | Add Trivy container scanning | 30 min | Catch container vulnerabilities | On release branches |
| 11 | Add Lighthouse CI (nightly) | 1 hour | Track web performance trends | Low priority |
| 12 | Add Maestro mobile E2E | 4 hours | Mobile integration testing | After mobile v1 |

---

## Anti-Recommendations (What NOT to Do)

| Avoid | Why |
|-------|-----|
| 100% coverage gates | Leads to garbage tests. 70% on new code is the sweet spot |
| Cypress for E2E | Playwright is faster, lighter, better CI integration, no paid dashboard upsell |
| Detox for mobile E2E | Requires native builds. Maestro is simpler for Expo apps |
| SaaS flaky test dashboards | Trunk.io, Buildkite analytics -- team tools, solo dev doesn't need them |
| Visual regression SaaS | Chromatic/Percy -- $150-400/mo for a solo self-hosted project |
| Test impact analysis tools | Nx/Turborepo -- designed for massive monorepos, not 3-component projects |
| Running E2E on every PR | 5+ min of E2E on every push burns CI minutes and slows feedback |
| Device farm services | BrowserStack/AWS -- simulator testing catches 95% of issues |

---

## Sources

### Test Speed & Parallelization
- [PyPI test suite 81% faster with xdist](https://blog.trailofbits.com/2025/05/01/making-pypis-test-suite-81-faster/)
- [pytest-xdist documentation](https://pytest-xdist.readthedocs.io/)
- [Vitest 3 monorepo setup](https://www.thecandidstartup.org/2025/09/08/vitest-3-monorepo-setup.html)
- [Vitest vs Jest 2026 benchmarks](https://www.sitepoint.com/vitest-vs-jest-2026-migration-benchmark/)

### E2E Testing
- [Playwright CI setup docs](https://playwright.dev/docs/ci-intro)
- [Maestro React Native support](https://docs.maestro.dev/get-started/supported-platform/react-native)
- [Expo EAS Workflows with Maestro](https://docs.expo.dev/eas/workflows/examples/e2e-tests/)
- [React Native testing guide 2026](https://reactnativerelay.com/article/complete-guide-testing-react-native-apps-2026-unit-tests-e2e-maestro)

### Flaky Tests
- [Flaky test benchmark 2026](https://testdino.com/blog/flaky-test-benchmark/)
- [Atlassian Flakinator](https://www.atlassian.com/blog/atlassian-engineering/taming-test-flakiness-how-we-built-a-scalable-tool-to-detect-and-manage-flaky-tests)
- [Slack auto-detection and suppression](https://slack.engineering/handling-flaky-tests-at-scale-auto-detection-suppression/)

### Coverage
- [Google's 75% coverage target](https://www.atlassian.com/continuous-delivery/software-testing/code-coverage)
- [Differential coverage best practices](https://www.harness.io/blog/code-coverage-measure-improve-and-scale-quality-in-ci)

### Security
- [Semgrep vs CodeQL 2026 comparison](https://konvu.com/compare/semgrep-vs-codeql)
- [Trivy GitHub Action](https://github.com/aquasecurity/trivy-action)

### Performance
- [Lighthouse CI action](https://github.com/marketplace/actions/lighthouse-ci-action)
- [size-limit for bundle tracking](https://github.com/andresz1/size-limit-action)

### AI-Specific Testing
- [Property-based testing empirical evaluation (OOPSLA 2025)](https://2025.splashcon.org/details/OOPSLA/102/An-Empirical-Evaluation-of-Property-Based-Testing-in-Python)
- [Mutation testing with mutmut](https://johal.in/mutation-testing-with-mutmut-python-for-code-reliability-2026/)
- [Hypothesis documentation](https://hypothesis.readthedocs.io/)

### Mobile CI
- [Expo EAS on GitHub Actions](https://expo.dev/blog/how-to-integrate-eas-workflows-with-github-actions)
- [Maestro Cloud + Expo integration](https://expo.dev/blog/expo-now-supports-maestro-cloud-testing-in-your-ci-workflow)
