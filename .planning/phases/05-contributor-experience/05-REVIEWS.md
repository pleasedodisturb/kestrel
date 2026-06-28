---
phase: 5
reviewers: [codex, gemini]
reviewed_at: "2026-04-28T12:30:00.000Z"
plans_reviewed: [05-01-PLAN.md, 05-02-PLAN.md]
notes: "cursor skipped (keychain locked)"
---

# Cross-AI Plan Review — Phase 5

## Codex Review (GPT-5.5)

### Summary

Both plans are well-scoped for a documentation/configuration-only milestone and map cleanly to the locked decisions. The work is mostly low-risk, but the acceptance checks should be tightened so they verify contributor usefulness, not just string presence. The biggest risks are brittle counts, ambiguous wording around "all milestone sections," and devcontainer startup commands that may not reliably run both backend and frontend servers in Codespaces.

### Plan 05-01: ROADMAP.md Callouts + Planning Hierarchy

**Strengths:**
- Clear split between roadmap callouts and planning hierarchy documentation
- Correctly honors the key locked decisions: inline blockquotes, all milestones, shipped vs planned framing, deep dive links only
- Keeps inventory.md as the planning hierarchy location, matching D-07
- Explicitly avoids naming Linear and uses generic "task tracker," matching D-09
- Acceptance criteria are mostly easy to verify with simple text checks

**Concerns:**
- **MEDIUM:** "Exactly 19 occurrences" is brittle if ROADMAP.md changes before implementation. The real acceptance condition is "one per milestone section"
- **MEDIUM:** The plan says `ROADMAP.md -> docs/roadmap/ -> ...`, but D-08 requires ASCII. A literal arrow character would violate that. Use `->` or plain indentation
- **MEDIUM:** "No AI slop words" is not objectively verifiable unless the team defines banned phrasing
- **LOW:** "Each callout links to the corresponding deep dive only" may under-specify the "area pointers" decision
- **LOW:** Acceptance says "Linear" absent; if inventory.md already contains that word elsewhere, a whole-file check may fail for unrelated content

**Suggestions:**
- Change acceptance to: "one `> **Want to help?**` callout at the bottom of every milestone section currently present in ROADMAP.md"
- Require each deep dive link to resolve to an existing `docs/roadmap/*.md` file
- Use a literal ASCII tree with indentation and `->`, not Unicode arrows
- Replace "No AI slop words" with concrete style constraints
- Add an acceptance check that shipped, in-progress, and planned milestones have distinct framing

**Risk:** LOW to MEDIUM

### Plan 05-02: CONTRIBUTING.md + Devcontainer

**Strengths:**
- Addresses contributor onboarding directly: finding work plus one-click setup
- Correctly places "Finding Work" before setup, matching D-14
- Keeps manual setup while adding Codespaces
- Devcontainer decisions are concrete: Python 3.11, Node 22, backend/frontend ports, useful VS Code extensions
- Acceptance criteria include JSON validity and key configuration checks

**Concerns:**
- **HIGH:** `postStartCommand` running both backend and frontend can be fragile. If one command blocks in the foreground, the second may never start unless the command backgrounds processes correctly
- **MEDIUM:** A Codespaces badge/link needs the correct GitHub owner/repo path. If hardcoded incorrectly, the most visible onboarding path breaks
- **MEDIUM:** "Keep postCreateCommand unchanged" may conflict with making frontend startup reliable if dependencies are not installed there already
- **MEDIUM:** "4 extensions" assumes there are currently exactly 2 extensions. Safer acceptance is "includes ESLint and Tailwind CSS IntelliSense while preserving existing extensions"
- **LOW:** The plan maps only to CONT-03, but the CONTRIBUTING.md task also supports contributor discovery (CONT-01)

**Suggestions:**
- Specify the exact postStartCommand strategy: use `bash -lc`, background both servers, or delegate to an existing dev script
- Verify backend binds to `0.0.0.0:8100` and frontend binds to `0.0.0.0:8101`
- Acceptance should include "both ports have clear labels" in portsAttributes
- Adjust extension acceptance to "existing extensions preserved plus ESLint and Tailwind added"
- Confirm the Codespaces link targets the public repository's main branch

