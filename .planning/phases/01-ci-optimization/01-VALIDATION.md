---
phase: 1
slug: ci-optimization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-19
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + vitest 3.x |
| **Config file** | `pyproject.toml` (pytest), `frontend/vitest.config.ts` (vitest) |
| **Quick run command** | `pytest tests/ -x -q --timeout=30` |
| **Full suite command** | `pytest tests/ -v && cd frontend && npx vitest run` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q --timeout=30`
- **After every plan wave:** Run `pytest tests/ -v && cd frontend && npx vitest run`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | CI-01 | — | N/A | unit | `pytest tests/ -m unit -q` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | CI-01 | — | N/A | unit | `pytest tests/ -m integration -q` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | CI-02 | — | N/A | manual | CI log shows "skipped" for unaffected jobs | — | ⬜ pending |
| 1-03-01 | 03 | 2 | CI-03 | — | N/A | manual | CI log shows testmon selective execution | — | ⬜ pending |
| 1-04-01 | 04 | 2 | CI-04 | — | N/A | manual | CI log shows venv cache hit, JUnit XML artifact | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_markers.py` — stubs for CI-01 marker verification
- [ ] Existing infrastructure covers CI-02 through CI-04 (CI workflow verification)

*Most CI optimization tasks are verified by observing CI behavior, not by running test files.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Backend job skipped on frontend-only PR | CI-02 | Requires actual GitHub Actions run | Create a PR changing only frontend files, verify backend job shows "skipped" |
| testmon selective execution | CI-03 | Requires CI cache state | Push a small change, verify testmon skips unaffected tests in CI log |
| Venv cache hit | CI-04 | Requires two consecutive CI runs | Run CI twice with same deps, verify second run shows cache restored |
| PR test result comment | CI-04 | Requires actual PR | Open PR, verify EnricoMi action posts combined test summary comment |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
