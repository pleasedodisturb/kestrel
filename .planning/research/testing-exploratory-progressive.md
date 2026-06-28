# Research: Exploratory, Fuzzing & Progressive Testing Techniques

**Domain:** Advanced testing for multi-frontend job search platform (FastAPI + React + React Native)
**Researched:** 2026-04-16
**Overall confidence:** HIGH

---

## 1. Automated Exploratory Testing

### API Fuzzing: Schemathesis (Recommended)

**What it is:** Property-based API testing that reads FastAPI's auto-generated OpenAPI spec and generates thousands of edge-case requests -- valid, invalid, and boundary. Uses Hypothesis under the hood.

**Why Schemathesis over alternatives:**
- Python-native, pip-installable, zero configuration for FastAPI (reads `/openapi.json`)
- Schema-aware mutation: if a field is `integer > 0`, it generates 0, -1, MAX_INT, not random noise
- Negative testing mode: systematically violates each schema constraint to verify error handling
- Stateful testing (link mode): chains API calls using OpenAPI links to test multi-step flows
- MIT licensed, free CLI. SaaS "Workbench" dashboard exists but not needed.
- Used by Spotify, JetBrains, Red Hat. Latest release: April 10, 2026.

**Kestrel-specific value:**
- Tests ALL endpoints with zero test authoring -- huge ROI for solo dev
- Application state machine (VALID_TRANSITIONS) gets exercised via stateful mode
- Scoring endpoints get boundary-value inputs (edge scores, empty fields, unicode)
- Discovery engine adapters get malformed data

**Implementation:** Run the CLI against the backend's `/openapi.json` endpoint with `--stateful=links`. For pytest integration, use `schemathesis.from_url()` pointed at the OpenAPI spec, then `@schema.parametrize()` to auto-generate test cases that call and validate each endpoint.

**Effort:** 2-4 hours for initial setup + CI integration. Near-zero ongoing maintenance.
**Cost:** Free (open source, MIT).

### Alternatives Evaluated

| Tool | Verdict | Reason |
|------|---------|--------|
| RESTler (Microsoft) | Skip | C#-based, heavier setup. Better for stateful cloud service testing. Schemathesis covers Kestrel's needs. |
| APIFuzzer | Skip | Random noise fuzzing, not schema-aware. Less sophisticated than Schemathesis. |
| Dredd | Skip | Less maintained, assertion-based (not property-based). |

### Web Monkey Testing: Gremlins.js

**What it is:** Injects random user interactions (clicks, form fills, scrolls, touch events) into a running web app. Catches unhandled JS exceptions, broken event handlers, UI crashes.

**How to use with Playwright:** Inject gremlins.js via `page.addScriptTag()`, then call `gremlins.createHorde().unleash()` to simulate 1000+ random interactions. Listen for `pageerror` events to catch unhandled exceptions. Assert zero errors at the end.

**Effort:** 4-8 hours (Playwright setup + gremlin scripts for key pages).
**Cost:** Free.
**Priority:** MEDIUM -- useful but less predictable than Schemathesis. Run weekly.

### AI-Powered Exploratory Testing Tools

| Tool | Pricing | Verdict |
|------|---------|---------|
| Applitools | $150+/mo | Skip. Visual AI testing -- overlaps with Playwright screenshots at $0. |
| Testim (Tricentis) | Enterprise pricing | Skip. Record-and-replay, designed for QA teams, not solo devs. |
| Mabl | $500+/mo | Skip. Full QA platform, massive overkill. |
| QA Wolf | Custom pricing | Skip. Managed QA service, not a tool. |
| Meticulous.ai | Free for open source | MAYBE. Records real user sessions, replays as tests. Worth evaluating if Kestrel gets real traffic. |

**Recommendation:** Skip AI-powered tools for now. Schemathesis + Gremlins.js cover the automated exploration need at $0.

### Session-Based Exploratory Testing (SBET) for Solo Dev

SBET is a structured manual testing approach. Adapted for solo developer:

