# Research: Portable Testing Standards & Cross-Project Test Infrastructure

**Domain:** Testing governance, standards-as-code, agentic workflow quality gates
**Researched:** 2026-04-16
**Overall confidence:** MEDIUM-HIGH

---

## 1. Testing Standards as Code

### How Organizations Codify Testing Standards

The industry has converged on three main approaches for codifying testing standards:

**Architecture Decision Records (ADRs)** document the "why" behind testing decisions. Format: context, decision, consequences. Best for one-time decisions like "we use integration tests over E2E for API testing." Not great for ongoing rules agents must follow.

**Testing Manifests / Living Standards Documents** are the better fit for Kestrel's use case. A `TESTING.md` or testing section in `CLAUDE.md` that agents read before writing tests. Must be prescriptive ("do X") not descriptive ("we prefer X"). Google's Testing Blog principles, Testing Library's guiding principles, and Shopify's testing guidelines all follow this pattern.

**Quality Gates as Config** encode standards mechanically: coverage thresholds in CI config, pre-commit hook rules, linting rules. These are the enforcement layer -- they don't explain why, they just block non-compliant code.

**Recommendation for Kestrel:** Use all three layers:
1. ADRs for major decisions (stored in `docs/decisions/`)
2. `TESTING.md` + CLAUDE.md sections for agent-readable standards
3. CI config + pre-commit hooks for mechanical enforcement

### What a Testing Standard Document Should Contain

For a document to be both human-readable and agent-consumable:

```markdown
## Testing Standard: [Project Name]

### Test Types and When to Use Each
- Unit test: Pure logic, no I/O, <100ms
- Integration test: Real DB (in-memory SQLite), mocked external APIs
- Contract test: API schema compliance
- Regression test: Golden set comparison

### Naming Convention
- Python: `test_<unit>_<scenario>_<expected>` (e.g., `test_score_missing_skills_returns_zero`)
- TypeScript: `describe('<Component>') > it('should <behavior>')`

### Test Structure
- Arrange, Act, Assert (always in that order, with blank lines separating)
- One logical assertion per test (multiple asserts OK if testing one behavior)

### What Must Be Tested
- Every public function/method
- Every API endpoint (happy path + one error case minimum)
- Every state transition
- Every scoring rule change (golden set)

### What Must NOT Be Done
- Never mock the unit under test
- Never use `assert True` or `assert result is not None` as sole assertions
- Never test private methods directly
- Never use time.sleep in tests (use freezegun/time mocking)
- Never hardcode IDs that exist in production data

### Coverage Requirements
- New code: 80% line coverage minimum
- Modified files: coverage must not decrease
- Excluded from metrics: generated code, type stubs, migrations

### Test Commands (Copy-Paste Ready)
[Exact commands for each test type]
```

### Versioning Testing Standards

**Do NOT version separately from application code.** For a solo developer, the standards evolve with the project. Keep `TESTING.md` in the repo root, version it with git. If extracting to a shared package later, the package has its own semver.

The exception: if you create a shared pytest plugin or GitHub Actions workflow, those get their own version because they serve multiple consumers.

### Open Source Examples Worth Studying

| Project | What to Learn | Link |
|---------|--------------|------|
| Google Testing Blog | Test behavior not implementation, test sizes (small/medium/large) | testing.googleblog.com |
| Testing Library | "The more your tests resemble the way software is used, the more confidence they give you" | testing-library.com/docs/guiding-principles |
| Django | Comprehensive test docs with conventions for contrib apps | docs.djangoproject.com/en/5.2/topics/testing/ |
| FastAPI | Testing patterns for dependency injection override | fastapi.tiangolo.com/tutorial/testing/ |

**Confidence: HIGH** -- These patterns are well-established across multiple authoritative sources.

---

## 2. CLAUDE.md Testing Integration

### Recommended CLAUDE.md Testing Section Template

Based on analysis of effective CLAUDE.md files from the awesome-claude-code-toolkit and Anthropic's best practices documentation:

