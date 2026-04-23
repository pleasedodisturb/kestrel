# Phase 4: Web Welcome Flow - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-21
**Phase:** 04-web-welcome-flow
**Areas discussed:** Welcome page experience, Step flow design, Post-onboarding transition, OnboardingGuard behavior

---

## Welcome Page Experience

| Option | Description | Selected |
|--------|-------------|----------|
| Full-page takeover | Dedicated /welcome route, no sidebar/nav until onboarding complete. Clean, focused. Like Notion/Linear first-run. | ✓ |
| Side panel wizard | Dashboard visible (blurred/dimmed) with slide-in panel from right | |
| Modal overlay | Dashboard loads normally, modal wizard on top. Similar to existing OnboardingWizard.tsx | |

**User's choice:** Full-page takeover
**Notes:** None — clear preference for focused experience.

### Visual Tone

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal with brand accent | White/dark bg, centered, logo, one accent color. Typography-forward, no illustrations. | ✓ |
| Warm with subtle illustration | Light bg, bird illustration, softer fonts. Friendly but not corporate. | |
| Data-forward teaser | Blurred preview of scored results behind welcome text. Creates anticipation. | |

**User's choice:** Minimal with brand accent
**Notes:** None

---

## Step Flow Design

| Option | Description | Selected |
|--------|-------------|----------|
| One question per screen | Full-page, one field at a time. Progress bar at top. Typeform-style. | ✓ |
| Scrollable single page | All questions on one long page, submit at bottom. | |
| Card-based groups | 2-3 expandable cards. Non-linear. | |

**User's choice:** One question per screen
**Notes:** None

### Resume Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Silent resume | Returns directly to last incomplete step. No interstitial. Backend-driven. | ✓ |
| Welcome-back prompt | "Continue where you left off?" with restart option. | |
| Summary then continue | Mini-summary of progress, then continue. | |

**User's choice:** Silent resume
**Notes:** None

---

## Post-Onboarding Transition

| Option | Description | Selected |
|--------|-------------|----------|
| Compact checklist + CTA | Filled/skipped steps as checkmarks, "do it later" links to Settings, big CTA to Pipeline. | ✓ |
| Celebration + redirect | Brief animation, auto-redirect to Pipeline. Skipped items as toast. | |
| Dashboard with banner | Skip summary, redirect immediately. Banner for skipped items. | |

**User's choice:** Compact checklist + CTA
**Notes:** None

### AI Provider Nudge Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Summary screen only | "Unlock full scoring" card only on post-onboarding summary. No persistent nagging. | ✓ |
| Summary + Pipeline banner | Show on summary AND dismissible Pipeline banner. More visible but pushy. | |
| Settings page highlight | No card — just "New" badge in Settings AI Provider section. | |

**User's choice:** Summary screen only
**Notes:** None — user values non-intrusive approach for self-hosted tool.

---

## OnboardingGuard Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Backend state check | GET /api/onboarding/status — null completed timestamp = redirect. Cross-device. | ✓ |
| Backend + localStorage fallback | Same but with localStorage perf cache to avoid flash-of-redirect. | |
| Replace existing localStorage wizard | Kill OnboardingWizard.tsx, replace with backend guard. | |

**User's choice:** Backend state check
**Notes:** None

### Existing OnboardingWizard.tsx

| Option | Description | Selected |
|--------|-------------|----------|
| Delete it | localStorage-based overlay from earlier iteration. New flow replaces it. Clean break. | ✓ |
| Keep as empty-state fallback | Repurpose as Pipeline nudge for users with no real jobs. | |
| Merge into new flow | Extract CTAs into post-onboarding summary. Delete component. | |

**User's choice:** Delete it
**Notes:** None

---

## Claude's Discretion

- Step ordering, form input types, animation transitions
- Progress bar implementation, React Router guard pattern
- Demo seed trigger timing, API hook patterns

## Deferred Ideas

None
