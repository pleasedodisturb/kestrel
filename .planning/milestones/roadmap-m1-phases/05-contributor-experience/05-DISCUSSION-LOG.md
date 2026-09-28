# Phase 5: Contributor Experience - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-28
**Phase:** 05-contributor-experience
**Areas discussed:** Want to help? callout design, Planning hierarchy scope, Devcontainer & existing assets, CONTRIBUTING.md integration

---

## Want to help? Callout Design

### Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Inline per milestone | Each milestone section gets a short callout at the bottom | ✓ |
| Grouped "Contribute" section | One section at bottom listing all milestones with contribution paths | |
| Both — inline + summary table | Short inline callout per milestone, plus summary table at bottom | |

**User's choice:** Inline per milestone
**Notes:** Readers see contribution paths right where their interest peaks

### Specificity

| Option | Description | Selected |
|--------|-------------|----------|
| Area pointers | Point to domain area + deep dive doc | ✓ |
| Concrete tasks with links | Link to specific Linear tickets or GitHub issues | |
| General area + deep dive link | Just point to deep dive, let contributors self-navigate | |

**User's choice:** Area pointers
**Notes:** Specific enough to act on, stable enough not to go stale

### Coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Planned milestones only | Shipped milestones are done, contribution is maintenance | |
| All milestones | Shipped and planned both get callouts | ✓ |
| Planned + select shipped | Only shipped milestones that genuinely need community help | |

**User's choice:** All milestones
**Notes:** None

### Shipped Tone

| Option | Description | Selected |
|--------|-------------|----------|
| Improvement-focused | Shipped callouts use slightly different framing for improvement areas | ✓ |
| Same style everywhere | No distinction between shipped and planned | |

**User's choice:** Improvement-focused
**Notes:** None

### Visual Format

| Option | Description | Selected |
|--------|-------------|----------|
| Blockquote | GitHub renders with left border, visually distinct | ✓ |
| GitHub alert syntax | > [!TIP] — colored icon and background | |
| Plain paragraph | Italic text, minimal visual weight | |

**User's choice:** Blockquote
**Notes:** None

### Link Targets

| Option | Description | Selected |
|--------|-------------|----------|
| Deep dive only | Callout links to deep dive, which handles routing to setup | ✓ |
| Deep dive + CONTRIBUTING.md | Two links per callout | |
| You decide | Claude picks per milestone | |

**User's choice:** Deep dive only
**Notes:** None

---

## Planning Hierarchy Scope

### Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Expand in place | Keep in inventory.md, flesh out with diagram and layer explanations | ✓ |
| Standalone doc | Create separate docs/PLANNING-HIERARCHY.md | |
| Already sufficient | Existing paragraph covers the chain | |

**User's choice:** Expand in place
**Notes:** None

### Diagram

| Option | Description | Selected |
|--------|-------------|----------|
| ASCII tree | Simple indented tree, renders everywhere | ✓ |
| Mermaid flowchart | More visual but another Mermaid to maintain | |
| No diagram — prose only | Simpler to maintain but harder to scan | |

**User's choice:** ASCII tree
**Notes:** None

### Linear Reference

| Option | Description | Selected |
|--------|-------------|----------|
| Mention Linear by name | Transparent about actual tooling | |
| Keep it generic | Say "task tracker" — external contributors can't access Linear | ✓ |
| You decide | Claude picks based on context | |

**User's choice:** Keep it generic
**Notes:** None

---

## Devcontainer & Existing Assets

### Python Version

| Option | Description | Selected |
|--------|-------------|----------|
| Keep 3.14 | Forward-compatible, project says 3.11+ (floor) | |
| Pin to 3.11 | Matches CI/CD and Docker base exactly | ✓ |
| Pin to 3.12 or 3.13 | Middle ground | |

**User's choice:** Pin to 3.11
**Notes:** Prevents "works on Codespace but fails in CI"

### Frontend Server

| Option | Description | Selected |
|--------|-------------|----------|
| Add frontend dev server | Both servers auto-start, forward both ports | ✓ |
| Backend only | Contributors run frontend manually when needed | |
| You decide | Claude picks best approach | |

**User's choice:** Add frontend dev server
**Notes:** None

### VS Code Extensions

| Option | Description | Selected |
|--------|-------------|----------|
| Add ESLint + Tailwind | Standard for the stack | ✓ |
| Keep minimal | Only Python + Ruff | |
| Full stack | ESLint, Tailwind, Prettier, SQLite viewer, Docker, GitLens | |

**User's choice:** Add ESLint + Tailwind
**Notes:** None

---

## CONTRIBUTING.md Integration

### Finding Work Section

| Option | Description | Selected |
|--------|-------------|----------|
| Add a short section | 3-4 lines bridging to ROADMAP.md and deep dives | ✓ |
| No change | ROADMAP.md handles "what", CONTRIBUTING.md handles "how" | |
| Major restructure | Rewrite to lead with finding work | |

**User's choice:** Add a short section
**Notes:** None

### Position

| Option | Description | Selected |
|--------|-------------|----------|
| Right after intro | Before Development Setup | ✓ |
| After Development Setup | Setup first, then find work | |
| You decide | Claude places naturally | |

**User's choice:** Right after intro
**Notes:** First thing a contributor sees after welcome is how to find work

### Questions Section

| Option | Description | Selected |
|--------|-------------|----------|
| Keep it | GitHub Issues fine for contributor questions | ✓ |
| Add Discussions | Enable GitHub Discussions for Q&A | |
| Remove the section | Use PRs for communication | |

**User's choice:** Keep it
**Notes:** Standard open-source convention

### Codespaces Mention

| Option | Description | Selected |
|--------|-------------|----------|
| Add a one-liner | Badge/link before manual setup | ✓ |
| Detailed section | Full Codespaces explanation with free tier info | |
| No mention | Discoverable through GitHub UI | |

**User's choice:** Add a one-liner
**Notes:** None

---

## Claude's Discretion

- Specific wording of each milestone's contribution callout
- Exact wording of expanded "How Planning Works" section
- Whether deep dive contributor sections need updates to receive callout traffic
- Devcontainer postStartCommand implementation detail (backgrounding approach)

## Deferred Ideas

None — discussion stayed within phase scope.
