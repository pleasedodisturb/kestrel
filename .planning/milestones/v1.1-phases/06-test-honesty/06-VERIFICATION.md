---
phase: 06-test-honesty
verified: 2026-09-30T12:45:00Z
status: passed
score: 5/5 must-haves verified
covered_files: [".planning/phases/06-test-honesty/06-01-PLAN.md", ".planning/phases/06-test-honesty/06-01-SUMMARY.md", ".planning/phases/06-test-honesty/06-02-PLAN.md", ".planning/phases/06-test-honesty/06-02-SUMMARY.md", ".planning/phases/06-test-honesty/06-PATTERNS.md", ".planning/phases/06-test-honesty/06-RESEARCH.md", ".planning/phases/06-test-honesty/06-REVIEW-DISPOSITION.md", ".planning/phases/06-test-honesty/06-REVIEW-FIX.md", ".planning/phases/06-test-honesty/06-REVIEW.md", ".planning/phases/06-test-honesty/06-VALIDATION.md", ".planning/phases/06-test-honesty/deferred-items.md", ".pre-commit-config.yaml", "pyproject.toml", "tests/test_json_parse_retry.py", "tests/test_no_import_masking_skips.py", "tests/test_toolchain_pins.py"]
covered_digest: "v2:sha256:c0d631e4354badf70488d7ef7f225b8f722108e2ff444f30e225ba0290d68be1"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 5/5
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 6: Test honesty Verification Report (Re-verification)

**Phase Goal:** The test suite tells the truth: no test silently vanishes behind a masked import error, and the formatter used locally cannot disagree with the one CI enforces.
**Verified:** 2026-09-30
**Status:** passed
**Re-verification:** Yes — the prior 06-VERIFICATION.md (status: passed, 5/5, dated 2026-09-30T00:00:00Z) went stale after commit `3738a5e` (extended the import-masking guard to catch the flag-variable and `unittest.SkipTest` bypasses found by code review, WR-01) and commit `274082e` (declared `packaging>=24` as a direct dev dependency, IN-01) landed on top of it. Every proof below was independently re-run against the current tree; none was copied from the prior report, SUMMARY.md, 06-REVIEW.md, or 06-REVIEW-FIX.md.

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth (Roadmap SC) | Status | Evidence |
|---|---------|------------|-----------|
| 1 | `pytest -rs tests/` reports zero module-level skips caused by ImportError-masking `pytest.skip(allow_module_level=True)` | VERIFIED | Full-suite run (`pytest tests/ -q -m "not eval" -rs`) lists exactly 24 SKIPPED lines. Classified: 6 `test_skills_parsing.py` file-presence guards, 4 `test_scoring_rescore.py` file-presence guards, 9 `test_migration.py` file-presence guards (`tracking/applications.csv` missing), 2 `test_arbeitsagentur_live.py` `KESTREL_LIVE_TESTS` gates, 1 `test_demo_seed.py` and 1 `test_billing_safety.py` (both sanctioned pre-existing per-test skips, G-1858, no import/exception handling involved), 1 `tests/fuzz/test_api_fuzz.py` third-party `importorskip` (schemathesis, G-1854). None wrap an `ImportError`. |
| 2 | `tests/test_parse_scoring_response.py` deleted with its dead subject; `pytest --collect-only` shows no collection error and no skip for that path | VERIFIED | `test ! -e tests/test_parse_scoring_response.py && git ls-files tests/test_parse_scoring_response.py` → file absent and untracked, printed `DEAD-SUITE-GONE`. `grep -rn parse_scoring_response --include='*.py' src tools` → zero hits (exit 1). `pytest --collect-only -q tests/ -rs` → `4587 tests collected`, no ERROR line, no mention of the deleted path. |
| 3 | A guard test or CI step fails on demand when an import-masking module-level skip is reintroduced (proven for THREE shapes: original try/except+skip, flag-variable, `raise unittest.SkipTest`) | VERIFIED | Verifier wrote each of the three exact fixture shapes to `tests/_scratch_reintro_check.py` in turn, one at a time, and re-ran `test_no_import_masking_module_level_skips` between each: **shape 1** (original block) → `AssertionError: ... tests/_scratch_reintro_check.py:11 ...`; **shape 2** (flag-variable: `except ImportError: _HAVE_MODULE = False` then `pytestmark = pytest.mark.skipif(not _HAVE_MODULE, ...)`) → `AssertionError: ... tests/_scratch_reintro_check.py:7 ...`; **shape 3** (`raise unittest.SkipTest(...)` inside the handler) → `AssertionError: ... tests/_scratch_reintro_check.py:5 ...`. Scratch file deleted after each; `git status --short --untracked-files=all -- tests/_scratch_reintro_check.py` printed nothing after every one of the three. Full guard file re-ran green (25 passed) after all three cleanups, and overall `git status --short` showed only the pre-existing untracked runtime files (`.gsd/`, `.planning/milestone.lock`, `.planning/state.json`). |
| 4 | `ruff format --check src/ tests/` and the local pre-commit `ruff-format` hook agree on every file; the `_alembic` exclude is preserved | VERIFIED | `.venv/bin/ruff --version` → `ruff 0.16.9`; `pyproject.toml` dev extra pins `"ruff==0.16.9"`; `.pre-commit-config.yaml` `rev: v0.16.9` under `astral-sh/ruff-pre-commit` — identical. `ruff check src/ tests/ && ruff format --check src/ tests/` → `All checks passed!` / `388 files already formatted`. Real `pre-commit run ruff --all-files` and `pre-commit run ruff-format --all-files` (actual hooks, not simulated) both `Passed`; `git status --short -- src tests` empty afterward. `ruff check src/career_os/_alembic/ && ruff format --check src/career_os/_alembic/` (no `--force-exclude` flag on the command line) → `All checks passed!`, relying on `force-exclude = true` under `[tool.ruff]` plus the unchanged `extend-exclude = ["src/career_os/_alembic"]`. |
| 5 | A test or CI step fails when the pre-commit ruff rev and the pyproject ruff pin drift apart (both directions) | VERIFIED | Mutated `.pre-commit-config.yaml` rev to `v0.0.0`, re-ran `test_ruff_pin_matches_precommit_rev` → captured `ruff drift: pyproject.toml dev extra pins ruff=={pin} but ...`; restored via `git checkout --`, full file re-ran green (16 passed), `git status --short` empty. Repeated in the other direction (pyproject pin → `0.0.0`) → same drift message captured; restored, 16 passed, `git status --short` empty. Both proofs printed `DRIFT-PROOF-PRECOMMIT-OK` / `DRIFT-PROOF-PYPROJECT-OK`. |

