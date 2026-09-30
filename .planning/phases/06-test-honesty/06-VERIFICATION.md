---
phase: 06-test-honesty
verified: 2026-09-30T00:00:00Z
status: passed
score: 5/5 must-haves verified
covered_files: [".planning/phases/06-test-honesty/06-01-PLAN.md", ".planning/phases/06-test-honesty/06-01-SUMMARY.md", ".planning/phases/06-test-honesty/06-02-PLAN.md", ".planning/phases/06-test-honesty/06-02-SUMMARY.md", ".planning/phases/06-test-honesty/06-PATTERNS.md", ".planning/phases/06-test-honesty/06-RESEARCH.md", ".planning/phases/06-test-honesty/06-VALIDATION.md", ".planning/phases/06-test-honesty/deferred-items.md", ".pre-commit-config.yaml", "pyproject.toml", "tests/test_json_parse_retry.py", "tests/test_no_import_masking_skips.py", "tests/test_toolchain_pins.py"]
covered_digest: "v2:sha256:4914f0e700674bc94a2d0336bf52b5d54dc547f97e54ab78dcebcb178cb2d827"
behavior_unverified: 0
overrides_applied: 0
---

# Phase 6: Test honesty Verification Report

**Phase Goal:** The test suite tells the truth: no test silently vanishes behind a masked import error, and the formatter used locally cannot disagree with the one CI enforces.
**Verified:** 2026-09-30
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

All five were independently re-run by the verifier in this session (not taken from SUMMARY.md claims), with scratch proofs executed and reverted by the verifier itself.

| # | Truth (Roadmap SC) | Status | Evidence |
|---|---------|------------|-----------|
| 1 | `pytest -rs tests/` reports zero module-level skips caused by ImportError-masking `pytest.skip(allow_module_level=True)` | ✓ VERIFIED | `pytest --collect-only -q tests/ -rs` → only `SKIPPED [1] tests/fuzz/test_api_fuzz.py:19: schemathesis not installed` (sanctioned third-party `importorskip`). Full-suite `-rs` run lists 24 SKIPPED lines total, all classified below as sanctioned (fuzz importorskip ×1, KESTREL_LIVE_TESTS gating ×2, `tracking/applications.csv` missing ×9, file-presence guards ×10, two unrelated per-test `@pytest.mark.skip`/`pytest.skip` calls with no ImportError handler ×2: `test_demo_seed.py::test_pipeline_shows_demo_banner` and `test_billing_safety.py::test_scheduled_chain_has_no_premium_literal_default`). None wrap a masked `ImportError`. |
| 2 | `tests/test_parse_scoring_response.py` deleted with its dead subject; `pytest --collect-only` shows no collection error and no skip for that path | ✓ VERIFIED | `test ! -e tests/test_parse_scoring_response.py && git ls-files tests/test_parse_scoring_response.py` → file absent and untracked. `grep -rn parse_scoring_response --include='*.py' src tools` → zero hits (exit 1). Collection run above shows no mention of the path and no ERROR line. |
| 3 | A guard test or CI step fails on demand when an import-masking module-level skip is reintroduced (deliberate scratch reintroduction) | ✓ VERIFIED | Verifier wrote the exact removed try/except-ImportError block to `tests/_scratch_reintro_check.py`, ran `test_no_import_masking_module_level_skips`, and got `AssertionError: import-masking module-level skip(s) found: tests/_scratch_reintro_check.py:11. Remedy: ...`. Deleted the scratch file, re-ran the guard: `19 passed`. `git status --short --untracked-files=all -- tests/_scratch_reintro_check.py` empty (`REINTRO-PROOF-OK`). |
| 4 | `ruff format --check src/ tests/` (CI invocation) and the local pre-commit `ruff-format` hook agree on every file; the `_alembic` exclude is preserved | ✓ VERIFIED | `ruff --version` → `ruff 0.16.9`; `pyproject.toml` dev extra pins `ruff==0.16.9`; `.pre-commit-config.yaml` rev is `v0.16.9` — identical. `ruff check src/ tests/ && ruff format --check src/ tests/` → `All checks passed!` / `388 files already formatted`. `pre-commit run ruff --all-files` and `pre-commit run ruff-format --all-files` (real hooks, not a simulation) both `Passed`, `git status --short -- src tests` empty afterward. `[tool.ruff]` has both `extend-exclude = ["src/career_os/_alembic"]` (byte-identical to before) and `force-exclude = true`; `ruff check src/career_os/_alembic/ && ruff format --check src/career_os/_alembic/` → `All checks passed!` (bare explicit-path invocation now honors the exclude). |
| 5 | A test or CI step fails when the pre-commit ruff rev and the pyproject ruff pin drift apart, in both directions (scratch drift) | ✓ VERIFIED | Verifier mutated `.pre-commit-config.yaml`'s rev to `v0.0.0` and re-ran `test_ruff_pin_matches_precommit_rev` verbosely: `AssertionError: ruff drift: pyproject.toml dev extra pins ruff==0.16.9 but .pre-commit-config.yaml astral-sh/ruff-pre-commit rev is v0.0.0; bump both together (G-1383)`. Restored via `git checkout --`, full file re-ran green (16 passed), `git status --short` empty. Repeated in the other direction (pyproject pin → `0.0.0`): `AssertionError: ruff drift: pyproject.toml dev extra pins ruff==0.0.0 but ... rev is v0.16.9; ...`. Restored, re-ran green, `git status --short` empty both times. |

