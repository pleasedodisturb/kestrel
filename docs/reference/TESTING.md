# Testing Standards

This document defines test quality standards for Kestrel. The machine-readable rules section at the top is consumed by AI agents and enforcement hooks. The educational guide below is for human developers.

<!-- RULES START -->
## Machine-Readable Rules

### Assertion Quality
- RULE-01: Every test function MUST contain at least 2 assert statements
- RULE-02: `assert True`, `assert False` are PROHIBITED (use specific value assertions)
- RULE-03: Bare `assert x is not None` is PROHIBITED (assert on actual value instead)
- RULE-04: Escape hatch: append `# noqa: KTEST001` to suppress a specific line (auditable)

### Mocking Rules
- RULE-05: NEVER mock database sessions — use the `db_session` fixture from conftest.py
- RULE-06: NEVER mock SQLAlchemy models — use real model instances with the test database
- RULE-07: Mock ONLY external services (HTTP calls, AI providers, file system I/O)
- RULE-08: Integration fixtures (INTEGRATION_FIXTURES in conftest.py) define the "do not mock" boundary

### Test Structure
- RULE-09: Every source file change MUST have a corresponding test file change
- RULE-10: Test functions MUST have descriptive docstrings explaining what behavior is verified
- RULE-11: Use pytest markers: @pytest.mark.unit, @pytest.mark.integration, @pytest.mark.slow

### Naming
- RULE-12: Test files: `test_{module_name}.py`
- RULE-13: Test functions: `test_{behavior_being_tested}`
- RULE-14: Test classes: `Test{FeatureName}` or `TestEndpoint{Method}{Path}`
<!-- RULES END -->

## Anti-Patterns (Numbered List)

### AP-01: Trivial Assertions
**Bad:**
```python
def test_create_user():
    user = create_user(name="Alice")
    assert user is not None  # Tests nothing meaningful
```
**Good:**
```python
def test_create_user():
    user = create_user(name="Alice")
    assert user.name == "Alice"
    assert user.id > 0
```

### AP-02: Over-Mocking
**Bad:**
```python
def test_save_application(mock_db):
    mock_db.query.return_value = [Mock(id=1)]  # Testing mock behavior, not code
    result = save_application(mock_db, data)
    assert mock_db.add.called
```
**Good:**
```python
def test_save_application(db_session):
    result = save_application(db_session, {"title": "SWE", "company": "Acme"})
    assert result.title == "SWE"
    assert result.company == "Acme"
    assert db_session.query(Application).count() == 1
```

### AP-03: Missing Value Assertions
**Bad:**
```python
def test_score_calculation():
    score = calculate_score(profile, job)
    assert score is not None
    assert isinstance(score, int)
```
**Good:**
```python
def test_score_calculation():
    score = calculate_score(profile_with_matching_skills, matching_job)
    assert 70 <= score <= 100  # High match expected
    assert isinstance(score, int)
```

## Marker Usage

| Marker | When to Use | Example |
|--------|-------------|---------|
| `@pytest.mark.unit` | Pure logic, no external deps | `test_score_calculation` |
| `@pytest.mark.integration` | Database, HTTP, file I/O | `test_create_application_api` |
| `@pytest.mark.slow` | > 5 seconds execution | `test_full_discovery_sweep` |
| `@pytest.mark.smoke` | Critical path sanity | `test_health_endpoint` |

Auto-marking: Tests using fixtures in `INTEGRATION_FIXTURES` (conftest.py) are automatically marked `integration`. Others default to `unit`.

## Mocking Decision Tree

1. Is it a database operation? -> DO NOT MOCK (use db_session fixture)
2. Is it an HTTP call to external service? -> MOCK IT (use responses or httpx mock)
3. Is it an AI provider call? -> MOCK IT (use MockProvider from ai/ package)
4. Is it file system I/O? -> MOCK IT (use tmp_path fixture)
5. Is it internal business logic? -> DO NOT MOCK (call the real function)

## Frontend Testing Rules (Vitest + React Testing Library)

### Test Infrastructure
- **Setup file:** `frontend/src/test-setup.ts` — localStorage/sessionStorage polyfill for Node.js 25 (built-in localStorage has undefined methods that conflict with jsdom 29)
- **Shared wrapper:** `frontend/src/test-utils.tsx` — `renderWithProviders(ui, options?)` bundles QueryClientProvider (retry: false, gcTime: 0) + MemoryRouter. All test files must use this instead of bare `render()`.

### Frontend Mocking Rules
- RULE-F01: Mock at the **API boundary** (`vi.mock("@/api/onboarding")`) — never mock hooks (`@/hooks/useOnboarding`) or router (`react-router-dom`)
- RULE-F02: When mocking a module that exports constants alongside functions, use `importOriginal` to preserve non-function exports (e.g., `DEFAULT_PROFILE_ID`)
- RULE-F03: Use `renderWithProviders` from `@/test-utils` for every component test — bare `render()` will crash components that use React Query hooks
- RULE-F04: Set `retry: false` and `gcTime: 0` on test QueryClients to prevent flaky async retries and stale cache between tests

### Frontend Mocking Decision Tree
1. Is it a React Query hook? -> DO NOT MOCK (mock the API function it calls instead)
2. Is it react-router-dom? -> DO NOT MOCK (use MemoryRouter via renderWithProviders)
3. Is it an API fetch function (`@/api/*`)? -> MOCK IT (use vi.mock with importOriginal)
4. Is it a browser API (localStorage, window.location)? -> Handled by test-setup.ts polyfill

## Enforcement Layers

| Layer | What It Checks | When It Runs |
|-------|----------------|--------------|
| Pre-commit hooks | Trivial assertions (regex) | Before every commit |
| Claude Code Stop hooks | Min 2 assertions per test function (AST) | After every Claude response |
| CI diff-cover gate | 80% coverage on changed lines | On every PR |
