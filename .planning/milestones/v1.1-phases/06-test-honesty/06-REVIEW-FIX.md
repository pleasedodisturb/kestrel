---
phase: 06-test-honesty
fixed_at: 2026-09-30T11:05:50Z
review_path: .planning/phases/06-test-honesty/06-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 06: Code Review Fix Report

**Fixed at:** 2026-09-30T11:05:50Z
**Source review:** .planning/phases/06-test-honesty/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2 (WR-01, IN-01)
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01: Import-masking guard silently passes the flag-variable and `unittest.SkipTest` variants of the exact anti-pattern it exists to catch

**Files modified:** `tests/test_no_import_masking_skips.py`
**Commit:** `3738a5e`
**Applied fix:**

Extended `find_import_masking_skips` to detect the two documented-but-unmitigated bypasses:

1. **Flag-variable pattern** — an `except ImportError`/`ModuleNotFoundError`-family handler (already recognised by `_handler_masks_imports`, so all its existing spelling variants — bare/tuple/dotted handler types, broad `except Exception`/bare `except:` around an import — are inherited for free) that assigns a name at module level, later read inside a `pytest.mark.skipif(...)`/`skipif(...)` condition. Covers both the `pytestmark = pytest.mark.skipif(...)` assignment form (restricted to top-level module-body statements) and a `@pytest.mark.skipif(...)` decorator on a test function or class (no depth restriction, since a decorator runs at collection time regardless of nesting).
2. **`raise unittest.SkipTest(...)`** inside an import-masking handler — treated the same as `pytest.skip(..., allow_module_level=True)`.

Implementation:
- `_pytest_names` was widened into an `_ImportNames` `NamedTuple` carrying alias sets for `pytest`, `pytest.skip`, `pytest.importorskip`, `pytest.mark` (new), `unittest` (new), and `unittest.SkipTest` (new) — so aliasing (`import pytest as pt`, `from pytest import mark as m`, `import unittest as ut`, `from unittest import SkipTest as ST`) is handled consistently with the existing spellings.
- `_handler_assigned_names(handler)` collects every name assigned anywhere in a masking handler's body (the flag).
- `_is_skipif_call`, `_condition_references_names`, and `_find_masking_skipif_uses` correlate those flag names with a later `skipif(...)` condition in the `pytestmark`/decorator positions described above.
- `_is_unittest_skiptest_raise` detects the `raise unittest.SkipTest(...)` variant (call or bare form).
- `find_import_masking_skips` now also collects `masked_flag_names` while walking masking handlers and runs `_find_masking_skipif_uses` over the whole tree afterward.

