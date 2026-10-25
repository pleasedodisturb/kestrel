---
gsd_state_version: "1.0"
milestone: v2.0
current_phase_name: defining requirements
status: planning
stopped_at: context exhaustion at 75% (2026-10-25)
last_updated: "2026-10-25T16:14:17.358Z"
last_activity: 2026-10-24
last_activity_desc: Milestone v2.0 started
state_head: 578bf28d852aa051e44a80baa1c38731b6cbb365
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
milestone_name: Lean Kestrel
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-21)

**Core value:** Make Kestrel's direction visible and structured so users can evaluate the product, contributors can pick meaningful work, and development stays coherent across sessions and milestones.
**Current focus:** Phase 6 — Test honesty

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-10-24 — Milestone v2.0 started

## Performance Metrics

**Velocity:**

- Total plans completed: 6
- Average duration: 6 min
- Total execution time: 0.37 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 2. Roadmap Foundation | 2 | 6 min | 3 min |
| 4. Milestone Deep Dives | 2 | 16 min | 8 min |
| 06 | 2 | - | - |

**Recent Trend:**

- Last 5 plans: 4 min, 2 min, 9 min, 7 min
- Trend: Stable, documentation-only phases. Phase 4 averaged 8 min/plan across 20 deep dives

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- This is an editorial milestone — no code changes, all documentation
- Web-first, user-first framing — every milestone described through end-user benefit
- Non-commercial repo — commercial SaaS forks off separately
- Mermaid diagrams must use GitHub-compatible subset only (no quadrantChart, HTML tags, color:#fff)
- CHANGELOG anchor pattern verified: [vX.Y.Z](CHANGELOG.md#XYZ-YYYY-MM-DD) with dots/parens stripped
- Shipped section uses warm teaching tone with user-facing language, no file paths or API routes
- Forward milestone version mapping: v0.13 Desktop App, v0.14 Browser Extension, v0.15 Mobile
- Milestone names reconciled: Voice Mode -> Writing Style Flywheel, Feature Flags -> Hosted Version
- Mermaid gantt todayMarker off + axisFormat %B confirmed safe for GitHub desktop rendering
- Flowchart dependency edges represent genuine prerequisites, not temporal ordering
- Pilot-first approach: write and validate one deep dive before scaling to all 10
- Word counts below 800 accepted for thinner milestones (CLI, Discovery) to honor D-23
- Dual-audience template established: user-facing top / contributor bottom separated by ---
- Planned template adaptation: Design Considerations, Open Questions, Research Needed replace shipped sections
- Feature Flags deep dive satisfies ROAD-15 without ROADMAP.md entry (internal infrastructure)
- All Mermaid diagrams synced with Phase 3 prose: Know Me added, Voice Mode renamed, Feature Flags edge added
- v1.1 roadmap: Phases 6-10 continue numbering from roadmap-m1 (ended at Phase 5); every phase ships as its own PR through the review-push gate (branch, signed review, merge only on green CI)
- Phase 8 (Over-admission rule, RULE-01..04) requires /gsd-discuss-phase before planning; the rule is a design decision to be re-measured against the 277-item blind set
- Phase 6: ruff pin resolved from CI at execution time (0.16.9); force-exclude kept as belt and braces; dead suite deleted with a 19-case ledger; AST guard has no allowlist and was extended post-review (flag-variable skipif, unittest.SkipTest)
- Phase 6 executor worktrees fork from HEAD via `worktree.baseRef: head` in .claude/settings.local.json (set with `gsd-tools worktree set-baseref head`); cleanup-wave merge commits are linearized onto the executor tip because review-push and the Review-trailers CI job refuse merge commits

### Pending Todos

1 pending after v1.0 close:
- contributor-issues-decision.md — design call: GitHub Issues for "Want to help?" callouts (low priority, can defer indefinitely)

### Blockers/Concerns

- ⚠️ [Phase 6] `tests/test_dep_security.py` npm-audit cases fail on GHSA-6j4f-fj2g-mc7p / GHSA-qhr7-859c-m2p7 (brace-expansion) in all three lockfiles — G-1856, blocks the frontend CI audit gate until bumped
- ⚠️ [Phase 6] Branch `G-1382/test-honesty` is local-only until `review-push run` → `sign` → push → PR

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260705-jcr | G-1274: fix and re-enable disabled workflows (scorecard pin, daily-scan guard, release-checks) | 2026-07-05 | efd1d0a | [260705-jcr-g-1274-fix-and-re-enable-disabled-workfl](./quick/260705-jcr-g-1274-fix-and-re-enable-disabled-workfl/) |
| 260705-kil | G-1277: Dependabot automerge + docker ecosystem + weekly image rebuild, Renovate removed | 2026-07-05 | 89973c6 | [260705-kil-g-1277-automate-security-fix-inclusion-d](./quick/260705-kil-g-1277-automate-security-fix-inclusion-d/) |
| 260705-lzs | G-1281: distill the Eyas writing system into public Kestrel docs — anti-slop, voice corpus, cover letters, LinkedIn. PR [#433](https://github.com/pleasedodisturb/kestrel/pull/433) | 2026-07-05 | 052bf9b | [260705-lzs-g-1281-distill-eyas-writing-system-into-](./quick/260705-lzs-g-1281-distill-eyas-writing-system-into-/) |
| 260705-msl | G-1282: port Eyas pipeline mechanisms — blocklist + parameterized geo gate (PII-stripped, PR [#436](https://github.com/pleasedodisturb/kestrel/pull/436)), then tiered application model + SmartRecruiters/Personio scrapers (PR [#439](https://github.com/pleasedodisturb/kestrel/pull/439)) | 2026-07-05 | 02f06db, 3804900 | [260705-msl-g-1282-port-eyas-pipeline-mechanisms-blo](./quick/260705-msl-g-1282-port-eyas-pipeline-mechanisms-blo/) |
| 20260718 | G-1361: update the stale Alembic Dash docset 0.8.4→1.18.5 — OSS PR [#5666](https://github.com/Kapeli/Dash-User-Contributions/pull/5666), no Kestrel source changed | 2026-07-18 | — (external PR) | [20260718-g-1361-update-alembic-dash-docset](./quick/20260718-g-1361-update-alembic-dash-docset/) |
| 20260718 | G-1362: refresh mypy (→2.3.0, [#5667](https://github.com/Kapeli/Dash-User-Contributions/pull/5667)) + click (→8.4.2, [#5668](https://github.com/Kapeli/Dash-User-Contributions/pull/5668)) Dash docsets — OSS PRs | 2026-07-18 | — (external PRs) | [20260718-g-1362-refresh-mypy-click-docsets](./quick/20260718-g-1362-refresh-mypy-click-docsets/) |
| 20260718 | G-1363 (partial 2/6): NEW Dash docsets via a custom MkDocs→Dash indexer — Typer [#5669](https://github.com/Kapeli/Dash-User-Contributions/pull/5669), FastAPI [#5670](https://github.com/Kapeli/Dash-User-Contributions/pull/5670). Vite/Vitest/Recharts/TanStack held (heavier Node builds) | 2026-07-18 | — (external PRs) | [20260718-g-1363-new-docset-typer](./quick/20260718-g-1363-new-docset-typer/) |
| 20260720 | G-1354 (scoring F1): hermetic provider api-key tests | 2026-07-20 | e428c1e | [20260720-g-1354-hermetic-provider-key-tests](./quick/20260720-g-1354-hermetic-provider-key-tests/) |
| 20260720 | G-1348 (scoring F2): repair the dead OpenAI provider — bad import + self-disabling test file + never registered in the factory; added cross-provider contract tests. Review caught a prompt-divergence BLOCKER. PR [#464](https://github.com/pleasedodisturb/kestrel/pull/464) | 2026-07-20 | 5548482 | [20260720-g-1348-repair-openai-provider](./quick/20260720-g-1348-repair-openai-provider/) |
| 20260720 | G-1350 (scoring F3): in-package Alembic migrations, single source of truth | 2026-07-20 | 2bb1bae | [20260720-g-1350-packaged-alembic-single-source](./quick/20260720-g-1350-packaged-alembic-single-source/) |
| 20260720 | G-1378: guard openrouter premium-model routing in fallback chains (G-1371 follow-up) — PR [#461](https://github.com/pleasedodisturb/kestrel/pull/461), adversarial-reviewed, 3 warnings fixed | 2026-07-20 | d83d2ed | [20260720-g-1378-openrouter-premium-guard](./quick/20260720-g-1378-openrouter-premium-guard/) |
| 20260721 | G-1353 (scoring F4): distillation logging in async-batch — investigated, re-scoped and PARKED (missing batch consumer) | 2026-07-21 | — (parked) | [20260721-g-1353-distillation-async-batch-investigation](./quick/20260721-g-1353-distillation-async-batch-investigation/) |
| 20260721 | G-1351 Phase A (scoring F5, 1/3): ESCO occupations taxonomy — model+migration, loader, bundled 2,942-occupation fixture (CC BY 4.0), 11 tests. Review: 7 warnings fixed incl. a wrong-DB `--db-url` bug. PR [#467](https://github.com/pleasedodisturb/kestrel/pull/467) | 2026-07-21 | 337dbc3 | [20260721-g-1351-esco-occupation-axis](./quick/20260721-g-1351-esco-occupation-axis/) |
| 260721-n1d | G-1351 Phase B (2/3): occupation matcher — in-package fixture consumer + pure `match_occupation`. 59 tests. 3-pass review found 10 (2 BLOCKER: inert-by-default → lazy self-populate; ambiguous ESCO alt-labels → probe-validated denylist), all fixed pre-merge. PR [#468](https://github.com/pleasedodisturb/kestrel/pull/468) | 2026-07-21 | aab8a97 | [260721-n1d-g-1351-phase-b-occupation-matcher](./quick/260721-n1d-g-1351-phase-b-occupation-matcher/) |
| 260721-p2l | G-1351 Phase C (3/3, **ticket DONE**): shadow-first occupation signal — cascade 4th signal structurally non-gating (16-case invariance test) + persisted + distillation `extra_signals`. Review: 1 BLOCKER (batch wiring untested — mutation survived) + 9 more, all fixed pre-merge. PR [#473](https://github.com/pleasedodisturb/kestrel/pull/473). Shadow data needs `CASCADE_SHADOW_ENABLED=true` | 2026-07-23 | cfa9832 | [260721-p2l-g-1351-phase-c-shadow-first-occupation-s](./quick/260721-p2l-g-1351-phase-c-shadow-first-occupation-s/) |
| 260805-lyl | G-1477 **DONE**: main CI RED — `tools.batch_apply_browser` collection error. Root cause PROVEN: mako 1.4.0 (CI-only; local resolves 1.4.1) ships a stray top-level `tools` package → PEP 420 namespace portion discarded → dotted import dies. Fix: bare-module imports off `tools/` sys.path; 105 refs incl. all mock.patch targets, mutation-probe verified. PR [#503](https://github.com/pleasedodisturb/kestrel/pull/503), main green | 2026-08-05 | b42a5d9 | [260805-lyl-g-1477-fix-kestrel-main-ci-red-tools-bat](./quick/260805-lyl-g-1477-fix-kestrel-main-ci-red-tools-bat/) |
| 260805-mv7 | G-1474 **DONE**: generic 7-way geo-eligibility engine (GeoProfile) forward-ported from Eyas geofix-v2 — config-driven, FRANKFURT + US_REMOTE presets, scrubbed 277-item blind set + differential/P-R/perf CI gates (**277/277 byte-identical**, R 93.62 / P 74.58), job_scorer delegation + opt-in prefilter annotation. 3 split plans, verifier 7/7, review found 4 config-route blockers + re-review found BL-05, ALL fixed pre-merge. PR [#504](https://github.com/pleasedodisturb/kestrel/pull/504). Follow-ups G-1483/1484/1485 | 2026-08-05 | dea5f7c | [260805-mv7-g-1474-generic-geo-eligibility-engine-ge](./quick/260805-mv7-g-1474-generic-geo-eligibility-engine-ge/) |
| 260806 | G-1491: commit the stale ruff autofixes loitering in `tools/` (F401 unused import, F541 f-string, I001 reorder). Review corrected the commit message pre-merge. PR [#505](https://github.com/pleasedodisturb/kestrel/pull/505) | 2026-08-06 | bea7f2d | — (no quick dir) |

## Deferred Items

Items acknowledged and deferred at roadmap-m1 milestone close on 2026-05-07:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| requirement | INV-01..08 (Phase 1 Feature Inventory) | absorbed into deep dives + inventory.md; formal artifact deferred | 2026-05-07 |
| tech_debt | 03-HUMAN-UAT.md status:partial — earlier human verification items still pending | non-blocking | 2026-05-07 |
| tech_debt | 05-02-SUMMARY.md describes superseded postStartCommand approach | planning artifact drift, no runtime impact | 2026-05-07 |
| polish | Codespaces URL inconsistency (README vs CONTRIBUTING) | cosmetic | 2026-05-07 |

## Session Continuity

Last session: 2026-10-25T17:17:00Z
Stopped at: v2.0 requirements step, phase-by-phase review with the maintainer (GSD new-milestone step 9)
Resume file: None

### v2.0 review position (2026-10-25)
Research (step 8) is committed: `.planning/research/{STACK,FEATURES,ARCHITECTURE,PITFALLS,SUMMARY,free-tier-routing}.md`.
The maintainer reviews each phase as idea / process / results, one at a time, before REQUIREMENTS.md is written.

Settled:
- Phase 0 **Map** (new, P0): Track A freezes today's outputs (script ledger, goldens with source hashes, mapping tables for every new behaviour encoded as red tests, per-source arrival counts). Track B is a June-October flow retrospective from this machine's evidence (commits, handoffs, action log, cost ledger, applications table, transcripts, screenpipe) with a keep / scope-and-plan / park / remove verdict per flow, each tagged profile-specific vs generic and "works for a non-tech profile". Cut lists for Phases 2 and 11 derive from these verdicts.
- Phase 1 **Foundation**: 1a safety nets (relocate trailer checker, CI Complete allow-list, wheel-content job fixing G-2015, import-all + OpenAPI tests, bootstrap with KESTREL_HOME resolver and ensure_schema, SQLite hardening, notify() seam, loopback bind for G-2009); 1b cost guard (status+code+Retry-After classifier with per-provider fixtures, spend halt at the provider factory with a non-swallowable exception and persisted ledger, bounded 429 waits, preflight, Free preset corrected, AST guard on provider construction).

Decisions: Pushover KEPT as opt-in notify() sink; all scrapers PORTED and judged on Map evidence; Release-As 2.0.0 at close; agents (Claude Code on subscription, API key in TUI, Codex/Pi via MCP or CLI twins) are swappable model suppliers while gates and state live in Kestrel; v2.0 carries a per-profile isolation constraint, real friend-profile searches plus an anonymised showcase are v2.1.

Next: present Phase 2 Cut A, then Phases 3-12 (Find, Filter, Scan, Score, Track, Write, Connect, Apply, Retire, Install). Then write REQUIREMENTS.md, spawn the roadmapper (phases numbered from 11, continuing v1.1 which ended at 10, unless --reset-phase-numbers), PR to main. Filed this session: G-2015 (stale frontend in the published wheel).
