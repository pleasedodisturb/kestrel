---
phase: 02-cli-wizard
plan: 03
subsystem: cli
tags: [onboarding, wizard, cli, init, first-run]
dependency_graph:
  requires: [02-01, 02-02]
  provides: [init-command, first-run-callback]
  affects: [cli-main, onboarding-state]
tech_stack:
  added: []
  patterns: [typer-command-registration, rich-prompt-wizard, mock-tty-testing]
key_files:
  created:
    - src/career_os/cli/init.py
    - tests/test_cli_init.py
  modified:
    - src/career_os/cli/main.py
decisions:
  - "Used mock_tty fixture pattern for testing interactive CLI commands in non-TTY test runner"
  - "Registered init as bare function via app.command('init')(init) matching doctor pattern"
metrics:
  duration: 5m 58s
  completed: 2026-04-20
  tasks: 3/3
  tests: 11
---

# Phase 02 Plan 03: Init Wizard Command Summary

Interactive kestrel init wizard with 5 skippable profile questions, step progress indicator, Rich summary table, confirm-before-save, --skip/--force flags, non-TTY detection, and first-run callback on main.py

## What Was Built

### Task 1: kestrel init wizard command (`src/career_os/cli/init.py`)
- 5-step wizard: name, location, job_family, salary_range, experience_level
- `Step X/5` progress indicator before each question (CLI-05)
- `--skip` flag creates default profile immediately (CLI-04)
- `--force` flag overrides resume detection to re-run wizard
- Non-TTY detection with guidance Panel (CLI-03)
- Rich Table summary of answers before save (D-04/PROF-03)
- `Confirm.ask` gate before writing to DB (PROF-03)
- Marks `profile_started` and `profile_completed` onboarding steps
- Next-step suggestion: "Try kestrel pipeline list" (CLI-08)
- Error handling for OnboardingError and unexpected exceptions (CLI-07)

### Task 2: main.py registration + first-run callback
- `main_callback` with `invoke_without_command=True` checks onboarding status
- Shows "Welcome to Kestrel" Panel when onboarding incomplete (D-09, D-10, D-11)
- Skips callback for `init` and `doctor` commands
- T-02-05 mitigation: DB query wrapped in try/except, never blocks normal commands
- `init` command registered via `app.command("init")(init)` pattern

### Task 3: Test suite (11 tests)
- test_init_skip / test_init_skip_no_existing_profile (CLI-04)
- test_init_happy_path (CLI-02)
- test_init_all_skipped (empty answers)
- test_init_confirm_rejected (PROF-03)
- test_non_tty_detection (CLI-03)
- test_step_indicator (CLI-05)
- test_next_step_suggestion (CLI-08)
- test_first_run_callback_shows_panel / test_first_run_callback_hidden_when_complete (CLI-01)
- test_init_already_completed_shows_message (D-14)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed typer.Exit swallowed by broad except handler**
- **Found during:** Task 3 (test_init_already_completed_shows_message failing)
- **Issue:** `typer.Exit` inherits from `Exception` via click's `Exit` class. The `except Exception` handler in resume detection was catching and swallowing `typer.Exit(0)`, causing the wizard to continue after printing "Profile already set up."
- **Fix:** Added explicit `except typer.Exit: raise` before the broad `except Exception` handler
- **Files modified:** src/career_os/cli/init.py
- **Commit:** 0286336

## Decisions Made

1. **mock_tty fixture pattern:** CliRunner runs in non-TTY mode by default. Created a `mock_tty` pytest fixture that patches `career_os.cli.init.sys.stdin.isatty` to return True for all interactive wizard tests. This is cleaner than patching in each test individually.

2. **Bare function registration:** Following the doctor command pattern from Plan 02, `init` is defined as a plain function (no decorator) in init.py and registered in main.py via `app.command("init")(init)`.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | dcaac07 | feat(02-03): create kestrel init interactive wizard command |
| 2 | 44f6b56 | feat(02-03): register init command and add first-run callback |
| 3 | 0286336 | test(02-03): add init wizard test suite with 11 tests |
