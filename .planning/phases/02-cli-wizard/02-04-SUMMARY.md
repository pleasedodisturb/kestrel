---
phase: 02-cli-wizard
plan: 04
subsystem: cli
tags: [cli, wizard, resume-paste, extraction, skills, onboarding]
dependency_graph:
  requires: [02-01, 02-03]
  provides: [resume-paste-step, resume-from-last-step, skill-save-from-extraction]
  affects: [src/career_os/cli/init.py, tests/test_cli_init.py]
tech_stack:
  added: []
  patterns: [rich-confirm-flow, sqlalchemy-dedup-insert, resume-detection]
key_files:
  modified:
    - src/career_os/cli/init.py
    - tests/test_cli_init.py
decisions:
  - "Skills from resume paste use evidence_source='resume_paste' and category='technical' as defaults"
  - "Resume-from-last-step pre-fills existing Profile values as Prompt defaults"
  - "Paste step is always offered (Confirm default=False) — not conditional on empty fields"
metrics:
  duration_seconds: 264
  completed: "2026-04-20T13:49:06Z"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 02 Plan 04: Resume Paste Integration Summary

Resume paste step integrated into init wizard with ESCO skill extraction, user review display, DB persistence, and resume-from-last-step detection with profile value pre-fill.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add resume paste step and resume-from-last-step | 8eb30a3 | src/career_os/cli/init.py |
| 1-fix | Fix evidence_source NOT NULL on Skill insert | 507cb5e | src/career_os/cli/init.py |
| 2 | Add tests for resume paste and resume-from-last-step | 3be955f | tests/test_cli_init.py |

## Implementation Details

### Resume Paste Step (PROF-02, D-16, D-18)
After all 5 guided questions, the wizard offers an optional paste step via `Confirm.ask` (default=False). When accepted:
1. `read_multiline_paste()` reads stdin until double-Enter
2. `extract_from_text()` pulls emails, phones, URLs via regex
3. `extract_skills_from_text()` fuzzy-matches n-grams against ESCO taxonomy
4. Findings displayed in a structured "Found in your resume" block
5. Email merged into answers if not already provided
6. Skills shown in the summary table before confirmation

### Skill Persistence
After profile save, extracted skills are deduplicated against existing `Skill` rows (by profile_id + name) and inserted with `category="technical"` and `evidence_source="resume_paste"`. Count of newly added skills shown to user.

### Resume-from-Last-Step (D-14)
On re-run, if `profile_started_at` is set but `profile_completed_at` is None, the wizard shows "Welcome back! Resuming where you left off." and pre-fills existing profile field values as defaults for each question (user presses Enter to keep).

### Terminal Tips (D-08)
Three contextual tips: skip-any-question (existing), paste instructions, and re-run reminder after save.

## Test Results

16 tests total (11 existing + 5 new), all passing:
- `test_resume_from_last_step` — "Welcome back" on partial completion
- `test_resume_prefills_existing_values` — defaults captured from profile
- `test_resume_paste_extracts_email` — email shown in output
- `test_resume_paste_declined` — paste step skipped cleanly
- `test_extracted_skills_saved` — Skill rows created in DB

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] NOT NULL constraint on skills.evidence_source**
- **Found during:** Task 2 test execution
- **Issue:** Skill model requires `evidence_source` (NOT NULL) but initial implementation omitted it, causing IntegrityError on commit
- **Fix:** Added `evidence_source="resume_paste"` to Skill constructor
- **Files modified:** src/career_os/cli/init.py
- **Commit:** 507cb5e

## Known Stubs

None. All data flows are wired end-to-end (extraction -> display -> DB persistence).

## Self-Check: PASSED