```markdown
## Testing

### Rules (Non-Negotiable)
- Every piece of code MUST have tests. Write tests alongside the code, not after.
- Run tests after writing them to confirm they pass.
- Test behavior, not implementation. Tests must survive refactoring.
- Each test validates one behavior. Use descriptive names: `test_score_missing_skills_returns_zero`
- Mock at boundaries only: HTTP, database, filesystem, clock, randomness.
- Never mock the unit under test. Never use `assert True` as a sole assertion.

### Test Commands
```bash
# Backend (from repo root)
pytest tests/ -v                          # all tests
pytest tests/ -v -m smoke                 # fast sanity check (<30s)
pytest tests/ -v -m "not slow"            # skip slow tests
pytest tests/ -k "test_name"              # single test by name
pytest tests/ -v --cov=src/career_os      # with coverage

# Frontend (from frontend/)
npx vitest run                            # all tests
npx vitest run src/__tests__/File.test.tsx # single file
npx vitest run --coverage                 # with coverage

# Mobile (from mobile/)
npx jest                                  # all tests
npx jest src/path/to/File.test.tsx        # single file
```

### Test Placement
- Backend: `tests/` directory, one test file per module
- Frontend: `frontend/src/__tests__/`, mirrors source structure
- Mobile: Co-located as `*.test.tsx` next to source files

### When Writing Tests
1. Identify the public interface being tested
2. Write the happy path test first
3. Add at least one error/edge case
4. Verify the test fails when the code is removed (red-green check)
5. Run the test to confirm it passes

### When Modifying Existing Code
1. Run existing tests first to confirm they pass
2. Make the change
3. Run tests again -- if any fail, fix the code or update the test
4. If changing behavior, update/add tests to match new behavior
5. Coverage on modified files must not decrease
```

### What Goes in CLAUDE.md vs. CI Config

| Standard | CLAUDE.md | CI Config |
|----------|-----------|-----------|
| "Write tests for new code" | YES (agent instruction) | YES (diff-cover gate) |
| "80% coverage on new code" | YES (awareness) | YES (enforced) |
| Test naming conventions | YES (primary location) | NO |
| Test structure (AAA) | YES (primary location) | NO |
| Mocking rules | YES (primary location) | NO |
| Test commands | YES (copy-paste reference) | Implicit in CI steps |
| Timeout limits | Mention exists | YES (pyproject.toml) |
| Coverage thresholds | Mention the target | YES (enforced numerically) |

**Rule of thumb:** CLAUDE.md holds the "how to write good tests" rules. CI config holds the "this build fails if you don't" rules. Overlap on coverage targets is intentional -- the agent should know the threshold before CI rejects the PR.

### Encoding "When to Run What" for Agents

Add this to CLAUDE.md:

```markdown
### Test Execution Guide for Agents
- After modifying Python files: `pytest tests/ -v -m "not slow" --tb=short`
- After modifying frontend files: `cd frontend && npx vitest run --reporter=verbose`
- After modifying scoring logic: `pytest tests/ -v -k "scoring or golden" --tb=short`
- After modifying API routes: `pytest tests/ -v -k "api" --tb=short`
- Before committing: Run the relevant subset above
- Before creating PR: Run full suite for the affected stack
```

**Confidence: HIGH** -- Based on Anthropic's own best practices docs and multiple community templates.

---

## 3. Portable Test Infrastructure

### Shared GitHub Actions Workflows

GitHub supports reusable workflows via `workflow_call` trigger. For a solo developer with multiple repos:

**Option A: Organization .github repo** (recommended when you have 3+ repos)
Create `pleasedodisturb/.github` repo with reusable workflows:

```yaml
# .github/workflows/python-test.yml (in the .github repo)
name: Python Test
on:
  workflow_call:
    inputs:
      python-version:
        type: string
        default: "3.11"
      test-path:
        type: string
        default: "tests/"
      source-path:
        type: string
        default: "src/"
      coverage-threshold:
        type: number
        default: 80
```

Consuming repo references it:
```yaml
jobs:
  test:
    uses: pleasedodisturb/.github/.github/workflows/python-test.yml@main
    with:
      coverage-threshold: 85
```

**Option B: Same-repo reusable workflows** (for now, with Kestrel only)
Keep the workflow in Kestrel's repo. Extract when a second project needs it.

**Recommendation:** Option B now. Option A when the second public project starts. Premature extraction creates maintenance burden with no consumer.

### Reusable pytest Configuration

**Shared conftest.py patterns** that port across FastAPI projects:

```python
# Portable FastAPI test fixtures (conftest.py)
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

@pytest.fixture
def db_engine(request):
    """In-memory SQLite with FK enforcement. Portable across projects."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Import Base from wherever the project defines it
    base_cls = request.config.getoption("--sqlalchemy-base", default=None)
    if base_cls:
        base_cls.metadata.create_all(bind=engine)

    yield engine
    engine.dispose()
```