1. **Define charter:** "Explore scoring edge cases for non-tech job families" (30 min)
2. **Execute:** Follow the charter, take notes in a scratch file
3. **Debrief:** Convert findings to failing tests or bug tickets
4. **Cadence:** One 30-min session per week, rotating through: API, Web UI, Mobile, Scoring

**No tool needed.** Just discipline and a template:
```
Charter: [what to explore]
Duration: 30 min
Area: [backend/web/mobile/scoring]
Findings: [bugs, edge cases, UX issues]
Tests created: [list of new test cases]
Tickets created: [Linear ticket IDs]
```

---

## 2. Property-Based & Generative Testing

### Hypothesis (Python) -- Recommended

**What it is:** Generate random valid/invalid inputs matching declared strategies. When a test fails, Hypothesis shrinks the input to the minimal failing example. Database of past failures ensures regressions stay caught.

**Kestrel-specific properties to test:**

1. **Scoring invariants:**
   - Score is always 0-100 for any valid input
   - Score is monotonically increasing with more matching skills
   - Score is deterministic (same input = same output)
   - Score never raises an unhandled exception regardless of input

2. **State machine transitions:** Use `hypothesis.stateful.RuleBasedStateMachine` to model the application status flow. Define rules for each transition (apply, reject, interview, etc.) with preconditions based on `VALID_TRANSITIONS`. Hypothesis will explore random sequences of transitions and find invalid paths the code allows but should not.

3. **Data integrity:**
   - Creating then fetching an application returns identical data
   - Deleting an application removes it from all queries
   - Profile isolation: operations on profile A never affect profile B

4. **Contact/skill normalization:**
   - Normalizing any string twice produces the same result (idempotence)
   - Normalized output is always valid (no empty strings, no control chars)

**Implementation effort:** 8-16 hours for initial property tests across scoring + state machine.
**Ongoing effort:** Add properties as new features ship (30 min per feature).

### fast-check (JavaScript) -- Recommended for Frontend

**What it is:** Property-based testing for TypeScript/JavaScript. Works with Vitest and Jest.

**Kestrel-specific use cases:**
- Score display components handle all numeric ranges (0, 50, 100, NaN, undefined)
- Date formatting works for all timezones and locales
- Filter/sort logic is commutative and idempotent
- API response parsing handles missing/null/extra fields

**Example:** Use `fc.property(fc.integer({ min: -100, max: 200 }))` to generate arbitrary score values and assert that `formatScore()` never throws and always returns a non-empty string.

**Implementation effort:** 4-8 hours for frontend property tests.
**Cost:** Free (MIT).

---

## 3. Chaos & Resilience Testing

### Assessment: How Much Does Kestrel Need This?

Kestrel is a self-hosted, single-instance app with SQLite. It is not a distributed system. Chaos testing value is MEDIUM:
- **Worth testing:** API client timeout handling, AI provider degradation, network disconnects on mobile
- **Not worth testing:** Database partitioning, service mesh failures, multi-region failover

### Toxiproxy (Recommended -- Lightweight)

**What it is:** TCP proxy (Go binary) that injects network faults between your app and its dependencies. HTTP API for programmatic control.

**Kestrel-specific scenarios:**

| Scenario | Toxic | What It Tests |
|----------|-------|---------------|
| AI provider slow response | `latency` (5000ms) | Does scoring timeout gracefully? Does UI show loading state? |
| AI provider down | `timeout` (1ms) | Does the app degrade gracefully? Does MockProvider fallback work? |
| AI provider returns garbage | Custom (via proxy rewrite) | Does response validation catch malformed JSON? |
| Database locked (WAL contention) | `latency` (100ms) | Does the app retry or fail gracefully? |

**Setup:** Install via `brew install toxiproxy`. Start the proxy server, create a proxy for the AI provider endpoint, add toxics (latency, timeout, etc.), then run tests with the app configured to route through the proxy via `AI_BASE_URL` environment variable.

