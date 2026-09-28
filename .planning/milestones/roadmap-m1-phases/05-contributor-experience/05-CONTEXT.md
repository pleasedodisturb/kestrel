# Phase 5: Contributor Experience - Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Make Kestrel approachable for potential contributors: every milestone in ROADMAP.md gets a "Want to help?" callout with concrete contribution paths, the planning hierarchy is documented clearly in `docs/roadmap/inventory.md`, the devcontainer is validated and updated, and CONTRIBUTING.md bridges to the roadmap for finding meaningful work. No code changes — editorial and configuration only.

Output: Updated ROADMAP.md (callouts on all milestones), expanded `docs/roadmap/inventory.md` (planning hierarchy section), updated `.devcontainer/devcontainer.json`, updated `CONTRIBUTING.md` (Finding Work section + Codespaces mention).

</domain>

<decisions>
## Implementation Decisions

### "Want to help?" Callout Design
- **D-01:** **Inline per milestone.** Each milestone section in ROADMAP.md gets a blockquote callout at the bottom. Readers see contribution paths right where their interest peaks
- **D-02:** **Area pointers for specificity.** Point to a domain area + the deep dive doc. "Research Electron vs Tauri trade-offs" or "Add a new job board adapter." Specific enough to act on, stable enough not to go stale (no ticket links)
- **D-03:** **All milestones get callouts.** Both shipped and planned milestones. Shipped work still needs improvement, new adapters, edge case testing
- **D-04:** **Shipped milestones use improvement framing.** Shipped callouts say "Want to help?" but focus on improvement areas (new adapters, better coverage, edge cases). Planned callouts focus on building/researching
- **D-05:** **Blockquote format.** Use `> **Want to help?**` — GitHub renders with left border, visually distinct without being loud. Not GitHub alert syntax (too prominent for every section)
- **D-06:** **Deep dive link only.** Each callout links to the corresponding deep dive doc. No CONTRIBUTING.md link per callout — the deep dive's contributor section handles routing to setup

### Planning Hierarchy
- **D-07:** **Expand in place in inventory.md.** Don't create a standalone doc. Flesh out the existing "How Planning Works" section with more detail: visual diagram, brief explanation of each layer, and where contributors enter the chain
- **D-08:** **ASCII tree diagram.** Simple indented tree showing ROADMAP.md → docs/roadmap/ → BMAD PRDs → milestones → epics → tickets. Renders everywhere, instantly scannable. No Mermaid
- **D-09:** **Keep Linear generic.** Say "task tracker" not "Linear" — external contributors can't access Linear anyway. Avoids making the doc feel like an internal process leak

### Devcontainer Updates
- **D-10:** **Pin Python to 3.11.** Match CI/CD and Docker base image exactly. Prevents "works on my Codespace but fails in CI" if 3.12+ features creep in. Change image from `python:3.14` to `python:3.11`
- **D-11:** **Add frontend dev server.** Both backend (8100) and frontend (8101) auto-start. Forward both ports. Contributors working on web UI get both servers without manual steps
- **D-12:** **Add ESLint + Tailwind CSS IntelliSense.** Extend VS Code extensions list to include `dbaeumer.vscode-eslint` and `bradlc.vscode-tailwindcss` alongside existing Python + Ruff

### CONTRIBUTING.md Updates
- **D-13:** **Add "Finding Work" section.** 3-4 lines bridging to ROADMAP.md and deep dives. "Not sure where to start? Browse ROADMAP.md for milestones with contribution callouts, or read a deep dive on a feature that interests you"
- **D-14:** **Place right after intro.** Before "Development Setup" — first thing a contributor sees after "Thanks for wanting to help" is how to find meaningful work. Setup follows when they've found something
- **D-15:** **Keep "Open an issue on GitHub" for questions.** GitHub Issues are fine for contributor questions even though task tracking is on Linear. Standard open-source convention
- **D-16:** **Add Codespaces one-liner.** Before manual setup: badge/link to open in Codespaces. Low effort, high value for the one-click story

### Claude's Discretion
- Specific wording of each milestone's contribution callout (area pointers chosen per milestone's actual contribution opportunities)
- Exact wording of the expanded "How Planning Works" section
- Which deep dive docs need their contributor sections updated to properly receive callout traffic
- Whether devcontainer postStartCommand uses `&` backgrounding or a process manager

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Files being modified
- `ROADMAP.md` (repo root) — Adding "Want to help?" callouts to every milestone section
- `CONTRIBUTING.md` (repo root) — Adding "Finding Work" section and Codespaces mention
- `docs/roadmap/inventory.md` — Expanding "How Planning Works" section
- `.devcontainer/devcontainer.json` — Python version, frontend server, extensions

### Prior phase decisions (carry forward)
- `.planning/phases/03-forward-vision/03-CONTEXT.md` — Tone decisions: warm second-person, no AI slop (D-09), no em dashes (D-08), natural variation in openers (D-06)
- `.planning/phases/04-milestone-deep-dives/04-CONTEXT.md` — Template decisions: dual-audience structure (D-01), descriptive slug filenames (D-03), planning hierarchy once in index (D-16)
- `.planning/phases/01-feature-inventory/01-CONTEXT.md` — No file paths in user-facing content (D-08)

### Reference docs
- `docs/roadmap/` — All 21 deep dive files (callouts will link to these)
- `.env.example` — Environment variable documentation (devcontainer references this)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CONTRIBUTING.md` — Already 160 lines covering setup, tests, code style, commits, PRs, deps, AI provider changes, and research links table. Only needs "Finding Work" section and Codespaces mention added
- `.devcontainer/devcontainer.json` — Already functional with Node 22, mock provider, postCreateCommand for full setup, postStartCommand for backend. Needs Python version pin, frontend server, and extensions
- `docs/roadmap/inventory.md` — Already has "How Planning Works" section. Needs expansion from 1 paragraph to full hierarchy explanation with ASCII tree

### Established Patterns
- Milestone sections in ROADMAP.md use `####` headings with bird codenames, status lines, and deep dive links (established in Phases 3-4)
- Deep dive docs have dual-audience structure with contributor sections at bottom (Phase 4 D-01)
- CONTRIBUTING.md uses Jekyll frontmatter for GitHub Pages rendering

### Integration Points
- Callouts in ROADMAP.md link to `docs/roadmap/*.md` deep dives
- "Finding Work" section in CONTRIBUTING.md links to ROADMAP.md
- Devcontainer auto-starts both servers, creating the one-click experience CONT-03 requires

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-contributor-experience*
*Context gathered: 2026-04-28*