**Score:** 5/5 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | ----------- | ------ | ------- |
| `tests/test_toolchain_pins.py` | Ruff pin drift guard (TEST-04) + `_alembic` exclude regression guard (TEST-03) + parser self-tests | VERIFIED | Exists; `def test_ruff_pin_matches_precommit_rev(` present; exports `get_pyproject_ruff_pin`, `get_precommit_ruff_rev`; 16 tests, all pass, 0 skipped. |
| `pyproject.toml` | Exact ruff pin in dev extra + `force-exclude = true` under `[tool.ruff]` + a declared `packaging` dependency (post-IN-01) | VERIFIED | `"ruff==0.16.9"` exact specifier; `force-exclude = true` present; `extend-exclude` unchanged; `"packaging>=24"` now present in the dev extra (IN-01 fix, commit `274082e`), matching the version actually installed (`26.2` per `pip show packaging`). |
| `.pre-commit-config.yaml` | `astral-sh/ruff-pre-commit` rev equal to the pyproject pin | VERIFIED | `rev: v0.16.9`, matches pyproject pin exactly. |
| `tests/test_no_import_masking_skips.py` | AST sweep guard against import-masking module-level skips (TEST-02), self-tests, guard-the-guard, hardened against flag-variable and `unittest.SkipTest` bypasses (WR-01) | VERIFIED | Exists; `def find_import_masking_skips(` present; exports `find_import_masking_skips`, `SWEPT_FILES`, `FIRST_PARTY`; `_handler_assigned_names`, `_is_skipif_call`, `_condition_references_names`, `_find_masking_skipif_uses`, `_is_unittest_skiptest_raise` all present and wired into `find_import_masking_skips`. 25 tests, all pass, 0 skipped — includes 2 new positive variant ids (`flag_variable_pytestmark`, `flag_variable_skipif_decorator`, `unittest_skiptest_raise` — 3 new positives total) and 3 new negative ids (`skipif_flag_not_from_handler`, `skipif_references_unrelated_flag`, `handler_raises_non_skiptest`). |
| `tests/test_json_parse_retry.py` | Live-parser coverage for the still-meaningful cases of the deleted suite | VERIFIED | `def test_recovers_payload_from_llm_wrapping(` present; file reports 20 passed (10 pre-existing + 10 new). |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `tests/test_toolchain_pins.py` | `pyproject.toml` | tomllib read of `project.optional-dependencies.dev`, parsed with `packaging.requirements.Requirement` | WIRED | `get_pyproject_ruff_pin` reads the real file and returns `0.16.9`, confirmed live. `packaging` is now a declared direct dependency (IN-01 fix), so this link no longer relies on an undeclared transitive import. |
| `tests/test_toolchain_pins.py` | `.pre-commit-config.yaml` | line scan scoped to the `astral-sh/ruff-pre-commit` block | WIRED | `get_precommit_ruff_rev` reads the real file and returns `0.16.9`, confirmed live. |
| `.github/workflows/ci.yml` | `pyproject.toml` | Install step (`pip install -e .[dev]`) installs the exact pin the Lint step then runs | WIRED (by pin equality) | Installed `.venv` ruff is `0.16.9`, equal to the pin; CI Lint step commands (`ruff check`/`ruff format --check`) pass with this ruff. |
| `tests/test_no_import_masking_skips.py` | `tests/**/*.py` and `tools/tests/**/*.py` | module-level `SWEPT_FILES` built with `rglob` over both `SWEEP_ROOTS` | WIRED | `test_sweep_covers_both_roots_and_subpackages` passes; sweep still finds zero real violations, and the three throwaway scratch-file reintroductions above were each caught by the live sweep. |
| `.github/workflows/ci.yml` | `tests/test_no_import_masking_skips.py` | `pytest tests/ -m 'not eval'` collects the guard (no `eval` marker) | WIRED | Verifier's own `pytest tests/ -q -m "not eval"` run collected and passed this file's 25 tests as part of the 4534-passed total. |
| `tests/test_json_parse_retry.py` | `src/career_os/ai/openrouter_provider.py` | direct top-level import of `_try_parse_structured` | WIRED | File imports `ScoreResult` from `career_os.schemas.ai` directly (no try/except); `TestTryParseStructured` tests import and call `_try_parse_structured` directly and pass. |
| `find_import_masking_skips` | `_find_masking_skipif_uses` | handler-assigned flag names collected during the Try-node walk are passed to the skipif-condition scan after the walk completes | WIRED | `masked_flag_names` is built up inside the same `for node in ast.walk(tree)` loop as the handler detection, then `_find_masking_skipif_uses(tree, names, frozenset(masked_flag_names))` is called once afterward and its line numbers are reported — confirmed by `skipif_references_unrelated_flag` (proves name-specific matching, not "any skipif near any handler") and `skipif_flag_not_from_handler` (proves a skipif with no masking handler in the file is never flagged) both passing. |