Verification performed (RED-first, all commands actually run):
- Reproduced the pre-fix gap: `git stash` (reverting the fix), then ran both exact WR-01 fixtures through `find_import_masking_skips` in the unmodified module — both returned `[]` (silent pass), confirming the bug existed. `git stash pop` restored the fix.
- `pytest tests/test_no_import_masking_skips.py -v` → **25 passed** (was 15 before this change; added 10 new parametrized cases: 2 exact WR-01 fixtures + 1 decorator-form positive + 3 negative cases — `skipif_flag_not_from_handler`, `skipif_references_unrelated_flag` (a masking handler exists but the skipif reads a *different*, unrelated flag — proves name-specific matching, not "any skipif near any handler"), and `handler_raises_non_skiptest` (a non-`SkipTest` `raise` must not be flagged, since that's the desired loud-failure remedy)).
- Live scratch-file proof: wrote `tests/test_scratch_wr01_proof.py` containing the exact flag-variable fixture, ran `pytest tests/test_no_import_masking_skips.py::test_no_import_masking_module_level_skips -v` → **FAILED**, naming `tests/test_scratch_wr01_proof.py:7` in the assertion message. Removed the scratch file; `git status --short` confirmed clean (only the intended `tests/test_no_import_masking_skips.py` modification staged).
- Re-ran `pytest tests/test_no_import_masking_skips.py -v` after cleanup → **25 passed** again.
- `test_real_file_presence_guards_are_not_flagged` and `test_sweep_covers_both_roots_and_subpackages` (existing self-tests over the real repo tree) still pass — the three legitimate file-presence guards and the third-party `importorskip` in `tests/fuzz/test_api_fuzz.py` remain unflagged.
- `test_detector_raises_on_unparseable_file` still passes — the guard still raises `SyntaxError` loudly on an unparseable file rather than returning `[]`.
- No allowlist or exemption mechanism was added.
- Module docstring updated: the "Not detected" list no longer includes the flag-variable pattern or `raise unittest.SkipTest(...)`; both are now described under "What is flagged." The two genuinely-remaining gaps (a per-test `pytest.skip(...)` without `allow_module_level` inside `except ImportError:`, and third-party `importorskip`, which is sanctioned) are still listed as known, unmitigated gaps.

**Logic-bug caveat (per verification_strategy):** the correlation logic (matching a handler-assigned flag name to a later `skipif` condition by AST `Name` identity) is a semantic judgment call, not pure syntax. Tier 1/2 verification (re-read + `ruff`/pytest) confirm the code is syntactically correct and the added test cases pass, but this finding's fix should be treated as **fixed: requires human verification** of the correlation logic's correctness on code shapes not covered by the 10 added test cases (e.g., a flag reassigned inside a nested function's local scope, which is out of scope for this AST-only guard by design).

## IN-01: `tests/test_toolchain_pins.py` imports `packaging` without it being a declared dependency anywhere in `pyproject.toml`

**Files modified:** `pyproject.toml`
**Commit:** `274082e`
**Applied fix:** Added `"packaging>=24"` to the `dev` extra, positioned next to the other test tooling (after `pytest-timeout`, before the `ruff` exact pin), with a floor matching the version already installed in `.venv` (`26.2`, confirmed via `pip show packaging`). No other entries in the `dev` list were reordered or edited.

Verification performed:
- `.venv/bin/python -c "import tomllib; ..."` confirmed the `dev` extra parses correctly and contains the new entry in the intended position, with all 13 prior entries unchanged and unreordered.
- `pytest tests/test_toolchain_pins.py -q` → **16 passed** (all pre-existing tests, no new tests added for this info-level finding — the fix is a declaration, not new behavior to test).
- `ruff check pyproject.toml` and `ruff format --check pyproject.toml` → clean.

## Skipped Issues

None — both findings in scope were fixed.

## Final Verification (run after both fixes, in the main checkout at `/Users/pleasedodisturb/Projects/apps/kestrel`, branch `G-1382/test-honesty`)

```
$ pytest tests/test_no_import_masking_skips.py tests/test_toolchain_pins.py tests/test_json_parse_retry.py -q
61 passed, 4 warnings in 0.75s

$ pytest tests/ -q -m "not eval"
FAILED tests/test_dep_security.py::test_npm_audit_no_high_or_critical[frontend]
FAILED tests/test_dep_security.py::test_npm_audit_no_high_or_critical[worker]
FAILED tests/test_dep_security.py::test_npm_audit_no_high_or_critical[extension]
3 failed, 4534 passed, 24 skipped, 27 deselected, 48 warnings in 119.72s (0:01:59)

$ ruff check src/ tests/
All checks passed!

$ ruff format --check src/ tests/
388 files already formatted
```

The 3 failures are the known out-of-scope `npm audit` failures tracked under G-1856 (frontend/worker/extension `brace-expansion` GHSA advisories); no other failures. Both `ruff check` and `ruff format --check` are clean.

## Working Tree State

`git status --short` after both commits shows only the three pre-existing untracked runtime files that were explicitly out of scope (`.gsd/`, `.planning/milestone.lock`, `.planning/state.json`) plus this report before the orchestrator stages it. No other uncommitted or untracked changes remain.

---

_Fixed: 2026-09-30T11:05:50Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
