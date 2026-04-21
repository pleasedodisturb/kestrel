---
phase: 03-demo-data
plan: 01
subsystem: demo-data-foundation
tags: [demo, fixture, seeder, migration, onboarding]
dependency_graph:
  requires: []
  provides: [is_demo_column, demo_fixture, seed_demo_data]
  affects: [Application_model, pyproject_toml]
tech_stack:
  added: [importlib.resources]
  patterns: [delete-then-insert idempotency, batch_alter_table SQLite migration]
key_files:
  created:
    - alembic/versions/r9s0t1u2v3w4_add_is_demo_column.py
    - src/career_os/fixtures/__init__.py
    - src/career_os/fixtures/demo_jobs.json
    - src/career_os/migration/demo_seed.py
  modified:
    - src/career_os/models/models.py
    - pyproject.toml
decisions:
  - "Used revision ID r9s0t1u2v3w4 instead of plan-specified a1b2c3d4e5f6 (already taken by job_requirements migration)"
metrics:
  duration: "3m"
  completed: "2026-04-20"
  tasks_completed: 3
  tasks_total: 3
---

# Phase 03 Plan 01: Demo Data Foundation Summary

Alembic migration, JSON fixture, and idempotent seeder for 10 diverse demo jobs spanning 7 job families with EU market emphasis.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | c01ab88 | is_demo Boolean column + Alembic migration |
| 2 | d6a69de | 10-job fixture file + fixtures package + pyproject.toml |
| 3 | 569bbba | Idempotent demo seeder module (seed_demo_data) |

## Key Implementation Details

- **Migration**: `r9s0t1u2v3w4` adds `is_demo` Boolean with `server_default=text("0")` using `batch_alter_table` for SQLite compatibility
- **Fixture**: 10 jobs, 7 families (Tech x2, Marketing x2, Finance x2, Legal, Operations, Sales, Recruiting/HR), score range 27.3-91.2
- **Seeder**: Delete-then-insert idempotency filtering on `Application.is_demo.is_(True)`, loads fixture via `importlib.resources.files`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Revision ID conflict**
- **Found during:** Task 1
- **Issue:** Plan specified revision `a1b2c3d4e5f6` but that ID already exists (used by job_requirements migration)
- **Fix:** Used `r9s0t1u2v3w4` as the new revision ID, maintaining `down_revision = "q8r9s0t1u2v3"` as planned
- **Files modified:** alembic/versions/r9s0t1u2v3w4_add_is_demo_column.py

## Verification Results

All three automated verification checks passed:
- `Application.is_demo` attribute exists on model
- Fixture loads via importlib.resources: 10 jobs, 7 families
- `seed_demo_data` imports successfully

## Self-Check: PASSED
