---
phase: 3
slug: advanced-testing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-20
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with hypothesis 6.152 and schemathesis 4.15 |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `pytest tests/regression/ -m regression -v --tb=short` |
| **Full suite command** | `pytest tests/ -v --tb=short -m 'regression or property or fuzz'` |
| **Estimated runtime** | ~30 seconds (golden set <5s, property ~15s, fuzz ~10s) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/regression/ -m regression -v --tb=short`
- **After every plan wave:** Run `pytest tests/ -v -m 'regression or property or fuzz'`
- **Before `/gsd-verify-work`:** Full advanced suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | ADV-01 | regression | `pytest tests/regression/test_golden_set.py -m regression -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | ADV-02 | property | `pytest tests/property/test_scoring_properties.py -m property -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | ADV-02 | property | `pytest tests/property/test_state_machine.py -m property -x` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 2 | ADV-03 | fuzz | `pytest tests/fuzz/test_api_fuzz.py -m fuzz -x` | ❌ W0 | ⬜ pending |
| 03-03-02 | 03 | 2 | ADV-03 | fuzz | `pytest tests/fuzz/test_api_fuzz.py::TestAPIWorkflow -m fuzz -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/regression/` directory and `__init__.py`
- [ ] `tests/regression/test_golden_set.py` — covers ADV-01
- [ ] `tests/property/` directory and `__init__.py`
- [ ] `tests/property/test_scoring_properties.py` — covers ADV-02a
- [ ] `tests/property/test_state_machine.py` — covers ADV-02b
- [ ] `tests/fuzz/` directory and `__init__.py`
- [ ] `tests/fuzz/test_api_fuzz.py` — covers ADV-03
- [ ] `property` and `fuzz` markers registered in pyproject.toml
- [ ] `hypothesis>=6.152.0` and `schemathesis>=4.15.0` in dev dependencies
- [ ] `.hypothesis/` added to `.gitignore`
- [ ] `addopts` updated to exclude regression/property/fuzz from default run

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Schemathesis stateful chains exercise real user flows | ADV-03 | OpenAPI links may need manual verification of transition coverage | Run stateful test, check transition count > 0 in output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
