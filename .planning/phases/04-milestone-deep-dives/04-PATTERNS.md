# Phase 4: Milestone Deep Dives - Pattern Map

**Mapped:** 2026-04-27
**Files analyzed:** 21 (19 deep-dive docs + 1 index rewrite + 1 ROADMAP.md edit)
**Analogs found:** 5 / 5 (all documentation-only, strong matches)

## File Classification

This is a documentation-only phase. All files are Markdown documents rendered by GitHub. No code, no build systems, no tests.

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `docs/roadmap/scoring-engine.md` | doc (shipped deep dive) | static | `docs/guides/cost-optimization.md` | exact |
| `docs/roadmap/discovery-engine.md` | doc (shipped deep dive) | static | `docs/guides/cost-optimization.md` | exact |
| `docs/roadmap/ai-provider-system.md` | doc (shipped deep dive) | static | `docs/guides/cost-optimization.md` | exact |
| `docs/roadmap/cost-control.md` | doc (shipped deep dive) | static | `docs/guides/cost-optimization.md` | exact |
| `docs/roadmap/application-pipeline.md` | doc (shipped deep dive) | static | `docs/guides/cost-optimization.md` | exact |
| `docs/roadmap/web-frontend.md` | doc (shipped deep dive) | static | `docs/guides/cost-optimization.md` | exact |
| `docs/roadmap/cli.md` | doc (shipped deep dive) | static | `docs/guides/cost-optimization.md` | exact |
| `docs/roadmap/infrastructure.md` | doc (shipped deep dive) | static | `docs/guides/cost-optimization.md` | exact |
| `docs/roadmap/onboarding-flow.md` | doc (shipped deep dive) | static | `docs/guides/cost-optimization.md` | exact |
| `docs/roadmap/pii-safety-boundary.md` | doc (shipped deep dive) | static | `docs/guides/cost-optimization.md` | exact |
| `docs/roadmap/public-roadmap.md` | doc (planned deep dive) | static | `docs/guides/cost-optimization.md` | role-match |
| `docs/roadmap/desktop-app.md` | doc (planned deep dive) | static | `docs/guides/cost-optimization.md` | role-match |
| `docs/roadmap/browser-extension.md` | doc (planned deep dive) | static | `docs/guides/cost-optimization.md` | role-match |
| `docs/roadmap/mobile-app.md` | doc (planned deep dive) | static | `docs/guides/cost-optimization.md` | role-match |
| `docs/roadmap/profile-and-skills.md` | doc (planned deep dive) | static | `docs/guides/cost-optimization.md` | role-match |
| `docs/roadmap/know-me.md` | doc (planned deep dive) | static | `docs/guides/cost-optimization.md` | role-match |
| `docs/roadmap/gap-analysis-coaching.md` | doc (planned deep dive) | static | `docs/guides/cost-optimization.md` | role-match |
| `docs/roadmap/voice-mode.md` | doc (planned deep dive) | static | `docs/guides/cost-optimization.md` | role-match |
| `docs/roadmap/hosted-version.md` | doc (planned deep dive) | static | `docs/guides/cost-optimization.md` | role-match |
| `docs/roadmap/feature-flags.md` | doc (infrastructure deep dive) | static | `docs/reference/release-pipeline.md` | role-match |
| `docs/roadmap/inventory.md` | doc (index page) | static | `docs/roadmap/inventory.md` (rewrite) | exact |
| `ROADMAP.md` | doc (roadmap, edit only) | static | `ROADMAP.md` (self) | exact |

## Pattern Assignments

### All 19 Deep-Dive Documents (shared template pattern)

All deep dives follow the same template defined in CONTEXT.md D-01/D-02. The closest analog for the tone, structure, and audience handling is `docs/guides/cost-optimization.md`.

**Analog:** `docs/guides/cost-optimization.md`

**Why this analog:** This guide is the best existing example of Kestrel's dual-audience writing. It has a warm, accessible user-facing top section with second-person tone and zero jargon, followed by increasingly technical depth. It demonstrates the exact voice these deep dives need: explains complex things simply, uses analogies ("like test-driving a car with the engine off"), avoids AI slop, and respects the reader's intelligence.

**Tone and voice pattern** (lines 1-10):
```markdown
# AI Costs and Privacy

Running AI-powered job scoring sounds expensive. It doesn't have to be. Kestrel is designed so
you can start for free, stay free as long as you want, and spend under $10/month if you decide
to pay. This guide explains how the pricing works, what "free" actually means, and what happens
to your data with each provider — because "free" doesn't always mean "no cost."
```

Key voice traits to replicate:
- Opens with what the reader cares about (the concern), not what the feature does
- Short declarative sentences mixed with longer explanatory ones
- Second person ("you") throughout
- No "seamlessly," "leverage," "robust," or other slop words
- Explains tradeoffs honestly ("What you get / What you give up" framing)

