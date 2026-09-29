---
phase: "6"
slug: "test-honesty"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-29"
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `06-RESEARCH.md` § Validation Architecture; the planner fills the per-task map.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (CI-installed; `pyproject.toml` `[tool.pytest.ini_options]`, `asyncio_mode = "auto"`, `timeout = 30`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_no_import_masking_skips.py tests/test_toolchain_pins.py -v` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -v --tb=short -m "not eval"` plus `.venv/bin/python -m pytest tools/tests/ -v --tb=short` (the two CI steps) plus `.venv/bin/ruff check src/ tests/` and `.venv/bin/ruff format --check src/ tests/` |
| **Estimated runtime** | ~5 s quick · ~120 s full |

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-T1 | 01 | 1 | TEST-03, TEST-04 | T-6-01, T-6-02, T-6-05 | One exact ruff pin in both files, taken from a green CI run with a matching ruff-pre-commit tag; `_alembic` excluded for explicit paths | tracer (unit + CLI) | `PYTHONPATH=src .venv/bin/python -m pytest tests/test_toolchain_pins.py -v` · `ruff check src/ tests/ && ruff format --check src/ tests/` · explicit-file-list `ruff format --check --force-exclude` (PRECOMMIT-SHAPE-OK) · `ruff check src/career_os/_alembic/` → `All checks passed!` | ❌ W0 (created by this task) | ⬜ pending |
| 06-01-T2 | 01 | 1 | TEST-04, TEST-03 | T-6-02, T-6-03 | Parsers raise on malformed or non-exact pins; drift proven in both directions and reverted; the real pre-commit hooks agree with CI and leave `_alembic` untouched | unit (self-test) + scratch check + hook parity | `pytest tests/test_toolchain_pins.py -v` · drift one-liners (DRIFT-PROOF-PRECOMMIT-OK, DRIFT-PROOF-PYPROJECT-OK) · `pre-commit run ruff/ruff-format --all-files` (PRECOMMIT-PARITY-OK) · alembic hook proof (ALEMBIC-HOOK-EXCLUDE-OK) | ✅ after T1 | ⬜ pending |
| 06-02-T1 | 02 | 2 | TEST-01, TEST-02 | T-6-06 | The guard catches the live violator on the real tree; the dead suite is deleted; collection is honest | tracer (AST sweep) + collection | `PYTHONPATH=src .venv/bin/python -m pytest tests/test_no_import_masking_skips.py -v` · DEAD-SUITE-GONE · `pytest --collect-only -q tests/ -rs` filter (COLLECTION-HONEST) | ❌ W0 (created by this task) | ⬜ pending |
| 06-02-T2 | 02 | 2 | TEST-02 | T-6-06, T-6-07, T-6-09 | Spelling variants flagged, legitimate skips spared, the sweep cannot shrink silently, unparseable files raise; live reintroduction caught and cleaned up | unit (self-test) + scratch check | `pytest tests/test_no_import_masking_skips.py -v` · reintroduction one-liner (REINTRO-PROOF-OK) · `ruff check`/`ruff format --check` on the file | ✅ after T1 | ⬜ pending |
| 06-02-T3 | 02 | 2 | TEST-01 | T-6-10 | All 19 deleted cases accounted for (7 covered, 10 re-pinned, 2 out of contract); no xfail or skip used | unit | `PYTHONPATH=src .venv/bin/python -m pytest tests/test_json_parse_retry.py -v` → `20 passed` · CI Lint step | ✅ (existing file) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

All plan commands use the absolute interpreter `/Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/python` (and `.../ruff`), so they run from a worktree too. The shortened `.venv/bin/...` form above is for readability only.

---

## Wave 0 Requirements

- [ ] `tests/test_no_import_masking_skips.py` — AST sweep + self-test for TEST-02 (also re-proves TEST-01 stays fixed)
- [ ] `tests/test_toolchain_pins.py` — pyproject vs `.pre-commit-config.yaml` ruff-pin drift guard for TEST-04
- [ ] `force-exclude = true` under `[tool.ruff]` in `pyproject.toml` — config, not a test, but required for TEST-03's `_alembic` exclude to hold under pre-commit's explicit-path invocation

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Guard fails on a deliberate reintroduction of an import-masking module-level skip | TEST-02 | Success criterion 3 demands a live scratch check, not only the permanent self-test | Add a throwaway `tests/_scratch_reintro_check.py` with `try: import not_a_real_module` / `except ImportError: pytest.skip("x", allow_module_level=True)`; run the quick command and observe FAIL; delete the file; re-run and observe PASS. Never commit the throwaway file. |
| Drift guard fails when the two ruff pins are made to disagree | TEST-04 | Success criterion 5 demands a live scratch check | On a clean tree, edit the `rev:` under `astral-sh/ruff-pre-commit` in `.pre-commit-config.yaml` to a different version; run the quick command and observe FAIL; `git checkout -- .pre-commit-config.yaml`; re-run and observe PASS; confirm `git status` clean. |
| Local pre-commit `ruff-format` and CI `ruff format --check` agree on every file | TEST-03 | Parity is proven by construction once both resolve the same pinned version; `pre-commit run` reformats in place so it must run only on a clean tree after the pin lands | After the pin commit, on a clean tree: `pre-commit run ruff-format --all-files` then `git status --short` must be empty. |

All three rows above run as automated, self-reverting one-liners inside the plans: 06-02-T2 (REINTRO-PROOF-OK) and 06-01-T2 (DRIFT-PROOF-PRECOMMIT-OK, DRIFT-PROOF-PYPROJECT-OK, PRECOMMIT-PARITY-OK, ALEMBIC-HOOK-EXCLUDE-OK). They stay listed here because success criteria 3 and 5 demand a live scratch check, and SUMMARY must quote their output.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
