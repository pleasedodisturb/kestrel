---
title: Mobile UX Findings
description: Design system, interaction patterns, and UX decisions from the Kestrel Mobile exploration
---

# Mobile UX Findings — Kestrel Mobile Exploration

**Source:** `feat/lovable-app-version` branch (React Native/Expo mobile app, parked 2026-04-12)
**Status:** Extracted for web v1 responsive design. Branch preserved for future mobile work.
**Note:** The mobile app is planned for a future release. This document preserves UX findings that inform both web responsive design and the eventual mobile app.

## Why This Matters for Web

The mobile app exploration forced every screen through a "fits on 375px" constraint. These findings directly inform responsive web design — not as mobile-specific patterns, but as universal UX decisions that work better at every breakpoint.

---

## Design System Decisions

### Color & Identity
- **Primary accent:** Electric Teal `#00C9A7` — distinctive, vivid, high-energy. Not a Duolingo/Cash App copy.
- **60/30/10 split:** `#FFFFFF` (60% dominant), `#F4F6F8` (30% secondary), `#00C9A7` (10% accent)
- **Destructive:** `#FF4D6A`
- **Grade badge scale:** A=`#22C55E`, B=`#3B82F6`, C=`#EAB308`, D=`#F97316`, F=`#EF4444`
- **Light mode only for v1** — bold playful energy reads best on white backgrounds

### Typography (4-size scale)
| Role | Size | Weight | Use |
|------|------|--------|-----|
| Display | 32px | 700 | Stat numbers, hero values |
| Heading | 22px | 700 | Section headers, screen titles |
| Body | 16px | 400 | Default text, descriptions |
| Label | 14px | 400/700 | Chips, badges, meta text |

### Spacing (7-token scale)
`4, 8, 16, 24, 32, 48, 64` — all multiples of 4. Touch targets: 44px min (Apple HIG).

### Animation Personality
- **Spring presets:** bouncy (damping 8, stiffness 120), quick (damping 15, stiffness 200), lazy (damping 20, stiffness 80)
- **Cards:** bounce-in on mount with visible overshoot
- **Tab switches:** slide + slight overshoot
- **Loading:** shimmer gradient sweep across skeleton shapes
- **Pull-to-refresh:** stretchy, playful feel

---

## Interaction Patterns (Translate to Web)

### Job Discovery — Swipe → Drag-and-Drop
- **Mobile:** Swipe right = interested (green reveal + checkmark), swipe left = dismiss (red reveal + X)
- **Web translation:** Drag cards to "Interested" / "Dismiss" zones, or use button actions with same color coding
- **Undo toast:** 3.5s auto-dismiss with undo button at bottom — works on web too
- **Threshold:** 30% of card width before action triggers (fast, forgiving with undo)
- **Exit animation:** Card flies off-screen, remaining cards bounce up to fill gap

### Pipeline — Collapsible Sections
- **Active stages:** Discovered → Interested → Applied → Interviewing → Offer (auto-expand if non-empty)
- **Archived:** Accepted, Rejected, Ghosted in collapsed "Archived" section at bottom
- **Clean headers:** Stage name only, no count badges (less visual noise)
- **Cards show next step:** Grade badge + title + company + "Next: [action]" or "Updated: [date]"
- **Status change:** Bottom sheet with only valid transitions (respects backend state machine)
- **Web translation:** Accordion sections or separate tabs. Same collapsible pattern works natively with `<details>/<summary>`.

### Detail Screen — Score Visualization
- **Hero element:** Animated radar chart (6 axes, bouncy draw-in from center)
- **Grade badge:** Overlaid in center of radar chart
- **Score breakdown:** Stacked horizontal bars (green positive, red negative) with factor name + description
- **ATS keywords:** Color-coded chips (green = matched, muted = missing)
- **Unscored state:** Radar outline at zero + "Not scored yet" message
- **Shared screen:** Same detail component for both discovery jobs and pipeline applications (pipeline variant adds "Change Status" button)
- **Web translation:** Radar chart with CSS/Framer Motion or D3. Same layout works in a side panel or full page.

### Dashboard — Analytics Overview
- **3 equal stat cards:** Total applications, response rate, active count
- **Count-up animation:** Numbers count from 0 to value with spring ease on load
- **Score distribution:** Colored bar chart using grade color scale
- **Trend chart:** Line with gradient fill, last 8 weeks
- **Conversion funnel:** Mini visualization of pipeline stage flow
- **Section order:** Stats + score (above fold) → trend + funnel (below fold)
- **Single API call:** `GET /api/analytics?profile_id=N` returns everything

---

## Empty & Error States

### Tone
- **Playful, not corporate:** "Nothing to swipe yet" not "No data found"
- **Actionable hints:** Every empty state tells the user what to do next
- **Friendly errors:** "Something went sideways" with retry button, not scary stack traces

### Specific Copy (Reuse on Web)
| Screen | Heading | Body |
|--------|---------|------|
| Discovery empty | Nothing to swipe yet | Run a discovery sweep from your backend to see matches here |
| Pipeline empty | Pipeline's empty | Mark some jobs as interested to start tracking them |
| Dashboard empty | Nothing tracked yet | Start discovering and tracking jobs to see your stats here |
| Error (generic) | Something went sideways | Your server might be taking a nap. Check your connection and try again. |

---

## Card Design — Compact First

### Job Card (Discovery)
- Grade badge (colored circle with letter) on the left
- Title, company, location — that's it. Everything else on detail screen.
- **Rationale:** Score is the hero element. Compact = scan 20+ jobs fast.

### Pipeline Card (Richer)
- Same grade badge + title + company
- Plus: "Next: [step]" or "Updated: [date]" line
- **Rationale:** Pipeline is action-oriented. Users need the next step at a glance.

---

## Technical Notes for Web Implementation

- **React Query hooks:** Same `useJobs`, `useApplications`, `useAnalytics` patterns work in web React
- **Auto-generated types:** `openapi-typescript` from `/openapi.json` — use this for web too
- **Grade color utility:** `gradeColors.ts` (score → letter → hex) — copy directly to web
- **Valid transitions:** `transitions.ts` mirrors backend `VALID_TRANSITIONS` — reuse for web status change UI
- **Dismissed jobs:** AsyncStorage on mobile → localStorage on web (same pattern, different storage)

---

*Extracted from `feat/lovable-app-version` on 2026-04-12. Branch preserved for future mobile work.*
