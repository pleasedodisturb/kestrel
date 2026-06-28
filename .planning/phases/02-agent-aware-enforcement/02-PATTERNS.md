# Phase 2: Agent-Aware Enforcement - Pattern Map

**Mapped:** 2026-04-20
**Files analyzed:** 6 (new/modified files)
**Analogs found:** 5 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `TESTING.md` | config/docs | N/A (documentation) | `CLAUDE.md` | role-match |
| `CLAUDE.md` (testing rules section) | config | N/A (documentation) | `CLAUDE.md` existing structure | exact |
| `.pre-commit-config.yaml` (new hooks) | config | event-driven | `.pre-commit-config.yaml` existing hooks | exact |
| `.claude/settings.json` | config | event-driven | `.claude/settings.local.json` | role-match |
| `.claude/hooks/check-test-assertions.py` | utility | file-I/O + transform | `tests/conftest.py` (AST/fixture logic) | partial |
| `.github/workflows/ci.yml` (diff-cover step) | config | batch | `.github/workflows/ci.yml` existing steps | exact |
| `tests/*` (~30 files, anti-pattern fixes) | test | CRUD/request-response | `tests/test_embeddings.py` (mixed patterns) | exact |

## Pattern Assignments

### `.pre-commit-config.yaml` (config, event-driven)

**Analog:** `.pre-commit-config.yaml` (self — extending existing file)

**Existing local repo hook pattern** (lines 15-22):
```yaml
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.0
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
        files: ^(src|tests)/
      - id: ruff-format
        files: ^(src|tests)/
```

**Pattern to follow for new hooks:** Add a `- repo: local` block after the gitleaks entry. Use `files: ^tests/` scoping per D-08. Use `language: system` with `pass_filenames: true` for the script-based hook (handles noqa inline suppression correctly — pygrep cannot filter line content).

**Insertion point:** After line 37 (end of gitleaks block).

---

### `.claude/settings.json` (config, event-driven)

**Analog:** `.claude/settings.local.json`

**Existing structure** (lines 1-10):
```json
{
  "permissions": {
    "allow": [
      "Bash(linearis issues:*)",
      "Read(//Users/<user>/**)",
      "Bash(export LINEAR_API_TOKEN=$\\(<secret-manager fetch> 2>/dev/null || cat ~/.linear_api_token 2>/dev/null\\))",
      "Bash(export LINEAR_API_TOKEN=$\\(<secret-manager fetch> || cat ~/.linear_api_token \\))"
    ]
  }
}
```

**Pattern note:** `settings.local.json` is for personal permissions (gitignored). The new `settings.json` (committable, project-level) will contain hooks configuration. Different top-level keys — `"hooks"` not `"permissions"`. Both are merged by Claude Code at runtime.

**New file structure:**
```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/check-test-assertions.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

---

### `.claude/hooks/check-test-assertions.py` (utility, file-I/O + transform)

**Analog:** `tests/conftest.py` (AST-aware Python that inspects test structure)

**AST walk pattern from conftest.py** (lines 35-49):
```python
def pytest_collection_modifyitems(items):
    """Auto-mark tests as unit or integration based on fixture usage."""
    for item in items:
        # Skip items that already have explicit markers
        if any(item.get_closest_marker(m) for m in ("unit", "integration", "smoke")):
            continue
        fixture_names = set(getattr(item, "fixturenames", []))
        if fixture_names & INTEGRATION_FIXTURES:
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)
```

**Pattern to copy:** The new script follows the same approach — walk Python AST, classify test functions, apply rules. Uses `ast.walk()` to find `FunctionDef` nodes starting with `test_`, then counts `ast.Assert` children. Same "iterate + classify + act" pattern.

**Import pattern for hook scripts:**
```python
#!/usr/bin/env python3
import ast
import subprocess
import sys
```

---

### `.github/workflows/ci.yml` (config, batch — diff-cover step)

**Analog:** `.github/workflows/ci.yml` (self — extending existing backend job)

**Existing coverage step** (lines 117-119):
```yaml
      - name: Run tests (main - full with coverage)
        if: github.event_name != 'pull_request'
        run: pytest tests/ -v --tb=short --cov=src/career_os --cov-report=xml --junitxml=test-results/backend-junit.xml
```

**Existing PR test step** (lines 113-115):
```yaml
      - name: Run tests (PR - selective via testmon)
        if: github.event_name == 'pull_request'
        run: pytest tests/ -v --tb=short --testmon --junitxml=test-results/backend-junit.xml
```

**Artifact upload pattern** (lines 121-128):
```yaml
      - name: Upload coverage report
        if: always() && github.event_name != 'pull_request'
        uses: actions/upload-artifact@v7
        with:
          name: backend-coverage
          path: coverage.xml
          retention-days: 1