**pip-installable pytest plugin** for cross-project fixtures:

```python
# kestrel_test_utils/plugin.py
import pytest

def pytest_addoption(parser):
    parser.addoption("--coverage-threshold", default=80, type=int)
    parser.addoption("--fail-on-no-tests", action="store_true", default=False)

@pytest.fixture
def api_client(app):
    """Generic FastAPI test client. Projects provide 'app' fixture."""
    from fastapi.testclient import TestClient
    return TestClient(app)
```

Register via entry points in pyproject.toml:
```toml
[project.entry-points."pytest11"]
kestrel_test_utils = "kestrel_test_utils.plugin"
```

**Recommendation:** Do NOT build the plugin yet. Extract after the second project reveals which patterns are truly shared. For now, keep conftest.py patterns documented in TESTING.md.

### Shared Vitest Configuration

Vitest 3+ supports `mergeConfig` for shared base configs:

```typescript
// packages/vitest-config/index.ts (shared config)
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    globals: true,
    coverage: {
      provider: 'v8',
      thresholds: { lines: 80, branches: 75 },
      exclude: ['**/*.d.ts', '**/types.generated.ts', '**/test/**'],
    },
    testTimeout: 10000,
  },
})

// Per-project vitest.config.ts
import { mergeConfig } from 'vitest/config'
import sharedConfig from '@kestrel/vitest-config'

export default mergeConfig(sharedConfig, {
  test: { environment: 'jsdom' },
})
```

**Recommendation:** Same as pytest plugin -- document the pattern, implement when needed.

**Confidence: MEDIUM-HIGH** -- GitHub reusable workflows are well-documented. Plugin pattern is standard pytest. Timing recommendation is judgment-based.

---

## 4. Test Maturity Model (Adapted for Solo Developer)

### Kestrel-Adapted Maturity Levels

The standard TMMi (Test Maturity Model integration) has 5 levels designed for organizations. Here is an adaptation for a solo developer using AI agents:

#### Level 1: Initial (Ad Hoc)
- Tests exist but inconsistently
- No conventions -- each test file has its own style
- No CI or manual CI
- **Kestrel is past this level**

#### Level 2: Managed (Current State)
- Tests are required for new code (CLAUDE.md rule)
- CI runs tests on every PR
- Coverage is measured but not gated
- Test style varies across files
- No test categorization (markers)
- **Kestrel is HERE** -- 99 backend test files, 22 frontend tests, CI with coverage + SonarCloud

#### Level 3: Defined (Target -- 2-4 weeks of work)
- Testing standards documented in TESTING.md + CLAUDE.md
- Test markers registered and used for tiering
- Coverage gated on modified files (diff-cover)
- Pre-commit hooks verify test existence for new modules
- Test naming conventions enforced consistently
- Agent testing rules explicit and followed
- **Metrics at this level:** coverage %, test count, CI time

#### Level 4: Measured (Target -- 2-3 months)
- Mutation testing reveals assertion quality (mutmut + Stryker)
- Coverage trending tracked over time (SonarCloud history)
- Flaky test rate measured and kept <2%
- Test execution time tracked per-tier
- Golden set regression automated
- **Metrics at this level:** mutation score, flaky rate, coverage trend, CI time trend

#### Level 5: Optimized (Aspirational)
- Predictive test selection (ML-based, beyond testmon)
- Automated test generation for new endpoints
- Self-healing tests (auto-update selectors/assertions)
- **Not recommended for solo dev** -- diminishing returns are severe

### How to Assess Current Maturity

Run this checklist:

| Criterion | Level 2 | Level 3 | Level 4 |
|-----------|---------|---------|---------|
| Tests exist for new code | Required | Required | Required |
| CI runs tests | Yes | Yes | Yes |
| Testing standards documented | No | Yes | Yes |
| Test markers/categories | No | Yes | Yes |
| Coverage gated | No | On modified files | On modified files + threshold |
| Pre-commit test hooks | No | Yes | Yes |
| Mutation testing | No | No | Yes |
| Flaky test tracking | No | No | Yes |
| Test execution trending | No | No | Yes |

### Key Metrics by Level

