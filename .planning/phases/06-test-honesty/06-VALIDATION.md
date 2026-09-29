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
| (filled by the planner from PLAN.md tasks) | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

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

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
