---
phase: 06-test-suite-rewrite
plan: 03
subsystem: frontend-test-onboarding
tags: [testing, vitest, api-mocking, onboarding]
dependency_graph:
  requires: [test-setup-polyfill, renderWithProviders]
  provides: [onboarding-guard-api-tests, welcome-page-api-tests]
  affects: [frontend-test-suite]
tech_stack:
  added: []
  patterns: [api-boundary-mocking, routes-based-navigation-testing, pre-seeded-query-cache]
key_files:
  created: []
  modified:
    - frontend/src/__tests__/OnboardingGuard.test.tsx
    - frontend/src/__tests__/WelcomePage.test.tsx
decisions:
  - "Pre-seed QueryCache for error test to avoid TourProvider remount loop caused by retry-on-new-observer"
  - "Use Routes-based rendering instead of mockNavigate spy for navigation assertions"
metrics:
  duration: 7min
  completed: "2026-04-21T12:39:00Z"
  tasks: 2
  files: 2
---

# Phase 6 Plan 03: OnboardingGuard + WelcomePage Test Rewrite Summary

API-boundary mocking for OnboardingGuard (4 tests) and WelcomePage (21 tests) replacing hook-level and router-level mocks with D-04-compliant vi.mock("@/api/onboarding") pattern.

## What Was Done

### Task 1: Rewrite OnboardingGuard.test.tsx (8b8289d)

Full rewrite to mock `@/api/onboarding` instead of `@/hooks/useOnboarding`. Removed the `UseQueryResult` type import, inline `createQueryClient`, and inline `renderGuard` that manually wrapped in QueryClientProvider + MemoryRouter. Replaced with `renderWithProviders` from `@/test-utils` and API-level mocks for `fetchOnboardingStatus`, `patchOnboardingStep`, and `resetOnboarding`.

Key changes:
- All assertions that depend on fetched data now use `await screen.findByTestId()` (async) since React Query loads data asynchronously
- Error test pre-seeds the QueryCache with an errored state to avoid a TourProvider remount loop (Layout -> TourProvider -> useOnboardingStatus triggers refetch -> remount cycle)
- Loading test uses `mockReturnValue(new Promise(() => {}))` for perpetual loading state

**Files modified:** `frontend/src/__tests__/OnboardingGuard.test.tsx`

### Task 2: Rewrite WelcomePage.test.tsx (754bc37)

Removed the `vi.mock("react-router-dom")` block and `mockNavigate` spy. Replaced inline `createQueryClient` + manual QueryClientProvider/MemoryRouter wrapper with `renderWithProviders`. Fixed the stale "Settings > Profile" text assertion from `/update anytime in Settings/` to `/update anything later in Settings/` to match the actual component text. Navigation assertion now uses Routes-based rendering: the "/" route renders a `pipeline-redirect` test ID element, and clicking the CTA navigates there.

All three API-level mocks (`@/api/onboarding`, `@/api/profiles`, `@/api/skills`) were already correct per D-04 and kept unchanged.

**Files modified:** `frontend/src/__tests__/WelcomePage.test.tsx`

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | 8b8289d | test(06-03): rewrite OnboardingGuard tests -- mock API not hooks (D-04) |
| 2 | 754bc37 | test(06-03): rewrite WelcomePage tests -- remove useNavigate mock, fix Settings text |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TourProvider remount loop on error test**
- **Found during:** Task 1
- **Issue:** When OnboardingGuard renders `<Layout />` on error, Layout contains TourProvider which also calls `useOnboardingStatus()`. The new observer subscription triggers a refetch, which errors again, causing OnboardingGuard to remount Layout, creating an infinite loop where the component never settles into error state.
- **Fix:** Pre-seed the QueryCache with an errored query state (status: "error", fetchStatus: "idle") before rendering, preventing the refetch-on-subscribe cycle.
- **Files modified:** `frontend/src/__tests__/OnboardingGuard.test.tsx`
- **Commit:** 8b8289d

## Verification

- `cd frontend && npx vitest run src/__tests__/OnboardingGuard.test.tsx` -- 4 tests pass
- `cd frontend && npx vitest run src/__tests__/WelcomePage.test.tsx` -- 21 tests pass
- Both files run together: 25 tests pass (0 failures)
- OnboardingGuard.test.tsx contains `vi.mock("@/api/onboarding"` (not hooks)
- WelcomePage.test.tsx does NOT contain `vi.mock("react-router-dom"` or `mockNavigate`
- Both files use `renderWithProviders` from `@/test-utils`
- Settings text assertion matches actual component: `/update anything later in Settings/`

## Self-Check: PASSED

- [x] `frontend/src/__tests__/OnboardingGuard.test.tsx` exists and passes 4 tests
- [x] `frontend/src/__tests__/WelcomePage.test.tsx` exists and passes 21 tests
- [x] Commit 8b8289d exists in git log
- [x] Commit 754bc37 exists in git log
- [x] No hook-level mocking in OnboardingGuard tests
- [x] No router-level mocking in WelcomePage tests
