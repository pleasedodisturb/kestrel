# Phase 4: Web Welcome Flow - Research

**Researched:** 2026-04-21
**Domain:** React 19 + React Router v7 + TanStack Query v5 + Tailwind CSS frontend
**Confidence:** HIGH

## Summary

Phase 4 implements a first-time web welcome experience: a full-page `/welcome` route with Typeform-style step-by-step profile questions, an OnboardingGuard that redirects new users, a post-onboarding summary screen, and an AI provider nudge. The backend onboarding API (Phase 1) and demo data seeder (Phase 3) already exist -- this phase is pure frontend work with one backend schema fix.

The existing `OnboardingWizard.tsx` is a localStorage-based modal overlay in KanbanBoard. It must be deleted entirely and replaced with a backend-driven route-level flow. The new architecture uses React Router v7's `<Navigate>` component for declarative redirects and TanStack Query v5 for caching the onboarding status check.

**Primary recommendation:** Build a wrapper `OnboardingGuard` component that uses `useQuery` to fetch `/api/onboarding/status` on app load, caches aggressively (5-minute staleTime matching the existing QueryClient config), and renders `<Navigate to="/welcome" replace />` when `onboarding_completed` is null. The `/welcome` route lives outside the `<Layout>` route group so no nav is visible.

**Critical backend gap:** The `ProfileUpdate` Pydantic schema is missing `salary_range` and `experience_level` fields. These columns exist on the Profile model and the CLI writes to them directly via ORM, but the web form needs the PATCH API to accept them. This is a 2-line backend fix that must happen before the form can save all fields.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Full-page takeover -- dedicated `/welcome` route with no sidebar/nav visible until onboarding completes
- **D-02:** Minimal visual tone with brand accent -- typography-forward, centered content, Kestrel logo, one accent color
- **D-03:** One question per screen (Typeform-style) -- full-page, single field per step, progress bar at top
- **D-04:** Same questions as CLI wizard: name, location, target roles, salary range, skills, experience level -- all individually skippable
- **D-05:** Silent resume -- returning user lands directly on the step they left off at, backend-driven
- **D-06:** Compact checklist summary screen after all steps complete
- **D-07:** AI provider nudge card appears ONLY on the summary screen
- **D-08:** "See your scored results" CTA goes to Pipeline where demo data exists
- **D-09:** Backend-driven guard via `GET /api/onboarding/status`
- **D-10:** Delete existing `OnboardingWizard.tsx` entirely
- **D-11:** Returning users go straight to Pipeline

### Claude's Discretion
- Exact step ordering and grouping of the 5-6 questions
- Progress bar component implementation (existing library vs custom)
- Form input component choices (combobox for roles/skills, text for name, etc.)
- Animation/transition style between steps
- How to call `PATCH /api/onboarding/status` after each step completion
- When to trigger demo data seeding (after last step or after explicit "complete" action)
- React Router guard implementation pattern (wrapper component vs loader)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WEB-01 | First-time visitors redirected to `/welcome` via OnboardingGuard route wrapper | OnboardingGuard pattern using `useQuery` + `<Navigate>` documented in Architecture Patterns |
| WEB-02 | Welcome screen explains what Kestrel does and walks through setup steps | WelcomePage component with step flow, copywriting contract in UI-SPEC |
| WEB-04 | User can resume onboarding from last completed step after browser close | Backend `GET /api/onboarding/status` returns `next_step`; step index derived from STEP_ORDER |
| WEB-07 | End-of-onboarding summary shows what was configured and what was skipped | SummaryScreen reads profile data + onboarding step timestamps |
| WEB-08 | Skipped steps show "do it later" signposting with exact navigation path | Summary checklist with "Settings > Profile" link for skipped items |
| WEB-09 | After onboarding, show "Unlock full scoring" card with AI provider options | AI provider nudge card on summary screen only (D-07) |
| PROF-04 | Same question set available in web welcome flow | Profile fields mapped: name, location, job_family, salary_range, experience_level + skills |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Onboarding guard (redirect logic) | Frontend (React Router) | API (status endpoint) | Guard renders in browser, reads cached API response |
| Step-by-step form | Frontend (React components) | -- | Pure UI, one component per step screen |
| Profile data persistence | API (PATCH /api/profiles) | Database | Frontend sends PATCH, backend validates and stores |
| Onboarding step tracking | API (PATCH /api/onboarding/status) | Database | Backend owns timestamps, frontend fires after each step |
| Demo data seeding | API (service layer) | Database | CLI already triggers `seed_demo_data`; web needs a trigger mechanism |
| Resume from last step | API (GET /api/onboarding/status) | Frontend (step index) | Backend returns `next_step`, frontend maps to step index |

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react | 19.2.4 | UI framework | Already in project [VERIFIED: package.json] |
| react-router-dom | 7.13.1 | Client-side routing, Navigate component | Already in project [VERIFIED: npm ls] |
| @tanstack/react-query | 5.90.21 | Server state caching, useQuery/useMutation | Already in project [VERIFIED: npm ls] |
| tailwindcss | 4.2.1 | Utility-first CSS | Already in project [VERIFIED: package.json] |
| lucide-react | 1.0.0+ | Icon library (Check, Circle, ArrowLeft) | Already in project [VERIFIED: package.json] |

