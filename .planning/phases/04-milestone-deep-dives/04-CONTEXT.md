# Phase 4: Milestone Deep Dives - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Create per-milestone companion documents in `docs/roadmap/` that provide depth without cluttering the master ROADMAP.md. 19 deep-dive documents (10 shipped + 8 planned + Feature Flags) plus an index page, with inline links added to ROADMAP.md. Also fix stale Mermaid diagrams deferred from Phase 3. No code changes — editorial only.

Output: 19 milestone deep-dive docs, updated `docs/roadmap/inventory.md` as index, ROADMAP.md with inline deep-dive links and corrected Mermaid diagrams.

</domain>

<decisions>
## Implementation Decisions

### Template Design
- **D-01:** **Dual-audience structure.** Top half is user-facing (warm tone, user-benefit language). Bottom half is contributor-facing (file paths, architecture, integration points). Clear `---` horizontal rule separator between halves
- **D-02:** **Narrative + technical template.** Sections: Goal, What This Delivers, How It Works, Current Status, Related Milestones, then separator, then For Contributors: Architecture, Research & Decisions, BMAD Integration. ~800-1200 words for shipped milestones, ~500-800 words for planned milestones
- **D-03:** **Descriptive slug file naming.** `scoring-engine.md`, `desktop-app.md`, `browser-extension.md` — immediately clear from directory listing. No bird codenames in filenames (those stay in headings)
- **D-04:** **Text-only in user-facing half.** No Mermaid diagrams inside deep-dive documents. Contributor section can reference `.planning/codebase/` diagrams if needed
- **D-05:** **Related Milestones section.** At the bottom of the user-facing half (before contributor separator). Short list of related milestones with one-line relationship description and links to their deep dives
- **D-06:** **Inline deep-dive links on ROADMAP.md milestone headings.** Each milestone in ROADMAP.md gets a "Deep dive →" link on its status line pointing to the corresponding `docs/roadmap/` doc

### Index & Navigation
- **D-07:** **Repurpose inventory.md as index.** `docs/roadmap/inventory.md` becomes the directory landing page listing all deep dives, grouped by Shipped/Planned. ROADMAP.md already links to it — no broken links
- **D-08:** **Planning hierarchy in index.** The index page gets a "How Planning Works" section explaining the full chain: ROADMAP.md → deep dives → BMAD PRDs → epics → Linear tickets. Individual deep dives link back to this section rather than repeating the hierarchy

### Milestone Coverage
- **D-09:** **All milestones covered.** 10 shipped + 8 planned + Feature Flags = 19 documents. Shipped docs have full content sourced from codebase analysis and research docs. Planned docs are lighter with vision, design considerations, and open questions
- **D-10:** **Feature Flags as standalone deep dive.** `feature-flags.md` — 19th document. Short user-facing half ("different app editions, hide incomplete features"), longer contributor half. Satisfies ROAD-15 which was excluded from ROADMAP.md user-facing content (Phase 3 D-29)
- **D-11:** **Planned milestones use adapted template.** Same sections, lighter content: "How It Works" becomes "Design Considerations", "Architecture" becomes "Open Questions", "Research & Decisions" becomes "Research Needed". Status line: `*Status: Planned — not yet started*`
- **D-12:** **Source from codebase docs, not Phase 1 inventory.** Phase 1 was never executed — `inventory.md` is a placeholder. Source chain: (1) ROADMAP.md shipped sections, (2) `.planning/codebase/` docs, (3) `docs/research/`, (4) `docs/reference/`, (5) CHANGELOG.md
- **D-13:** **Writing order: Claude's discretion.** No mandated order — efficiency over sequence

### Plans
- **D-14:** **Two plans.** Plan 04-01: 10 shipped deep dives + inventory-as-index + ROADMAP.md inline links for shipped milestones. Plan 04-02: 9 planned deep dives (including Feature Flags) + ROADMAP.md inline links for planned milestones + Mermaid diagram fixes + final index update

