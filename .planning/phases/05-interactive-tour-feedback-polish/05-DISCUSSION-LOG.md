# Phase 5: Interactive Tour, Feedback, and Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-21
**Phase:** 05-interactive-tour-feedback-polish
**Areas discussed:** Guided tour design, Empty state coaching, Feedback button, Non-dev docs page, Tour accessibility, Tour state persistence, Feedback button styling, Help page in nav

---

## Guided Tour Design

### Tour Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Auto after onboarding | Tour launches automatically when user first lands on Pipeline after completing the welcome flow. One-time only. | ✓ |
| Manual button | User clicks a 'Take a tour' button. No auto-launch. | |
| Both | Auto-launches on first visit, plus 'Replay tour' option. | |

**User's choice:** Auto after onboarding

### Tour Path

| Option | Description | Selected |
|--------|-------------|----------|
| Pipeline -> Discovery -> Scoring | Core workflow, 5-7 stops. Matches success criteria. | ✓ |
| All main tabs | Pipeline, Discovery, Contacts, Skills, More. 10+ stops. | |
| Pipeline only | Just kanban board. 3-4 stops. | |

**User's choice:** Pipeline -> Discovery -> Scoring

### Tooltip Style

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal popover | Small tooltip, 1-2 sentences, highlight on target, Next/Skip. | ✓ |
| Card overlay | Larger card with title, description, icon. | |
| You decide | Claude picks based on defaults and design system. | |

**User's choice:** Minimal popover

### Shepherd.js Fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Custom tooltips | Build with Radix/Tailwind popovers and step manager hook. No external dep. | ✓ |
| Try Shepherd first | Install and test, fall back if broken. | |
| React Joyride | Alternative library (rejected in earlier research). | |

**User's choice:** Custom tooltips -- skip Shepherd.js entirely

---

## Empty State Coaching

### Component Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Shared EmptyState component | Reusable component with icon/heading/description/CTA props. | ✓ |
| Custom per page | Each page has inline empty state. More flexibility, more duplication. | |
| You decide | Claude picks. | |

**User's choice:** Shared EmptyState component

### Tone

| Option | Description | Selected |
|--------|-------------|----------|
| Coaching | Warm, action-oriented: points to next action. | ✓ |
| Minimal | Terse fact + CTA. | |
| Educational | Explains what section does. | |

**User's choice:** Coaching tone

---

## Feedback Button

### What It Opens

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-filled GitHub issue URL | Opens GH new issue with template + system info. | ✓ |
| In-app form | Modal/slide-out form creating GH issue via API. | |
| Mailto link | Opens email client. | |

**User's choice:** Pre-filled GitHub issue URL

### End-of-Onboarding Prompt

| Option | Description | Selected |
|--------|-------------|----------|
| On the summary screen | Small link below Pipeline CTA on existing summary. | ✓ |
| Separate screen after summary | Additional screen in the flow. | |
| Toast after Pipeline loads | Dismissible notification. | |

**User's choice:** On the summary screen

---

## Non-Dev Docs Page

### Location

| Option | Description | Selected |
|--------|-------------|----------|
| In-app /help page | Route in web UI, accessible from More tab. | ✓ |
| Markdown in repo docs/ | GETTING-STARTED.md on GitHub. | |
| Both | In-app page rendering same markdown. | |

**User's choice:** In-app /help page

### Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Terminal basics + Kestrel commands | What is a terminal, how to open it, key commands. 1-page. | ✓ |
| Full onboarding walkthrough | Step-by-step with screenshots. | |
| You decide | Claude determines scope. | |

**User's choice:** Terminal basics + Kestrel commands

---

## Tour Accessibility (WEB-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Full WCAG 2.1 AA | Focus trap, Escape dismiss, aria-live, skip button. | ✓ |
| Basic keyboard support | Tab to navigate, Escape to close. No aria-live. | |
| You decide | Match existing codebase patterns. | |

**User's choice:** Full WCAG 2.1 AA

## Tour State Persistence

| Option | Description | Selected |
|--------|-------------|----------|
| Backend via tour_completed_at | Existing field in onboarding_state. Survives browser clears. | ✓ |
| localStorage flag | Simple boolean. Faster but doesn't sync. | |
| No persistence | Auto-launches every time. | |

**User's choice:** Backend via tour_completed_at

## Feedback Button Styling

| Option | Description | Selected |
|--------|-------------|----------|
| Small icon button | Circular, bottom-right, tooltip on hover. | ✓ |
| Icon + label | 'Feedback' text next to icon. More discoverable. | |
| Text link in footer | Most subtle, easy to miss. | |

**User's choice:** Small icon button

## Help Page in Nav

| Option | Description | Selected |
|--------|-------------|----------|
| More tab | 'Getting Started' link in More tab. | ✓ |
| Header help icon | '?' icon in top header. Always visible. | |
| Both | More tab + header icon. | |

**User's choice:** More tab

---

## Claude's Discretion

- Tour step content (exact tooltip copy)
- Tour highlight/overlay CSS approach
- EmptyState component icon choices
- System info collected for feedback pre-fill
- Help page content and formatting
- Radix Popover vs simpler custom tooltip
- Tour step animations

## Deferred Ideas

None
