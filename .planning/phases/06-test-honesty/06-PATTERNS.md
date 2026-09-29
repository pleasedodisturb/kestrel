# Phase 6: Test honesty - Pattern Map

**Mapped:** 2026-09-29
**Files analyzed:** 5 (2 new, 1 delete, 2 modify)
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|---------------|
| `tests/test_no_import_masking_skips.py` | test (guard/sweep) | batch (AST scan over repo files) | `tests/test_provider_contract.py` | exact (sweep + guard-the-guard shape) |
| `tests/test_toolchain_pins.py` | test (guard/drift-check) | transform (parse two config files, compare) | `tools/tests/test_config_loaders.py` | role-match (config-file parsing test with `tmp_path` fixtures + yaml) |
| `tests/test_parse_scoring_response.py` | test | request-response (dead) | — | DELETE, no replacement analog needed |
| `pyproject.toml` (`dev` extra + `[tool.ruff]`) | config | — | itself (existing block) | exact — edit in place |
| `.pre-commit-config.yaml` (ruff hooks) | config | — | itself (existing block, mirror `end-of-file-fixer`'s per-hook `exclude:`) | exact — edit in place |

## Pattern Assignments

### `tests/test_no_import_masking_skips.py` (test, batch/AST sweep)

**Analog:** `tests/test_provider_contract.py`

**Imports pattern** (`tests/test_provider_contract.py:16-25`):
```python
import importlib
import json
import pkgutil

import httpx
import pytest

import career_os.ai as ai_pkg
from career_os.ai import factory
from career_os.ai.base import ROLE_FIT_GATE_PROMPT
```
For the new file, the equivalent stdlib-only import block is `ast`, `pathlib.Path` (per RESEARCH.md Pattern 2) plus `pytest`. No project imports needed — this test operates on `tests/*.py` and `tools/tests/*.py` as text/AST, not as importable modules.

**Sweep pattern** (`tests/test_provider_contract.py:30-32`):
```python
PROVIDER_MODULES = sorted(
    m.name for m in pkgutil.iter_modules(ai_pkg.__path__) if m.name.endswith("_provider")
)
```
Copy the *shape*: a module-level discovery expression (here: `sorted(Path(__file__).parent.rglob("test_*.py"))` plus the same glob rooted at `tools/tests/`, per RESEARCH.md Open Question recommendation — sweep both directories), computed once at import time so it can be asserted on directly.

**Guard-the-guard pattern** (`tests/test_provider_contract.py:35-45`):
```python
def test_provider_modules_discovered():
    """Guard the guard: the sweep must cover every real provider, not a magic number."""
    assert "openai_provider" in PROVIDER_MODULES
    expected_modules = {module for module, _cls, _kwargs in REAL_PROVIDERS.values()}
    missing = expected_modules - set(PROVIDER_MODULES)
    assert not missing, f"provider modules not found by the sweep: {sorted(missing)}"
```
Mirror this exactly for the new file: assert the sweep actually finds a known-present file (e.g. `"test_provider_contract.py" in {p.name for p in SWEPT_FILES}`), so deleting/renaming files under `tests/` can't silently shrink the sweep to zero and make the guard vacuously pass.

**Parametrized per-target check** (`tests/test_provider_contract.py:48-51`):
```python
@pytest.mark.parametrize("module_name", PROVIDER_MODULES)
def test_provider_module_imports(module_name: str):
    """Every provider module must import (G-1348: openai_provider did not)."""
    importlib.import_module(f"career_os.ai.{module_name}")
```
Equivalent for the new file: either one `@pytest.mark.parametrize("path", SWEPT_FILES)` test asserting `find_import_masking_skips(path) == []`, or a single aggregate test collecting all violations across all swept files and asserting the combined list is empty with a clear per-file message — either is consistent with the analog's per-target-assert style.

**Self-test with `tmp_path`** — no exact self-test precedent in `test_provider_contract.py` (it self-tests by pinning constants — `test_gate_marker_is_actually_in_the_prompt`, `test_real_providers_covers_every_registered_provider` — not by writing fixture files). For the `tmp_path`-based positive fixture, use `tools/tests/test_config_loaders.py`'s `_write_yaml` helper pattern instead:

**`tmp_path` fixture-writing pattern** (`tools/tests/test_config_loaders.py:54-57`):
```python
def _write_yaml(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
```
Apply the same shape but write a `.py` fixture instead of `.yaml`: a private helper `_write_fixture(tmp_path, content) -> Path` that does `path = tmp_path / "bad.py"; path.write_text(content); return path`, then per RESEARCH.md's scratch-check design:
```python
def test_detector_flags_import_masking_skip(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text(
        "try:\n"
        "    import not_a_real_module\n"
        "except ImportError:\n"
        "    import pytest\n"
        "    pytest.skip(\"x\", allow_module_level=True)\n"
    )
    assert find_import_masking_skips(bad) != []
```
And a negative counterpart proving the file-presence-guard shape is NOT flagged (mirrors the real `tests/test_batch_apply_browser.py`/`tests/test_batch_apply_overlay.py` shape) — write a `tmp_path` fixture with `if not path.exists(): pytest.skip(..., allow_module_level=True)` and assert the detector returns `[]` for it. This directly encodes Pitfall 1 from RESEARCH.md as a permanent regression test.

**Core AST-detection logic** — already fully specified in RESEARCH.md § Pattern 2 (lines 164-197 of `06-RESEARCH.md`), copy verbatim as the starting implementation (flagged `[ASSUMED]` there — validate against the two real file-presence-guard files and the one real anti-pattern file before trusting it, per RESEARCH.md Assumption A2).

---

### `tests/test_toolchain_pins.py` (test, transform/drift-check)

**Analog:** `tools/tests/test_config_loaders.py`

**Imports pattern** (`tools/tests/test_config_loaders.py:22-34`):
```python
from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
```
For the new file (which lives at `tests/`, one level up from `tools/tests/`), use `_REPO_ROOT = Path(__file__).resolve().parent.parent` and add `import tomllib` (stdlib) alongside `yaml` — matches RESEARCH.md's Standard Stack recommendation (`tomllib` for `pyproject.toml`, `yaml` or regex for `.pre-commit-config.yaml`).

**Config-file-reading test pattern with `tmp_path`+`monkeypatch`** (`tools/tests/test_config_loaders.py:257-266`):
```python
class TestLoadCompanyLists:
    def test_absent_uses_floor_silently(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(sns, "_COMPANIES_CONFIG", tmp_path / "companies.yaml")
        with caplog.at_level(logging.WARNING, logger="scrape_new_sources"):
            lists = sns._load_company_lists()
        assert lists["greenhouse"] == sns._FLOOR_GREENHOUSE_COMPANIES
```
For the drift-guard test, the equivalent shape (per RESEARCH.md's scratch-check design) is writing two `tmp_path` fixture files directly rather than monkeypatching a module attribute, since the pure functions take a path:
```python
def test_comparator_flags_mismatched_pins(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project.optional-dependencies]\ndev = ["ruff==1.0.0"]\n')
    precommit = tmp_path / ".pre-commit-config.yaml"
    precommit.write_text(
        "repos:\n"
        "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
        "    rev: v2.0.0\n"
    )
    pin = get_pyproject_ruff_pin(pyproject)
    rev = get_precommit_ruff_rev(precommit)
    assert pin != rev
```

**Malformed-input assertion pattern** (`tools/tests/test_config_loaders.py:84-89`):
```python
def test_malformed_raises_yaml_error(self, tmp_path, monkeypatch):
    # The raw reader does not swallow — callers are responsible for fallback.
    monkeypatch.setattr(bab, "PROJECT_ROOT", tmp_path)
    _write_yaml(tmp_path / "config" / "personal.yaml", "answers: [unterminated\n")
    with pytest.raises(yaml.YAMLError):
        bab._read_personal_yaml()
```
Same idiom applies if the drift-guard's parsers should raise rather than return a sentinel on genuinely malformed input (distinct from "mismatched but well-formed" fixtures above) — `pytest.raises(...)` around the parser call.

**Real-file (non-fixture) assertion** — the primary guard test (not just the self-test) should run against the real `pyproject.toml` and `.pre-commit-config.yaml` at repo root, using `_REPO_ROOT` from the import block above, e.g.:
```python
def test_ruff_pin_matches_precommit_rev():
    pin = get_pyproject_ruff_pin(_REPO_ROOT / "pyproject.toml")
    rev = get_precommit_ruff_rev(_REPO_ROOT / ".pre-commit-config.yaml")
    assert pin == rev, f"pyproject.toml ruff=={pin} but .pre-commit-config.yaml rev={rev}"
```
This is the test that actually enforces TEST-04 in CI; the `tmp_path` fixture tests above are the "guard the guard" self-tests proving the comparator itself works.

---

### `tests/test_parse_scoring_response.py` (DELETE)

**Current header being removed** (`tests/test_parse_scoring_response.py:1-18`):
```python
"""Tests for the robust parse_scoring_response() JSON parser."""

import json
import sys
from pathlib import Path

import pytest

# Ensure tools/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

try:
    from job_scorer import parse_scoring_response
except ImportError:
    pytest.skip(
        "parse_scoring_response removed from tools/job_scorer.py",
        allow_module_level=True,
    )
```
This is the exact anti-pattern block TEST-01/02 target: `try: from job_scorer import parse_scoring_response` / `except ImportError: pytest.skip(..., allow_module_level=True)`. Per RESEARCH.md Finding 2, `parse_scoring_response` has zero live callers (superseded by `_try_parse_structured` in `src/career_os/ai/openrouter_provider.py:353-420`, already covered by `tests/test_json_parse_retry.py`, `tests/test_ai_provider.py`, `tests/test_dimensional_scaling.py`, `tests/test_role_intelligence.py`). **Action: delete the whole file** (not just this block) — no relocation target exists with a matching contract. Baseline collection count before deletion: `4536 tests collected, 0 errors` (verified in RESEARCH.md); expect `4536 - 19 = 4517` after deletion, still `0 errors`.

---

### `pyproject.toml` (config, dev extra + `[tool.ruff]`)

**Current `dev` extra ruff line** (`pyproject.toml:51`):
```toml
    "ruff>=0.11.0",
```
Change to an exact pin: `"ruff==<X.Y.Z>"` where `<X.Y.Z>` is re-verified at execution time per RESEARCH.md Pitfall 2 (do not hardcode `0.16.9` from this document without re-checking `gh run list --workflow=ci.yml --branch=main --limit=1` first).

**Current `[tool.ruff]` block** (`pyproject.toml:94-101`):
```toml
[tool.ruff]
target-version = "py311"
# Alembic scaffolding is generated + historical: linting/reformatting it churns
# files that already ran against production databases, and pre-commit's pinned
# ruff disagrees with CI's floating one on their formatting (G-1350).
extend-exclude = ["src/career_os/_alembic"]
line-length = 100
src = ["src", "tests"]
```
`force-exclude` is absent — confirmed by RESEARCH.md Finding 5 / Pitfall 3. Add `force-exclude = true` here so `extend-exclude` also applies when pre-commit passes `_alembic` paths as explicit CLI arguments (the failure mode pre-commit's `files: ^(src|tests)/` regex triggers, since it matches `src/career_os/_alembic/...` literally). This is a one-line addition inside the existing block, not a new block.

---

### `.pre-commit-config.yaml` (config, ruff hooks)

**Current ruff hook block** (`.pre-commit-config.yaml:22-28`):
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
Change `rev: v0.11.0` to `rev: v<same X.Y.Z as pyproject.toml>` (must match exactly — this equality is what `tests/test_toolchain_pins.py` asserts).

**Existing per-hook `exclude:` pattern to mirror, if the `.pre-commit-config.yaml`-side fix is chosen instead of (or in addition to) `force-exclude`** (`.pre-commit-config.yaml:9-16`):
```yaml
      - id: end-of-file-fixer
        exclude: ^src/career_os/_alembic/
      - id: trailing-whitespace
        exclude: ^src/career_os/_alembic/
      ...
      - id: mixed-line-ending
        args: ["--fix=lf"]
        exclude: ^src/career_os/_alembic/
```
Per RESEARCH.md, `force-exclude = true` in `pyproject.toml` is the single-fix recommendation covering both invocation shapes; this per-hook `exclude:` mirror is the file-header comment's stated rationale for *why* per-hook excludes exist at all in this file (`.pre-commit-config.yaml:1-6`: "a global `exclude:` would also switch off detect-private-key... for that path") — use it only as a fallback/belt-and-suspenders if `force-exclude` alone is judged insufficient at implementation time.

## Shared Patterns

### Sweep + guard-the-guard
**Source:** `tests/test_provider_contract.py:30-45`
**Apply to:** `tests/test_no_import_masking_skips.py` (both the file-discovery sweep and its own "did the sweep actually find files" guard)

### `tmp_path`-fixture-file config/code test
**Source:** `tools/tests/test_config_loaders.py:54-57, 68-90`
**Apply to:** Both new test files' self-tests — `test_no_import_masking_skips.py`'s positive/negative fixture files, `test_toolchain_pins.py`'s mismatched-pin fixture pair

### Stdlib-only parsing (no new dependency)
**Source:** RESEARCH.md § Don't Hand-Roll — `ast` for Python source, `tomllib` for TOML (both stdlib, Python 3.11+)
**Apply to:** Both new test files. `yaml` for `.pre-commit-config.yaml` is already an undeclared transitive dependency exercised directly by `tools/tests/test_config_loaders.py:30` (`import yaml` with no explicit `pyproject.toml` declaration) — same precedent applies if `test_toolchain_pins.py` chooses YAML parsing over a `rev:`-line regex; RESEARCH.md recommends declaring `pyyaml` explicitly in the `dev` extra if this route is taken.

## No Analog Found

None — all 5 files have a usable analog (2 direct test-pattern analogs, 3 in-place config edits with existing structure to mirror).

## Metadata

**Analog search scope:** `tests/`, `tools/tests/`, `pyproject.toml`, `.pre-commit-config.yaml`
**Files scanned:** `tests/test_provider_contract.py`, `tests/test_parse_scoring_response.py`, `tools/tests/test_config_loaders.py`, `pyproject.toml` (dev extra + `[tool.ruff]` block), `.pre-commit-config.yaml` (all hook blocks)
**Pattern extraction date:** 2026-09-29
</content>
