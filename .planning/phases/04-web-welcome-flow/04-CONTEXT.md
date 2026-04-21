# Phase 4: Web Welcome Flow - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Phase Boundary

First-time web welcome experience: OnboardingGuard redirect, full-page `/welcome` route, step-by-step profile questions, post-onboarding summary with signposting, and AI provider nudge. Replaces the existing `OnboardingWizard.tsx` entirely with a backend-driven flow.

</domain>

<decisions>
## Implementation Decisions

### Welcome Page Experience
- **D-01:** Full-page takeover — dedicated `/welcome` route with no sidebar/nav visible until onboarding completes. Clean, focused, no distractions.
- **D-02:** Minimal visual tone with brand accent — typography-forward, centered content, Kestrel logo, one accent color. No illustrations. Clean like Linear's first-run.

### Step Flow Design
- **D-03:** One question per screen (Typeform-style) — full-page, single field per step, progress bar at top showing "Step N/M". Back/Next/Skip controls on each step.
- **D-04:** Same questions as CLI wizard (PROF-04): name, location, target roles, salary range, skills, experience level — all individually skippable.
- **D-05:** Silent resume — returning user lands directly on the step they left off at. No "welcome back" interstitial. Backend onboarding state (Phase 1 INF-01) drives which step to show.

### Post-Onboarding Transition
- **D-06:** Compact checklist summary screen after all steps complete — shows filled steps (checkmarks) and skipped steps (bullet with exact Settings path, e.g., "Settings > Profile"). Single big CTA: "See your scored results →" redirects to Pipeline.
- **D-07:** AI provider nudge card ("Unlock full AI scoring") appears ONLY on the summary screen — not persistent on Pipeline or anywhere else. After summary, provider setup lives in Settings. No nagging.
- **D-08:** "See your scored results" CTA goes to Pipeline where demo data (from Phase 3) is already seeded. User immediately sees the "Sample Results" banner with 10 scored jobs.

### OnboardingGuard Behavior
- **D-09:** Backend-driven guard — `GET /api/onboarding/status` checked on app load. If `onboarding_completed` timestamp is null, redirect to `/welcome`. Works across devices and browsers, no localStorage dependency.
- **D-10:** Delete existing `OnboardingWizard.tsx` entirely — it's a localStorage-based overlay from an earlier iteration. The new `/welcome` flow replaces it completely. Clean break, no dual paths.
- **D-11:** Returning users (onboarding already completed) go straight to Pipeline — guard is transparent, no redirect.

### Claude's Discretion
- Exact step ordering and grouping of the 5-6 questions
- Progress bar component implementation (existing library vs custom)
- Form input component choices (combobox for roles/skills, text for name, etc.)
- Animation/transition style between steps
- How to call `PATCH /api/onboarding/status` after each step completion
- When to trigger demo data seeding (after last step or after explicit "complete" action)
- React Router guard implementation pattern (wrapper component vs loader)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Frontend Architecture
- `frontend/src/App.tsx` — React Router routes, Layout wrapper. New `/welcome` route goes here outside the `<Layout>` wrapper (no nav during onboarding)
- `frontend/src/components/OnboardingWizard.tsx` — DELETE THIS. Existing localStorage-based overlay being replaced.
- `frontend/src/components/Layout.tsx` — Main layout with sidebar/nav. OnboardingGuard wraps this.

### Backend Onboarding API (Phase 1)
- `src/career_os/api/onboarding.py` — `GET /api/onboarding/status` and `PATCH /api/onboarding/status` endpoints
- `src/career_os/services/onboarding.py` — `mark_step_complete()` function for step tracking
- `src/career_os/schemas/onboarding.py` — Pydantic schemas for onboarding state

### Profile API
- `src/career_os/api/profiles.py` — Profile CRUD endpoints (web form submits profile data here)
- `src/career_os/schemas/profiles.py` — Profile Pydantic schemas

### Demo Data Integration (Phase 3)
- `src/career_os/migration/demo_seed.py` — `seed_demo_data()` called after onboarding completes
- Phase 3 decisions D-02 (auto-seed after init), D-14 (Sample Results banner in web)

### Data Fetching Pattern
- `frontend/src/api/` — TanStack React Query hooks. New hooks needed for onboarding status and profile mutation.

### Project Requirements
- `.planning/REQUIREMENTS.md` section Web UI — WEB-01, WEB-02, WEB-04, WEB-07, WEB-08, WEB-09
- `.planning/REQUIREMENTS.md` section Profile — PROF-04

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- TanStack React Query hooks in `frontend/src/api/` — follow this pattern for onboarding status fetching
- Tailwind CSS throughout — all styling uses Tailwind utility classes
- `lucide-react` icons already imported in OnboardingWizard.tsx
- React Router `useNavigate` for programmatic redirect

### Established Patterns
- **Pages** live in `frontend/src/pages/`, components in `frontend/src/components/`
- **API hooks** pattern: `frontend/src/api/{resource}.ts` exports `useResource()` query hooks
- **Layout wrapper** via React Router `<Route element={<Layout />}>` — new `/welcome` route should be OUTSIDE this wrapper (no nav)

### Integration Points
- `App.tsx` routes — add `/welcome` route outside `<Layout>` wrapper
- `App.tsx` or `Layout.tsx` — add OnboardingGuard that checks backend status
- Profile API — web form POSTs/PATCHes to same profile endpoints as CLI
- Onboarding API — `PATCH /api/onboarding/status` after each step complete
- Demo seeding — needs a trigger point (either backend auto-seeds when onboarding_completed is set, or web explicitly calls a seed endpoint)

</code_context>

<specifics>
## Specific Ideas

- The "See your scored results" CTA is the payoff — user lands on Pipeline with 10 pre-scored demo jobs already there. This is the "aha moment" that proves the tool works.
- Skipped items showing exact navigation paths ("Settings > Profile") means users know exactly where to go later — no hunting.
- The AI provider nudge is deliberately non-persistent. The user just installed a self-hosted tool — they don't want to be sold. One mention on the summary screen, then it's in Settings if they want it.
- Silent resume means the onboarding state API is hit on every `/welcome` load to determine which step to show. No localStorage caching — backend is the single source of truth.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-web-welcome-flow*
*Context gathered: 2026-04-21*
