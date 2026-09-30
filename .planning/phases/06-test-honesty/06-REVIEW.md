---
phase: 06-test-honesty
reviewed: 2026-09-30T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - pyproject.toml
  - .pre-commit-config.yaml
  - tests/test_toolchain_pins.py
  - tests/test_no_import_masking_skips.py
  - tests/test_json_parse_retry.py
findings:
  critical: 0
  warning: 1
  info: 1
  total: 2
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-09-30
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

This phase (G-1382/G-1383, "test honesty") does three things: pins ruff to an exact `==0.16.9` in `pyproject.toml`'s `dev` extra to match `.pre-commit-config.yaml`'s `rev: v0.16.9` (with a guard test that fails loudly on drift), adds `force-exclude = true` to `[tool.ruff]`, and replaces a 19-test dead parser suite (`tests/test_parse_scoring_response.py`, testing a `parse_scoring_response` function with zero remaining callers) with an AST-based guard against the import-masking anti-pattern that caused it, plus a 10-case re-pin of the still-meaningful behaviors against the live parser (`_try_parse_structured`).

I verified every load-bearing claim directly against the running code rather than trusting the plan/summary docs:

- All 55 tests across the three test files pass (`pytest tests/test_toolchain_pins.py tests/test_no_import_masking_skips.py tests/test_json_parse_retry.py -q` → `55 passed`).
- `ruff==0.16.9` (pyproject) and `rev: v0.16.9` (pre-commit) do match today, and CI's `pip install -e ".[dev]"` step means CI genuinely resolves the pinned version, not a floating floor — the guard is not decorative.
- `force-exclude = true` was checked with `ruff check --show-settings` against a file under `src/career_os/_alembic`: it is excluded even when the path is passed explicitly, and I found no unintended fallout on any other `src/`/`tests/` file from ruff's built-in default excludes.
- The 19-case ledger in `06-02-SUMMARY.md` (7 covered / 10 re-pinned / 2 "out of contract") is accurate. I independently ran the two "out of contract" inputs (single-quoted JSON, `None` content) against the live `_try_parse_structured` and confirmed both fail closed (return `None`, logged, no crash) exactly as claimed — no regression is being hidden behind the "out of contract" label.
- The re-pinned `test_recovers_payload_from_llm_wrapping` / `test_blank_content_returns_none_and_logs` cases assert real parser behavior (`isinstance(result, ScoreResult)`, `fit_score`, `len(score_breakdown)`, log message content) against the production function, not tautologies — each parametrized input is asserted `!= clean` first, so every case genuinely exercises a wrapping variant rather than re-testing the happy path.

The one substantive gap is in the new AST guard itself: two of the "not detected" patterns the module's own docstring lists are not just theoretically undetected — I reproduced both and got a silent, zero-violation pass, and one of them (the flag-variable pattern) is arguably the more natural way a future contributor would recreate exactly the bug this phase exists to prevent. See WR-01.

## Warnings

### WR-01: Import-masking guard silently passes the flag-variable and `unittest.SkipTest` variants of the exact anti-pattern it exists to catch

**File:** `tests/test_no_import_masking_skips.py:1-247` (guard logic: `_handler_masks_imports`, `_is_module_level_skip`, `find_import_masking_skips`)
**Issue:** The guard's own docstring (lines 26-35) already admits it does not detect (a) the flag-variable pattern — `except ImportError: FLAG = False` followed by a later `pytest.mark.skipif(not FLAG, ...)` — or (b) a module-level `raise unittest.SkipTest(...)`. I did not take the docstring's word for it; I reproduced both against the real detector:

```python
# flag-variable pattern — same effect as the deleted anti-pattern, zero violations
src = '''
import pytest
_HAVE_MODULE = True
try:
    import not_a_real_module
except ImportError:
    _HAVE_MODULE = False
pytestmark = pytest.mark.skipif(not _HAVE_MODULE, reason="module removed")
def test_something():
    assert not_a_real_module.thing() == 1
'''
# find_import_masking_skips(fixture) -> []

# unittest.SkipTest pattern — also zero violations
src2 = '''
import unittest
try:
    import not_a_real_module
except ImportError:
    raise unittest.SkipTest("module removed")
def test_something():
    assert not_a_real_module.thing() == 1
'''
# find_import_masking_skips(fixture2) -> []
```

Both fixtures reproduce the same collection-silently-never-runs failure mode that `tests/test_parse_scoring_response.py` had (G-1382's whole motivating incident), and both sail through `find_import_masking_skips` with an empty result. The flag-variable form in particular is a very plausible refactor: a contributor "fixing" a ruff/lint complaint about a bare `pytest.skip(allow_module_level=True)` inside an `except` block might reach for exactly this shape without realizing it reintroduces the masking behavior the guard is supposed to block. Since `test_no_import_masking_module_level_skips` is the single mechanism this phase relies on to prevent recurrence, a documented-but-unfixed gap in the exact same failure family is worth a deliberate decision, not just a docstring note.
**Fix:** File a follow-up ticket (or extend `_handler_masks_imports`/`find_import_masking_skips` now) to also flag: (1) an `except ImportError`-family handler whose body assigns to a name that is later read by a `pytest.mark.skipif`/`skipif` condition at module level, and (2) a `raise unittest.SkipTest(...)` inside an import-masking handler, treating it the same as the `pytest.skip(allow_module_level=True)` case. At minimum, downgrade the docstring's phrasing from "recorded rather than silently ignored" to explicitly note these are *known, reproduced, unmitigated* bypasses so a future reader doesn't assume the docstring's disclaimer means someone verified they're low-risk.

## Info

### IN-01: `tests/test_toolchain_pins.py` imports `packaging` without it being a declared dependency anywhere in `pyproject.toml`

**File:** `tests/test_toolchain_pins.py:26,30-31`
**Issue:** `import tomllib` is stdlib (fine, py311+), but `from packaging.requirements import Requirement` and `from packaging.utils import canonicalize_name` pull in the third-party `packaging` distribution. `grep -n packaging pyproject.toml` returns nothing — it is not listed in `dependencies` or in the `dev` extra. It currently resolves only because `pytest>=8.3.0` transitively requires it (confirmed via `pip show pytest` → `Requires: iniconfig, packaging, pluggy, pygments`), which is a stable, long-standing pytest dependency, so this is low risk in practice, not a live bug today.
**Fix:** Add `"packaging>=24"` (or similar) directly to the `dev` extra in `pyproject.toml`, since this test file imports it directly and a toolchain-pin integrity guard is exactly the kind of test that should not depend on an *undeclared* transitive import silently continuing to be true.

---

_Reviewed: 2026-09-30_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
