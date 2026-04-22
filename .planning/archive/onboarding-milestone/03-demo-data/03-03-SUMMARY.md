---
phase: 03-demo-data
plan: 03
subsystem: demo-data-lifecycle
tags: [demo, auto-clear, tests, D-13, DEMO-01, DEMO-02, DEMO-03, DEMO-04, DEMO-05]
dependency_graph:
  requires: [is_demo_column, demo_fixture, seed_demo_data]
  provides: [auto_clear_demo_data, demo_seed_tests, demo_autoclear_tests]
  affects: [applications_service, discovery_service]
tech_stack:
  added: []
  patterns: [delete-filter on boolean column, import-on-use for circular avoidance]
key_files:
  created:
    - tests/test_demo_seed.py
    - tests/test_demo_autoclear.py
  modified:
    - src/career_os/services/applications.py
    - src/career_os/services/discovery.py
decisions:
  - "Auto-clear placed after db.refresh in create_application (not before commit) to avoid clearing demo data if creation fails"
  - "Discovery path uses local import to avoid circular dependency between applications and discovery services"
metrics:
  duration: "2m27s"
  completed: "2026-04-20"
  tasks_completed: 3
  tasks_total: 3
---

# Phase 03 Plan 03: Auto-Clear and Test Coverage Summary

Auto-clear hook in both job creation paths (D-13) plus comprehensive test suites covering all DEMO-01 through DEMO-05 requirements and auto-clear edge cases.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | c4b5b4c | Auto-clear hook in applications.py and discovery.py |
| 2 | cf7387b | Demo seeder test suite (7 tests, DEMO-01 through D-07) |
| 3 | 69196ad | Auto-clear behavior test suite (4 tests, D-13) |

## Key Implementation Details

- **_auto_clear_demo_data**: Filters exclusively on `Application.is_demo.is_(True)` + `profile_id` — never uses `source` field (T-03-06 mitigation)
- **Two trigger points**: `create_application` (manual path) and discovery service `_persist_or_update_job` (auto-discovery path)
- **No-op safety**: Only commits if `count > 0` to avoid empty transactions (T-03-07 accepted risk)
- **Test coverage**: 10 passing tests + 1 skipped (pipeline banner requires Plan 02 CLI changes)

## Test Results

```
10 passed, 1 skipped in 0.35s
```

| Test File | Tests | Status |
|-----------|-------|--------|
| tests/test_demo_seed.py | 6 pass, 1 skip | GREEN |
| tests/test_demo_autoclear.py | 4 pass | GREEN |

## Deviations from Plan

None - plan executed exactly as written.

## Threat Surface Scan

No new threat surfaces introduced. Auto-clear filter uses `is_demo.is_(True)` exclusively as required by T-03-06.

## Self-Check: PASSED
