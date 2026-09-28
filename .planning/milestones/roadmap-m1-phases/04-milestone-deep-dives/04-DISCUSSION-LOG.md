# Phase 4: Milestone Deep Dives - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-27
**Phase:** 04-milestone-deep-dives
**Areas discussed:** Template design & audience, Milestone coverage scope, BMAD integration pattern, Stale Mermaid diagrams, Research links depth, Tone across 19 docs, Private research handling, Existing docs/reference/ overlap

---

## Template Design & Audience

| Option | Description | Selected |
|--------|-------------|----------|
| Dual-audience | Top half user-facing (warm), bottom half contributor-facing (technical), clear separator | ✓ |
| Contributor-first | Technical throughout — architecture, file paths, integration points | |
| Evaluator-first | Same warm tone as ROADMAP.md, technical in footnotes only | |

**User's choice:** Dual-audience
**Notes:** Clear `---` separator between user-facing and contributor sections

---

| Option | Description | Selected |
|--------|-------------|----------|
| Narrative + technical | Goal, What This Delivers, How It Works, Current Status, separator, Architecture, Research, BMAD. ~800-1200 words | ✓ |
| Compact card format | Metadata table + paragraphs + collapsed details. ~500-800 words | |
| Minimal reference | Bullet-point facts only. ~300-500 words | |

**User's choice:** Narrative + technical
**Notes:** User viewed preview template and confirmed structure

---

| Option | Description | Selected |
|--------|-------------|----------|
| Descriptive slugs | scoring-engine.md, desktop-app.md — clear from directory listing | ✓ |
| Bird codenames | peregrine.md, osprey.md — on-brand but less discoverable | |

**User's choice:** Descriptive slugs

---

| Option | Description | Selected |
|--------|-------------|----------|
| Update existing index.md | docs/roadmap/ gets an index listing all deep dives grouped by status | ✓ |
| No separate index | ROADMAP.md links are sufficient, no directory-level landing page | |
| README.md instead | GitHub auto-renders README when opening folder | |

**User's choice:** Update existing index.md

---

| Option | Description | Selected |
|--------|-------------|----------|
| Inline links on headings | Each ROADMAP.md milestone gets a "Deep dive →" link on its status line | ✓ |
| Single link at top | One "see docs/roadmap/" line near the top | |
| Both | Top-level + per-milestone links | |

**User's choice:** Inline links on milestone headings

---

| Option | Description | Selected |
|--------|-------------|----------|
| Related Milestones section | Short list at bottom of user-facing half with cross-links | ✓ |
| No cross-links | Each doc standalone, ROADMAP.md flowchart shows dependencies | |

**User's choice:** Related Milestones section

---

| Option | Description | Selected |
|--------|-------------|----------|
| Text-only | No Mermaid diagrams in deep dives. Contributor section can reference codebase docs | ✓ |
| Optional Mermaid per doc | Include where it genuinely aids understanding | |
| Standardized diagram | Every deep dive gets one Mermaid diagram | |

**User's choice:** Text-only

---

## Milestone Coverage Scope

| Option | Description | Selected |
|--------|-------------|----------|
| All milestones | 10 shipped + 8 planned = 18, plus Feature Flags = 19 docs total | ✓ |
| Shipped only | 10 shipped milestones, planned milestones stay in ROADMAP.md only | |
| Shipped + deferred items only | 10 shipped + Desktop App + Hosted Version only | |

**User's choice:** All milestones

---

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone deep dive | feature-flags.md as 19th document, satisfies ROAD-15 | ✓ |
| Section in Hosted Version | Feature flags as subsection of hosted-version.md | |
| Internal doc only | Document in docs/reference/ or docs/internal/ | |

**User's choice:** Standalone deep dive for Feature Flags

---

| Option | Description | Selected |
|--------|-------------|----------|
| Same template, lighter content | Same sections, "How It Works" → "Design Considerations", Architecture → Open Questions. ~500-800 words | ✓ |
| Abbreviated format | Shorter format: Goal, Vision, Open Questions, BMAD hook. ~300-500 words | |
| Same depth as shipped | Full-length speculative design docs | |

**User's choice:** Same template, lighter content

---

| Option | Description | Selected |
|--------|-------------|----------|
| Source from codebase docs | .planning/codebase/, ROADMAP.md, docs/research/, docs/reference/, CHANGELOG.md | ✓ |
| Execute Phase 1 first | Go back and fill inventory.md before deep dives | |
| Write inventory as part of Phase 4 | Fold Phase 1 into Phase 4 | |