| Metric | Level 2 | Level 3 | Level 4 |
|--------|---------|---------|---------|
| Line coverage (new code) | Measured | >=80% gated | >=80% gated |
| Branch coverage (new code) | Not tracked | >=75% gated | >=75% gated |
| Mutation score | N/A | N/A | >=60% |
| Flaky test rate | Unknown | Tracked | <2% |
| Mean time to fix broken test | Unknown | <1 day | <4 hours |
| CI test time (PR) | ~2 min | <3 min (testmon) | <3 min |

**Confidence: MEDIUM** -- Maturity model adapted from TMMi (well-established) but solo-dev adaptation is my synthesis, not from a single authoritative source.

---

## 5. Documentation & Maintainability

### Test Architecture Documentation

Create a `TESTING.md` at repo root with these sections:

```markdown
# Testing Guide

## Overview
- 3 test suites: Backend (pytest), Frontend (Vitest), Mobile (Jest)
- CI runs on every PR: lint + test + coverage
- SonarCloud for cross-suite analysis

## Test Inventory
| Suite | Test Files | Total Tests | Coverage | Last Audit |
|-------|-----------|-------------|----------|------------|
| Backend | 99 | ~500 | XX% | YYYY-MM-DD |
| Frontend | 22 | ~80 | XX% | YYYY-MM-DD |
| Mobile | 0 | 0 | 0% | N/A |

## What's Tested / What's Not
| Area | Status | Priority | Notes |
|------|--------|----------|-------|
| Scoring engine | Well tested | - | Golden set + unit tests |
| API routes | Partially | High | Missing: some error paths |
| Frontend components | Partially | Medium | Core components covered |
| Mobile app | Not tested | High | Blocked on mobile dev start |
| CLI commands | Partially | Low | Some commands covered |

## Conventions
[Link to CLAUDE.md testing section or inline]

## Runbooks
### Adding a new test tier
### Updating golden sets
### Debugging flaky tests
### Running mutation testing locally
```

### Keeping Docs in Sync

The biggest risk is documentation drift. Mitigation strategies:

1. **CI check for TESTING.md freshness** -- A simple script that warns (not blocks) if TESTING.md hasn't been updated in 90 days
2. **Test inventory generation** -- A script that counts test files and updates the inventory table:
   ```bash
   # Generate test inventory
   echo "Backend: $(find tests -name 'test_*.py' | wc -l) files"
   echo "Frontend: $(find frontend/src/__tests__ -name '*.test.*' | wc -l) files"
   ```
3. **Include doc updates in Definition of Done** -- When CLAUDE.md says "write tests," also say "update TESTING.md inventory if adding a new test domain"

### Test Map / Test Inventory

A test map answers: "what code is tested by what tests?"

For Kestrel, this is partially automated:
- **pytest-cov** shows which source lines are hit by which tests
- **SonarCloud** shows uncovered code on PRs
- **testmon** maintains a code-to-test dependency graph in `.testmondata`

What's missing: a high-level "what areas are covered" view. The TESTING.md inventory table above fills this gap at low maintenance cost.

### Runbooks for Common Tasks

Include in TESTING.md or as separate files in `docs/testing/`:

**Runbook: Adding a New Golden Set**
```
1. Create fixture file in tests/fixtures/ (copy format from existing)
2. Add profile + job pairs with expected_band ranges
3. Register fixture path in GOLDEN_SET_FILES list
4. Run: pytest tests/ -k golden -v
5. If bands are wrong, adjust based on scoring service output
6. Commit fixture file + test updates together
```

**Runbook: Debugging a Flaky Test**
```
1. Run test 10x: pytest tests/test_foo.py -v --count=10 (needs pytest-repeat)
2. If fails intermittently: check for time-dependent logic, random ordering, shared state
3. Common causes: datetime.now() in test, missing db session cleanup, import side effects
4. Fix: use freezegun for time, ensure fixture cleanup, isolate imports
5. If unfixable quickly: quarantine with @pytest.mark.skip(reason="flaky: tracking in G-XXX")
```

**Confidence: HIGH** -- Documentation patterns are universal and well-established.

---

## 6. Testing Governance for Agentic Workflows

### The Core Problem

AI agents write tests that pass but test nothing meaningful. Common failure modes:
- `assert result is not None` (tests existence, not correctness)
- Mocking the unit under test (test always passes regardless of implementation)
- Testing implementation details (test breaks on every refactor)
- Copy-pasting test structure without understanding (identical tests with different names)
- `assert True` or `assert len(result) > 0` as primary assertions

