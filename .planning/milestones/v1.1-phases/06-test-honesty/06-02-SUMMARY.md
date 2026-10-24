---
phase: 06-test-honesty
plan: 02
subsystem: testing
tags: [pytest, ast, test-honesty, skip-guard, json-parsing]

requires:
  - phase: 06-01
    provides: "ruff pinned to 0.16.9 in pyproject.toml and .pre-commit-config.yaml, so this plan's new test files are formatted/linted by the exact pin CI uses"
provides:
  - "tests/test_no_import_masking_skips.py: an AST-based sweep over tests/ and tools/tests/ that fails collection loudly on any pytest.skip(allow_module_level=True) masking an ImportError/ModuleNotFoundError (bare, tuple, aliased, or via a broad except around an import), or a first-party pytest.importorskip(...)"
  - "tests/test_parse_scoring_response.py deleted (19 dead tests; dead subject parse_scoring_response had zero live callers)"
  - "10 of the 19 deleted test cases re-pinned in tests/test_json_parse_retry.py against the live parser _try_parse_structured"
affects: []

actuals:
  tokens: 6772
  tasks: 3
  commits: 3
  plan_head_before: 6e39c85185f07628d0270b1109e7e0b84e404ca7
  plan_head_after: 5ec4a9fa3d735ae28abdc5cb2e56fc63aaf0cdf0

tech-stack:
  added: []
  patterns:
    - "Sweep + guard-the-guard style test (tests/test_provider_contract.py analog) applied to an AST-based anti-pattern detector instead of a module-import sweep"
    - "ast.Try/ExceptHandler walk keyed on the enclosing handler, not the call alone, to distinguish an anti-pattern from a structurally-identical legitimate guard"

key-files:
  created:
    - tests/test_no_import_masking_skips.py
  modified:
    - tests/test_json_parse_retry.py
  deleted:
    - tests/test_parse_scoring_response.py

key-decisions:
  - "DEC-07 executed: deleted tests/test_parse_scoring_response.py rather than relocating it. grep -rn parse_scoring_response --include='*.py' src tools returned nothing (zero definitions, zero callers)."
  - "DEC-08 executed: all 19 deleted cases accounted for in a ledger (7 covered, 10 re-pinned, 2 out of contract), rather than dropped silently."
  - "DEC-09 executed: the sweep covers both tests/ and tools/tests/, recursively, including conftest.py and subpackages (property/, geo/, fuzz/, eval/, regression/)."
  - "DEC-10 executed: detection is AST-based and keyed on the enclosing handler. Widened in Task 2 to cover ModuleNotFoundError, tuple handlers, a pytest alias, a from-imported skip, a broad except (bare/Exception/BaseException) around an import (direct import, importlib.import_module, or __import__), and a first-party pytest.importorskip anywhere in the file."
  - "Rule 1 bug fix (Task 2 widening): find_import_masking_skips originally called path.relative_to(_REPO_ROOT) unconditionally, which raises ValueError for a tmp_path self-test fixture living outside the repo. Fixed with a try/except fallback to the absolute path — needed for the guard-the-guard self-tests introduced in this same task, and does not change behavior for any real-tree file (all of which are under _REPO_ROOT)."

requirements-completed: [TEST-01, TEST-02]

coverage:
  - id: D1
    description: "No test file under tests/ or tools/tests/ masks an ImportError-family exception with a module-level pytest.skip(allow_module_level=True); tests/test_parse_scoring_response.py is deleted with its dead subject"
    requirement: "TEST-01"
    verification:
      - kind: unit
        ref: "tests/test_no_import_masking_skips.py#test_no_import_masking_module_level_skips"
        status: pass
      - kind: integration
        ref: "pytest --collect-only -q tests/ -rs -> COLLECTION-HONEST (only sanctioned skips remain)"
        status: pass
    human_judgment: false
  - id: D2
    description: "An AST-based guard fails when an import-masking module-level skip is reintroduced, catches every named spelling variant, and cannot be bypassed by an allowlist or emptiness"
    requirement: "TEST-02"
    verification:
      - kind: unit
        ref: "tests/test_no_import_masking_skips.py#test_detector_flags_masking_variants (11 parametrized ids)"
        status: pass
      - kind: unit
        ref: "tests/test_no_import_masking_skips.py#test_detector_ignores_legitimate_skips (3 parametrized ids)"
        status: pass
      - kind: unit
        ref: "tests/test_no_import_masking_skips.py#test_detector_raises_on_unparseable_file"
        status: pass
      - kind: unit
        ref: "tests/test_no_import_masking_skips.py#test_sweep_covers_both_roots_and_subpackages"
        status: pass
      - kind: manual_procedural
        ref: "live reintroduction of the removed block into tests/_scratch_reintro_check.py, caught and cleaned up (REINTRO-PROOF-OK)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The 19 deleted test cases from tests/test_parse_scoring_response.py are accounted for: 7 already covered, 10 re-pinned against the live parser, 2 recorded as out of contract"
    requirement: "TEST-01"
    verification:
      - kind: unit
        ref: "tests/test_json_parse_retry.py#test_recovers_payload_from_llm_wrapping (8 parametrized ids) and #test_blank_content_returns_none_and_logs (2 parametrized ids)"
        status: pass
    human_judgment: false