### BMAD Integration
- **D-15:** **Status + hook pattern per doc.** Each BMAD Integration section states: PRD status (exists/in-progress/not started), what a PRD would cover for this milestone, and a standard call-to-action for starting one
- **D-16:** **Planning hierarchy explained once in index.** Individual deep dives link to the index's "How Planning Works" section. No 19x repetition of the hierarchy chain
- **D-17:** **Desktop App references in-progress PRD.** The Desktop App deep dive notes PRD Status: In progress (5/13 steps), references branch `docs/prd-creation` and output directory `_bmad-output/planning-artifacts/`

### Mermaid Diagram Fixes
- **D-18:** **Fix both diagrams in Plan 2.** Gantt: rename "Writing Style Flywheel" → "Voice Mode", add "Know Me" milestone. Flowchart: same rename, add Know Me node with edges (Profile & Skills → Know Me → Gap Analysis → Voice Mode)
- **D-19:** **Gantt order matches D-31.** Later section: Profile and Skills → Know Me → Gap Analysis → Voice Mode → Hosted Version. Matches Phase 3's user journey narrative ordering
- **D-20:** **Add Feature Flags → Hosted Version to flowchart.** Feature Flags appears in the dependency diagram (technical context) even though it's excluded from ROADMAP.md prose. Shows the real engineering dependency
- **D-21:** **Remove staleness HTML comments.** Both diagrams currently have comments noting "Phase 2 milestone names." Remove after fixes are applied

### Tone & Content
- **D-22:** **Same voice, natural tense.** Warm second-person tone throughout (carrying forward Phase 1 D-05, Phase 2 D-19). Shipped docs use present/past tense. Planned docs use future-oriented language. Voice stays consistent, only tense shifts
- **D-23:** **No AI slop.** Phase 3 D-09 carries forward — avoid "seamlessly," "leverage," "revolutionize," "cutting-edge," etc. Every word earns its place
- **D-24:** **Annotated research links.** Each link in Research & Decisions gets a one-sentence annotation explaining what the doc covers and why it's relevant. 3-8 links per deep dive
- **D-25:** **Private docs inform framing, never cited.** Insights from `private/` shape tone and framing (e.g., privacy positioning, audience awareness) but are never linked, quoted, or referenced by filename. Deep dives only link to public docs
- **D-26:** **Link to reference docs, don't duplicate.** Deep dives reference existing `docs/reference/` files (AI-PROVIDERS.md, DEPLOY.md, TESTING.md, etc.) in their Research & Decisions section. Roadmap = product story, reference = technical spec. No content duplication

### Claude's Discretion
- Writing order for the 19 documents (efficiency over sequence)
- Exact wording of "How It Works" and "What This Delivers" sections
- Which research docs are relevant to which milestones (annotated link selection)
- Related Milestones connections (which milestones link to which)
- Exact architecture details in contributor sections
- How to frame open questions for planned milestones

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior Phase Outputs (primary context)
- `ROADMAP.md` (repo root) — Current milestone descriptions, status lines, and Mermaid diagrams. Phase 4 adds inline links and fixes diagrams in this file
- `.planning/phases/01-feature-inventory/01-CONTEXT.md` — Phase 1 decisions on tone (D-05), no file paths in user-facing content (D-08), domain groupings (D-01)
- `.planning/phases/02-roadmap-foundation/02-CONTEXT.md` — Phase 2 decisions on audience (D-02), privacy-led pitch (D-03), status system (D-08/D-09), Mermaid constraints (D-16/D-17/D-18), warm tone (D-19/D-20)
- `.planning/phases/03-forward-vision/03-CONTEXT.md` — Phase 3 decisions on milestone prose style (D-01 through D-10), milestone ordering (D-31/D-32), Feature Flags exclusion (D-29), diagram deferrals (D-35)