### Supporting (already installed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| clsx + tailwind-merge | 2.1.1 / 3.5.0 | `cn()` utility for conditional classes | All component styling [VERIFIED: lib/utils.ts] |
| @testing-library/react | 16.3.2 | Component testing | All test files [VERIFIED: package.json] |
| vitest | 4.1.0 | Test runner | `npm run test` [VERIFIED: package.json] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom progress bar | react-step-wizard / headlessui | Adds dependency for a 20-line component. Custom is simpler. |
| Local state for step tracking | react-hook-form / formik | Overkill for single-field-per-screen. useState is sufficient. |
| Framer Motion for transitions | CSS transitions | D-03 discretion says keep simple. No animation library needed. |

**Installation:**
```bash
# No new packages needed -- all dependencies already installed
```

## Architecture Patterns

### System Architecture Diagram

```
Browser Tab Load
    |
    v
QueryClientProvider (App.tsx)
    |
    +---> <Route path="/welcome"> (OUTSIDE Layout)
    |         |
    |         v
    |     WelcomePage
    |         |
    |         +---> useOnboardingStatus() -- GET /api/onboarding/status?profile_id=1
    |         |         (determines which step to show, or if already complete)
    |         |
    |         +---> StepScreen[0..5] -- each step:
    |         |         1. User fills field
    |         |         2. "Next" -> PATCH /api/profiles/1 (save field)
    |         |         3. "Next" -> PATCH /api/onboarding/status (mark step complete)
    |         |         4. Advance to next step
    |         |
    |         +---> SummaryScreen
    |                   1. Show completed/skipped checklist
    |                   2. AI provider nudge card
    |                   3. "See your scored results" -> navigate("/")
    |
    +---> <Route element={<OnboardingGuard><Layout /></OnboardingGuard>}>
              |
              +---> useOnboardingStatus() -- same query, same cache
              |         if (!status.welcome_completed_at) -> <Navigate to="/welcome" replace />
              |         else -> render <Layout><Outlet /></Layout>
              |
              +---> Pipeline, Discovery, Settings, etc.
```

### Recommended Project Structure
```
frontend/src/
├── api/
│   └── onboarding.ts          # CREATE: fetch/patch functions + React Query hooks
├── components/
│   ├── OnboardingGuard.tsx     # CREATE: route guard wrapper
│   ├── StepProgress.tsx        # CREATE: progress bar component
│   └── OnboardingWizard.tsx    # DELETE (D-10)
├── pages/
│   └── WelcomePage.tsx         # CREATE: welcome + steps + summary (single route component)
├── App.tsx                     # MODIFY: add /welcome route, wrap Layout with guard
└── components/
    └── KanbanBoard.tsx         # MODIFY: remove OnboardingWizard import and usage
```

