---
milestone: roadmap-m1
milestone_name: Public Roadmap
audited: 2026-05-07T17:30:00Z
status: gaps_found
scores:
  requirements: 23/31
  phases: 4/5
  integration: 5/8
  flows: 1/1 (E2E navigable via GitHub repo root, partially via README)
gaps:
  requirements:
    - id: "INV-01..INV-08"
      status: "orphaned"
      phase: "Phase 1: Feature Inventory"
      claimed_by_plans: ["01-01-PLAN.md (created but never executed)"]
      completed_by_plans: []
      verification_status: "missing"
      evidence: "Phase 1 deliberately skipped during milestone execution. No SUMMARY.md, no VERIFICATION.md. Inventory work was partially absorbed into docs/roadmap/inventory.md (created in Phase 4) and the deep dives, but the formal INV-* requirements were never explicitly checked off."
      mitigation: "The intent (visible record of shipped work) is satisfied via docs/roadmap/inventory.md (Shipped/Planned/Internal tables) and the 10 shipped deep dives. Formally, requirements remain pending."
  integration:
    - finding: "README.md → ROADMAP.md unwired"
      file: "README.md:30, 171-185"
      severity: major
      affects: "contributor-flow, CONT-01"
      evidence: "Header nav [Roadmap](#whats-coming) jumps to internal anchor for a 7-row table, not the actual ROADMAP.md file. README-first readers will not discover the full roadmap."
    - finding: "docs/index.md missing ROADMAP.md entry"
      file: "docs/index.md"
      severity: minor
      affects: "doc discoverability"
      evidence: "Documentation index referenced from CONTRIBUTING.md:184 does not list ROADMAP.md or any docs/roadmap/*.md. Contributors exploring docs from index will not discover deep dives."
    - finding: "Shipped deep dives missing contributor section"
      file: "docs/roadmap/{scoring-engine,discovery-engine,ai-provider-system,cost-control,application-pipeline,web-frontend,cli,infrastructure,onboarding-flow,pii-safety-boundary}.md"
      severity: minor
      affects: "DEEP-02, contributor-flow"
      evidence: "inventory.md:26 promises 'Each deep dive has a contributor section at the bottom' but 10 shipped deep dives have no such section. Planned deep dives correctly include 'Open Questions' / 'Research Needed'."
  flows: []
tech_debt:
  - phase: 03-forward-vision
    items:
      - "03-HUMAN-UAT.md status: partial — earlier human verification items still pending"
  - phase: 05-contributor-experience
    items:
      - "05-02-SUMMARY.md describes outdated postStartCommand approach (was superseded by .vscode/tasks.json after UAT) — planning artifact drift, no runtime impact"
      - "Codespaces URL inconsistency: README uses no query string, CONTRIBUTING uses ?quickstart=1 (cosmetic)"
nyquist:
  compliant_phases: []
  partial_phases: []
  missing_phases: ["02", "03", "04", "05"]
  overall: "VALIDATION.md not produced for any milestone phase (nyquist_validation enabled in config but not run)"
deferred_decision:
  intent: "Phase 1 was deliberately skipped — see decision log"
  rationale: "Editorial milestone; inventory work was naturally absorbed into deep-dive content (Phase 4) and the planning hierarchy section in inventory.md (Phase 5)"
---

# roadmap-m1 (Public Roadmap) — Milestone Audit

## Summary

| Metric | Value |
|--------|-------|
| Status | **gaps_found** |
| Requirements | 23/31 satisfied (74%) |
| Phases complete | 4/5 (Phase 1 skipped) |
| Integration wiring | 5/8 connections solid; 3 partial/missing |
| E2E contributor flow | Navigable via GitHub repo root (auto-renders ROADMAP.md); broken via README's internal nav |

## Phase Verifications

| Phase | VERIFICATION.md | Status | Notes |
|-------|----------------|--------|-------|
| 01-feature-inventory | ✗ missing | skipped | Plan exists, never executed |
| 02-roadmap-foundation | ✓ exists | passed | ROAD-01..08 satisfied |
| 03-forward-vision | ✓ exists | human_needed | UAT partial — older session |
| 04-milestone-deep-dives | ✓ exists | passed | DEEP-01..04 satisfied |
| 05-contributor-experience | ✓ exists | human_needed → resolved via UAT | All 3 UAT tests pass after iteration |

## Requirements Coverage (3-Source Cross-Reference)

