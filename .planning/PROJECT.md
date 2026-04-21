# Kestrel Onboarding Experience

## What This Is

A first-class onboarding flow for Kestrel that takes a new user from install to seeing their first scored job results in under 10 minutes. The onboarding is user-oriented (not sales-oriented): get setup out of the way fast, help the user load their data via smart CV import, walk them through the happy path with an interactive tour, and give them a persistent feedback channel. Covers CLI wizard (`kestrel init`) and web UI welcome flow. pip and Docker install paths only for v1.

## Core Value

A user who has never seen Kestrel finishes onboarding understanding what the tool does, has their profile populated from their CV, has seen scored results proving it works, and knows where to go next -- all in under 10 minutes.

## Requirements

### Validated

(None yet -- ship to validate)

### Active

- [ ] Smart CV import: accept resume file, auto-extract roles/skills/location/preferences, confirm with user, fill gaps interactively
- [ ] Guided fallback: if CV parsing doesn't extract enough, walk through data collection step by step with skip options
- [ ] Quick install/settings phase: get pip/Docker setup out of the problem space fast, don't dwell
- [ ] Data loading: help user upload CVs, writing sample links, fill in as much profile data as possible
- [ ] "Do it later" signposting: clearly explain where users can complete/edit each data type after onboarding
- [ ] Feature overview: quick explanation of what features exist (discover, score, triage, apply, track)
- [ ] Interactive happy path tour: highlight UI elements with tooltips/popovers walking through the pipeline flow
- [ ] Pre-baked demo scoring: ship sample jobs with pre-computed scores for instant, offline, deterministic first-run experience
- [ ] Feedback channel (onboarding): end-of-onboarding screen with GitHub issue creation link and contact info
- [ ] Feedback channel (persistent): always-visible feedback button/link in the web UI
- [ ] CLI wizard (`kestrel init`): interactive profile setup that replaces manual YAML editing
- [ ] Web UI welcome flow: first-time welcome screen with guided tour and empty state coaching
- [ ] True non-dev accessibility: someone who has never used a terminal should succeed with clear, guided instructions
- [ ] Skip option for power users: entire wizard skippable for those who know what they're doing
- [ ] Error messages as solutions: every error during onboarding includes resolution steps, not stack traces

### Out of Scope

- Mobile app onboarding -- distant future, park all React Native onboarding code for now
- npx / Codespaces / Homebrew install paths -- v2+
- Live API scoring during onboarding -- pre-baked samples only, no API key required
- AI provider setup during onboarding -- deferred to post-onboarding settings
- Video/GIF walkthrough format -- using interactive tour instead
- Windows native support -- WSL2 only per existing constraints

## Context

**Existing state:**
- `setup.sh` (Docker): solid pre-flight checks but stops at "edit your config file" -- doesn't personalize or explain the product
- `config/personal.yaml.example`: user must manually edit YAML (hostile to non-devs)
- Web UI has no welcome flow -- user lands on empty dashboard with no context
- Mobile app has onboarding screens in `mobile/app/onboarding/` but mobile is parked for now
- CLI entry points exist: `kestrel` and `career` (Typer-based in `src/career_os/cli/`)

**User philosophy:**
- This is NOT a sales funnel. The user already chose to install Kestrel.
- Respect their time: get setup friction out of the way, help them load data, show it works.
- Smart import first (parse CV), guided fallback second.
- Progressive disclosure: basic scoring first, advanced features later.
- Show, don't tell: demo scoring beats explanation paragraphs.

**Design principles:**
- User-oriented, not product-oriented
- Get install/settings out of problem space quickly
- Help load as much data as possible upfront
- Always explain where to do things later
- Interactive tour over static documentation
- Persistent feedback channel, not just onboarding-time

**Linear epic:** G-392
**Depends on:** G-385 (personal data scrub) -- already shipped

## Constraints

- **Install paths**: pip + Docker only for v1
- **Target user**: True non-developer (may not know what a terminal is)
- **Time budget**: Under 10 minutes from install to scored results
- **Wizard questions**: Max 7 if smart import fails to extract enough
- **API keys**: Not required during onboarding (pre-baked demo data)
- **Existing code**: Don't break setup.sh
- **Platforms**: macOS, Ubuntu 22+, WSL2
- **Data privacy**: CV parsing must happen locally, never sent to external services

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Smart CV import as primary data loading | Minimizes manual input, respects user time | -- Pending |
| Pre-baked samples over live scoring | No API key barrier, instant results, works offline | -- Pending |
| Interactive tour over video/cards | More engaging, contextual, works with actual UI | -- Pending |
| pip + Docker only for v1 | These are the documented paths today, focus effort | -- Pending |
| True non-dev as target persona | Lowest common denominator ensures everyone succeeds | -- Pending |
| Park mobile onboarding | Mobile app is distant future, don't distract | -- Pending |
| Persistent feedback button in UI | Users should always be able to reach out, not just during onboarding | -- Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check -- still the right priority?
3. Audit Out of Scope -- reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-19 after initialization*