**Effort:** 4-8 hours for initial setup + 3-4 resilience test scenarios.
**Cost:** Free.
**Priority:** LOW-MEDIUM. Valuable for AI provider resilience, but the MockProvider pattern already handles most failure modes in tests.

### Chaos Toolkit -- Skip

Chaos Toolkit is an orchestration framework for chaos experiments. Overkill for single-instance app. Toxiproxy alone covers Kestrel's needs.

### Mobile Network Simulation

For React Native/Expo, network failure testing is better handled at the API client level by mocking `fetch` to reject with a network error, then asserting the UI shows an error state rather than crashing. No separate tool needed. Maestro can also test airplane mode behavior on device.

---

## 4. Visual & Snapshot Regression

### Playwright Screenshots (Recommended -- Web)

**What it is:** Built-in `toHaveScreenshot()` in Playwright Test. First run creates baseline ("golden") images. Subsequent runs pixel-compare against baselines.

**How it works:**
1. Test navigates to page/component state
2. `await expect(page).toHaveScreenshot('pipeline.png')` captures screenshot
3. First run: saves as baseline in `tests/screenshots/`
4. Subsequent runs: compares via pixelmatch, fails if diff exceeds threshold
5. On failure: generates expected/actual/diff images in `test-results/`

**Key pages to screenshot:**
- Pipeline board (empty state, populated state)
- Scoring detail (high score, low score, borderline)
- Discovery feed (with results, empty state)
- Contact list
- Dashboard/analytics

**Configuration:** Set `maxDiffPixelRatio: 0.01` (allow 1% pixel difference for font rendering variance) and `threshold: 0.2` (per-pixel color tolerance) in `playwright.config.ts` under `expect.toHaveScreenshot`.

**Effort:** 4-8 hours (Playwright setup + 10-15 screenshot tests for key pages).
**Cost:** Free.
**Priority:** HIGH for web frontend.

### Percy / Chromatic -- Skip for Now

| Tool | Free Tier | Monthly Cost | When to Consider |
|------|-----------|-------------|------------------|
| Percy | 5,000 screenshots/mo | $99/mo (Pro) | When cross-browser visual testing matters |
| Chromatic | 5,000 snapshots/mo | $149/mo (Pro) | When using Storybook (Kestrel does not) |

**Verdict:** Playwright built-in covers the use case at $0. Revisit if Kestrel needs cross-browser rendering validation (Safari, Firefox).

### React Native Visual Testing

Options for mobile visual regression are limited and higher-effort:

| Approach | Effort | Reliability |
|----------|--------|-------------|
| Maestro screenshots | Low | Medium (device-dependent rendering) |
| Storybook React Native + Chromatic | High | High (but requires Storybook setup) |
| Manual screenshots in CI | Medium | Low (fragile) |

**Recommendation:** Defer mobile visual regression. Use Maestro for functional E2E; visual testing on mobile adds too much maintenance for a solo dev. Rely on web visual regression + component-level Jest snapshot tests.

---

## 5. Security Testing Integration

### Current State

Kestrel already has:
- `pip-audit` for Python dependency vulnerabilities (CI)
- `npm audit` + signature verification for JS dependencies (CI)
- CodeQL analysis (separate workflow)
- SonarCloud SAST (separate workflow)
- PII leak check (CI)

### Bandit -- Python SAST (Recommended)

**What it does:** AST-based analysis of Python code for 47 common security issues (SQL injection, hardcoded passwords, weak crypto, unsafe deserialization, etc.).

**Implementation:** Add a CI step that runs `bandit -r src/career_os/ -f sarif -o bandit.sarif` after the lint step. Upload the SARIF file via `github/codeql-action/upload-sarif` for GitHub code scanning integration.

**Key checks relevant to Kestrel:**
- B608: Possible SQL injection via string formatting (SQLAlchemy raw queries)
- B324: Use of weak hash functions
- B501: Requests with verify=False
- B110: Try/except/pass (swallowing errors)

