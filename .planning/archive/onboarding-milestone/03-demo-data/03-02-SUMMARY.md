---
phase: 03-demo-data
plan: 02
subsystem: cli-demo-integration
tags: [demo, cli, init, doctor, pipeline, onboarding]
dependency_graph:
  requires: [is_demo_column, demo_fixture, seed_demo_data]
  provides: [init_demo_seeding, doctor_auto_fix, pipeline_banner]
  affects: [cli/init.py, cli/doctor.py, cli/main.py]
tech_stack:
  added: []
  patterns: [auto-fix health check, graceful attribute access]
key_files:
  created: []
  modified:
    - src/career_os/cli/init.py
    - src/career_os/cli/doctor.py
    - src/career_os/cli/main.py
decisions:
  - "Used getattr(app, 'is_demo', False) in pipeline list for graceful degradation if migration not yet applied"
metrics:
  duration: "1m"
  completed: "2026-04-20"
  tasks_completed: 3
  tasks_total: 3
---

# Phase 03 Plan 02: CLI Demo Integration Summary

Wire demo seeder into three CLI commands: auto-seed after kestrel init, auto-fix in kestrel doctor, and Sample Results banner in pipeline list.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 0767c9d | Wire seed_demo_data into kestrel init (both --skip and wizard paths) |
| 2 | 42772d0 | Replace doctor _check_demo_data with auto-fix logic |
| 3 | 99fc40a | Add Sample Results yellow banner to pipeline list |

## Key Implementation Details

- **init.py**: Calls `seed_demo_data(db, profile_id=profile.id)` after `mark_step_complete("profile_completed")` in both the `--skip` path and the post-wizard path. Marks `demo_seeded` onboarding step and prints count.
- **doctor.py**: Replaced `source == "demo"` filter with `Application.is_demo.is_(True)`. Auto-seeds when missing by calling `seed_demo_data`. Reports count. Falls back gracefully if no profile exists.
- **main.py**: After `query.all()` and before table rendering, checks `has_demo` via `getattr` safe access. Shows yellow `Panel` with "Sample Results" title explaining demo data will disappear once real jobs are added.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - all integrations are fully wired to the demo_seed module from Plan 01.

## Self-Check: PASSED