duration: ~50min
completed: 2026-09-30
status: complete
---

# Phase 6 Plan 2: Delete the dead parser suite, guard against import-masking skips, re-pin live behaviour Summary

**An AST-based guard now fails collection loudly on any pytest.skip(allow_module_level=True) that masks an ImportError/ModuleNotFoundError (in all its spelling variants, including broad excepts around an import and first-party pytest.importorskip), the 19-test dead parser suite is deleted, and 10 of its still-meaningful cases are re-pinned against the live `_try_parse_structured` parser.**

## Performance

- **Duration:** ~50 min (approx — start time not separately captured; first commit `12:24 CEST` / `10:24Z`, plan-level verification completed `10:37Z`)
- **Tasks:** 3
- **Files modified:** 3 (1 created, 1 modified, 1 deleted)

## Accomplishments

- `tests/test_no_import_masking_skips.py` created: an AST sweep of every `*.py` under `tests/` and `tools/tests/` (recursively, `SWEPT_FILES` = 219 files at commit time), flagging a `pytest.skip(allow_module_level=True)`/`pytest.importorskip(...)` call that masks a broken import, while leaving the three legitimate file-presence guards and every third-party `importorskip` untouched.
- `tests/test_parse_scoring_response.py` (19 dead tests, dead subject `parse_scoring_response`) deleted in the same commit as the guard that proves the deletion is now enforced.
- `tests/test_json_parse_retry.py` gained 10 new test ids (`test_recovers_payload_from_llm_wrapping` ×8, `test_blank_content_returns_none_and_logs` ×2) re-pinning the still-meaningful behaviour of the deleted suite against the live parser.
- Full plan-level `<verification>` re-run clean: targeted guards (35 passed), full backend suite (4528 passed, 3 pre-existing/out-of-scope failures, 24 skipped, 27 deselected), `tests/eval/geo` (7 passed), `tools/tests/` (535 passed), ruff check + format (`All checks passed!`), collection honesty (`COLLECTION-HONEST`), `git status --short` clean.

## Task Commits

Each task was committed atomically:

1. **Task 1 (tracer): the guard sweeps the real test tree, catches the live import-masking skip, and the dead suite is deleted** — `f59f72e` (test)
2. **Task 2 (tdd): harden the detector against spelling variants, add guard-the-guard, and prove live reintroduction is caught** — `a9f334b` (test)
3. **Task 3: account for the 19 deleted cases by re-pinning the 10 behaviours the live parser still claims** — `5ec4a9f` (test)

All three commits are on the executor branch (`worktree-agent-a53540edbe73d0315`); this plan does not push, open a PR, or run review-push, per the plan's own success criteria.

## Tracer Feedback Gate

`workflow.human_verify_mode` is unset (default `end-of-phase`) and the run is interactive (`workflow._auto_chain_active`/`workflow.auto_advance` both `false`), and Task 1's `<verify>` block carries only `<automated>` entries (no `<human-check>`). Per checkpoints.md row 3, Task 1's full `<verify>` (all 3 automated checks) was re-run end-to-end after the Task 1 commit and all passed — no checkpoint synthesized, expansion into Task 2 proceeded directly (`⚡ Tracer verified end-to-end — expanding`).

## Task 1: RED line and grep proof

RED, against the real tree, before deletion:

```
AssertionError: import-masking module-level skip(s) found: tests/test_parse_scoring_response.py:15. Remedy: import directly, with no try/except-ImportError around it, so a broken import fails collection loudly instead of looking like a deliberate, reasoned skip.
```

Dead-subject proof:

```
$ grep -rn parse_scoring_response --include='*.py' src tools
(no output — zero definitions, zero callers)

$ grep -rln parse_scoring_response --include='*.py' tests
tests/test_no_import_masking_skips.py   (docstring text mention only, not an import)
tests/test_parse_scoring_response.py    (the file about to be deleted)
```

## Task 2 (TDD): RED-first tests and hardening

11 new `test_detector_flags_masking_variants` parametrized cases were written against Task 1's already-committed detector before any detector change. All 11 initially failed:

