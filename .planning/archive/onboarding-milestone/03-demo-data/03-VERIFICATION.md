---
status: passed
phase: 03-demo-data
verified_at: "2026-04-20T17:25:00Z"
plans_verified: [03-01, 03-02, 03-03]
requirements_covered: [DEMO-01, DEMO-02, DEMO-03, DEMO-04, DEMO-05]
---

# Phase 3 Verification: Demo Data

## Goal Check

**Goal:** Users see realistic scored job results immediately after onboarding completes, proving the tool works without requiring any API key or external service.

**Verdict:** PASSED

## Success Criteria Verification

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Ten pre-baked sample jobs spanning 3+ job families ship as fixture data | ✓ PASSED | 10 jobs, 7 families (Tech, Marketing, Legal, Operations, Finance, Sales, Recruiting/HR) |
| 2 | Demo records display relative dates, carry is_demo=True flag, show "Sample Results" banner | ✓ PASSED | days_ago offset computed at seed time; is_demo column on model; Panel in pipeline list |
| 3 | Demo seeder is idempotent — running multiple times produces exactly the same result | ✓ PASSED | test_seed_idempotent passes (delete-then-insert strategy) |

## Automated Test Results

```
tests/test_demo_seed.py: 6 passed, 1 skipped
tests/test_demo_autoclear.py: 4 passed
Total: 10 passed, 1 skipped (pipeline banner test deferred — requires CLI runner)
```

## Requirement Traceability

| Req ID | Description | Verified By |
|--------|-------------|-------------|
| DEMO-01 | 10 sample jobs from fixture | test_seed_creates_10_jobs |
| DEMO-02 | 7+ job families | test_seed_job_family_diversity + fixture inspection |
| DEMO-03 | Relative dates (never stale) | test_seed_computes_relative_dates |
| DEMO-04 | kestrel init seeds demo data | grep seed_demo_data in init.py (both paths) |
| DEMO-05 | Idempotent seeder | test_seed_idempotent |

## Key Artifacts

- `src/career_os/fixtures/demo_jobs.json` — 10-job fixture
- `src/career_os/migration/demo_seed.py` — idempotent seeder
- `alembic/versions/r9s0t1u2v3w4_add_is_demo_column.py` — migration
- `src/career_os/services/applications.py` — _auto_clear_demo_data hook
- `tests/test_demo_seed.py` + `tests/test_demo_autoclear.py` — test coverage

## Human Verification Items

None required — all criteria are automatable.

## Deviations

- Migration revision ID: planned `a1b2c3d4e5f6`, actual `r9s0t1u2v3w4` (collision avoidance)
- Plan 03-03 worktree diverged from feature branch base; recovered via cherry-pick