| REQ-ID | Phase | VERIFICATION | SUMMARY | REQUIREMENTS.md | Final |
|--------|-------|--------------|---------|-----------------|-------|
| INV-01 | 1 | missing | absent | `[ ]` | **orphaned** |
| INV-02 | 1 | missing | absent | `[ ]` | **orphaned** |
| INV-03 | 1 | missing | absent | `[ ]` | **orphaned** |
| INV-04 | 1 | missing | absent | `[ ]` | **orphaned** |
| INV-05 | 1 | missing | absent | `[ ]` | **orphaned** |
| INV-06 | 1 | missing | absent | `[ ]` | **orphaned** |
| INV-07 | 1 | missing | absent | `[ ]` | **orphaned** |
| INV-08 | 1 | missing | absent | `[ ]` | **orphaned** |
| ROAD-01..06,08 | 2 | passed | listed (02-01) | `[x]` | **satisfied** |
| ROAD-07 | 2 | passed | listed (02-02) | `[x]` | **satisfied** |
| ROAD-09..11,16 | 3 | human_needed | inferred (03-01) | `[x]` | **satisfied** |
| ROAD-12..14 | 3 | human_needed | inferred (03-02) | `[x]` | **satisfied** |
| ROAD-15 | 3 | human_needed | inferred (03-02) | `[x]` | **satisfied** (deliberate ROADMAP exclusion per D-29) |
| DEEP-01..04 | 4 | passed | listed (04-01, 04-02) | `[x]` | **satisfied** |
| CONT-01 | 5 | resolved (UAT) | inferred (05-01) | `[x]` | **satisfied** |
| CONT-02 | 5 | resolved (UAT) | inferred (05-01) | `[x]` | **satisfied** |
| CONT-03 | 5 | resolved (UAT) | inferred (05-02) | `[x]` | **satisfied** |

## Integration Findings

### 1. README.md → ROADMAP.md unwired (major)

`README.md:30, 171-185` — the header nav `[Roadmap](#whats-coming)` jumps to a self-contained "What's coming" mini-table inside the README itself; nothing in README points to `ROADMAP.md` or `docs/roadmap/`. The full milestone roadmap with deep dives is invisible to a README-first reader.

**Fix:** Add a "Full Roadmap" link to the "What's coming" section, or change the header nav target to the file.

### 2. docs/index.md missing ROADMAP entry (minor)

`docs/index.md` does not list ROADMAP.md or any `docs/roadmap/*.md`. Contributors exploring docs from `CONTRIBUTING.md:184` ("Full documentation index →") will not discover deep dives.

**Fix:** Add a "Roadmap" section to `docs/index.md` linking to `../ROADMAP.md` and `roadmap/inventory.md`.

### 3. Shipped deep dives missing contributor section (minor)

10 shipped deep dives (`scoring-engine`, `discovery-engine`, `ai-provider-system`, `cost-control`, `application-pipeline`, `web-frontend`, `cli`, `infrastructure`, `onboarding-flow`, `pii-safety-boundary`) have no contributor-facing section. `inventory.md:26` advertises one. Planned deep dives correctly have "Open Questions" / "Research Needed".

**Fix (option A):** Add a "Where Help is Needed" section to each shipped deep dive. **Fix (option B):** Soften `inventory.md:26` to acknowledge shipped milestones surface contributor entry points via the `ROADMAP.md` "Want to help?" callouts only.

## Tech Debt

- **Phase 3 UAT partial** — `03-HUMAN-UAT.md status: partial` from earlier session, items pending
- **05-02-SUMMARY.md outdated** — describes `postStartCommand` approach superseded by `.vscode/tasks.json`. Planning-artifact drift only.
- **Codespaces URL inconsistency** — README has no query string, CONTRIBUTING uses `?quickstart=1`. Cosmetic.

## Nyquist Compliance

| Phase | VALIDATION.md | Compliant | Action |
|-------|---------------|-----------|--------|
| 02 | missing | — | `/gsd-validate-phase 2` (optional) |
| 03 | missing | — | `/gsd-validate-phase 3` (optional) |
| 04 | missing | — | `/gsd-validate-phase 4` (optional) |
| 05 | missing | — | `/gsd-validate-phase 5` (optional) |

`workflow.nyquist_validation: true` is enabled but no phase ran validation. For an editorial milestone (no code), validation is low-value — pure documentation work doesn't have meaningful test sampling to audit.

## Verdict

**`gaps_found`** because of:
1. **8 INV requirements orphaned** (Phase 1 deliberately skipped — known, intentional)
2. **3 cross-phase wiring gaps** (README→ROADMAP, docs/index→ROADMAP, shipped deep dives' contributor section)

The gaps are all addressable with small documentation edits. None block the milestone's substantive value (the public roadmap exists, renders, links work, contributors can find work, Codespace works live).

## Recommended Next Steps

| Option | Effect |
|--------|--------|
| **A. Fix 3 integration gaps inline** (~30 min) | Add README→ROADMAP link, add docs/index entry, soften inventory.md:26. Then re-audit. |
| **B. `/gsd-plan-milestone-gaps`** | Spawn planner to create a "Phase 6: Gap Closure" with formal plans for all gaps |
| **C. Accept gaps and `/gsd-complete-milestone`** | Ship v1.0 with gaps documented in MILESTONES.md as known deferrals; address in v1.1 |
| **D. Defer INV-* to v1.1** | Accept the 3 integration fixes as v1.0 closure scope, move INV-01..08 to v1.1 requirements |

**My recommendation:** **Option A.** The 3 integration findings are 30 minutes of editing, all in files we already touched this milestone. INV-01..08 should be officially deferred — they're already partially absorbed by the deep dives + inventory.md, and re-doing Phase 1 now would create a redundant artifact.