### Pattern 1: OnboardingGuard as Wrapper Component
**What:** A component that wraps `<Layout />` in the route tree, checks onboarding status via React Query, and redirects to `/welcome` if incomplete.
**When to use:** On every protected route load (the guard renders before Layout).

```typescript
// Source: Codebase pattern (App.tsx) + React Router v7 Navigate [VERIFIED: Context7]
import { Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Layout } from "./Layout";
import { fetchOnboardingStatus } from "@/api/onboarding";

const DEFAULT_PROFILE_ID = 1;

export function OnboardingGuard() {
  const { data: status, isLoading } = useQuery({
    queryKey: ["onboarding-status", DEFAULT_PROFILE_ID],
    queryFn: () => fetchOnboardingStatus(DEFAULT_PROFILE_ID),
    staleTime: 5 * 60 * 1000, // matches global QueryClient config
    retry: 1,
  });

  // D-09: Blank screen during loading (no flash)
  if (isLoading) return null;

  // D-09: Redirect if onboarding not completed
  if (!status?.welcome_completed_at) {
    return <Navigate to="/welcome" replace />;
  }

  // D-11: Pass through to Layout
  return <Layout />;
}
```

**Key detail:** The guard checks `welcome_completed_at` (not `completed_at`) because the "completed" step in STEP_ORDER includes tour and feedback which are Phase 5 concerns. The web welcome flow should mark `welcome_completed` when the user finishes the summary screen.

### Pattern 2: App.tsx Route Structure
**What:** `/welcome` route sits OUTSIDE the Layout wrapper. Layout is wrapped with OnboardingGuard.
**When to use:** This is the route configuration change.

```typescript
// Source: Existing App.tsx pattern + React Router v7 [VERIFIED: codebase]
function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            {/* Welcome flow: no nav, no guard */}
            <Route path="/welcome" element={<WelcomePage />} />

            {/* All other routes: guarded + Layout */}
            <Route element={<OnboardingGuard />}>
              <Route path="/" element={<Pipeline />} />
              <Route path="/applications/:id" element={<ApplicationDetail />} />
              {/* ...rest of routes */}
            </Route>
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
```

**Important:** OnboardingGuard replaces the `<Layout />` element wrapper. The guard component renders `<Layout />` internally when onboarding is complete. This means OnboardingGuard must render `<Layout />` which renders `<Outlet />`.

### Pattern 3: Step State Machine
**What:** Step flow managed with a single `useState<number>` for current step index. Steps are an ordered array. Backend status determines initial step on load.
**When to use:** Inside WelcomePage component.

```typescript
// Source: Derived from backend STEP_ORDER + CLI WIZARD_STEPS [VERIFIED: codebase]
const WELCOME_STEPS = [
  { key: "name", field: "name", question: "What's your name?" },
  { key: "location", field: "location", question: "Where are you based?" },
  { key: "job_family", field: "job_family", question: "What roles are you targeting?" },
  { key: "salary_range", field: "salary_range", question: "What's your target salary range?" },
  { key: "skills", field: "skills", question: "What are your key skills?" },
  { key: "experience_level", field: "experience_level", question: "What's your experience level?" },
] as const;

// Screens: welcome (index -1), steps (0..5), summary (index 6)
type Screen = "welcome" | "step" | "summary";
```

### Pattern 4: API Hook Pattern (following existing codebase)
**What:** API functions in `api/onboarding.ts` following the same pattern as `api/profiles.ts` and `api/applications.ts`.