- 9 cases (`removed_block`, `module_not_found`, `tuple_handler`, `pytest_alias`, `from_import_skip`, `nested_if_in_handler`, `broad_except_around_import`, `bare_except_around_import`, `broad_except_around_importlib`) failed with an uncaught `ValueError` from `path.relative_to(_REPO_ROOT)` — a real bug: the function assumed every scanned path lives under the repo root, which is false for a `tmp_path` self-test fixture.
- 2 cases (`first_party_importorskip_package`, `first_party_importorskip_tools_module`) failed with a genuine empty result — the detector had no `importorskip` support yet.

Both were fixed in the same commit: a `try/except ValueError` fallback to the absolute path in `find_import_masking_skips`, and new `_handler_is_broad`/`_body_contains_import`/`_is_first_party_importorskip` functions. All 19 tests in the file then passed (0 skipped, 0 xfailed, 0 errors).

Live reintroduction proof:

```
$ (write the exact removed try/except-ImportError block into tests/_scratch_reintro_check.py)
$ pytest tests/test_no_import_masking_skips.py::test_no_import_masking_module_level_skips -q
AssertionError: import-masking module-level skip(s) found: tests/_scratch_reintro_check.py:11. Remedy: ...
$ rm tests/_scratch_reintro_check.py
$ pytest tests/test_no_import_masking_skips.py -q
19 passed
$ git status --short --untracked-files=all -- tests/_scratch_reintro_check.py
(empty)
```
**REINTRO-PROOF-OK**

The scratch file was never staged or committed; `git show --stat a9f334b` lists only `tests/test_no_import_masking_skips.py`.

## Task 3: the 19-line ledger

**COVERED already by TestTryParseStructured (7):**
- `test_clean_json` by `test_clean_json_parses_correctly`
- `test_json_code_fence` by `test_json_in_markdown_fence`
- `test_trailing_comma_in_object` by `test_json_with_trailing_comma`
- `test_text_both_sides` by `test_json_embedded_in_text`
- `test_nested_object_extraction` by `test_json_embedded_in_text` (that payload carries nested objects inside `score_breakdown`)
- `test_completely_invalid_text` by `test_completely_invalid_content_returns_none`
- `test_truncated_json` by `test_truncated_json_returns_none`

**NEW here (10):**
- `test_json_with_whitespace` as `whitespace_padded`
- `test_plain_code_fence` as `plain_fence`
- `test_code_fence_with_trailing_whitespace` as `fence_trailing_whitespace`
- `test_trailing_comma_in_nested` as `nested_trailing_comma`
- `test_text_before_json` as `text_before_only`
- `test_text_after_json` as `text_after_only`
- `test_code_fence_with_trailing_comma` as `fence_plus_trailing_comma`
- `test_surrounding_text_with_trailing_comma` as `text_plus_trailing_comma`
- `test_empty_string` as `empty`
- `test_whitespace_only` as `whitespace_only`

**OUT OF CONTRACT (2):**
- `test_single_quotes`: the successor has no single-quote fallback by design, and providers request strict JSON
- `test_none_input`: the successor's signature takes `content: str`

All 10 new inputs were probed against `_try_parse_structured` before writing them into the committed test file, and all passed with **zero production-code changes** — reported as-is, not staged as an artificial fix. `tests/test_json_parse_retry.py` now reports **20 passed** (10 pre-existing + 10 new).

## COLLECTION-HONEST output

```
$ pytest --collect-only -q tests/ -rs
SKIPPED [1] tests/fuzz/test_api_fuzz.py:19: schemathesis not installed — fuzz tests skipped
4553 tests collected in 2.81s
```
**COLLECTION-HONEST** — the only remaining SKIPPED line is the sanctioned third-party `pytest.importorskip("schemathesis", ...)`.

## Files Created/Modified

- `tests/test_no_import_masking_skips.py` (new, 349 lines) — `_REPO_ROOT`, `SWEEP_ROOTS`, `SWEPT_FILES`, `FIRST_PARTY`, `find_import_masking_skips`, `_pytest_names`, `_handler_masks_imports`, `_handler_is_broad`, `_body_contains_import`, `_is_module_level_skip`, `_is_first_party_importorskip`, `_write_fixture`, and 8 test functions (2 parametrized with 11 and 3 ids respectively).
- `tests/test_parse_scoring_response.py` — DELETED (19 dead tests; subject `parse_scoring_response` has zero references outside this file).
- `tests/test_json_parse_retry.py` — modified: new import `ScoreResult` from `career_os.schemas.ai`, plus `logging` import; `TestTryParseStructured` gains `test_recovers_payload_from_llm_wrapping` (8 ids) and `test_blank_content_returns_none_and_logs` (2 ids).

## Decisions Made