**Score:** 5/5 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | ----------- | ------ | ------- |
| `tests/test_toolchain_pins.py` | Ruff pin drift guard (TEST-04) + `_alembic` exclude regression guard (TEST-03) + parser self-tests | ✓ VERIFIED | Exists; `def test_ruff_pin_matches_precommit_rev(` present; exports `get_pyproject_ruff_pin`, `get_precommit_ruff_rev`; 16 tests all pass, 0 skipped |
| `pyproject.toml` | Exact ruff pin in dev extra + `force-exclude = true` under `[tool.ruff]` | ✓ VERIFIED | `ruff==0.16.9` exact specifier; `force-exclude = true` present; `extend-exclude` unchanged |
| `.pre-commit-config.yaml` | `astral-sh/ruff-pre-commit` rev equal to the pyproject pin | ✓ VERIFIED | `rev: v0.16.9`, matches pyproject pin exactly |
| `tests/test_no_import_masking_skips.py` | AST sweep guard against import-masking module-level skips (TEST-02), self-tests, guard-the-guard | ✓ VERIFIED | Exists; `def find_import_masking_skips(` present; exports `find_import_masking_skips`, `SWEPT_FILES`, `FIRST_PARTY`; 19 tests all pass |
| `tests/test_json_parse_retry.py` | Live-parser coverage for the still-meaningful cases of the deleted suite | ✓ VERIFIED | `def test_recovers_payload_from_llm_wrapping(` present; file reports 20 passed (10 pre-existing + 10 new, matching the 19-case ledger's NEW column) |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `tests/test_toolchain_pins.py` | `pyproject.toml` | tomllib read of `project.optional-dependencies.dev`, parsed with `packaging.requirements.Requirement` | ✓ WIRED | `get_pyproject_ruff_pin` reads the real file and returns `0.16.9`, confirmed live |
| `tests/test_toolchain_pins.py` | `.pre-commit-config.yaml` | line scan scoped to the `astral-sh/ruff-pre-commit` block | ✓ WIRED | `get_precommit_ruff_rev` reads the real file and returns `0.16.9`, confirmed live |
| `.github/workflows/ci.yml` | `pyproject.toml` | Install step (`pip install -e .[dev]`) installs the exact pin the Lint step then runs | ✓ WIRED (by pin equality) | Installed `.venv` ruff is `0.16.9`, equal to the pin; CI Lint step commands (`ruff check`/`ruff format --check`) pass with this ruff |
| `tests/test_no_import_masking_skips.py` | `tests/**/*.py` and `tools/tests/**/*.py` | module-level `SWEPT_FILES` built with `rglob` over both `SWEEP_ROOTS` | ✓ WIRED | `test_sweep_covers_both_roots_and_subpackages` passes; sweep found the real violator at commit time (`tests/test_parse_scoring_response.py:15`) before deletion, per SUMMARY, and now finds zero |
| `.github/workflows/ci.yml` | `tests/test_no_import_masking_skips.py` | `pytest tests/ -m 'not eval'` collects the guard (no `eval` marker) | ✓ WIRED | Verifier's own `pytest tests/ -q -m "not eval"` run collected and passed this file's 19 tests as part of the 4528-passed total |
| `tests/test_json_parse_retry.py` | `src/career_os/ai/openrouter_provider.py` | direct top-level import of `_try_parse_structured` | ✓ WIRED | File imports `ScoreResult` from `career_os.schemas.ai` directly (no try/except); `TestTryParseStructured` tests import and call `_try_parse_structured` directly and pass |

### Behavioral Spot-Checks / Scratch Proofs (re-run by verifier, not trusted from SUMMARY)

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Reintroduced import-masking skip caught | write scratch file, run `test_no_import_masking_module_level_skips`, delete file, re-run | Failed naming `tests/_scratch_reintro_check.py:11`, then 19 passed after cleanup; `git status` clean | ✓ PASS |
| Drift in `.pre-commit-config.yaml` caught | mutate rev to `v0.0.0`, run `test_ruff_pin_matches_precommit_rev`, restore | `AssertionError: ruff drift: ...rev is v0.0.0`; restored, 16 passed, `git status` clean | ✓ PASS |
| Drift in `pyproject.toml` caught | mutate pin to `0.0.0`, run `test_ruff_pin_matches_precommit_rev`, restore | `AssertionError: ruff drift: pyproject.toml dev extra pins ruff==0.0.0 ...`; restored, 16 passed, `git status` clean | ✓ PASS |
| Real pre-commit hooks agree with CI | `pre-commit run ruff --all-files` / `pre-commit run ruff-format --all-files` | Both `Passed`; `git status --short -- src tests` empty | ✓ PASS |
| `_alembic` stays excluded for bare explicit paths | `ruff check src/career_os/_alembic/ && ruff format --check src/career_os/_alembic/` | `All checks passed!` (no `--force-exclude` flag passed on the command line — relies on `force-exclude = true` in pyproject) | ✓ PASS |
| Full backend suite | `pytest tests/ -q -m "not eval"` | `4528 passed, 24 skipped, 27 deselected`, 3 failed — all 3 are the ticketed, out-of-scope `test_npm_audit_no_high_or_critical[frontend\|worker\|extension]` (G-1856) | ✓ PASS (no new failures) |
| `tests/eval/geo` and `tools/tests/` (remaining CI steps) | `pytest tests/eval/geo -q` / `pytest tools/tests/ -q` | `7 passed` / `535 passed` | ✓ PASS |
| Both guard files together | `pytest tests/test_toolchain_pins.py tests/test_no_import_masking_skips.py -v` | `35 passed`, 0 skipped, 0 xfailed | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| TEST-01 | 06-02 | No test masks an ImportError with a module-level skip; dead file relocated or deleted | ✓ SATISFIED | `tests/test_parse_scoring_response.py` deleted (dead subject confirmed via grep); guard proves no remaining masking construct in `tests/` or `tools/tests/`; 19-case ledger in 06-02-SUMMARY.md (7 covered, 10 re-pinned in `test_json_parse_retry.py`, 2 out-of-contract) — all 20 tests in that file pass |
| TEST-02 | 06-02 | A guard fails when an import-masking module-level skip is reintroduced | ✓ SATISFIED | Verifier's own scratch reintroduction (see above) caught the exact construct and its variants (11 parametrized `test_detector_flags_masking_variants` ids); 3 `test_detector_ignores_legitimate_skips` ids confirm no false positives; guard-the-guard (`test_sweep_covers_both_roots_and_subpackages`) confirms the sweep can't shrink silently |
| TEST-03 | 06-01 | One ruff version governs pre-commit and CI; `_alembic` exclude preserved | ✓ SATISFIED | Pin equality verified live (0.16.9 both files); real pre-commit hook run passes; `_alembic` explicit-path check passes |
| TEST-04 | 06-01 | A test/CI step fails when the pins drift | ✓ SATISFIED | Both drift directions independently reproduced and reverted by the verifier with the real assertion failure text confirmed |

No orphaned requirements: `.planning/REQUIREMENTS.md`'s Phase 6 row lists exactly TEST-01 through TEST-04, and both plans' frontmatter jointly declare all four (`06-01`: TEST-03, TEST-04; `06-02`: TEST-01, TEST-02).

**Note (tracking metadata, not a code gap):** `.planning/REQUIREMENTS.md` and `.planning/ROADMAP.md` still show TEST-01/TEST-02 as unchecked (`[ ]`) and Phase 6 overall as unchecked, while TEST-03/TEST-04 are checked. Verification confirms the underlying code/test evidence for all four requirements is equally solid; the unchecked boxes for TEST-01/TEST-02 and the phase line appear to be a pending doc-sync step (expected to be flipped by the ship/complete-phase workflow), not a functional gap. Flagging for the orchestrator to reconcile post-verification.

### Anti-Patterns Found

None. Scanned `pyproject.toml`, `.pre-commit-config.yaml`, `tests/test_toolchain_pins.py`, `tests/test_no_import_masking_skips.py`, `tests/test_json_parse_retry.py` for TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER markers, empty implementations, and hardcoded stub returns — none found. No `xfail` or `skip` marker was added anywhere in this phase's diff (confirmed by SUMMARY's own `git show` diffs and by the fact the full-suite skip count only decreased, never increased, relative to the phase's starting point).

### Requirements/Threat Model Prohibitions

| Prohibition | Verification | Result |
|---|---|---|
| MUST NOT get ruff green by suppressing findings (no new noqa/per-file-ignores/excludes) | judgment | `git show 7a4245a -- pyproject.toml` per SUMMARY touches only the ruff dev entry, its comment, the comment above `extend-exclude`, and the added `force-exclude` line — no new `noqa`, no widened excludes. Independently confirmed `extend-exclude` value unchanged. |
| MUST NOT hardcode ruff version in the drift test / MUST NOT skip or default on parse failure | test | `grep -c "0.16.9" tests/test_toolchain_pins.py` in `test_ruff_pin_matches_precommit_rev`'s body: none (test reads both real files); parser functions raise `ValueError`, confirmed via passing self-tests `test_precommit_rev_rejects_missing_ruff_block`, `test_precommit_rev_rejects_duplicate_ruff_blocks`, `test_precommit_rev_rejects_frozen_sha_rev`, `test_pyproject_pin_rejects_non_exact_specifiers` |
| MUST NOT replace the removed masking skip with another masking mechanism (xfail, skipif-on-import-flag, first-party importorskip, broad except, conftest skip) | judgment | Full-suite skip listing (24 lines) manually reviewed above — none wrap an ImportError; the two unrelated per-test skips (`test_demo_seed.py`, `test_billing_safety.py`) are pre-existing, unrelated features with no import/exception handling involved |
| MUST NOT weaken the legitimate file-presence guards in `test_batch_apply_browser.py`, `test_batch_apply_overlay.py`, `tools/tests/test_config_loaders.py` | test | `git diff --quiet main -- <those 3 files>` — per SUMMARY this passed; guard's own `test_real_file_presence_guards_are_not_flagged` confirms all three remain unflagged and untouched |
| MUST NOT let the guard pass by exemption/emptiness (no allowlist, no silent empty result) | test | Confirmed no allowlist mechanism exists in `tests/test_no_import_masking_skips.py` (grep for `allowlist`/`exempt` finds nothing); `test_detector_raises_on_unparseable_file` confirms SyntaxError propagates rather than returning `[]` |

### Human Verification Required

None. All success criteria are automatable and were independently re-executed by the verifier.

### Gaps Summary

No gaps found. All 5 roadmap success criteria, all 5 artifacts, all 6 key links, and all 4 requirement IDs (TEST-01 through TEST-04) are verified against live re-execution of the scratch proofs, not against SUMMARY.md narrative. One tracking-metadata inconsistency noted above (REQUIREMENTS.md/ROADMAP.md checkboxes for TEST-01/TEST-02 not yet flipped) — informational only, does not block phase completion.

---

_Verified: 2026-09-30_
_Verifier: Claude (gsd-verifier)_