### Behavioral Spot-Checks / Scratch Proofs (all re-run live by the verifier in this session)

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Reintroduced import-masking skip caught — shape 1 (original try/except+skip) | write scratch file, run guard, delete file | `AssertionError: ... tests/_scratch_reintro_check.py:11 ...`; cleanup `git status` empty | PASS |
| Reintroduced import-masking skip caught — shape 2 (flag-variable + `pytestmark = pytest.mark.skipif(...)`) | write scratch file, run guard, delete file | `AssertionError: ... tests/_scratch_reintro_check.py:7 ...`; cleanup `git status` empty | PASS |
| Reintroduced import-masking skip caught — shape 3 (`raise unittest.SkipTest(...)`) | write scratch file, run guard, delete file | `AssertionError: ... tests/_scratch_reintro_check.py:5 ...`; cleanup `git status` empty | PASS |
| Guard file re-runs green after all three scratch proofs | `pytest tests/test_no_import_masking_skips.py -q` | `25 passed` | PASS |
| Real file-presence guards and third-party importorskip stay unflagged | direct call to `find_import_masking_skips` on `test_batch_apply_browser.py`, `test_batch_apply_overlay.py`, `tools/tests/test_config_loaders.py`, `tests/fuzz/test_api_fuzz.py` | all four return `[]` | PASS |
| No allowlist/exemption mechanism exists (prohibition) | `grep -in "allowlist\|exempt" tests/test_no_import_masking_skips.py` | no match (exit 1) | PASS |
| Unparseable file raises rather than silently passing (prohibition) | `pytest tests/test_no_import_masking_skips.py::test_detector_raises_on_unparseable_file` | `1 passed` | PASS |
| Drift in `.pre-commit-config.yaml` caught | mutate rev to `v0.0.0`, run drift test, restore | `ruff drift: ...` captured; restored, 16 passed, `git status` clean | PASS |
| Drift in `pyproject.toml` caught | mutate pin to `0.0.0`, run drift test, restore | `ruff drift: ...` captured; restored, 16 passed, `git status` clean | PASS |
| Real pre-commit hooks agree with CI | `pre-commit run ruff --all-files` / `pre-commit run ruff-format --all-files` | both `Passed`; `git status --short -- src tests` empty | PASS |
| `_alembic` stays excluded for bare explicit paths | `ruff check src/career_os/_alembic/ && ruff format --check src/career_os/_alembic/` | `All checks passed!` (no `--force-exclude` flag passed) | PASS |
| Full backend suite (run once) | `pytest tests/ -q -m "not eval"` | `4534 passed, 24 skipped, 27 deselected`, 3 failed — all 3 the ticketed, out-of-scope `test_npm_audit_no_high_or_critical[frontend\|worker\|extension]` (G-1856) | PASS (no new failures vs. environment baseline) |
| `tests/eval/geo` and `tools/tests/` (remaining CI steps) | `pytest tests/eval/geo -q` / `pytest tools/tests/ -q` | `7 passed` / `535 passed` | PASS |
| Both guard files together | `pytest tests/test_toolchain_pins.py tests/test_no_import_masking_skips.py tests/test_json_parse_retry.py -v` | `61 passed`, 0 skipped, 0 xfailed | PASS |
| Dead file confirmed gone and subject confirmed dead | `test ! -e tests/test_parse_scoring_response.py`, `grep -rn parse_scoring_response --include='*.py' src tools` | `DEAD-SUITE-GONE`; grep exit 1 (no hits) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| TEST-01 | 06-02 | No test masks an ImportError with a module-level skip; dead file deleted | SATISFIED | `tests/test_parse_scoring_response.py` deleted (dead subject confirmed via grep); collection is clean with only sanctioned skips (24, classified above); ledger of the 19 deleted cases (7 covered, 10 re-pinned, 2 out-of-contract) all pass. |
| TEST-02 | 06-02 | A guard fails when an import-masking module-level skip is reintroduced | SATISFIED | Verifier's own scratch reintroductions caught all three shapes — the original construct, the flag-variable form, and `raise unittest.SkipTest` — each independently reproduced and cleaned up in this session, plus 25 self-tests including the 6 new WR-01 cases. |
| TEST-03 | 06-01 | One ruff version governs pre-commit and CI; `_alembic` exclude preserved | SATISFIED | Pin equality verified live (0.16.9 both files); real pre-commit hook run passes; `_alembic` explicit-path check passes. |
| TEST-04 | 06-01 | A test/CI step fails when the pins drift | SATISFIED | Both drift directions independently reproduced and reverted by the verifier with the real assertion failure text confirmed. |