**Effort:** 1 hour to add to CI. May need `.bandit` config to suppress false positives.
**Cost:** Free.
**CI impact:** ~5 seconds for Kestrel's codebase.

### eslint-plugin-security (Recommended)

**What it does:** Detects unsafe JS patterns -- eval(), non-literal regex, prototype pollution vectors.

**Implementation:** Install via npm as a dev dependency in the frontend directory, then add `plugin:security/recommended` to the eslint extends array.

**Effort:** 30 minutes.
**Cost:** Free.

### OWASP ZAP Baseline Scan (Recommended)

**What it does:** Docker-based DAST scan against a running API. Baseline scan mode is fast (~2 min), finds common vulnerabilities without active attack.

**Implementation:** Create a weekly scheduled workflow that starts the backend, then runs the `zaproxy/action-baseline` GitHub Action against the local server. Configure rules in `.zap/rules.tsv` to suppress known false positives.

**What it finds:**
- Missing security headers (CSP, HSTS, X-Content-Type)
- CORS misconfigurations
- Cookie security flags
- Information disclosure
- Basic injection vectors

**Effort:** 2-4 hours (workflow setup + tuning false positives).
**Cost:** Free.
**CI impact:** ~2-5 minutes. Run weekly, not on every PR.

### SQLi/XSS Fuzzing for FastAPI

Schemathesis already covers this partially via schema-aware input mutation. For deeper SQLi testing:
- FastAPI + SQLAlchemy parameterized queries prevent SQLi by design
- Pydantic validation rejects malformed input before it reaches queries
- ZAP baseline scan tests common injection patterns from outside

**Verdict:** No additional SQLi-specific tool needed. The stack (Pydantic + SQLAlchemy + Schemathesis + ZAP) covers it.

---

## 6. Scheduled & Progressive Test Runs

### Three-Tier Strategy

| Tier | Trigger | What Runs | Duration Target |
|------|---------|-----------|-----------------|
| Smoke | Every PR | Lint + unit tests + type check | < 5 min |
| Standard | Nightly (cron) | Full test suite + Schemathesis + Bandit | < 15 min |
| Deep | Weekly (cron) | Everything + ZAP baseline + visual regression + Gremlins | < 30 min |

### GitHub Actions Cron Configuration

Create two new workflow files:

**Nightly** (`.github/workflows/nightly.yml`): Schedule `cron: '0 4 * * *'` (4am UTC daily). Includes full pytest suite, Schemathesis API fuzzing against the running backend's OpenAPI spec with `--stateful=links --hypothesis-max-examples=100`, and Bandit SARIF upload. Always add `workflow_dispatch` alongside `schedule` for manual triggering.

**Weekly** (`.github/workflows/weekly.yml`): Schedule `cron: '0 3 * * 0'` (Sunday 3am UTC). Includes everything from nightly plus ZAP baseline scan and Playwright visual regression tests.

**Key best practices:**
- Use `concurrency` key to cancel in-progress runs when a new one starts
- GitHub Actions now supports `timezone` field alongside cron (March 2026 update)
- Always add `workflow_dispatch` -- without it, you cannot manually trigger for debugging

### Reporting Results

**Recommended: GitHub Actions Summary + Allure**

Allure generates HTML reports with trend tracking. Host on GitHub Pages for free. Install `allure-pytest` and use the `--alluredir` flag, then generate the report and publish via `peaceiris/actions-gh-pages`.

**Alternatives evaluated:**

| Tool | Cost | Verdict |
|------|------|---------|
| Allure | Free (self-hosted) | Recommended. HTML reports, trend tracking, GitHub Pages hosting. |
| BuildPulse | $49/mo+ | Skip. Flaky test detection is not needed at 106 tests. Revisit at 500+. |
| Datadog CI | $20/committer/mo | Skip. Overkill for solo dev. |
| Slack notifications | Free | MAYBE. Simple webhook curl on failure. Low effort. |
| GitHub Issues auto-creation | Free | Skip. Creates noise. Prefer Allure dashboard. |

### Flaky Test Detection

