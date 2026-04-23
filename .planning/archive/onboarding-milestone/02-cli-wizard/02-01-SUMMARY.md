---
phase: 02-cli-wizard
plan: 01
subsystem: cli-extraction
tags: [profile-model, alembic-migration, regex-extraction, esco-matching, tdd]
dependency_graph:
  requires: []
  provides: [extract_from_text, extract_skills_from_text, read_multiline_paste, profile-salary-experience-columns]
  affects: [src/career_os/models/models.py]
tech_stack:
  added: []
  patterns: [rapidfuzz-esco-matching, regex-contact-extraction, double-enter-multiline-input]
key_files:
  created:
    - src/career_os/cli/extract.py
    - alembic/versions/q8r9s0t1u2v3_add_profile_salary_experience.py
    - tests/test_resume_extraction.py
  modified:
    - src/career_os/models/models.py
decisions:
  - "ESCO skill matching threshold set to 80.0 (lower than normalizer's 85.0) for broader recall during extraction"
  - "N-gram generation capped at 500 words per T-02-02 threat mitigation"
  - "Migration written manually (autogenerate requires up-to-date DB) following existing batch_alter_table pattern"
metrics:
  duration: 3min
  completed: "2026-04-20T13:28:02Z"
---

# Phase 02 Plan 01: Profile Columns + Resume Extraction Summary

Profile model extended with salary_range and experience_level columns, resume extraction module built with regex contact parsing and ESCO fuzzy skill matching via rapidfuzz, all verified by 15 passing TDD tests.

## Task Completion

| Task | Name | Commit | Status |
|------|------|--------|--------|
| 1 | Add Profile columns + Alembic migration | 30de51b | Done |
| 2 | Create extraction module with tests (TDD) | cc867f0 (RED), 0bc8e7c (GREEN) | Done |

## What Was Built

### Task 1: Profile Model Extension
- Added `salary_range` (String 255, nullable) and `experience_level` (String 50, nullable) to Profile model
- Created Alembic migration `q8r9s0t1u2v3` using `batch_alter_table` for SQLite compatibility
- Columns placed after `dream_companies`, before `last_market_refreshed_at`

### Task 2: Resume Extraction Module (TDD)
- **extract_from_text()**: Regex extraction of emails, phones, URLs from pasted text
- **extract_skills_from_text()**: Generates 1-3 word n-grams, fuzzy-matches against ESCO taxonomy using rapidfuzz (score_cutoff=80.0), returns sorted list capped at top_n
- **read_multiline_paste()**: Reads stdin line-by-line, terminates on two consecutive empty lines (D-18), handles EOF
- T-02-02 threat mitigation: input capped at 500 words to prevent O(n^2) n-gram explosion

### Test Suite
15 tests covering all three functions:
- 6 tests for extract_from_text (email, phone, URL, empty, multiple, keys)
- 6 tests for extract_skills_from_text (exact match, multi-word, sorted, top_n, no matches, 500-word cap)
- 3 tests for read_multiline_paste (double-enter, EOF, strip)

## TDD Gate Compliance

- RED commit: cc867f0 (test(G-392): add failing tests)
- GREEN commit: 0bc8e7c (feat(G-392): implement extraction module)
- REFACTOR: not needed (code clean after linting)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Alembic autogenerate unavailable in worktree**
- **Found during:** Task 1
- **Issue:** `alembic revision --autogenerate` failed with "Target database is not up to date" because the worktree has no local DB
- **Fix:** Wrote migration manually following existing `batch_alter_table` pattern from `e68f373345cd`
- **Files modified:** alembic/versions/q8r9s0t1u2v3_add_profile_salary_experience.py
- **Commit:** 30de51b

## Verification Results

- Profile model imports with new fields: PASSED
- Ruff lint + format: PASSED (both files)
- pytest tests/test_resume_extraction.py: 15/15 PASSED

## Known Stubs

None -- all functions are fully implemented with real logic.

## Self-Check: PASSED