### Codebase Analysis (source material for shipped deep dives)
- `.planning/codebase/ARCHITECTURE.md` — System architecture, layers, entry points, data flow
- `.planning/codebase/STRUCTURE.md` — File tree, module organization
- `.planning/codebase/STACK.md` — Technology stack, frameworks, dependencies
- `.planning/codebase/CONVENTIONS.md` — Code style, patterns
- `.planning/codebase/INTEGRATIONS.md` — External service connections
- `.planning/codebase/CONCERNS.md` — Known issues, tech debt (for contributor sections)
- `.planning/codebase/TESTING.md` — Test infrastructure details

### Research Documents (annotated links in deep dives)
- `docs/research/` — 20 research documents covering scoring, testing, cost optimization, CI/CD, providers, privacy, token optimization, mobile UX
- `docs/reference/` — 11 reference documents including AI-PROVIDERS.md, DEPLOY.md, TESTING.md, release-pipeline.md (link to, don't duplicate)

### Release History
- `CHANGELOG.md` — All releases with commit references. Cross-reference pattern: `[v0.X.0](CHANGELOG.md#anchor)`

### Project Context
- `.planning/PROJECT.md` — North star, business model, planning hierarchy definition
- `.planning/REQUIREMENTS.md` — DEEP-01 through DEEP-04 requirements this phase covers

### BMAD Context
- `_bmad-output/planning-artifacts/` — In-progress PRD output (5/13 steps, Desktop App)
- `_bmad/bmm/config.yaml` — BMAD project config

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **ROADMAP.md** — 230-line document with established milestone format (headings, status lines, codenames, prose). Phase 4 adds inline links
- **CHANGELOG.md** — Cross-reference pattern: `[v0.X.0](CHANGELOG.md#anchor)`. Already used in ROADMAP.md shipped section
- **docs/roadmap/inventory.md** — Placeholder that becomes the index page
- **7 codebase analysis docs** in `.planning/codebase/` (~1,693 lines) — Primary source for shipped milestone architecture sections
- **20 research docs** in `docs/research/` — Annotated link targets for Research & Decisions sections
- **11 reference docs** in `docs/reference/` — Link targets, not to be duplicated

### Established Patterns
- Status line format: `*Status: Shipped/In Progress/Planned/Considering*` (from Phase 2/3)
- Heading format: `#### Milestone Name (vX.Y Codename)` (from Phase 3)
- Warm second-person tone (from Phase 1, carried through all phases)
- No AI slop (Phase 3 D-09)
- GitHub-compatible Mermaid only (Phase 2 D-18): basic gantt and flowchart, no quadrantChart, HTML tags, `&` joins, color styles

### Integration Points
- `docs/roadmap/` — 19 new files + updated inventory.md as index
- `ROADMAP.md` — Inline deep-dive links on each milestone + fixed Mermaid diagrams
- Phase 5 adds contributor paths per milestone — deep dives provide the foundation

</code_context>

<specifics>
## Specific Ideas

- Desktop App deep dive is the highest-value planned doc — it has the in-progress PRD, the PWA-to-native path deferred from Phase 3, and the code signing detail. Give it the most attention
- Feature Flags deep dive satisfies ROAD-15 cleanly — short user-facing half, longer contributor section with design considerations
- The "How Planning Works" section in the index makes the BMAD integration tangible — shows the hierarchy isn't just theoretical
- Related Milestones cross-links create a web of connected docs that readers can explore beyond the linear ROADMAP.md ordering
- Gantt and flowchart fixes bring diagrams into sync with Phase 3 prose — removes the jarring "Writing Style Flywheel" label that no longer matches anything

</specifics>

<deferred>
## Deferred Ideas

- **Phase 1 (Feature Inventory)** — May no longer be needed. Deep dives effectively supersede the inventory concept. inventory.md becomes the index. If Phase 1 is executed later, it would need rescoping
- **Hosted Version business model details** — Pricing, tiers, sustainability angle. Deep dive describes user benefit only (Phase 3 D-30). Business model discussion deferred to BMAD PRD or strategy session

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-milestone-deep-dives*
*Context gathered: 2026-04-27*
