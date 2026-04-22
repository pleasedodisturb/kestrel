# Phase 1: Feature Inventory - Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Catalogue all shipped work into a coherent, verifiable feature list organized by domain clusters. Produce `docs/roadmap/inventory.md` — a user-facing document that tells the story of how Kestrel evolved, honestly documents what's shipped (and what's not), and organizes features into 8 retrospective domain milestones plus a Parked Work section. No code changes — editorial only. This document feeds directly into Phase 2 (Roadmap Foundation) which assembles ROADMAP.md.

</domain>

<decisions>
## Implementation Decisions

### Milestone Grouping
- **D-01:** Group shipped work into **8 domain clusters** (not chronological eras): Scoring Engine, Discovery Engine, AI Provider System, Application Pipeline, Web Frontend, CLI & Packaging, Infrastructure, Integrations
- **D-02:** Mobile app and Voice mode go in a separate **"Parked Work"** section after the 8 shipped domains — not mixed into shipped features
- **D-03:** Cross-domain features live in **one primary domain with cross-references** to other relevant domains — no duplication
- **D-04:** Release tags are cross-references within each domain section, not the organizing principle

### Narrative Voice & Depth
- **D-05:** **Warm teaching tone** — explain what each domain does and why it matters to a job seeker. "The scoring engine learns what kinds of jobs you actually want" not "multi-factor rubric with 288 presets"
- **D-06:** **Opening evolution narrative** (2-3 paragraphs) tells the story of how Kestrel grew from CLI tool to full-stack platform, followed by standalone domain sections
- **D-07:** Each domain section: **1-2 warm paragraphs + concise bullet list** of key capabilities. ~150-250 words per domain. Total inventory: ~2,000-3,000 words
- **D-08:** **Release tags only** in the inventory — file paths, API routes, and architecture details are reserved for Phase 4 deep dives

### Honesty Framing
- **D-09:** **Inline honest assessment** — gaps and rough edges woven into each domain's warm prose, not separated into a "problems" section
- **D-10:** **User-impact gaps only** — mention gaps that affect end users (no desktop installer, Docker issues, requires terminal). Skip internal concerns (no lockfile, sync clients, scoring monolith)
- **D-11:** **Tech debt goes in Phase 2** — ROAD-06 handles tech debt disclosure in ROADMAP.md. The inventory stays user-facing

### Output Structure
- **D-12:** Output file: **`docs/roadmap/inventory.md`** — permanent reference doc in the roadmap directory. Phase 2 reads it to assemble ROADMAP.md's shipped section
- **D-13:** **Summary table at the top** with domain, highlights, and status (Shipped/Parked) for quick scanning, followed by full narrative sections
- **D-14:** Each domain includes **release tags with CHANGELOG.md links** — `[v0.3.0](CHANGELOG.md#030)` style. Satisfies ROAD-08 cross-referencing requirement early

### Claude's Discretion
- Exact domain section ordering (logical grouping, not alphabetical)
- Precise wording of the evolution narrative
- How to handle minor features that don't fit neatly into one domain
- Summary table column choices beyond the required domain/highlights/status

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase Analysis (primary sources for inventory content)
- `.planning/codebase/ARCHITECTURE.md` — System architecture, layers, entry points, data flow
- `.planning/codebase/STRUCTURE.md` — File tree, module organization, naming patterns
- `.planning/codebase/STACK.md` — Technology stack, frameworks, dependencies with versions
- `.planning/codebase/CONVENTIONS.md` — Code style, patterns, commit conventions
- `.planning/codebase/INTEGRATIONS.md` — External service connections (TickTick, Pushover, Calendar, OAuth)
- `.planning/codebase/CONCERNS.md` — Known issues, tech debt (for Phase 2 reference, NOT for inventory)
- `.planning/codebase/TESTING.md` — Test infrastructure details

### Release History
- `CHANGELOG.md` — All releases v0.1.0 through v0.10.0 with commit references
- Git tags `v0.1.0` through `v0.10.0` — Release boundaries

### Deployment & Packaging
- `docs/reference/DEPLOY.md` — Current deployment documentation
- `docs/reference/AI-PROVIDERS.md` — AI provider reference (feeds AI Provider System domain)
- `Dockerfile` — Multi-stage build configuration
- `docker-compose.yml` / `docker-compose.prod.yml` — Dev and prod Docker configs
- `pyproject.toml` — PyPI package configuration, entry points

### Project Context
- `.planning/PROJECT.md` — North star: web-first, user-first. Business model decisions. Planned features list
- `.planning/REQUIREMENTS.md` — INV-01 through INV-08 requirements this phase covers

</canonical_refs>

<code_context>
## Existing Code Insights

### Assets to Inventory
- **31 API route files** in `src/career_os/api/` — each represents a shipped capability
- **39 service modules** in `src/career_os/services/` — business logic backing routes
- **13 frontend pages** in `frontend/src/pages/` — each a distinct UI view
- **9 AI provider files** in `src/career_os/ai/` — plus cache, factory, PII masking, privacy
- **5 CLI subcommand groups** — pipeline, skills, goals, interview-prep, contacts
- **10 release tags** — v0.1.0 through v0.10.0 with CHANGELOG entries

### Existing Documentation
- 7 codebase analysis docs in `.planning/codebase/` (~1,693 lines) — PRIMARY source for inventory content
- 20+ research docs in `docs/research/` — background context per domain
- Reference docs in `docs/reference/` — deployment, testing, AI providers, validation contracts

### Integration Points
- `docs/roadmap/` directory needs to be created (doesn't exist yet)
- Phase 2 will read `docs/roadmap/inventory.md` to build ROADMAP.md
- Phase 4 will create per-milestone deep dives in `docs/roadmap/milestone-*.md`

</code_context>

<specifics>
## Specific Ideas

- Evolution narrative framing: "Started as a CLI scoring tool, grew into a full-stack platform"
- Summary table should include Parked items (Mobile, Voice) with "Parked" status — not just shipped domains
- Docker issue G-488 should be acknowledged in CLI & Packaging known gaps
- Voice mode: "API endpoint and frontend page exist. Status: Untested, needs audit"
- Mobile: "React Native 0.81 / Expo 54 scaffold. Paused for web v1 priority. UX findings preserved in docs/"

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-feature-inventory*
*Context gathered: 2026-04-22*