See `key-decisions` in the frontmatter (DEC-07 through DEC-10 executed as specified, plus one Rule 1 bug fix during Task 2's TDD cycle).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `find_import_masking_skips` crashed on a path outside `_REPO_ROOT`**
- **Found during:** Task 2, writing the RED-first `tmp_path`-based self-tests
- **Issue:** `path.relative_to(_REPO_ROOT)` raised `ValueError` for any fixture file outside the repo (every `tmp_path` self-test), which would have made 9 of the 11 new parametrized cases error out rather than genuinely test the detector.
- **Fix:** Wrapped the relative-path formatting in `try/except ValueError`, falling back to the absolute path. No behavior change for any real-tree file (all of which are under `_REPO_ROOT`).
- **Files modified:** `tests/test_no_import_masking_skips.py`
- **Verification:** All 19 tests in the file pass; `test_real_file_presence_guards_are_not_flagged` and `test_no_import_masking_module_level_skips` (both exercised against real repo paths) are unaffected.
- **Commit:** `a9f334b` (part of Task 2's commit)

**2. [Ruff formatting, not a deviation rule] `ruff format` reformatted both new/modified test files**
- **Found during:** Task 1 and Task 3 lint verification
- **Issue:** Initial hand-written code had 2 `SIM` lint findings (Task 1: nested-if, redundant-negation) and formatting that didn't match ruff 0.16.9's line-wrapping.
- **Fix:** Fixed the 2 `SIM` findings inline, then ran `ruff format` on both files.
- **Files modified:** `tests/test_no_import_masking_skips.py`, `tests/test_json_parse_retry.py`
- **Verification:** `ruff check` and `ruff format --check` both pass clean.
- **Commit:** included in the respective task commits (formatting/lint fixes happened before each commit, not as separate commits)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug), plus routine pre-commit lint/format fixes.
**Impact on plan:** The Rule 1 fix was necessary for the TDD self-tests to actually exercise the detector rather than error out; no scope creep, no production code touched.

## Out-of-scope discovery (logged for the orchestrator, not fixed here)

**tests/fuzz/test_api_fuzz.py skips at collection everywhere**, because `schemathesis` is neither a declared dependency nor installed by any workflow under `.github/`. Its own docstring says the fuzz tests are "intended for nightly CI", but no workflow installs `schemathesis`, so the fuzz suite never actually runs anywhere. This is a **sanctioned** third-party `pytest.importorskip` (not TEST-01's defect — the guard correctly leaves it unflagged), but it is the same underlying "test suite implies coverage that does not exist" honesty gap this phase targets. Recommend a follow-up Linear ticket to either install `schemathesis`/`hypothesis` in a nightly CI job or remove the now-permanently-skipped fuzz suite. This finding was already recorded in RESEARCH.md's "Out-of-scope finding for the orchestrator" section and is repeated here per the plan's `<output>` requirement.

## Issues Encountered

None beyond the two items documented above (a real Rule 1 bug found and fixed during TDD, and routine lint/format fixes).

## User Setup Required

None — no external service configuration required. `config/personal.yaml` and `data/` were created locally (gitignored) to match CI's setup, per the plan's `<verification>` preamble.

## Next Phase Readiness

- All three commits (`f59f72e`, `a9f334b`, `5ec4a9f`) are on `worktree-agent-a53540edbe73d0315`, ready for the orchestrator to merge.
- `git status --short -- src tests tools pyproject.toml .pre-commit-config.yaml` is empty.
- Phase 6 (both plans) is now complete: TEST-01 through TEST-04 all satisfied.
- One out-of-scope finding logged above (fuzz suite never runs in any CI workflow) — recommend a follow-up ticket, not part of this phase.

## Self-Check: PASSED

- `tests/test_no_import_masking_skips.py` exists: FOUND.
- `tests/test_parse_scoring_response.py` absent from disk and from `git ls-files`: FOUND (confirmed).
- Commit `f59f72e` exists: FOUND.
- Commit `a9f334b` exists: FOUND.
- Commit `5ec4a9f` exists: FOUND.
- `git show --stat f59f72e` lists `tests/test_no_import_masking_skips.py` (added) and `tests/test_parse_scoring_response.py` (deleted): confirmed.
- `git show --stat a9f334b` lists only `tests/test_no_import_masking_skips.py`: confirmed.
- `git show --stat 5ec4a9f` lists only `tests/test_json_parse_retry.py`: confirmed.
- Plan-level `<verification>` re-run: targeted guards 35 passed; full suite 4528 passed / 3 pre-existing failures (documented) / 24 skipped / 27 deselected; `tests/eval/geo` 7 passed; `tools/tests/` 535 passed; ruff check + format clean; COLLECTION-HONEST; `git status --short` clean.

---
*Phase: 06-test-honesty*
*Plan: 02*
*Completed: 2026-09-30*
