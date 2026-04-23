# Phase 5: Interactive Tour, Feedback, and Polish - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Post-onboarding engagement layer: a guided tour of the actual UI after onboarding completes, empty state coaching on data-less pages, a persistent feedback button on all pages, an end-of-onboarding feedback prompt, and a non-developer help page. This phase does NOT add new features to existing pages -- it layers guidance, coaching, and feedback on top of what exists.

</domain>

<decisions>
## Implementation Decisions

### Guided Tour
- **D-01:** Auto-launch after onboarding -- tour starts automatically when user first lands on Pipeline after completing the welcome flow. One-time only, never re-triggers after completion.
- **D-02:** Tour path: Pipeline -> Discovery -> Scoring. Core workflow only, 5-7 stops. Matches WEB-05 success criteria. Does NOT cover all tabs (avoids drop-off from long tours).
- **D-03:** Minimal popover tooltips -- small tooltip with 1-2 sentences, highlight on target element, Next/Skip buttons. Matches the minimal design language from Phase 4.
- **D-04:** Custom implementation (no Shepherd.js) -- build lightweight tour with Radix/Tailwind popovers and a step manager hook. No external dependency, full control, guaranteed React 19 compatibility. Shepherd.js + React 19 concurrent mode was flagged as unverified risk.
- **D-05:** Full WCAG 2.1 AA accessibility -- focus trapped in tooltip, Escape to dismiss, aria-live for step changes, skip button always visible. Keyboard-navigable throughout. Required by WEB-06.
- **D-06:** Tour completion tracked via backend `tour_completed_at` field (already exists in onboarding_state from Phase 1). Tour only auto-launches if this field is null. Survives browser clears and works cross-device.

### Empty State Coaching
- **D-07:** Shared `EmptyState` component -- one reusable component with props for icon, heading, description, and CTA button. Each page (Pipeline, Discovery, Contacts, Skills) passes different content but gets consistent styling.
- **D-08:** Coaching tone -- warm, action-oriented messages that point to the next action. Example: "No jobs in your pipeline yet. Start by discovering jobs that match your profile." Not terse, not overly educational.

### Feedback
- **D-09:** Pre-filled GitHub issue URL -- feedback button opens GitHub new issue page with template pre-filled with OS, Python version, Kestrel version, current page. User types feedback and submits. Matches FB-02.
- **D-10:** Small circular icon button (message/chat icon), bottom-right corner of all pages. Tooltip on hover says "Send feedback". Minimal, non-intrusive. Lives in Layout.tsx so it's global.
- **D-11:** End-of-onboarding feedback prompt on the summary screen -- small "How was setup?" link below the Pipeline CTA on the existing WelcomePage summary screen. Non-intrusive, reuses existing screen (no new screen added to the flow).

### Non-Developer Docs
- **D-12:** In-app `/help` route -- a page in the web UI accessible from the More tab. Always available, no context switching to external docs.
- **D-13:** Scope: terminal basics + Kestrel commands -- what is a terminal, how to open it on macOS/Linux/WSL, what `pip install` does, key commands (`kestrel init`, `kestrel pipeline`, `kestrel doctor`). Single-page reference, warm teaching tone with analogies.
- **D-14:** Navigation: "Getting Started" link in the More tab. Not in the main nav or header to avoid clutter. Visible only after onboarding completes (not during welcome flow).

### Claude's Discretion
- Tour step content (exact tooltip copy for each stop)
- Tour highlight/overlay implementation (CSS backdrop, border highlight, etc.)
- EmptyState component icon choices per page
- Exact system info collected for feedback pre-fill
- Help page markdown content and formatting
- Whether to use Radix Popover or a simpler custom tooltip for tour
- Animation/transition between tour steps

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 4 Deliverables (this phase builds on)
- `frontend/src/pages/WelcomePage.tsx` -- Summary screen where D-11 feedback prompt goes
- `frontend/src/components/OnboardingGuard.tsx` -- Guard pattern; tour trigger checks similar state
- `frontend/src/components/Layout.tsx` -- Global layout where D-10 feedback button goes
- `frontend/src/App.tsx` -- Route definitions; /help page route goes here

### Backend Onboarding State (Phase 1)
- `src/career_os/api/onboarding.py` -- `GET/PATCH /api/onboarding/status` endpoints
- `src/career_os/services/onboarding.py` -- `mark_step_complete()` for tour_completed tracking
- `src/career_os/models/onboarding.py` -- `OnboardingState` model with `tour_completed_at` field

### Pages Needing Empty States
- `frontend/src/pages/Pipeline.tsx` -- KanbanBoard empty state
- `frontend/src/pages/Discovery.tsx` -- Discovery empty state
- `frontend/src/pages/ContactsPage.tsx` -- Contacts empty state
- `frontend/src/pages/Skills.tsx` -- Skills empty state

### Existing Components
- `frontend/src/components/StepProgress.tsx` -- Progress bar pattern (reference for tour progress)
- `frontend/src/hooks/useOnboarding.ts` -- Onboarding status hooks (reuse for tour state check)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `useOnboardingStatus` hook: Can check `tour_completed_at` to determine if tour should launch
- `patchOnboardingStep`: Can mark `tour_completed` step when tour finishes
- `StepProgress` component: Progress bar pattern that could inform tour progress indicator
- `Layout.tsx`: Global wrapper -- ideal anchor for the persistent feedback button

### Established Patterns
- React Query for all data fetching (use for profile/onboarding status checks in empty states)
- Tailwind CSS for all styling (tour tooltips, empty states, feedback button)
- `hsl(var(--...))` CSS variable pattern for theme-aware colors
- Lucide React for icons (use for empty state icons and feedback button icon)

### Integration Points
- `App.tsx` route definitions: Add `/help` route
- `Layout.tsx`: Add feedback button as a fixed-position child
- `WelcomePage.tsx` summary screen: Add feedback prompt link
- Each page component: Wrap data display in empty state check

</code_context>

<specifics>
## Specific Ideas

- Tour should feel like a continuation of the onboarding flow, not a separate experience
- Empty states should cross-link: Pipeline empty state points to Discovery, Contacts empty state explains why contacts matter for applications
- Feedback button should not overlap with any existing floating UI (check for conflicts)
- Help page tone: warm and teaching, like explaining to a friend who's never used a terminal (per docs tone feedback memory)

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 05-interactive-tour-feedback-polish*
*Context gathered: 2026-04-21*
