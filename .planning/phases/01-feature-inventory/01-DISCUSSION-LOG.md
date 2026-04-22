# Phase 1: Feature Inventory - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-22
**Phase:** 01-feature-inventory
**Areas discussed:** Milestone grouping, Narrative voice & depth, Honesty framing, Output structure

---

## Milestone Grouping

| Option | Description | Selected |
|--------|-------------|----------|
| Domain clusters | Group by product domain regardless of when shipped | ✓ |
| Chronological eras | Group by development eras (v0.1-0.3, v0.4-0.5, etc.) | |
| Hybrid (domains within eras) | Top-level by era, features by domain within each | |

**User's choice:** Domain clusters
**Notes:** Tells a clearer product story than version numbers. Release tags become cross-references, not the organizing principle.

---

### How many domain clusters?

| Option | Description | Selected |
|--------|-------------|----------|
| 8 domains | Scoring, Discovery, AI Providers, Pipeline, Frontend, CLI & Packaging, Infra, Integrations | ✓ |
| 6 domains (consolidated) | Merge CLI into Infra, Integrations into Pipeline | |
| Let Claude decide | Claude picks during writing | |

**User's choice:** 8 domains
**Notes:** Granular enough to be useful, not so many it fragments.

---

### Parked mobile app placement

| Option | Description | Selected |
|--------|-------------|----------|
| Separate "Parked Work" section | Distinct section after shipped domains, clearly labeled as paused | ✓ |
| Inside Web Frontend cluster | Group under broader "Frontend" cluster with status marker | |
| Let Claude decide | Place wherever reads best | |

**User's choice:** Separate "Parked Work" section

---

### Cross-domain features

| Option | Description | Selected |
|--------|-------------|----------|
| Primary domain + cross-refs | Feature lives in ONE domain, others cross-reference | ✓ |
| Duplicate in both domains | Full mention in each relevant domain | |
| Separate cross-cutting section | Dedicated section for spanning features | |

**User's choice:** Primary domain + cross-refs

---

### Voice mode placement

| Option | Description | Selected |
|--------|-------------|----------|
| In "Parked Work" alongside mobile | Honest — code exists but isn't verified working | ✓ |
| Inside shipped domain with caveat | List with "untested / status unknown" marker | |
| Separate "Experimental" section | Third category beyond Shipped and Parked | |

**User's choice:** In Parked Work alongside mobile

---

## Narrative Voice & Depth

### Tone

| Option | Description | Selected |
|--------|-------------|----------|
| Warm teaching | Explain what each domain does and why it matters to a job seeker | ✓ |
| Technical catalog | Dry, precise listing focused on what exists | |
| Layered (warm intro + technical detail) | Warm paragraph + technical capabilities list per domain | |

**User's choice:** Warm teaching

---

### Evolution narrative approach

| Option | Description | Selected |
|--------|-------------|----------|
| Opening narrative + domain sections | 2-3 paragraph opening story, then standalone domain sections | ✓ |
| Timeline sidebar per domain | Brief "how it evolved" sentence per domain, no separate narrative | |
| Full chronological story first | 1-2 page chronological account before domains | |

**User's choice:** Opening narrative + domain sections

---

### Depth per domain

| Option | Description | Selected |
|--------|-------------|----------|
| Paragraph + bullet list | 1-2 warm paragraphs + concise bullets, ~150-250 words/domain, ~2-3K total | ✓ |
| Brief (bullet list only) | Intro sentence + bullets, ~50-100 words/domain | |
| Deep (full feature writeups) | Mini-article per domain, ~400-600 words/domain, 5K+ total | |

**User's choice:** Paragraph + bullet list

---

### Technical detail level

| Option | Description | Selected |
|--------|-------------|----------|
| Release tags only | File paths, routes, architecture go in Phase 4 deep dives | ✓ |
| Light technical sidebar | Small footnote per domain with API route prefix and key file | |
| Full technical detail inline | File paths, API routes, architecture notes in each section | |

**User's choice:** Release tags only

---

## Honesty Framing

### How to present gaps and rough edges

| Option | Description | Selected |
|--------|-------------|----------|
| Inline honest assessment | Gaps woven into each domain's warm prose | ✓ |
| Separate "Known Limitations" section | Positive domains + dedicated gap section at end | |
| Status badges per capability | [shipped], [partial], [broken], [untested] markers | |

**User's choice:** Inline honest assessment

---

### Tech debt in inventory

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 2 only | Tech debt is internal, handled by ROAD-06 in Phase 2 | ✓ |
| Light mention in inventory | Brief "Under the Hood" notes for developers | |
| Both places | Inventory for awareness, ROADMAP.md for planning | |

**User's choice:** Phase 2 only

---

### Gap specificity

| Option | Description | Selected |
|--------|-------------|----------|
| User-impact gaps only | Only gaps affecting end users, skip internal concerns | ✓ |
| All gaps including internal | Both user-facing and developer-facing gaps | |
| No gap bullets — weave into prose only | Gaps in paragraphs only, no explicit list | |

**User's choice:** User-impact gaps only

---

## Output Structure

### File location

| Option | Description | Selected |
|--------|-------------|----------|
| docs/roadmap/inventory.md | Permanent reference doc, Phase 2 reads it for ROADMAP.md | ✓ |
| Directly in ROADMAP.md | First draft of ROADMAP.md shipped section | |
| .planning/ only (internal) | Working doc, never ships, Phase 2 transforms | |

**User's choice:** docs/roadmap/inventory.md

---

### Summary table

| Option | Description | Selected |
|--------|-------------|----------|
| Top summary table + narrative | Quick-scan table at top, full narrative below | ✓ |
| Narrative only | No table, let sections speak for themselves | |
| Let Claude decide | Pick best format during writing | |

**User's choice:** Top summary table + narrative

---

### CHANGELOG cross-references

| Option | Description | Selected |
|--------|-------------|----------|
| Release tags + CHANGELOG links | Links to CHANGELOG.md sections per release tag | ✓ |
| Release tags only (no links) | Just version numbers, Phase 2 adds links | |
| Skip release info entirely | Phase 2 handles all release-tag mapping | |

**User's choice:** Release tags + CHANGELOG links

---

## Claude's Discretion

- Exact domain section ordering
- Precise evolution narrative wording
- Minor features that don't fit neatly into one domain
- Summary table column choices beyond domain/highlights/status

## Deferred Ideas

None — discussion stayed within phase scope
