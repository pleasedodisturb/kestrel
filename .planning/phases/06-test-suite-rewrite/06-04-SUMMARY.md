---
phase: 06-test-suite-rewrite
plan: 04
subsystem: frontend-test-tourprovider-helppage
tags: [testing, vitest, anti-mocking, api-level-mocks]
dependency_graph:
  requires: [test-setup-polyfill, renderWithProviders]
  provides: [tourprovider-tests-green, helppage-tests-green]
  affects: [frontend-test-suite]
tech_stack:
  added: []
  patterns: [api-boundary-mocking, async-waitfor-assertions, minimal-navigate-spy]
key_files:
  created: []
  modified:
    - frontend/src/__tests__/TourProvider.test.tsx
    - frontend/src/__tests__/HelpPage.test.tsx
decisions:
  - "Kept minimal useNavigate spy for TourProvider imperative navigation test (Option B from RESEARCH.md Open Question #1)"
  - "Mutation assertions wrapped in waitFor since React Query mutations are async"
metrics:
  duration: 5min
  completed: "2026-04-21T12:36:02Z"
  tasks: 2
  files: 2
---

# Phase 6 Plan 04: TourProvider + HelpPage Test Rewrite Summary

TourProvider rewritten to mock @/api/onboarding instead of hooks (18 tests), HelpPage wrapped with renderWithProviders fixing QueryClientProvider crash (13 tests). All 50 tests across 5 plan-relevant files pass green.

## What Was Done

### Task 1: Rewrite TourProvider.test.tsx (c360ec1)

Full rewrite of TourProvider.test.tsx to comply with D-04 anti-mocking methodology:

- Removed `vi.mock("@/hooks/useOnboarding")` -- hooks now run for real via React Query
- Removed `UseQueryResult` and `UseMutationResult` type imports (no longer needed)
- Added `vi.mock("@/api/onboarding")` with `mockFetchOnboardingStatus`, `mockPatchOnboardingStep`, `mockResetOnboarding`
- Replaced inline `renderWithProvider` with shared `renderWithProviders` from `@/test-utils`
- Converted all sync hook-mock assertions to async API-mock pattern with `waitFor`
- Mutation assertions now check `mockPatchOnboardingStep(1, "tour_completed")` directly (positional args from mutationFn destructuring)
- Kept minimal `useNavigate` spy for imperative navigation test (TourProvider calls `navigate("/discovery")` programmatically -- Route-based assertions too complex with fake timers)
- All 18 tests pass green

**Files modified:** `frontend/src/__tests__/TourProvider.test.tsx`

### Task 2: Rewrite HelpPage.test.tsx (70370cf)

- Replaced bare `render` + `MemoryRouter` with `renderWithProviders` from `@/test-utils` (fixes QueryClientProvider crash from RestartOnboarding component)
- Added `vi.mock("@/api/onboarding")` for `resetOnboarding` and `fetchOnboardingStatus` dependencies
- All 13 tests pass (previously 0/13 due to missing QueryClientProvider)
- Verified StepProgress (7), EmptyState (6), FeedbackButton (6) still pass unchanged

**Files modified:** `frontend/src/__tests__/HelpPage.test.tsx`

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | c360ec1 | test(06-04): rewrite TourProvider.test.tsx -- mock API not hooks, remove UseQueryResult |
| 2 | 70370cf | test(06-04): rewrite HelpPage.test.tsx -- add renderWithProviders + API mock |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Mutation assertions needed waitFor**
- **Found during:** Task 1
- **Issue:** `mockPatchOnboardingStep` assertions failed because React Query mutations fire asynchronously. The test checked the mock immediately after `act()` but the mutationFn hadn't executed yet.
- **Fix:** Wrapped all `expect(mockPatchOnboardingStep).toHaveBeenCalledWith(...)` in `await waitFor(() => { ... })`
- **Files modified:** `frontend/src/__tests__/TourProvider.test.tsx`
- **Commit:** c360ec1

### Notes

**Full suite gate (D-05):** The full `npm run test` has 14 failures across 6 other test files (KanbanBoard, Discovery, Skills, Layout, OnboardingGuard, WelcomePage). These are pre-existing failures handled by plans 06-02 and 06-03 in this wave. The 5 files within this plan's scope (TourProvider, HelpPage, StepProgress, EmptyState, FeedbackButton) all pass -- 50/50 tests green.

## Verification

- `npx vitest run src/__tests__/TourProvider.test.tsx` -- 18 tests pass
- `npx vitest run src/__tests__/HelpPage.test.tsx` -- 13 tests pass
- `npx vitest run src/__tests__/StepProgress.test.tsx` -- 7 tests pass (unchanged)
- `npx vitest run src/__tests__/EmptyState.test.tsx` -- 6 tests pass (unchanged)
- `npx vitest run src/__tests__/FeedbackButton.test.tsx` -- 6 tests pass (unchanged)
- TourProvider contains `vi.mock("@/api/onboarding"` -- YES
- TourProvider does NOT contain `vi.mock("@/hooks/useOnboarding"` -- CONFIRMED
- TourProvider does NOT contain `UseQueryResult` or `UseMutationResult` -- CONFIRMED
- HelpPage contains `renderWithProviders` -- YES
- HelpPage contains `vi.mock("@/api/onboarding"` -- YES

## Self-Check: PASSED

- [x] `frontend/src/__tests__/TourProvider.test.tsx` exists
- [x] `frontend/src/__tests__/HelpPage.test.tsx` exists
- [x] Commit c360ec1 exists in git log
- [x] Commit 70370cf exists in git log
- [x] All 50 tests across 5 files pass green
