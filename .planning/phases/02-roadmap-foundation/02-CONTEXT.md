# Phase 2: Roadmap Foundation - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Assemble the master ROADMAP.md at repo root as a well-structured, GitHub-rendered document with shipped content (sourced from Phase 1 inventory), status system, Mermaid timeline, tech debt section, disclaimers, and all structural scaffolding for Phases 3-5 to extend. No code changes — editorial only. Output: a single ROADMAP.md file that a non-technical visitor can read and understand what Kestrel is, what's shipped, and where it's going.

</domain>

<decisions>
## Implementation Decisions

### Document Structure
- **D-01:** **Vision-first section flow** — (1) Hero pitch, (2) What's Shipped, (3) What's Next (Now/Next/Later), (4) Timeline (Mermaid diagrams), (5) Known Limitations, (6) About This Project, (7) Contributing stub
- **D-02:** **Primary audience: product evaluator** — someone hitting the GitHub repo cold asking "what does this do, is it for me, where's it going?" Builder-credential story lives in blog posts and README, not in the roadmap
- **D-03:** **Privacy-led hero pitch** — lead with self-hosted, data-stays-local, BYOK AI. This is the genuine differentiator vs Huntr/Teal and matches the r/selfhosted target audience
- **D-04:** **One paragraph philosophy** after hero — frame as self-hosted + privacy-first without leaning hard on "open source" as the selling point. License is a fact stated once, not the pitch. **Do NOT promise "forever AGPL" or "forever free"** — keep language flexible for potential future commercial path
- **D-05:** **Contributing stub placeholder** — simple "See CONTRIBUTING.md" line at the bottom. Phase 5 replaces it with per-milestone contribution paths

### Shipped Content
- **D-06:** **Condensed summary + link** — ROADMAP.md gets a tight shipped section (~500 words) with domain highlights and a link to `docs/roadmap/inventory.md` for the full story. Most readers want "what's next" not "what's done"
- **D-07:** **Cross-references on shipped items only** (ROAD-08) — release tags and CHANGELOG links on shipped milestones. Forward milestones have no releases to reference yet. Use the `[v0.3.0](CHANGELOG.md#030)` pattern established in Phase 1

### Status System & Horizons
- **D-08:** **Emoji status badges** — 4 statuses only: ✅ Shipped, 🔨 In Progress, 📋 Planned, 💭 Considering. No finer granularity (no "Researched", "Paused", etc.). Low-maintenance for solo maintainer
- **D-09:** **Version-anchored horizons** — Now (v0.12), Next (v0.13-v0.15), Later (v1.0+). Version numbers give concrete anchoring without promising dates
- **D-10:** **Empty scaffolding for forward milestones** — Phase 2 creates the Now/Next/Later section headers with "Details coming in next update" placeholders. Phase 3 fills them with full user-facing content
- **D-11:** **Disclaimers as footnote-style "About This Project" section** at the bottom. Matter-of-fact: solo maintainer, plans evolve, currently non-commercial. NOT apologetic, NOT a banner

### Tech Debt & Honesty
- **D-12:** **Lead with the audience mismatch** — the real limitation is "currently developer-only install." Kestrel works but installing it requires a terminal. Frame the Desktop App milestone as THE fix for this gap
- **D-13:** **Confident acknowledgment tone** — frame limitations as known tradeoffs, not apologies. "SQLite is intentional for local-first. Postgres/Supabase path researched for future hosted version"
- **D-14:** **User-impact debt only** — disclose: developer-only install (THE gap), SQLite-only (scaling concern), no lockfile (reproducibility). Skip: individual bugs (Docker G-488 etc.), internal architecture debt (scoring monolith, duplicate exceptions, type drift)
- **D-15:** **No bug immortalization** — don't mention specific bug tickets in the roadmap. Bugs come and go. Structural limitations stay

### Mermaid Diagrams
- **D-16:** **Two diagrams** — gantt chart for timeline/ordering, flowchart for milestone dependencies
- **D-17:** **Quarters without years** on the gantt — relative ordering without specific date commitments. Avoids going stale when milestones slip (solo project, they will)
- **D-18:** **GitHub-compatible only** — basic gantt and flowchart LR/TD. No quadrantChart, `&` joins, HTML tags, `color:#fff`, subgraph edges. Tested by previewing on GitHub, not Mermaid live editor

### Carrying Forward from Phase 1
- **D-19:** Warm teaching tone (Phase 1 D-05) — "what it does for you" not "what's under the hood"
- **D-20:** No file paths or API routes in user-facing content (Phase 1 D-08) — reserve for Phase 4 deep dives
- **D-21:** User-impact gaps only in prose (Phase 1 D-10)
- **D-22:** `docs/roadmap/inventory.md` is the full inventory (Phase 1 D-12) — ROADMAP.md links to it

