# Phase 1: CI Optimization - Pattern Map

**Mapped:** 2026-04-19
**Files analyzed:** 5 modified files
**Analogs found:** 5 / 5 (all files are modifications of existing files)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `.github/workflows/ci.yml` | config | event-driven | Self (existing CI workflow) | exact |
| `tests/conftest.py` | config (test infra) | event-driven (pytest hooks) | Self (existing conftest) | exact |
| `pyproject.toml` | config | N/A | Self (existing pytest config) | exact |
| `frontend/vitest.config.ts` | config | N/A | Self (existing vitest config) | exact |
| `.gitignore` | config | N/A | Self (existing gitignore) | exact |

## Pattern Assignments

### `.github/workflows/ci.yml` (config, event-driven)

**Analog:** Self -- this is a modification of the existing workflow. All new jobs/steps follow patterns already established in this file.

**Permissions pattern** (line 10-11):
```yaml
permissions:
  contents: read
```
New `test-results` job needs additional permissions. Follow the `sonarcloud` job pattern (lines 198-200) for per-job permissions:
```yaml
  sonarcloud:
    name: SonarCloud Analysis
    runs-on: ubuntu-latest
    if: github.event_name != 'merge_group'
    needs: [backend, frontend]
    permissions:
      contents: read
      pull-requests: write
```

**Concurrency pattern** (lines 13-15):
```yaml
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
```
Keep as-is per D-11.

**Artifact upload pattern** (lines 67-73):
```yaml
      - name: Upload coverage report
        if: always()
        uses: actions/upload-artifact@v7
        with:
          name: backend-coverage
          path: coverage.xml
          retention-days: 1
```
JUnit XML upload follows this exact pattern -- same action, same `if: always()`, same retention.

**SonarCloud comment upsert pattern** (lines 241, 301-320):
```javascript
const MARKER = '<!-- sonarcloud-issues -->';
// ...
const existing = comments.find(c => c.body && c.body.includes(MARKER));
if (existing) {
  await github.rest.issues.updateComment({
    owner: context.repo.owner, repo: context.repo.repo,
    comment_id: existing.id, body,
  });
} else {
  await github.rest.issues.createComment({
    owner: context.repo.owner, repo: context.repo.repo,
    issue_number: PR, body,
  });
}
```
The `EnricoMi/publish-unit-test-result-action` handles upsert internally, so no custom script needed for test results. But this pattern documents the established upsert approach if customization is ever needed.

**Checkout action version pattern** (line 22):
```yaml
      - uses: actions/checkout@v6
```
All new jobs should use `actions/checkout@v6` (same version used throughout).

**Conditional job execution pattern** -- Use the `sonarcloud` job's `if:` clause (line 196) as the template for conditionally running jobs:
```yaml
  sonarcloud:
    if: github.event_name != 'merge_group'
```
New `changes`, `ci-complete`, and `test-results` jobs will use similar `if:` conditions.

**Frontend working-directory pattern** (lines 147-149):
```yaml
    defaults:
      run:
        working-directory: frontend
```
Keep this pattern when modifying the frontend job.

---

### `tests/conftest.py` (config/test-infra, event-driven)

**Analog:** Self -- adding pytest hooks to the existing conftest.

**Existing imports pattern** (lines 1-12):
```python
"""Shared test fixtures."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.main import app
```
New hooks only need `pytest` (already imported). No new imports required.

**Integration fixture definitions** (lines 23-98) -- These are the exact fixtures that define the integration boundary per D-01:
- `client` (line 23) -- `TestClient(app)`
- `db_engine` (line 34) -- in-memory SQLite engine
- `db_session` (line 50) -- depends on `db_engine`
- `authenticated_client` (line 95) -- depends on `db_session`

The `pytest_collection_modifyitems` hook should inspect for these four fixture names. Note that `profile` (line 71) and `application` (line 80) depend on `db_session`, so they will transitively include `db_session` in `item.fixturenames`.