No orphaned requirements: `.planning/REQUIREMENTS.md`'s Phase 6 section lists exactly TEST-01 through TEST-04, and both plans' frontmatter jointly declare all four (`06-01`: TEST-03, TEST-04; `06-02`: TEST-01, TEST-02).

**Note (tracking metadata, not a code gap, unchanged from the prior verification):** `.planning/REQUIREMENTS.md` and `.planning/ROADMAP.md` still show TEST-01/TEST-02 as unchecked (`[ ]`) and the Phase 6 roadmap line as unchecked, while TEST-03/TEST-04 are checked. The underlying code/test evidence for all four requirements is equally solid; this is a pending doc-sync step expected to be flipped by the ship/complete-phase workflow, not a functional gap.

### Anti-Patterns Found

None. Scanned `pyproject.toml`, `.pre-commit-config.yaml`, `tests/test_toolchain_pins.py`, `tests/test_no_import_masking_skips.py`, `tests/test_json_parse_retry.py` for TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER markers — no matches (grep exit 1). No `xfail` or new `skip` marker was added by either the original phase commits or the review-fix commits.

### Requirements/Threat Model Prohibitions

| Prohibition | Verification | Result |
|---|---|---|
| MUST NOT get ruff green by suppressing findings (no new noqa/per-file-ignores/excludes) | judgment | `extend-exclude` unchanged; the only new `[tool.ruff]` line is `force-exclude = true`; no new `noqa` introduced. |
| MUST NOT hardcode ruff version in the drift test / MUST NOT skip or default on parse failure | test | `test_ruff_pin_matches_precommit_rev`'s body reads both real files, no hardcoded version literal; self-tests `test_precommit_rev_rejects_missing_ruff_block`, `test_precommit_rev_rejects_duplicate_ruff_blocks`, `test_precommit_rev_rejects_frozen_sha_rev`, `test_pyproject_pin_rejects_non_exact_specifiers` all pass. |
| MUST NOT replace the removed masking skip with another masking mechanism (xfail, skipif-on-import-flag, first-party importorskip, broad except, conftest skip) | judgment | Full-suite skip listing (24 lines) manually reviewed above — none wrap an ImportError. The guard now *actively detects* the skipif-on-import-flag variant (post-WR-01) rather than merely documenting it as a gap, which strengthens this prohibition's enforcement compared to the prior verification. |
| MUST NOT weaken the legitimate file-presence guards in `test_batch_apply_browser.py`, `test_batch_apply_overlay.py`, `tools/tests/test_config_loaders.py` | test | `test_real_file_presence_guards_are_not_flagged` passes; verifier's own direct calls to `find_import_masking_skips` on all three return `[]`. |
| MUST NOT let the guard pass by exemption/emptiness (no allowlist, no silent empty result) | test | `grep -in "allowlist\|exempt" tests/test_no_import_masking_skips.py` — no match; `test_detector_raises_on_unparseable_file` confirms SyntaxError propagates rather than returning `[]`. |

### Human Verification Required

None. All success criteria are automatable and were independently re-executed by the verifier in this session.

### Gaps Summary

No gaps found. All 5 roadmap success criteria, all 5 artifacts, all 7 key links, and all 4 requirement IDs (TEST-01 through TEST-04) remain verified against live re-execution of the scratch proofs after the two review-fix commits (`3738a5e`, `274082e`). The WR-01 fix (commit `3738a5e`) closes the flag-variable and `raise unittest.SkipTest(...)` bypass gaps that 06-REVIEW.md flagged — the guard now detects both, proven live in this session for both shapes plus the original construct. The IN-01 fix (commit `274082e`) makes `packaging` a declared direct dependency instead of relying on pytest's transitive install, closing that supply-chain gap without changing any test behavior (16/16 `test_toolchain_pins.py` tests still pass). No regressions were found against the prior verification's 5/5 passed state. One tracking-metadata inconsistency (REQUIREMENTS.md/ROADMAP.md checkboxes for TEST-01/TEST-02 not yet flipped) persists unchanged from the prior verification — informational only, does not block phase completion.

---

_Verified: 2026-09-30_
_Verifier: Claude (gsd-verifier)_