**Risk:** MEDIUM

---

## Gemini Review (Gemini 2.5 Pro)

### Summary

The plans for Phase 5 are exceptionally well-aligned with the "locked decisions" and provide a high-signal, low-friction path for new contributors. By shifting from generic "PRs welcome" invitations to milestone-specific callouts and providing a one-click development environment via Codespaces, the project significantly lowers the barrier to entry. The strategy of using documentation as the primary interface for contribution is a mature approach to open-source project management.

### Plan 05-01: ROADMAP.md Callouts + Planning Hierarchy

**Strengths:**
- Contextual engagement: Adding "Want to help?" callouts directly to milestones provides immediate context, matching tasks to current project priorities
- Structural clarity: ASCII tree diagram is a "render-anywhere" solution that provides transparency into how a roadmap item becomes a task
- Information architecture: Placing "Finding Work" before "Development Setup" prioritizes "Why/What" over "How"

**Concerns:**
- **LOW:** Deep dive link validity: Task 1 assumes a 1:1 mapping between 19 milestones and deep dive documents. 19 manual edits are prone to typographical errors in file paths
- **LOW:** BMAD acronym clarity: Ensure the "1-2 sentence explanation" explicitly defines BMAD for external contributors unfamiliar with the framework

**Suggestions:**
- Add a verification step to Plan 05-01 Task 1 to run a simple link check or manually verify that all 19 target files exist in `docs/roadmap/`
- Refine the ASCII tree to show how a single Roadmap item can result in multiple PRDs or Milestones

**Risk:** LOW

### Plan 05-02: CONTRIBUTING.md + Devcontainer

**Concerns:**
- **MEDIUM:** Blocking dev server: `postStartCommand` is often blocking. If `npm run dev` starts a persistent process that doesn't background itself, the container might hang or fail to signal "Ready" to the IDE
- **LOW:** Environment parity: Python 3.11 pin is correct and important

**Suggestions:**
- Background the dev server: Update the command to `npm run dev &` or use a process manager
- In CONTRIBUTING.md, mention that the first Codespace open may need 1-2 minutes for postCreateCommand to complete before servers are ready
- Add ESLint and Tailwind extensions provide immediate "guardrails" without manual configuration

**Risk:** LOW

---

## Consensus Summary

### Agreed Strengths
- Plans are well-scoped and correctly implement all 16 locked decisions (both reviewers)
- Clear separation of concerns with zero file overlap enables parallel execution (both)
- Acceptance criteria are mostly verifiable with grep/file checks (both)
- Using documentation as the contribution interface is a mature approach (Gemini)
- High ROI for effort: enabling Codespaces + clarifying contribution paths (both)

### Agreed Concerns (Priority Order)
1. **HIGH/MEDIUM: postStartCommand process management** — Both reviewers flagged that running backend + frontend in postStartCommand is fragile without explicit backgrounding. The `&` operator or a process manager is needed to prevent blocking. (Codex: HIGH, Gemini: MEDIUM)
2. **MEDIUM: Deep dive link validity** — Both reviewers noted that 19 manual link edits are error-prone. A verification step checking file existence would catch typos. (Codex: suggestion, Gemini: LOW concern)
3. **MEDIUM: Brittle milestone count** — "Exactly 19 occurrences" should be "one per milestone section" for resilience against ROADMAP.md changes. (Codex only)
4. **MEDIUM: Codespaces badge URL** — Must target the correct GitHub owner/repo path. (Codex only)

### Divergent Views
- **Overall risk:** Codex rated MEDIUM overall; Gemini rated LOW. Gemini emphasized the zero-risk to core application logic since only docs/config change. Codex focused more on the devcontainer startup subtlety.
- **BMAD acronym:** Gemini flagged need to define BMAD for external contributors; Codex did not mention this.
- **First-run UX:** Gemini suggested documenting that first Codespace open takes 1-2 min for setup; Codex did not raise this.
