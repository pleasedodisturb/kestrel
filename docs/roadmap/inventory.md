# Kestrel Milestone Deep Dives

> Detailed companion documents for each milestone in the [Kestrel roadmap](../../ROADMAP.md).

## How Planning Works

Kestrel organizes its work in layers, from big-picture direction down to individual tasks:

```
ROADMAP.md                 What Kestrel does and where it is heading
  docs/roadmap/            Deep dives with detail for each milestone
    BMAD PRDs              Formal product specs when a milestone enters development
      Milestones           Scoped groups of related work
        Epics              Feature-sized chunks within a milestone
          Tickets           Atomic tasks a developer picks up and completes
```

At the top is [ROADMAP.md](../../ROADMAP.md), which tells the story of what Kestrel does today and where it is heading. It is written for anyone visiting the project: users evaluating whether Kestrel fits their needs, developers looking for ways to contribute, and the maintainer keeping development coherent across sessions.

The documents in this directory are the next layer down. Each milestone in the roadmap has a companion deep dive that goes further: what the feature does in detail, how it works under the hood, which research informed the decisions, and what a formal product spec would cover. Shipped milestones describe what exists. Planned milestones describe the vision and open questions.

When a milestone moves into active development, it gets a formal product requirements document (PRD). These are created through BMAD (Build More, Architect Dreams), a product planning framework that produces structured specs covering scope, user flows, edge cases, and acceptance criteria. You do not need to know how BMAD works internally. The important thing is that each milestone gets a thorough spec before development begins.

From there, the work breaks into milestones (scoped groups of related work), epics (feature-sized chunks within a milestone), and finally tickets in the project's task tracker (the atomic units of work that a developer picks up and completes).

Most contributors enter at the deep dive level. Find a milestone that interests you, read its deep dive, and look for places where help is needed. Shipped milestones surface contribution areas through the "Want to help?" callouts in [ROADMAP.md](../../ROADMAP.md) — improvements, edge cases, new adapters, better coverage. Planned and considering milestones include "Open Questions" or "Research Needed" sections within the deep dive itself, where contribution often starts as research or design work before any code. You do not need to understand the full hierarchy to make a meaningful contribution.

## Shipped

| Milestone | Version | Description |
|-----------|---------|-------------|
| [Scoring Engine](scoring-engine.md) | v0.4 | AI scores every job against your profile |
| [Discovery Engine](discovery-engine.md) | v0.3 | Automatic job board scanning and pre-filtering |
| [AI Provider System](ai-provider-system.md) | v0.5 | Eleven providers with privacy tiers |
| [Cost Control](cost-control.md) | v0.11 | Five presets from free to custom spending |
| [Application Pipeline](application-pipeline.md) | v0.2 | Kanban board for tracking applications |
| [Web Frontend](web-frontend.md) | v0.11 | Eleven-page React interface |
| [CLI](cli.md) | v0.3 | Terminal access to your pipeline |
| [Infrastructure](infrastructure.md) | v0.12 | CI/CD, testing, and release automation |
| [Onboarding Flow](onboarding-flow.md) | v0.11 | Six-step guided first-run setup |
| [PII Safety Boundary](pii-safety-boundary.md) | v0.12 | Privacy controls for AI provider data |

## Planned

| Milestone | Version | Description |
|-----------|---------|-------------|
| [Public Roadmap](public-roadmap.md) | v0.12 | Making the project's direction visible |
| [Desktop App](desktop-app.md) | v0.13 | Download, double-click, and start scoring |
| [Browser Extension](browser-extension.md) | v0.14 | One-click job save from any site |
| [Mobile App](mobile-app.md) | v0.15 | Pipeline and scores from your phone |
| [Profile and Skills](profile-and-skills.md) | v1.0 | Honest visual map of where you stand |
| [Know Me](know-me.md) | v1.0 | Deep personal understanding beyond resume |
| [Gap Analysis and Coaching](gap-analysis-coaching.md) | v1.0 | What is missing and how to close it |
| [Voice Mode](voice-mode.md) | v1.0 | Talk to Kestrel instead of typing |
| [Hosted Version](hosted-version.md) | v1.0 | Zero-setup subscription from any browser |

## Internal

| Document | Description |
|----------|-------------|
| [Feature Flags](feature-flags.md) | Different editions, hidden features, per-deployment capabilities |
