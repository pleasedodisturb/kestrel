---
phase: 02-cli-wizard
plan: 02
subsystem: cli
tags: [doctor, health-check, typer, rich]
dependency_graph:
  requires: []
  provides: [kestrel-doctor-command]
  affects: [cli/main.py]
tech_stack:
  added: []
  patterns: [pass-fail-checklist, module-level-get-session-patching]
key_files:
  created:
    - src/career_os/cli/doctor.py
    - tests/test_cli_doctor.py
  modified:
    - src/career_os/cli/main.py
decisions:
  - "Demo data check included as non-critical but still fails the overall exit code -- keeps doctor honest about full setup"
  - "DB connection error shows generic message only (T-02-03 mitigation) -- no path/connection string leaked"
  - "Migrations check uses SELECT COUNT(*) FROM profiles as proxy instead of alembic CLI"
metrics:
  duration: 200s
  completed: 2026-04-20T13:28:31Z
  tasks_completed: 2
  tasks_total: 2
  test_count: 7
  files_changed: 3
---

# Phase 02 Plan 02: kestrel doctor Health Check Summary

TDD-built `kestrel doctor` command with 5 local health checks (Python version, DB connection, migrations, profile, demo data), pass/fail Rich output with resolution text, no stack traces, registered on main app.

## Task Results

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for doctor | de2bc25 | tests/test_cli_doctor.py |
| 1 (GREEN) | Implement doctor command | c7e489c | src/career_os/cli/doctor.py, tests/test_cli_doctor.py |
| 2 | Register doctor in main app | d448e76 | src/career_os/cli/main.py |

## Implementation Details

### Health Checks (5 total)
1. **Python version** -- verifies >= 3.11 via `sys.version_info`
2. **Database connection** -- `SELECT 1` probe via `SessionLocal()`
3. **Migrations applied** -- `SELECT COUNT(*) FROM profiles` as proxy
4. **Default profile** -- `db.query(Profile).filter(Profile.id == 1)`
5. **Demo data** -- `db.query(Application).filter(Application.source == "demo")`

Each check returns `(passed, label, resolution)`. Failed checks display resolution commands (e.g., "Run `kestrel init`"). Exit code 0 if all pass, 1 if any fail. Summary line: "N/M checks passed".

### Registration
Doctor is a bare function registered via `app.command("doctor")(doctor)` in main.py, following the pattern used for contacts and warn subcommands.

## TDD Gate Compliance

1. RED gate: `de2bc25` (test commit) -- 7 tests, all failing (ModuleNotFoundError)
2. GREEN gate: `c7e489c` (feat commit) -- 7 tests passing
3. REFACTOR gate: not needed -- code was clean from GREEN phase

## Deviations from Plan

None -- plan executed exactly as written.

## Threat Flags

None -- no new network endpoints, auth paths, or trust boundary changes. T-02-03 (info disclosure on DB error) mitigated: generic "Database connection failed" message with no path/connection string.

## Known Stubs

None -- all checks are fully wired to real database queries.

## Verification

- `kestrel doctor` shows checklist output with 5 checks
- `kestrel --help` lists "doctor" command
- Failing checks show resolution commands ("Run `kestrel init`", "Run `kestrel seed-demo`")
- No stack traces in any error scenario (tested)
- 7 tests pass, ruff lint + format clean

## Self-Check: PASSED

All 3 files found, all 3 commits verified in git log.