**Section heading pattern** (lines 17-30):
```markdown
## Start Free: Demo Mode

When you first install Kestrel, it runs in Demo Mode. No API key needed. The AI provider is
set to `mock`, which means scoring returns realistic-looking results generated locally — no
network calls, no tokens burned, no data leaving your machine.

Demo Mode is not a crippled trial. You can:

- Add your profile, skills, and job preferences
- Browse and filter discovered jobs
- See how the scoring pipeline works end to end
- Set up the mobile app and web dashboard
```

Key structural traits:
- Section headings are descriptive, not generic ("Start Free: Demo Mode" not "Overview")
- Lists used for concrete feature enumeration
- Paragraphs are 2-3 sentences max
- No frontmatter (unlike `docs/reference/AI-PROVIDERS.md` which has YAML frontmatter -- deep dives should NOT have frontmatter)

**Tables for structured comparison** (lines 63-69):
```markdown
| Task | Volume | Model Tier | Monthly Cost |
|------|--------|-----------|-------------|
| Job scoring | ~600/day | Budget (GPT-4o-mini) | ~$1-5 |
| Company research | ~10/week | Standard (Sonnet) | ~$5 |
| Interview prep | ~3/week | Standard (Sonnet) | ~$3 |
```

Tables are used when comparing structured data. Deep dives may use tables in contributor sections for architecture details.

---

### Shipped Deep-Dive Template Pattern

**Sources:** CONTEXT.md D-02, RESEARCH.md Template Structure section

The shipped template has these exact sections in this order. This is the canonical structure every shipped deep dive must follow.

```markdown
# [Milestone Name]

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

[1-2 sentences: what problem this solves for the user]

## What This Delivers

[2-3 paragraphs: user-facing description of capabilities. Warm second-person tone.
Present tense for current features. No file paths, no API routes.]

## How It Works

[1-2 paragraphs: simplified explanation of the approach without implementation details.
User-accessible language. "Under the hood" framing if needed.]

## Current Status

*Shipped in [vX.Y.0](../../CHANGELOG.md#anchor)*

[Brief status note: what's done, any known limitations worth mentioning]

## Related Milestones

- **[Related Milestone](related-file.md)** -- one-line relationship description
- **[Related Milestone](related-file.md)** -- one-line relationship description

---

*For Contributors*

## Architecture

[File paths, module structure, key abstractions. Can reference
.planning/codebase/ docs by description, never by link.]

## Research & Decisions

Annotated links to research and reference documents:

- [Title](../research/file.md) -- one-sentence annotation
- [Title](../reference/file.md) -- one-sentence annotation

## BMAD Integration

**PRD Status:** Not started

[What a PRD would cover for this milestone. One paragraph.]

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
```

**Word count target:** 800-1200 words per shipped deep dive.

---

### Planned Deep-Dive Template Pattern

**Sources:** CONTEXT.md D-11, RESEARCH.md Template Structure section

Adapted template for planned milestones. Same structure with section name changes.

```markdown
# [Milestone Name]

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

[1-2 sentences: what problem this will solve]

## What This Delivers

[1-2 paragraphs: future-oriented user benefit description.]

## Design Considerations

[1-2 paragraphs: key decisions that need to be made, tradeoffs to consider.
Replaces "How It Works" since nothing is built yet.]

## Current Status

*Status: Planned/Considering -- not yet started*

[Brief note on readiness, prerequisites, or dependencies]

## Related Milestones

- **[Related Milestone](related-file.md)** -- one-line relationship description

---

*For Contributors*

## Open Questions

[Bullet list of unresolved technical and design questions.
Replaces "Architecture" since nothing is built yet.]

## Research Needed

[What research should happen before building. Links to any existing
docs that are relevant, with annotations.]

## BMAD Integration

**PRD Status:** Not started

[What a PRD would cover for this milestone. One paragraph.]

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
```

**Word count target:** 500-800 words per planned deep dive.

---

### `docs/roadmap/feature-flags.md` (infrastructure deep dive, hybrid template)

**Analog:** `docs/reference/release-pipeline.md`

**Why this analog:** Feature Flags is internal infrastructure, not a user-facing milestone. `release-pipeline.md` demonstrates how to write about infrastructure in a concise, technical way with clear structure. Feature Flags uses the planned template but with a short user-facing half and longer contributor section.

**Concise infrastructure style** (lines 1-5):
```markdown
# Release Pipeline

How Kestrel gets from code to release. Every step is automated.

## Overview
```

Key traits for Feature Flags doc:
- Short, direct opening (not warm/narrative like user-facing milestones)
- User-facing half is brief: "different app editions, hide incomplete features"
- Contributor half is the substance: design considerations, open questions, implementation patterns
- Tables for structured comparison (tiers, flag types)