### Claude's Discretion
- Version-to-milestone mapping for forward milestones (assign reasonable version numbers based on scope)
- Mermaid diagram detail level (milestone-level vs. sub-features, based on what renders cleanly on GitHub)
- Exact wording of hero pitch and philosophy paragraph
- How to condense the shipped section into ~500 words
- Section heading exact phrasing

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 Output (primary input)
- `docs/roadmap/inventory.md` — Full feature inventory with 8 domain sections (Phase 2 reads this to build shipped section). **NOTE: This file may not exist yet if Phase 1 execution hasn't completed. If missing, agents must build shipped content from codebase analysis docs below.**
- `.planning/phases/01-feature-inventory/01-CONTEXT.md` — Phase 1 decisions that carry forward (D-05 through D-14)

### Codebase Analysis (fallback if inventory not yet written)
- `.planning/codebase/ARCHITECTURE.md` — System architecture, layers, entry points
- `.planning/codebase/STACK.md` — Technology stack, frameworks, dependencies
- `.planning/codebase/CONCERNS.md` — Known tech debt (user-impact items only for Phase 2)

### Release History
- `CHANGELOG.md` — All releases v0.1.0 through v0.12.0 with commit references
- Git tags `v0.1.0` through `v0.12.0` — Release boundaries for cross-referencing

### Project Context
- `.planning/PROJECT.md` — North star (web-first, user-first), business model, constraints
- `.planning/REQUIREMENTS.md` — ROAD-01 through ROAD-08 requirements this phase covers

### Strategic Context (private, do not commit content to public files)
- `private/kestrel-gtm-conversation.md` — Full GTM analysis: audience mismatch, EU/privacy wedge, commercialization considerations, positioning. Informs tone and framing decisions. **Do not quote or reference this file in ROADMAP.md — use the insights, not the source.**

### Mermaid Constraints
- Memory: "Mermaid GitHub Compatibility" — GitHub renderer fails on quadrantChart, `&` joins, subgraph edges, HTML tags, color styles. Use basic gantt + flowchart only.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **CHANGELOG.md** — 16 release entries (v0.1.0 through v0.12.0) with conventional commit format. Cross-referencing pattern: `[v0.3.0](CHANGELOG.md#030)`
- **Phase 1 inventory** (`docs/roadmap/inventory.md` when complete) — 8 domain sections ready to condense
- **7 codebase analysis docs** in `.planning/codebase/` — ~1,693 lines of structured analysis as fallback source

### Established Patterns
- Conventional commits with ticket IDs — consistent release history to reference
- Warm teaching tone from Phase 1 — maintain consistency in ROADMAP.md prose
- GitHub-rendered markdown — all docs use standard GFM, no custom rendering

### Integration Points
- `ROADMAP.md` at repo root — new file, GitHub renders it prominently
- `docs/roadmap/` directory — Phase 1 creates `inventory.md`, Phase 4 adds deep dives. ROADMAP.md links into this directory
- Phase 3 extends the Now/Next/Later scaffold with full milestone content
- Phase 5 replaces the contributing stub with per-milestone contribution paths

</code_context>

<specifics>
## Specific Ideas

- Hero pitch should evoke "self-hosted Obsidian for job search" — download, open, use, data stays local
- The "mutant without clear audience" honesty: Kestrel is powerful but currently requires terminal skills. Desktop App milestone is the bridge from dev-tool to real product. Name this gap directly
- EU/privacy positioning from GTM analysis should be visible but not heavy-handed — it's the wedge, not the entire identity
- "About This Project" section: say "currently non-commercial" not "forever non-commercial" — leave room for future commercial path (recruiter spin-off, dual-license, hosted version)
- Shipped section should feel like "look at everything this does" not "look at all the code we wrote" — user benefits, not engineering metrics

</specifics>

<deferred>
## Deferred Ideas

### Strategic (High Priority — needs own focused session)
- **Commercialization path research** — market analysis, product vision, promotion strategy. GTM conversation surfaced that "delivery and marketing is harder than dev." Needs dedicated `/bmad-brainstorming` or strategy session
- **Recruiter-oriented spin-off** — scoring engine inverted for recruiter-side signal extraction. B2B play with real budgets. Closest to Ashby/Gem/Metaview territory
- **License strategy review** — AGPL blocks B2B/integration (Google bans it). Evaluate dual-license, CLA addition, or fork model. Do this while zero external contributors
- **CLA addition to CONTRIBUTING.md** — prerequisite for any future dual-licensing. Easy now, painful to retrofit later

### Content (Future Phases)
- **Open-source positioning rethink** — "open source" may not be the selling point. Privacy-first, self-hosted is. License is a fact, not the pitch
- **Grant applications** — Prototype Fund (fall 2026) and NLnet (rolling) are realistic. "EU-sovereign AI for job search" fits NLnet thesis. Park until after July 23 kill criterion

### Reviewed Todos (not folded)
None — no pending todos matched this phase

</deferred>

---

*Phase: 02-roadmap-foundation*
*Context gathered: 2026-04-24*