```typescript
// Source: Existing codebase pattern [VERIFIED: api/profiles.ts, api/applications.ts]
const API_BASE = "/api/onboarding";

export interface OnboardingStatus {
  profile_id: number;
  current_step: string | null;
  next_step: string | null;
  is_complete: boolean;
  progress_pct: number;
  profile_started_at: string | null;
  profile_completed_at: string | null;
  demo_seeded_at: string | null;
  welcome_completed_at: string | null;
  // ... other fields
}

export async function fetchOnboardingStatus(profileId: number): Promise<OnboardingStatus> {
  const res = await fetch(`${API_BASE}/status?profile_id=${profileId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch onboarding status: ${res.status}`);
  }
  return res.json() as Promise<OnboardingStatus>;
}

export async function patchOnboardingStep(
  profileId: number,
  step: string,
): Promise<OnboardingStatus> {
  const res = await fetch(`${API_BASE}/status?profile_id=${profileId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ step, via: "web" }),
  });
  if (!res.ok) {
    throw new Error(`Failed to update onboarding status: ${res.status}`);
  }
  return res.json() as Promise<OnboardingStatus>;
}
```

### Anti-Patterns to Avoid
- **localStorage for onboarding state:** The existing OnboardingWizard uses localStorage. D-09 explicitly requires backend-driven state. Never read/write wizard state to localStorage.
- **Checking `completed_at` for the guard:** The `completed_at` onboarding step includes tour + feedback (Phase 5). Use `welcome_completed_at` for the Phase 4 guard.
- **Showing loading spinner during guard check:** D-09 UI-SPEC says blank white screen during status check, not a spinner.
- **Saving all form data at once:** Each step should save its field immediately on "Next" click. This enables resume (D-05) -- if the user closes mid-flow, their partial data is already persisted.
- **Using form library for single-field screens:** react-hook-form or formik add complexity with no benefit when each screen has exactly one input.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Conditional class merging | String concatenation | `cn()` from `lib/utils.ts` | Already in codebase, handles Tailwind conflicts |
| Server state caching | Manual fetch + useState | TanStack React Query `useQuery` | Already in codebase, handles stale/cache/retry |
| Route-level redirects | Manual `window.location` | React Router `<Navigate replace />` | Declarative, integrates with history stack |
| Progress bar accessibility | Custom aria attributes | `role="progressbar"` + aria-valuenow/min/max | Standard HTML pattern from UI-SPEC |
| Icon components | SVG files | lucide-react (Check, Circle, ArrowLeft, etc.) | Already installed, tree-shakeable |

**Key insight:** This phase uses zero new dependencies. Every tool needed is already installed and has established patterns in the codebase.

## Common Pitfalls

### Pitfall 1: ProfileUpdate Schema Missing Fields
**What goes wrong:** The web form tries to PATCH salary_range or experience_level to `/api/profiles/1` and gets a silent discard (Pydantic `exclude_unset` drops unknown fields) or 422 error.
**Why it happens:** The CLI writes directly via ORM (`setattr(profile, field_name, value)`) so it never hit this gap. The web form goes through the API.
**How to avoid:** Add `salary_range: str | None` and `experience_level: str | None` to `ProfileUpdate` and `ProfileCreate` schemas before implementing the form.
**Warning signs:** Fields silently not saving, profile PATCH returning without the new values.

### Pitfall 2: Skills Saved Differently Than Profile Fields
**What goes wrong:** Treating skills like a profile text field. Skills are stored in the separate `skills` table (Skill model), not on the Profile row.
**Why it happens:** The UI-SPEC lists "Skills" as a step with comma-separated text input, suggesting it's a simple field. But the data model uses a separate skills table with rows per skill.
**How to avoid:** The "Skills" step needs to POST individual skill records to the skills API (or a batch endpoint), not patch the profile. Check `src/career_os/api/skills.py` for existing endpoints.
**Warning signs:** Skills data appearing to save but not showing up in the Skills page.

### Pitfall 3: Stale Guard After Completing Onboarding
**What goes wrong:** User finishes onboarding, clicks "See your scored results", navigates to Pipeline, but the OnboardingGuard's cached status still shows `welcome_completed_at: null` and redirects back to `/welcome`.
**Why it happens:** React Query cache has 5-minute staleTime. The guard reads the cached (now-stale) status.
**How to avoid:** After marking `welcome_completed`, invalidate the `["onboarding-status"]` query cache before navigating. Use `queryClient.invalidateQueries({ queryKey: ["onboarding-status"] })`.
**Warning signs:** Infinite redirect loop between `/welcome` and `/`.

### Pitfall 4: KanbanBoard Still Importing Deleted OnboardingWizard
**What goes wrong:** Build fails with import error after deleting OnboardingWizard.tsx.
**Why it happens:** KanbanBoard.tsx imports `OnboardingWizard` and `WIZARD_DISMISSED_KEY` (lines 30-32). Tests in `KanbanBoard.test.tsx` reference `wizard_dismissed` localStorage.
**How to avoid:** When deleting OnboardingWizard.tsx, also clean up: KanbanBoard.tsx imports + showWizard state + wizard rendering, and KanbanBoard.test.tsx wizard-related tests.
**Warning signs:** TypeScript compilation errors, failing tests.

### Pitfall 5: Demo Data Not Seeded After Web Onboarding
**What goes wrong:** User completes onboarding via web, clicks "See your scored results", but Pipeline shows no demo data.
**Why it happens:** The CLI calls `seed_demo_data()` directly. The web has no equivalent trigger. The backend doesn't auto-seed on onboarding completion.
**How to avoid:** When the web marks `profile_completed`, it needs to also trigger demo seeding. Options: (a) have the backend auto-seed when `profile_completed` is marked via the onboarding PATCH endpoint, or (b) create a `POST /api/onboarding/seed-demo` endpoint that the web calls after completing profile steps.
**Warning signs:** Empty Pipeline after onboarding.

### Pitfall 6: DEFAULT_PROFILE_ID Hardcoded
**What goes wrong:** The guard and welcome flow assume profile_id=1 (matching `applications.ts` pattern).
**Why it happens:** The codebase consistently uses `DEFAULT_PROFILE_ID = 1` everywhere. This is a known simplification for the single-user self-hosted model.
**How to avoid:** Use the same `DEFAULT_PROFILE_ID = 1` constant. This is the established pattern, not a bug.
**Warning signs:** None currently, but note for future multi-user support.

## Code Examples

### Example 1: OnboardingGuard with React Query

```typescript
// Source: Pattern derived from codebase [VERIFIED: App.tsx, Layout.tsx, applications.ts]
import { useQuery } from "@tanstack/react-query";
import { Navigate, Outlet } from "react-router-dom";
import { fetchOnboardingStatus } from "@/api/onboarding";