---

### `docs/roadmap/inventory.md` (index page, full rewrite)

**Analog:** Current `docs/roadmap/inventory.md` (7-line placeholder) + `ROADMAP.md` (table-of-contents structure)

**Current content to be replaced** (entire file, lines 1-6):
```markdown
# Feature Inventory

> Full feature inventory for Kestrel, organized by domain.
> This document is being written as part of the roadmap milestone.

_Coming soon. Track progress in [ROADMAP.md](../../ROADMAP.md)._
```

**New structure pattern** (from RESEARCH.md Index Page Template):
```markdown
# Kestrel Milestone Deep Dives

> Detailed companion documents for each milestone in the [Kestrel roadmap](../../ROADMAP.md).

## How Planning Works

[Full hierarchy chain: ROADMAP.md -> deep dives -> BMAD PRDs -> epics -> Linear tickets.
This is the ONLY place this hierarchy is explained. All 19 deep dives link back here.]

## Shipped

| Milestone | Version | Description |
|-----------|---------|-------------|
| [Scoring Engine](scoring-engine.md) | v0.4 | [one-liner] |
| ... | ... | ... |

## Planned

| Milestone | Version | Description |
|-----------|---------|-------------|
| [Desktop App](desktop-app.md) | v0.13 | [one-liner] |
| ... | ... | ... |

## Internal

| Document | Description |
|----------|-------------|
| [Feature Flags](feature-flags.md) | [one-liner] |
```

---

### `ROADMAP.md` (edit only -- inline links + Mermaid fixes)

**Analog:** `ROADMAP.md` (self -- editing existing patterns)

**Current status line pattern** (line 22 as example):
```markdown
*Status: Shipped*
```

**New status line pattern with deep-dive link** (D-06):
```markdown
*Status: Shipped* | [Deep dive](docs/roadmap/scoring-engine.md)
```

For planned milestones:
```markdown
*Status: Planned* | [Deep dive](docs/roadmap/desktop-app.md)
```

**Important:** Links from ROADMAP.md (repo root) use `docs/roadmap/` path. Links FROM deep dives TO ROADMAP.md use `../../ROADMAP.md`.

**Mermaid Gantt fix** (replace lines 184-188):
Current:
```
    section Later
    Profile and Skills       :prof, 2026-10-01, 90d
    Gap Analysis             :gap,  2027-01-01, 90d
    Writing Style Flywheel   :voice, 2027-03-01, 60d
    Hosted Version           :hosted, 2027-02-01, 60d
```

Fixed (D-18, D-19):
```
    section Later
    Profile and Skills       :prof, 2026-10-01, 90d
    Know Me                  :know, 2027-01-01, 60d
    Gap Analysis             :gap,  2027-02-01, 90d
    Voice Mode               :voice, 2027-04-01, 60d
    Hosted Version           :hosted, 2027-05-01, 60d
```

**Mermaid Flowchart fix** (replace lines 196-204):
Current:
```
flowchart LR
    A[Scoring Engine] --> B[Cost Control]
    A --> C[Discovery Engine]
    C --> D[Browser Extension]
    A --> E[Desktop App]
    E --> F[Mobile App]
    A --> G[Profile and Skills]
    G --> H[Gap Analysis and Coaching]
    H --> I[Writing Style Flywheel]
```

Fixed (D-18, D-20):
```
flowchart LR
    A[Scoring Engine] --> B[Cost Control]
    A --> C[Discovery Engine]
    C --> D[Browser Extension]
    A --> E[Desktop App]
    E --> F[Mobile App]
    A --> G[Profile and Skills]
    G --> J[Know Me]
    J --> H[Gap Analysis and Coaching]
    H --> I[Voice Mode]
    K[Feature Flags] --> L[Hosted Version]
```

**HTML comment removal** (D-21): Remove comments on lines 162 and 193-194 after fixes are applied.

---

## Shared Patterns

### Cross-Reference Link Paths

**Apply to:** All 19 deep-dive documents and ROADMAP.md edits

Relative path patterns from `docs/roadmap/`:

| Target | Relative Path |
|--------|---------------|
| ROADMAP.md | `../../ROADMAP.md` |
| CHANGELOG.md | `../../CHANGELOG.md` |
| docs/research/*.md | `../research/filename.md` |
| docs/reference/*.md | `../reference/filename.md` |
| docs/guides/*.md | `../guides/filename.md` |
| Other deep dives (same dir) | `filename.md` |
| .planning/codebase/*.md | Never link (gitignored). Reference by description only |

Relative path patterns from repo root (ROADMAP.md):

| Target | Relative Path |
|--------|---------------|
| Deep dive docs | `docs/roadmap/filename.md` |
| CHANGELOG.md | `CHANGELOG.md` |

### CHANGELOG Cross-Reference Pattern

**Source:** `ROADMAP.md` lines 23-77 and `CHANGELOG.md` lines 1-3
**Apply to:** All 10 shipped deep-dive "Current Status" sections

Pattern: `[vX.Y.0](../../CHANGELOG.md#anchor)`

| Version | Full Reference |
|---------|---------------|
| v0.2.0 | `[v0.2.0](../../CHANGELOG.md#020-2026-04-12)` |
| v0.3.0 | `[v0.3.0](../../CHANGELOG.md#030-2026-04-13)` |
| v0.4.0 | `[v0.4.0](../../CHANGELOG.md#040-2026-04-16)` |
| v0.5.0 | `[v0.5.0](../../CHANGELOG.md#050-2026-04-16)` |
| v0.11.0 | `[v0.11.0](../../CHANGELOG.md#0110-2026-04-21)` |
| v0.12.0 | `[v0.12.0](../../CHANGELOG.md#0120-2026-04-23)` |

### Annotated Research Links Pattern

**Source:** CONTEXT.md D-24
**Apply to:** All deep-dive Research & Decisions / Research Needed sections

Each link gets a one-sentence annotation. 3-8 links per deep dive. Format:

```markdown
- [Scoring Research](../research/scoring-research.md) -- Core scoring philosophy: human-first rubric design, multi-factor evaluation, and why "recommended" means balanced, not optimal
- [Scoring Validation Report](../reference/scoring-validation-report.md) -- Before/after validation data: variance dropped 15.7%, reject accuracy 100%
```

Key traits:
- Link text is the document's own title (not a description)
- Annotation after `--` describes what the doc covers and why it is relevant
- Annotations are factual, not promotional
- 3-8 links per deep dive (not exhaustive)

### BMAD Integration Boilerplate Pattern

**Source:** CONTEXT.md D-15, D-16
**Apply to:** All 19 deep-dive documents (bottom of each)

```markdown
## BMAD Integration

**PRD Status:** Not started

[One paragraph unique to this milestone describing what a PRD would cover.]

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
```

The "what a PRD would cover" paragraph must be unique per document (D-15, Pitfall 4). Examples:
- Scoring Engine: "A PRD would formalize the scoring rubric dimensions, define quality metrics for scoring accuracy, and specify the golden set regression testing approach."
- Desktop App: "A PRD would specify the installer experience, auto-update mechanism, platform support matrix, and code signing requirements."

### Breadcrumb Pattern

**Apply to:** All 19 deep-dive documents (line 3 of each)

```markdown
*Part of the [Kestrel roadmap](../../ROADMAP.md).*
```

This creates a navigation breadcrumb back to the master roadmap from every deep dive.

### Related Milestones Pattern

**Source:** CONTEXT.md D-05, RESEARCH.md Cross-Link Map
**Apply to:** All 19 deep-dive documents (bottom of user-facing half, before `---` separator)

```markdown
## Related Milestones

- **[Discovery Engine](discovery-engine.md)** -- Discovery feeds jobs into the scoring queue
- **[Cost Control](cost-control.md)** -- Cost presets configure how scoring uses AI providers
- **[AI Provider System](ai-provider-system.md)** -- Providers execute the scoring prompts
```

Each deep dive should include 2-4 entries (not the full dependency graph). Links are relative within `docs/roadmap/`.

### Tone Rules (Carry Forward)

**Apply to:** All user-facing content in all 19 deep dives and the index page

| Rule | Source |
|------|--------|
| Warm second-person tone | Phase 1 D-05, Phase 2 D-19 |
| No file paths in user-facing content | Phase 1 D-08 |
| No em dashes anywhere | Phase 3 D-08 |
| No AI slop: "seamlessly," "leverage," "revolutionize," "cutting-edge," "game-changer," "delve," "robust," "streamline," "harness" | Phase 3 D-09, Phase 4 D-23 |
| Natural variation in openers (no repetitive "You will be able to...") | Phase 3 D-06 |
| Shipped = present/past tense. Planned = future-oriented | Phase 4 D-22 |
| Private docs (`private/`) inform framing, never cited or linked | Phase 4 D-25 |

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | -- | -- | All files have adequate analogs. This is a documentation phase writing Markdown files; the existing `docs/guides/`, `docs/reference/`, and `ROADMAP.md` provide strong patterns for every document type |

---

## Metadata

**Analog search scope:** `docs/guides/`, `docs/reference/`, `docs/research/`, `docs/roadmap/`, `ROADMAP.md`, `CHANGELOG.md`
**Files scanned:** 46 (21 research docs, 11 reference docs, 13 guides, 1 roadmap inventory placeholder)
**Pattern extraction date:** 2026-04-27
