---
phase: 04-web-welcome-flow
plan: 01
subsystem: frontend-infrastructure
tags: [onboarding, api-layer, route-guard, schema-fix]
dependency_graph:
  requires: []
  provides: [onboarding-api-client, onboarding-hooks, onboarding-guard, welcome-route]
  affects: [App.tsx, KanbanBoard.tsx, profiles-schema]
tech_stack:
  added: []
  patterns: [react-query-hooks, route-guard-wrapper, fail-open-guard]
key_files:
  created:
    - frontend/src/api/onboarding.ts
    - frontend/src/hooks/useOnboarding.ts
    - frontend/src/components/OnboardingGuard.tsx
    - frontend/src/pages/WelcomePage.tsx
  modified:
    - src/career_os/schemas/profiles.py
    - frontend/src/App.tsx
    - frontend/src/components/KanbanBoard.tsx
    - frontend/src/__tests__/KanbanBoard.test.tsx
  deleted:
    - frontend/src/components/OnboardingWizard.tsx
decisions:
  - "OnboardingGuard checks welcome_completed_at (not completed_at) to allow Phase 5 tour without re-blocking"
  - "Guard fails open on API error (self-hosted, prefer usability over strictness)"
  - "WelcomePage placeholder created to unblock TypeScript compilation; full implementation in Plan 02"
metrics:
  duration: 6min
  completed: "2026-04-21T00:28:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 9
---

# Phase 4 Plan 01: Infrastructure Layer Summary

Backend schema fix for profile fields, frontend onboarding API client and React Query hooks, OnboardingGuard route wrapper, App.tsx route restructuring, and legacy wizard removal.

## One-liner

OnboardingGuard with fail-open redirect to /welcome, API layer for onboarding status, salary_range + experience_level added to profile schemas, old localStorage wizard deleted.

## Tasks Completed

| Task | Name | Commit | Key Changes |
|------|------|--------|-------------|
| 1 | Backend schema fix + frontend API layer + hooks | 3c0f2ef | Added salary_range/experience_level to ProfileCreate/Update/Response; created onboarding.ts API client and useOnboarding.ts hooks |
| 2 | OnboardingGuard + route wiring + wizard removal | 48a1804 | Created OnboardingGuard, restructured App.tsx routes, removed wizard from KanbanBoard, deleted OnboardingWizard.tsx, created WelcomePage placeholder |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] KanbanBoard.test.tsx wizard test cleanup**
- **Found during:** Task 2
- **Issue:** Deleting OnboardingWizard.tsx would break KanbanBoard.test.tsx which had 3 wizard-related tests and a beforeEach localStorage pre-dismiss
- **Fix:** Removed the wizard describe block (3 tests) and the wizard pre-dismiss from beforeEach
- **Files modified:** frontend/src/__tests__/KanbanBoard.test.tsx
- **Commit:** 48a1804

## Known Stubs

| File | Line | Stub | Reason |
|------|------|------|--------|
| frontend/src/pages/WelcomePage.tsx | 3 | Placeholder "Loading welcome flow..." | Full implementation in Plan 02; needed for TypeScript compilation |

## Pre-existing Test Failures

KanbanBoard.test.tsx and Discovery.test.tsx both fail with `localStorage.clear is not a function` -- a jsdom environment issue predating this plan. Confirmed by running tests on the commit before any plan changes. Not introduced or affected by this plan's changes.

## Verification Results

- TypeScript compilation: PASS (npx tsc --noEmit exits 0)
- Backend schema validation: PASS (ProfileUpdate/ProfileCreate contain salary_range and experience_level)
- Test suite: 20/22 test files pass (2 pre-existing failures unrelated to this plan)
- All acceptance criteria met for both tasks

## Self-Check: PASSED