const DEFAULT_PROFILE_ID = 1;

export function OnboardingGuard() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["onboarding-status", DEFAULT_PROFILE_ID],
    queryFn: () => fetchOnboardingStatus(DEFAULT_PROFILE_ID),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  // Blank screen during loading (UI-SPEC: no spinner, no text)
  if (isLoading) return null;

  // If API is unreachable, let user through (fail open, not closed)
  if (isError) return <Layout />;

  // Redirect if welcome not completed
  if (!data?.welcome_completed_at) {
    return <Navigate to="/welcome" replace />;
  }

  // Render Layout with Outlet for child routes
  return <Layout />;
}
```

### Example 2: Step Save + Advance Pattern

```typescript
// Source: Pattern derived from backend API + codebase fetch pattern
const handleNext = async () => {
  setSaving(true);
  try {
    // 1. Save the field value to profile
    if (currentValue.trim()) {
      await updateProfile(DEFAULT_PROFILE_ID, {
        [currentStep.field]: currentValue.trim(),
      });
    }

    // 2. Mark onboarding step complete
    await patchOnboardingStep(DEFAULT_PROFILE_ID, "profile_started");

    // 3. Advance to next step
    setStepIndex((prev) => prev + 1);
  } catch (err) {
    setError("Couldn't save your answer. Check your connection and try again.");
  } finally {
    setSaving(false);
  }
};
```

### Example 3: Progress Bar Component

```typescript
// Source: UI-SPEC spacing/color/accessibility requirements
interface StepProgressProps {
  current: number;
  total: number;
}