At Kestrel's scale (106 backend + ~30 frontend tests), a dedicated flaky test tool is not justified.

**Lightweight approach:**
1. Run tests 3x in nightly CI using pytest-repeat
2. If a test passes sometimes and fails sometimes, it is flaky
3. Add `@pytest.mark.flaky` marker and skip in PR CI, investigate in next session

**Cost:** $0. Install pytest-repeat.

### GitHub Actions Free Tier Budget

- Free tier: 2,000 minutes/month for private repos, unlimited for public
- Kestrel is public, so minutes are unlimited
- Even if private: nightly (15 min x 30) + weekly (30 min x 4) = 570 min/month, well within budget

---

## 7. Mobile-Specific Testing

### Maestro (Recommended)

**What it is:** YAML-based mobile E2E testing. No code, no native module integration, no build configuration changes. Works with Expo Go, development builds, and EAS Workflows.

**Why Maestro over Detox:**
- Setup: Install CLI + write YAML vs. native module integration + build config + boilerplate
- Reliability: Detox has frequent launch failures (2/10 success on physical devices per Jupiter's 2025 evaluation)
- Learning curve: YAML is approachable, no testing framework expertise needed
- Animation handling: Maestro handles animations natively, Detox struggles with synchronization

**Kestrel flows to test:** Write YAML flow files in `.maestro/` for onboarding (launch, tap connect, enter server URL, verify pipeline visible), pipeline browsing (launch, navigate to pipeline, scroll, tap application, verify score visible), and contact management.

**Expo integration:** Maestro works with Expo via EAS Workflows. Define a build step followed by a maestro step that depends on the build, pointing at the `.maestro/` flow directory.

**Effort:** 4-8 hours for initial setup + 5-6 critical flow scripts.
**Cost:** Free (CLI is open source). Cloud execution via maestro.dev starts at $50/mo but not needed for solo dev.
**Priority:** MEDIUM. Start after mobile app stabilizes (currently in active development).

### Detox -- Skip

- Gray-box testing: hooks into React Native's JS thread for synchronization
- Requires native build modifications, longer setup
- Launch failures reported widely in 2025 evaluations
- Better for large teams with dedicated QA

### Device Farm Testing

| Service | Free Tier | Monthly Cost | Verdict |
|---------|-----------|-------------|---------|
| AWS Device Farm | 250 device-minutes free (one-time) | $0.17/device-minute | Skip. Too expensive for solo dev. |
| BrowserStack | None | $199/mo | Skip. Enterprise pricing. |
| Expo EAS | Included with EAS subscription | $0-99/mo depending on plan | MAYBE. Worth it when ready for release. |

**Recommendation:** Test on local simulator (iOS) + emulator (Android). Device farm only matters for release-readiness testing, which is premature for a project in active development.

---

## 8. Prioritized Implementation Roadmap

### Tier 1: Immediate (This Week) -- Effort: 4-6 hours

| Tool | Action | Why First |
|------|--------|-----------|
| Schemathesis | `pip install schemathesis` + add to nightly CI | Highest bug-finding ROI, zero test authoring |
| Bandit | Add to CI as lint step | 1 hour, finds security issues immediately |
| eslint-plugin-security | Add to frontend eslint config | 30 minutes, zero maintenance |

### Tier 2: Soon (This Sprint) -- Effort: 8-16 hours

| Tool | Action | Why |
|------|--------|-----|
| Hypothesis | Write property tests for scoring + state machine | Catches edge cases in critical business logic |
| Nightly CI workflow | Create `.github/workflows/nightly.yml` | Enables heavier tests without slowing PRs |
| fast-check | Add property tests for frontend data transforms | Complements Hypothesis for TypeScript code |

### Tier 3: Next Sprint -- Effort: 8-12 hours

| Tool | Action | Why |
|------|--------|-----|
| Playwright screenshots | Set up visual regression for 10-15 key pages | Catches CSS regressions |
| Weekly CI workflow | Create `.github/workflows/weekly.yml` with ZAP scan | Security testing on cadence |
| Gremlins.js | Monkey test key web pages in weekly CI | Finds unhandled exceptions |

### Tier 4: When Mobile Stabilizes -- Effort: 8-12 hours

| Tool | Action | Why |
|------|--------|-----|
| Maestro | Write YAML flows for onboarding + pipeline + contacts | Mobile E2E with minimal maintenance |
| Manual SBET | Establish weekly 30-min exploratory testing cadence | Finds issues automation misses |

### Tier 5: Optional / When Needed

| Tool | Action | Trigger |
|------|--------|---------|
| Toxiproxy | Set up AI provider resilience tests | When adding production AI provider error handling |
| Allure | Set up test reporting dashboard | When test count exceeds 200 |
| BuildPulse | Flaky test detection | When test count exceeds 500 |

---

## 9. Cost Summary

| Item | Monthly Cost | Annual Cost |
|------|-------------|-------------|
| Schemathesis | $0 | $0 |
| Hypothesis + fast-check | $0 | $0 |
| Playwright (visual) | $0 | $0 |
| Maestro CLI | $0 | $0 |
| Bandit + eslint-plugin-security | $0 | $0 |
| OWASP ZAP | $0 | $0 |
| Gremlins.js | $0 | $0 |
| Toxiproxy | $0 | $0 |
| GitHub Actions (public repo) | $0 | $0 |
| Allure (self-hosted) | $0 | $0 |
| **Total** | **$0** | **$0** |

The entire advanced testing stack is achievable at zero cost. All recommended tools are open source.

---

## Sources

- [Schemathesis GitHub](https://github.com/schemathesis/schemathesis) -- v3.x, April 2026
- [Schemathesis official site](https://schemathesis.io/)
- [Hypothesis docs](https://hypothesis.readthedocs.io/) -- v6.151+
- [fast-check GitHub](https://github.com/dubzzz/fast-check) -- v4.5+
- [fast-check official docs](https://fast-check.dev/)
- [Playwright Visual Testing docs](https://playwright.dev/docs/test-snapshots)
- [Maestro React Native docs](https://docs.maestro.dev/get-started/supported-platform/react-native)
- [Expo + Maestro E2E guide](https://docs.expo.dev/eas/workflows/examples/e2e-tests/)
- [Detox vs Maestro vs Appium comparison (2026)](https://www.pkgpulse.com/blog/detox-vs-maestro-vs-appium-react-native-e2e-testing-2026)
- [Bandit PyPI](https://pypi.org/project/bandit/) -- v1.9.3, January 2026
- [Bandit GitHub (PyCQA)](https://github.com/PyCQA/bandit)
- [OWASP ZAP Automation docs](https://www.zaproxy.org/docs/automate/)
- [Toxiproxy GitHub](https://github.com/Shopify/toxiproxy) -- v2.12+
- [Gremlins.js GitHub](https://github.com/marmelab/gremlins.js/)
- [Percy visual testing tools comparison](https://percy.io/blog/visual-regression-testing-tools) -- 5K screenshots/mo free
- [Chromatic pricing (2026)](https://aisotools.com/pricing/chromatic) -- 5K snapshots/mo free
- [GitHub Actions March 2026 updates (timezone support)](https://github.blog/changelog/2026-03-19-github-actions-late-march-2026-updates/)
- [BuildPulse flaky test detection](https://buildpulse.io/)
- [RESTler vs Schemathesis ACM comparison](https://dl.acm.org/doi/10.1145/3597205)
- [Small-scale chaos testing (2025)](https://blog.gaborkoos.com/posts/2025-10-01-Small-Scale-Chaos-Testing-The-Missing-Step-Before-Production/)
- [QA Wolf best mobile E2E frameworks 2026](https://www.qawolf.com/blog/best-mobile-app-testing-frameworks-2026)
- [React Native Testing Guide 2026](https://reactnativerelay.com/article/complete-guide-testing-react-native-apps-2026-unit-tests-e2e-maestro)