```

**Pattern for diff-cover insertion:** Add after the coverage step (line 119). Use `if: github.event_name == 'pull_request'` conditional. The PR step currently uses testmon (no coverage.xml). Must either: (a) add `--cov` to PR step, or (b) add a separate coverage run for PRs before diff-cover. Follow existing `run: |` multi-line pattern.

---

### `TESTING.md` (documentation)

**Analog:** `CLAUDE.md` (repo-root documentation with structured sections)

**Structure pattern from CLAUDE.md** (lines 1-10):
```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Kestrel** is an AI-powered, self-hosted job search platform...
```

**Pattern to follow:** Use `#` title, brief intro paragraph, then structured sections with `##` headings. Machine-readable rules section uses code-block fencing or structured markers (per D-06 dual-audience format). Educational sections use examples with before/after code blocks.

---

### `CLAUDE.md` testing rules section (modification)

**Analog:** `CLAUDE.md` existing "Workflow Rules" section structure

**Existing rules section pattern** (from CLAUDE.md lines ~130-150, "Workflow Rules" area):
```markdown
### Commits
- **Every commit uses conventional commit format** — `type(scope): description`...
- **Commit messages must have a body** — title + blank line + explanation...

### Testing
- Every piece of code must have tests. Write tests alongside the code, not after.
- Backend: pytest in `tests/`, Frontend: Vitest in `frontend/src/__tests__/`, Mobile: Jest co-located as `*.test.tsx`
- Run tests after writing them to confirm they pass.
```

**Pattern to follow:** Bold imperative statements with dash-separated explanation. Add a new `### Testing Rules (Agent-Enforceable)` subsection with the same format. Use `NEVER` / `ALWAYS` absolute language per D-10.

---

### `tests/*` anti-pattern fixes (~30 files)

**Analog:** `tests/test_embeddings.py` — demonstrates both the anti-pattern AND the correct pattern side by side.

**Anti-pattern (line 229):**
```python
    def test_build_profile_text(self, db: Session, profile: Profile):
        """Profile text includes job family, skills, goals, and location."""
        text = build_profile_text(db, profile.id)
        assert text is not None          # <-- bare is-not-None (WEAK)
        assert "TPM" in text             # <-- value assertion (GOOD)
        assert "Python (expert)" in text # <-- value assertion (GOOD)
```

**Correct pattern (lines 240-249):**
```python
    def test_build_job_text(self):
        """Job text includes title, company, and description."""
        text = build_job_text("Full stack developer needed", title="SWE", company="Acme")
        assert "Title: SWE" in text
        assert "Company: Acme" in text
        assert "Full stack developer" in text

    def test_build_job_text_empty(self):
        """Empty inputs produce empty string."""
        assert build_job_text(None) == ""
```

**Fix strategy:** Replace `assert x is not None` with assertions on the actual value. For example:
- `assert app is not None` → `assert app.title == "expected_title"` or `assert isinstance(app, Application)`
- `assert result is not None` → `assert result == expected_value` or check specific attributes
- If the value truly only needs existence check (e.g., testing optional return), add a second assertion on a property: `assert app is not None` becomes `assert app.status == "applied"`

---

## Shared Patterns

### Pre-commit Hook Scoping
**Source:** `.pre-commit-config.yaml` lines 20-22
**Apply to:** All new pre-commit hooks (trivial assertion checker)
```yaml
        files: ^tests/
```
All test-quality hooks scope to `^tests/` only. Non-test files are never scanned.

### CI Step Conditionals
**Source:** `.github/workflows/ci.yml` lines 107-119
**Apply to:** diff-cover step
```yaml
      - name: Run tests (PR - selective via testmon)
        if: github.event_name == 'pull_request'
        run: ...

      - name: Run tests (main - full with coverage)
        if: github.event_name != 'pull_request'
        run: ...
```
Use `if:` conditionals to differentiate PR vs main-branch behavior. diff-cover only runs on PRs (`if: github.event_name == 'pull_request'`).

### Test Assertion Quality Standard
**Source:** `tests/test_embeddings.py` lines 240-255 (correct pattern)
**Apply to:** All 30 test files with anti-pattern violations
```python
    def test_build_job_text(self):
        """Job text includes title, company, and description."""
        text = build_job_text("Full stack developer needed", title="SWE", company="Acme")
        assert "Title: SWE" in text
        assert "Company: Acme" in text
        assert "Full stack developer" in text
```
Every test function asserts on **specific values**, not just existence. Minimum 2 assertions per test function (D-09).

### noqa Escape Hatch Pattern
**Source:** Ruff convention already used in project (e.g., `tests/conftest.py` line 14)
**Apply to:** Pre-commit hook script, TESTING.md documentation
```python
from tests.profile_data import DEFAULT_PROFILE_KWARGS, SECOND_PROFILE_KWARGS  # noqa: F401
```
The `# noqa: KTEST001` pattern follows the same inline comment convention that ruff already uses. Greppable with `grep -rn "noqa: KTEST001"`.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `TESTING.md` | documentation | N/A | No standalone test standards doc exists yet; closest analog is CLAUDE.md structure but content is unique. Use RESEARCH.md Pattern 6 (dual-audience format) for internal structure. |

## Metadata

**Analog search scope:** Repository root, `.pre-commit-config.yaml`, `.github/workflows/`, `.claude/`, `tests/`
**Files scanned:** 8 (targeted reads of known analogs)
**Pattern extraction date:** 2026-04-20