### Three-Layer Enforcement Model

**Layer 1: CLAUDE.md Rules (Preventive)**
The agent reads these before writing code. Include explicit anti-patterns:

```markdown
### Test Anti-Patterns (NEVER DO THESE)
- `assert result is not None` as the only assertion -- always assert specific values
- `assert True` or `assert len(x) > 0` -- assert the actual expected value
- Mocking the function you're testing -- mock dependencies, not the subject
- `except Exception: pass` in test code -- let exceptions propagate
- Tests that pass when the tested code is deleted -- verify with red-green
```

**Layer 2: Pre-Commit Hooks (Detective)**

Use `pre-commit` framework with custom hooks:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: check-test-exists
        name: Check test exists for new Python modules
        entry: python scripts/check_test_exists.py
        language: python
        files: ^src/career_os/.*\.py$
        exclude: ^src/career_os/(__|_alembic)

      - id: check-test-quality
        name: Check for trivial test assertions
        entry: python scripts/check_test_quality.py
        language: python
        files: ^tests/.*\.py$
```

**check_test_exists.py** (simplified):
```python
"""Verify that new/modified source files have corresponding test files."""
import sys
from pathlib import Path

def main():
    failures = []
    for filepath in sys.argv[1:]:
        source = Path(filepath)
        if source.name.startswith("_"):
            continue
        test_file = Path("tests") / f"test_{source.stem}.py"
        # Also check for tests that import the module
        if not test_file.exists():
            failures.append(f"No test file found for {filepath} (expected {test_file})")

    if failures:
        print("Missing test files:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

**check_test_quality.py** (simplified):
```python
"""Flag trivial assertions in test files."""
import re
import sys

TRIVIAL_PATTERNS = [
    (r'assert\s+True\b', 'assert True is never a meaningful assertion'),
    (r'assert\s+result\s+is\s+not\s+None\s*$', 'assert is not None alone is trivial'),
    (r'assert\s+len\([^)]+\)\s*>\s*0\s*$', 'assert len > 0 alone is trivial'),
    (r'assert\s+1\s*==\s*1', 'assert 1 == 1 is a placeholder'),
]

def main():
    failures = []
    for filepath in sys.argv[1:]:
        with open(filepath) as f:
            for i, line in enumerate(f, 1):
                for pattern, msg in TRIVIAL_PATTERNS:
                    if re.search(pattern, line.strip()):
                        failures.append(f"{filepath}:{i}: {msg}")

    if failures:
        print("Trivial assertions detected:")
        for f in failures:
            print(f"  - {f}")
        # Warning, not blocking (some edge cases are legitimate)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

**Layer 3: CI Gates (Enforcing)**

```yaml
# In CI workflow
- name: Coverage on modified files
  run: |
    diff-cover coverage.xml --compare-branch=origin/main \
      --fail-under=80 --diff-range-notation='..'

- name: Check for test-less source changes
  run: |
    # Get list of modified Python source files in this PR
    CHANGED=$(git diff --name-only origin/main...HEAD -- 'src/career_os/*.py' | grep -v '__')
    for f in $CHANGED; do
      stem=$(basename "$f" .py)
      if ! find tests/ -name "test_${stem}.py" -o -name "*test*${stem}*" | grep -q .; then
        echo "::warning::No test file found for modified source: $f"
      fi
    done
```

### Preventing Low-Quality Agent Tests

Beyond the three layers above:

1. **Require red-green verification in CLAUDE.md**: "After writing a test, temporarily break the code under test and verify the test fails. If it doesn't, the test is useless."

2. **Mutation testing as periodic audit**: Run mutmut weekly or before releases. If mutation score drops, investigate which tests are weak.

3. **Test review checklist for agents**: Add to CLAUDE.md:
   ```
   Before committing tests, verify:
   - [ ] Each test would fail if the tested code were deleted
   - [ ] Assertions check specific expected values, not just existence
   - [ ] No mocking of the unit under test
   - [ ] Test name describes the behavior being tested
   ```

**Confidence: HIGH** -- Quality gates for AI code are a hot topic in 2025-2026 with multiple credible sources converging on the same patterns.

---

## 7. Industry Benchmarks

### Coverage Levels in Mature Open-Source Projects

| Project Type | Typical Coverage | Notes |
|-------------|-----------------|-------|
| Mature OSS (average) | 78% | Study of 1,270 projects using TravisCI |
| Ruby projects | 86% | Higher than average |
| Java projects | 63% | Lower than average |
| Safety-critical | 100% required | Aerospace, medical, financial |
| Recommended target | 80-90% | Consensus across Google, SonarCloud, industry |

**Key insight from Google Testing Blog:** "Coverage is a useful metric, but only when combined with other quality signals. 80% coverage with strong assertions is better than 95% coverage with weak assertions."

**Code coverage does not correlate significantly with post-release bug count** (study of 100 large OSS Java projects). This is why mutation testing matters more than coverage percentage alone.

### ROI of Testing Investments for Small Teams

Ranked by bug-prevention-per-hour (highest first):

| Investment | ROI | Time to Value | Notes |
|-----------|-----|---------------|-------|
| Integration tests for API routes | Very High | Immediate | Catches most real bugs; FastAPI TestClient makes it fast |
| Static analysis (ruff, eslint, TypeScript strict) | Very High | Immediate | Already in place for Kestrel; prevents entire bug categories |
| Contract testing (Schemathesis/OpenAPI) | High | 1-2 days setup | Catches API drift, missing validation, edge cases |
| Golden set regression | High | 1 day setup | Domain-specific but critical for scoring accuracy |
| Pre-commit quality hooks | Medium-High | 2-4 hours | Prevents agent mistakes before they reach CI |
| Unit tests for business logic | Medium | Ongoing | Important but less bug-per-hour than integration tests |
| Mutation testing | Medium | 1 day setup | Best for assessing test quality, not finding bugs directly |
| E2E browser tests | Low for solo dev | 1-2 weeks | High maintenance, flaky, better alternatives exist |

### Case Studies: Small Teams with Excellent Testing

**SQLite** (solo/small team): One of the most thoroughly tested codebases in existence. 100% branch coverage, billions of test cases via fuzzing. Key lesson: testing investment pays off when your software is foundational infrastructure.

**FastAPI** (started as solo): Comprehensive test suite that also serves as documentation. Every example in the docs is a tested code block. Key lesson: tests-as-documentation reduces maintenance burden because docs and tests can't drift.

**pytest itself**: Tests its own features exhaustively. Uses its own plugin system for testing. Key lesson: eating your own dog food (testing your test infrastructure) catches meta-bugs.

**Confidence: MEDIUM** -- Coverage benchmarks are from studies but specific numbers vary by methodology. ROI ranking is synthesized from multiple sources and professional judgment.

---

## 8. Recommended Maturity Progression for Kestrel

### Phase 1: Formalize (Level 2 -> Level 3) -- Est. 1-2 weeks

**Do now:**
- Create `TESTING.md` with conventions, inventory, runbooks
- Expand CLAUDE.md testing section with agent-specific rules and anti-patterns
- Register pytest markers in pyproject.toml (`smoke`, `slow`, `integration`, `regression`)
- Tag existing tests with appropriate markers (bulk operation, ~2 hours)
- Add `diff-cover` to CI to gate coverage on modified files

**Do not:**
- Restructure test directories (not needed at 99 files)
- Add mutation testing (premature)
- Build shared infrastructure (only one consumer)

### Phase 2: Enforce (Level 3 solidified) -- Est. 1 week

**Do now:**
- Install pre-commit with test existence check and trivial assertion detector
- Add `--strict-markers` to pytest config
- Create the "when to run what" guide in CLAUDE.md
- Set up testmon for selective test execution in CI

**Do not:**
- Make pre-commit hooks blocking for everything (start with warnings)
- Require coverage on untouched files

### Phase 3: Measure (Level 3 -> Level 4) -- Est. 2-4 weeks

**Do now:**
- Add mutmut to Python dev dependencies, run baseline measurement
- Set up coverage trending in SonarCloud (already partially there)
- Track flaky test rate (annotate flaky tests with skip reason + ticket)
- Implement golden set regression runner
- Add pytest-json-report for machine-readable results

**Do not:**
- Add Stryker for frontend yet (do when frontend test count exceeds 50)
- Chase mutation score above 60% (diminishing returns)

### Phase 4: Extract (when second project starts) -- Est. 1-2 weeks

**Do now:**
- Extract shared GitHub Actions workflow to `.github` org repo
- Extract shared pytest fixtures into pip-installable plugin
- Extract shared vitest config into npm package
- Document extraction decisions in ADRs

**Do not:**
- Do this before a second project exists
- Over-abstract (keep it simple, 2-3 shared configs max)

---

## 9. Templates

### CLAUDE.md Testing Section (Ready to Use)

```markdown
## Testing

### Rules (Non-Negotiable)
- Every piece of code MUST have tests. Write tests alongside the code, not after.
- Run tests after writing them to confirm they pass.
- Test behavior, not implementation. Tests must survive refactoring.
- Each test validates one behavior. Use descriptive names.
- Mock at boundaries only: HTTP, database, filesystem, clock.
- Never mock the unit under test.

### Anti-Patterns (NEVER DO THESE)
- `assert result is not None` as the only assertion
- `assert True` or `assert len(x) > 0` without checking values
- Mocking the function you're testing
- Tests that pass when the tested code is deleted
- Copy-pasting test bodies without changing assertions

### Test Commands
```bash
# Backend
pytest tests/ -v                          # all
pytest tests/ -v -m smoke                 # fast sanity
pytest tests/ -v -m "not slow"            # skip slow
pytest tests/ -k "test_name"              # by name
pytest tests/ -v --cov=src/career_os      # with coverage

# Frontend (from frontend/)
npx vitest run                            # all
npx vitest run --coverage                 # with coverage

# Mobile (from mobile/)
npx jest                                  # all
```

### When to Run What (Agent Guide)
- Modified Python source: `pytest tests/ -v -m "not slow" --tb=short`
- Modified scoring logic: `pytest tests/ -v -k "scoring or golden" --tb=short`
- Modified API routes: `pytest tests/ -v -k "api" --tb=short`
- Modified frontend: `cd frontend && npx vitest run`
- Before committing: relevant subset above
- Before PR: full suite for affected stack

### Test Placement
- Backend: `tests/test_<module>.py`
- Frontend: `frontend/src/__tests__/<Component>.test.tsx`
- Mobile: co-located `*.test.tsx` next to source

### Coverage
- New code: 80% line coverage minimum
- Modified files: coverage must not decrease
- Excluded: generated code, type stubs, migrations
```

### pre-commit-config.yaml (Ready to Use)

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: local
    hooks:
      - id: check-test-quality
        name: Check for trivial test assertions
        entry: python scripts/check_test_quality.py
        language: python
        files: ^tests/.*\.py$
        pass_filenames: true
```

### pyproject.toml Marker Registration (Ready to Use)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
timeout = 30
strict_markers = true
markers = [
    "smoke: Fast tests for basic sanity (<1s each)",
    "slow: Tests that take >5s (excluded from default runs)",
    "integration: Tests requiring database or HTTP client",
    "regression: Golden set and scoring regression tests",
    "contract: API contract/schema validation tests",
]
```

---

## Sources

### Primary (HIGH confidence)
- [pytest documentation](https://docs.pytest.org/en/stable/)
- [Vitest workspace/projects](https://vitest.dev/guide/projects)
- [GitHub: Reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)
- [Claude Code Best Practices](https://code.claude.com/docs/en/best-practices)
- [Google Testing Blog: Coverage Best Practices](https://testing.googleblog.com/2020/08/code-coverage-best-practices.html)

### Secondary (MEDIUM confidence)
- [Quality Gates in the Age of Agentic Coding](https://blog.heliomedeiros.com/posts/2025-07-18-quality-gates-agentic-coding/)
- [AI Agent Coding Quality Controls](https://www.geeky-gadgets.com/ai-agent-quality-gates/)
- [awesome-claude-code-toolkit testing rules](https://github.com/rohitg00/awesome-claude-code-toolkit/blob/main/rules/testing.md)
- [TMMi Guide (BrowserStack)](https://www.browserstack.com/guide/how-to-achieve-high-test-maturity)
- [TMM in Software Testing (TestFort)](https://testfort.com/blog/tmm-in-software-testing)

### Tertiary (LOW confidence -- needs validation)
- Mutation testing ROI claims (76% fewer bugs with mutmut -- single survey, JetBrains 2025)
- Coverage-to-bug-rate non-correlation (single study of 100 Java projects)
- AI-generated code needing 85-90% coverage vs human 70-80% (blog claim, no peer review)
