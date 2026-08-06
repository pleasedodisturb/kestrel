---
gsd_state_version: 1.0
milestone: roadmap-m1
milestone_name: milestone
status: milestone_complete
stopped_at: Phase 5 complete. Milestone phases 2-5 done (Phase 1 skipped).
last_updated: "2026-05-07T17:40:00.000Z"
last_activity: 2026-05-07 — roadmap-m1 (Public Roadmap) milestone archived
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 8
  completed_plans: 8
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-21)

**Core value:** Make Kestrel's direction visible and structured so users can evaluate the product, contributors can pick meaningful work, and development stays coherent across sessions and milestones.
**Current focus:** Phase 5 complete. Milestone phases 2-5 done. Phase 1 (Feature Inventory) skipped.

## Current Position

Phase: 5 of 5 (Contributor Experience) — Complete
Plan: 2 of 2 in phase 5 (both plans complete, verified)
Status: Phase 5 complete. All requirements verified (CONT-01, CONT-02, CONT-03). 3 items in human UAT.
Last activity: 2026-08-06 — G-1477 (red-main fix, #503 → `b42a5d9`) and G-1474 (geo engine, #504 → `dea5f7c`) merged + closed; **v0.26.0 released** (#500 → `7184230`, PyPI/npm green); **`PII_PATTERNS` secret populated** → the G-1449 gate is armed for the first time (6 patterns, was silently fail-open at 0) and its first run cleared the new geo fixture. Follow-ups filed: G-1483/1484/1485 (geo, Backlog + route/agent), G-1491 (tools/ ruff autofixes, merged `bea7f2d`), G-1492 (linear cheatsheet, terminal-craft #160 merged), **G-1493 (P2 — `pr-review-standard.md` claims a pre-push `Reviewed-by` hook that does not exist; G-579 never landed)**.

> **NOTE (2026-08-06):** this file's quick-task table was rebuilt after a `git reset --hard` discarded ~1 month of uncommitted working-tree state in `.planning/`. Rows were reconstructed from the surviving untracked `.planning/quick/*/` dirs + git log; `ROADMAP.md` and `config.json` could not be reconstructed and sit at their committed state. `.planning/` is now COMMITTED rather than tracked-but-uncommitted, precisely so this cannot recur. See the COE.

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 4
- Average duration: 6 min
- Total execution time: 0.37 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 2. Roadmap Foundation | 2 | 6 min | 3 min |
| 4. Milestone Deep Dives | 2 | 16 min | 8 min |

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

### Pending Todos

1 pending after v1.0 close:
- contributor-issues-decision.md — design call: GitHub Issues for "Want to help?" callouts (low priority, can defer indefinitely)

### Blockers/Concerns

None.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260705-jcr | G-1274: fix and re-enable disabled workflows (scorecard pin, daily-scan guard, release-checks) | 2026-07-05 | efd1d0a | [260705-jcr-g-1274-fix-and-re-enable-disabled-workfl](./quick/260705-jcr-g-1274-fix-and-re-enable-disabled-workfl/) |
| 260705-kil | G-1277: Dependabot automerge + docker ecosystem + weekly image rebuild, Renovate removed | 2026-07-05 | 89973c6 | [260705-kil-g-1277-automate-security-fix-inclusion-d](./quick/260705-kil-g-1277-automate-security-fix-inclusion-d/) |
| 260705-lzs | G-1281: distill the Eyas writing system into public Kestrel docs | 2026-07-05 | — | [260705-lzs-g-1281-distill-eyas-writing-system-into-](./quick/260705-lzs-g-1281-distill-eyas-writing-system-into-/) |
| 260705-msl | G-1282: port Eyas pipeline mechanisms (blog) | 2026-07-05 | — | [260705-msl-g-1282-port-eyas-pipeline-mechanisms-blo](./quick/260705-msl-g-1282-port-eyas-pipeline-mechanisms-blo/) |
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

Last session: 2026-04-27T17:16:00.000Z
Stopped at: Completed 04-02-PLAN.md (Phase 4 complete: all deep dives, ROADMAP.md links, Mermaid fixes)
Resume file: None (Phase 4 complete)