**User's choice:** Source from codebase docs (Phase 1 skipped)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Replace with index | inventory.md becomes the docs/roadmap/ landing page | ✓ |
| Keep as redirect | One-liner pointing to index or ROADMAP.md | |
| Delete it | Remove placeholder entirely | |

**User's choice:** Replace inventory.md with index

---

| Option | Description | Selected |
|--------|-------------|----------|
| Claude's discretion | No mandated writing order | ✓ |
| Match ROADMAP.md order | Write in ROADMAP.md section order | |

**User's choice:** Claude's discretion

---

| Option | Description | Selected |
|--------|-------------|----------|
| Two plans | Plan 1: shipped + index. Plan 2: planned + diagrams | ✓ |
| Three plans | Smaller chunks with more checkpoints | |
| Single plan | All 19 docs in one plan | |

**User's choice:** Two plans

---

## BMAD Integration Pattern

| Option | Description | Selected |
|--------|-------------|----------|
| Status + hook pattern | PRD status, what PRD would cover, call-to-action per doc | ✓ |
| Placeholder only | Simple "PRD: Not yet created" note | |
| Worked example in one doc | Detailed example in one doc, others reference it | |

**User's choice:** Status + hook pattern

---

| Option | Description | Selected |
|--------|-------------|----------|
| Once in index, reference elsewhere | "How Planning Works" section in index, deep dives link back | ✓ |
| Repeated in every doc | Full hierarchy chain in every BMAD section | |

**User's choice:** Once in index, reference elsewhere

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, note it exists | Desktop App references in-progress PRD (5/13 steps) with branch and output dir | ✓ |
| Skip it | Don't reference work-in-progress from shipped docs | |

**User's choice:** Reference in-progress PRD
**Notes:** PRD is for Desktop App milestone. Branch: docs/prd-creation

---

## Stale Mermaid Diagrams

| Option | Description | Selected |
|--------|-------------|----------|
| Include in Phase 4 | Fix both diagrams as part of Plan 2 alongside planned milestone work | ✓ |
| Separate cleanup task | Diagram fixes as separate Linear ticket | |
| Include in Plan 1 | Fix early alongside shipped work | |

**User's choice:** Include in Phase 4

---

| Option | Description | Selected |
|--------|-------------|----------|
| Add, connected to Feature Flags | Feature Flags → Hosted Version dependency edge | ✓ |
| Add standalone | Disconnected node | |
| Leave it out | No Hosted Version in flowchart | |

**User's choice:** Add connected to Feature Flags

---

| Option | Description | Selected |
|--------|-------------|----------|
| Plan 2 | With planned milestones and cleanup | ✓ |
| Plan 1 | Fix diagrams early | |

**User's choice:** Plan 2

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, match D-31 order | Profile & Skills → Know Me → Gap Analysis → Voice Mode → Hosted Version | ✓ |
| Keep approximate | Claude positions logically without strict D-31 adherence | |

**User's choice:** Match D-31 order

---

## Research Links Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Annotated link list | One-sentence annotation per link, 3-8 links per doc | ✓ |
| Just links | Bare link list, no context | |
| Summary paragraphs | 2-3 sentence summaries per research doc | |

**User's choice:** Annotated link list

---

## Tone Across 19 Docs

| Option | Description | Selected |
|--------|-------------|----------|
| Same voice, natural tense | Warm second-person throughout, shipped=present/past, planned=future. Voice consistent | ✓ |
| Distinct register | Shipped=factual, planned=aspirational | |
| Uniform present tense | All docs use present tense regardless of status | |

**User's choice:** Same voice, natural tense

---

## Private Research Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Inform framing, never cite | Insights shape tone, never linked/quoted/referenced by filename | ✓ |
| Ignore private docs entirely | Only use public source material | |

**User's choice:** Inform framing, never cite

---

## Existing docs/reference/ Overlap

| Option | Description | Selected |
|--------|-------------|----------|
| Link, don't duplicate | Reference existing docs in Research & Decisions section. Roadmap=story, reference=spec | ✓ |
| Consolidate into deep dives | Move reference content into deep dive contributor sections | |
| Ignore overlap | Write independently, accept some duplication | |

**User's choice:** Link, don't duplicate

---

## Claude's Discretion

- Writing order for 19 documents
- Exact prose in user-facing sections
- Research doc to milestone mapping (annotated link selection)
- Related Milestones connections
- Architecture details in contributor sections
- Open questions framing for planned milestones

## Deferred Ideas

- Phase 1 may no longer be needed — deep dives supersede the inventory concept
- Hosted Version business model details deferred to BMAD PRD or strategy session