**Fixture that is NOT integration** -- `sample_jobs` (line 101) and `tmp_tracking_dir` (line 180) use no DB fixtures. Tests using only these should be marked `unit`.

**Hook insertion point:** After the imports block (after line 12) and before the first `@pytest.fixture` decorator (line 23). The hooks are module-level functions, not fixtures.

---

### `pyproject.toml` (config)

**Analog:** Self -- extending existing pytest config section.

**Existing pytest config** (lines 94-97 of pyproject.toml):
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
timeout = 30
```
Add `markers` list directly below `timeout = 30`.

**Existing dev dependencies** (lines 41-54 of pyproject.toml):
```toml
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.25.0",
    "pytest-cov>=6.1.0",
    "pytest-timeout>=2.3.0",
    "ruff>=0.11.0",
    "httpx>=0.28.0",
    # pandas 3.0 evaluation (G-251): blocked by python-jobspy which pins
    # pandas<3.0.0. Kestrel's own usage is compatible (tested), but the
    # transitive constraint prevents upgrading. Revisit when jobspy relaxes.
    "pandas>=2.2.0,<3",
    "python-jobspy>=1.1.82,<1.2",
    "fpdf2>=2.8.0",
]
```
Add `"pytest-testmon>=2.2.0",` after `pytest-timeout` (keep pytest plugins grouped).

---

### `frontend/vitest.config.ts` (config)

**Analog:** Self -- adding reporter config to existing vitest config.

**Existing test config** (lines 7-17):
```typescript
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    globals: true,
    coverage: {
      provider: "v8",
      reporter: ["lcov", "text"],
      reportsDirectory: "./coverage",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/__tests__/**", "src/test-setup.ts"],
    },
  },
```
Add `reporters` key at the same level as `environment`, `setupFiles`, `globals`, `coverage`:
```typescript
    reporters: ['default', ['junit', {
      outputFile: 'test-results/frontend-junit.xml',
      suiteName: 'Kestrel Frontend',
    }]],
```

---

### `.gitignore` (config)

**Analog:** Self.

**Existing Python section** (lines 4-17):
```
# Python
__pycache__/
*.py[cod]
...
```
Add `.testmondata` in the Python section (it is a pytest-testmon artifact).

---

## Shared Patterns

### Artifact Upload (CI)
**Source:** `.github/workflows/ci.yml` lines 67-73
**Apply to:** Backend JUnit XML upload, frontend JUnit XML upload
```yaml
      - name: Upload coverage report
        if: always()
        uses: actions/upload-artifact@v7
        with:
          name: backend-coverage
          path: coverage.xml
          retention-days: 1
```
Replace `name`/`path` with JUnit XML equivalents. Keep `if: always()` and `retention-days: 1`.

### Per-Job Permissions (CI)
**Source:** `.github/workflows/ci.yml` lines 198-200 (sonarcloud job)
**Apply to:** `test-results` job (needs `checks: write` and `pull-requests: write`)
```yaml
    permissions:
      contents: read
      pull-requests: write
```

### Existing Test File Structure (for new test file)
**Source:** `tests/test_parse_scoring_response.py` lines 1-30
**Apply to:** `tests/test_conftest_markers.py` (Wave 0 gap from RESEARCH.md)
```python
"""Tests for the robust parse_scoring_response() JSON parser."""

import json
import sys
from pathlib import Path

import pytest

# ... test data constants ...

class TestParseValidJSON:
    """Test parsing of well-formed JSON."""

    def test_clean_json(self):
        raw = json.dumps(VALID_PAYLOAD)
        result = parse_scoring_response(raw)
        assert result is not None
```
Pattern: module docstring, imports, constants, test classes grouping related assertions. The marker test file should follow this structure -- class-based grouping with descriptive class names.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | -- | -- | All files are modifications to existing files with established patterns |

## Metadata

**Analog search scope:** `.github/workflows/`, `tests/`, `frontend/`, project root configs
**Files scanned:** 5 (all files being modified)
**Pattern extraction date:** 2026-04-19