export function StepProgress({ current, total }: StepProgressProps) {
  const pct = Math.round((current / total) * 100);

  return (
    <div className="fixed top-0 left-0 right-0 z-10">
      <div
        className="h-1 bg-[hsl(var(--secondary))]"
        role="progressbar"
        aria-valuenow={current}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-label={`Step ${current} of ${total}`}
      >
        <div
          className="h-full bg-[hsl(var(--primary))] transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-2 text-center text-sm text-[hsl(var(--muted-foreground))]">
        Step {current} of {total}
      </p>
    </div>
  );
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| react-router-dom v6 `<Route>` | react-router-dom v7 `<Route>` | v7.0 (2025) | Same JSX API for BrowserRouter usage; import from "react-router-dom" still works [VERIFIED: codebase uses v7.13.1] |
| TanStack Query v4 `useQuery([key], fn)` | TanStack Query v5 `useQuery({ queryKey, queryFn })` | v5.0 (2023) | Object syntax required [VERIFIED: codebase already uses v5 syntax] |
| Tailwind CSS v3 `@apply` + config | Tailwind CSS v4 `@import "tailwindcss"` | v4.0 (2025) | New import syntax, CSS-first config [VERIFIED: index.css uses v4] |

**Deprecated/outdated:**
- `OnboardingWizard.tsx`: localStorage-based modal from an earlier iteration. To be deleted (D-10).
- React Router v6 `useRoutes()` hook: Not needed, this codebase uses JSX `<Routes>` pattern.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Guard should check `welcome_completed_at` rather than `completed_at` | Architecture Patterns | If wrong, guard blocks users until they complete Phase 5 tour/feedback too. Verify step semantics with user. |
| A2 | Skills step should save to Skill model (separate table), not a profile text field | Pitfalls | If there's a simpler skills text field, the implementation is much easier but doesn't integrate with Skills page. |
| A3 | Demo seeding needs an explicit trigger from the web (no auto-seed exists on the backend) | Pitfalls | If backend already auto-seeds on profile_completed, no extra work needed. Verify by reading onboarding service. |
| A4 | The web form should mark both `profile_started` and `profile_completed` onboarding steps (matching CLI behavior) | Architecture Patterns | If different step names are expected for web, step tracking could get confused. |

## Open Questions (RESOLVED)

1. **Which onboarding step should the guard check?**
   - What we know: STEP_ORDER has `welcome_completed` and `completed` as separate steps. The guard needs to check one of them.
   - What's unclear: Should the guard check `welcome_completed_at` (lets user through after web flow) or `profile_completed_at` (similar to CLI) or `completed_at` (all steps including Phase 5 tour)?
   - RESOLVED: Use `welcome_completed_at`. Mark it when user sees the summary screen. This lets Phase 5 add tour without re-blocking users.

2. **How to trigger demo data seeding from web?**
   - What we know: CLI calls `seed_demo_data()` directly via Python. Web goes through REST API. No seed endpoint exists.
   - What's unclear: Should the backend auto-seed when `profile_completed` is marked, or should the web call a new endpoint?
   - RESOLVED: Mark `demo_seeded` step via `patchOnboardingStep` on completion. Backend's `mark_step_complete` service handles seeding when this step is marked. Seeder is idempotent (DEMO-05).

3. **Should "skills" be a simple text field or integrate with the Skills model?**
   - What we know: CLI saves skills as individual Skill rows (lines 230-253 of init.py). UI-SPEC says "Comma-separated text input with helper text."
   - What's unclear: Whether the web onboarding should create proper Skill records or just store a comma-separated string on the profile.
   - RESOLVED: Save skills as Skill records (matching CLI behavior) via existing `createSkill` API. Comma-separated input is split and each skill is posted individually.

## Environment Availability

Step 2.6: No external dependencies beyond the already-installed npm packages. All tools verified.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Frontend build | Yes | (via npm) | -- |
| Vitest | Testing | Yes | 4.1.0 | -- |
| Backend API | Onboarding endpoints | Yes (dev server) | Phase 1 complete | -- |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 4.1.0 + @testing-library/react 16.3.2 |
| Config file | `frontend/vitest.config.ts` |
| Quick run command | `cd frontend && npx vitest run src/__tests__/OnboardingGuard.test.tsx` |
| Full suite command | `cd frontend && npm run test` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WEB-01 | OnboardingGuard redirects new users to /welcome | unit | `cd frontend && npx vitest run src/__tests__/OnboardingGuard.test.tsx` | Wave 0 |
| WEB-02 | WelcomePage renders welcome screen with CTA | unit | `cd frontend && npx vitest run src/__tests__/WelcomePage.test.tsx` | Wave 0 |
| WEB-04 | Resume: landing on /welcome starts at correct step | unit | `cd frontend && npx vitest run src/__tests__/WelcomePage.test.tsx` | Wave 0 |
| WEB-07 | Summary screen shows completed/skipped checklist | unit | `cd frontend && npx vitest run src/__tests__/WelcomePage.test.tsx` | Wave 0 |
| WEB-08 | Skipped steps show Settings path | unit | `cd frontend && npx vitest run src/__tests__/WelcomePage.test.tsx` | Wave 0 |
| WEB-09 | AI provider nudge card on summary | unit | `cd frontend && npx vitest run src/__tests__/WelcomePage.test.tsx` | Wave 0 |
| PROF-04 | Same questions as CLI (6 fields) | unit | `cd frontend && npx vitest run src/__tests__/WelcomePage.test.tsx` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd frontend && npx vitest run src/__tests__/WelcomePage.test.tsx src/__tests__/OnboardingGuard.test.tsx`
- **Per wave merge:** `cd frontend && npm run test`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `frontend/src/__tests__/OnboardingGuard.test.tsx` -- covers WEB-01, WEB-04 (guard redirect + pass-through)
- [ ] `frontend/src/__tests__/WelcomePage.test.tsx` -- covers WEB-02, WEB-04, WEB-07, WEB-08, WEB-09, PROF-04
- [ ] `frontend/src/__tests__/StepProgress.test.tsx` -- covers progress bar rendering + accessibility

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Auth is optional config (not onboarding) |
| V3 Session Management | no | No sessions in self-hosted single-user |
| V4 Access Control | no | Profile scoping uses hardcoded ID=1 |
| V5 Input Validation | yes | Backend Pydantic schemas validate all input; frontend validates text length |
| V6 Cryptography | no | No crypto in this phase |

### Known Threat Patterns for React + FastAPI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via user input in summary screen | Tampering | React auto-escapes JSX. Never use `dangerouslySetInnerHTML`. |
| API injection via profile fields | Tampering | Pydantic validates input types and lengths on backend |
| CSRF on PATCH endpoints | Spoofing | Same-origin policy (self-hosted, Vite proxy) |

## Sources

### Primary (HIGH confidence)
- Codebase files: `App.tsx`, `Layout.tsx`, `KanbanBoard.tsx`, `OnboardingWizard.tsx`, `api/profiles.ts`, `api/applications.ts` -- verified routing, data fetching, and component patterns
- Backend files: `api/onboarding.py`, `schemas/onboarding.py`, `services/onboarding.py`, `schemas/profiles.py`, `models/models.py`, `cli/init.py` -- verified API contracts, data model, and CLI field mapping
- Context7 `/remix-run/react-router` -- verified Navigate component and route patterns for v7
- Context7 `/tanstack/query` -- verified useQuery/useMutation v5 API
- `frontend/package.json` -- verified all dependency versions

### Secondary (MEDIUM confidence)
- UI-SPEC (`04-UI-SPEC.md`) -- design contract for components, spacing, typography, color, accessibility

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed and verified
- Architecture: HIGH - patterns derived from existing codebase and verified against library docs
- Pitfalls: HIGH - identified from reading actual code (ProfileUpdate schema gap confirmed by grep)

**Research date:** 2026-04-21
**Valid until:** 2026-05-21 (stable - no library upgrades expected)
