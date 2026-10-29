# Roadmap: Kestrel

## Milestones

- ✅ **roadmap-m1 (Public Roadmap)** - Phases 1-5 (shipped 2026-05-07) - see [archive](milestones/roadmap-m1-ROADMAP.md)
- ⏹ **v1.1 (Geo gate to production)** - Phases 6-10, closed early 2026-10-23 at Phase 6; Phases 7-10 folded into v2.0 - see [archive](milestones/v1.1-ROADMAP.md)
- 🚧 **v2.0 (Lean Kestrel)** - Phases 11+ (in progress, hybrid: phases added as each review closes) - Linear epic G-2013

## Phases

<details>
<summary>✅ roadmap-m1 (Public Roadmap) (Phases 1-5) - SHIPPED 2026-05-07</summary>

- [ ] Phase 1: Feature Inventory (0/1 plans, deferred; intent absorbed into Phase 4 deep dives, INV-01..08 remain deferred)
- [x] Phase 2: Roadmap Foundation (2/2 plans, completed 2026-04-25)
- [x] Phase 3: Forward Vision (2/2 plans, completed 2026-04-26)
- [x] Phase 4: Milestone Deep Dives (2/2 plans, completed 2026-04-27)
- [x] Phase 5: Contributor Experience (2/2 plans, completed 2026-05-07)

Full archive: `.planning/milestones/roadmap-m1-ROADMAP.md`
Audit: `.planning/milestones/roadmap-m1-MILESTONE-AUDIT.md`

</details>

<details>
<summary>⏹ v1.1 (Geo gate to production) (Phases 6-10) - CLOSED EARLY 2026-10-23</summary>

- [x] Phase 6: Test honesty (2/2 plans, completed 2026-09-30)
- [ ] Phase 7: Wire the geo gate (not started; folded into v2.0 Filter)
- [ ] Phase 8: Over-admission rule (not started; folded into v2.0 Filter)
- [ ] Phase 9: Single authority (not started; folded into v2.0 Filter and Retire)
- [ ] Phase 10: Provider preflight (not started; folded into v2.0 Foundation cost guard)

Full archive: `.planning/milestones/v1.1-ROADMAP.md`

</details>

### 🚧 v2.0 Lean Kestrel (In Progress)

**Milestone goal:** Turn Kestrel from a do-everything platform into one loop a real person can run: it finds and triages jobs, helps you write in your own voice, and learns from every outcome. The maintainer runs his own daily search on it, and a technical stranger gets from clone to a first useful job list in 15 minutes. Linear epic G-2013 (phase tickets G-2039 Map, G-2040 and G-2041 Foundation waves, G-2042 Cut A umbrella).

Phase numbering continues from v1.1 (ended at Phase 10). This roadmap is hybrid: Phases 11 to 13 are the settled ones, and the remaining phases of the reconciled build order (`.planning/research/SUMMARY.md`) are added with `/gsd-phase add` as each review closes, in this order: Find, Filter, Scan, Score, Track, Write, Connect, Apply, Retire, Install. Every phase ships as its own PR (or a short series) on a `<ticket>/<slug>` branch: conventional commits scoped to the ticket, `review-push run` then `review-push sign` before push, merge only on green CI. Release-As 2.0.0 at milestone close.

- [ ] **Phase 11: Map** - Freeze what exists before anything is ported or cut: script ledger, goldens with source hashes, red mapping tests, per-source arrival counts, and the anonymised flow verdicts every later cut must cite (read-only, no paid LLM calls)
- [ ] **Phase 12: Foundation** - Safety nets (wave 1) and the cost guard (wave 2) land before any cut or unattended paid run: CI that fails closed, one `KESTREL_HOME`, loopback bind by default, no identifying profile fields in cloud scoring prompts, a spend halt no caller can swallow
- [ ] **Phase 13: Cut A** - Sprawl with no port dependency goes, one integration per PR, each citing a Map verdict: TickTick, the `icalendar` dependency, worker and dashboard, BMAD scaffolding, consumer-less workflows and release channels

## Phase Details

### Phase 11: Map

**Goal**: Before anything is ported or cut, today's behaviour is frozen as evidence: every script has a ledger row, every output v2.0 reproduces has a golden with the hash that produced it, every later behaviour has a red test CI already collects, and every flow and feature carries an anonymised verdict that the cut lists cite.
**Depends on**: Nothing in v2.0 (first phase of the milestone; main carries v1.1 Phase 6)
**Requirements**: MAP-01, MAP-02, MAP-03, MAP-04, MAP-05, MAP-06, MAP-07, MAP-08, MAP-09
**Linear tickets**: G-2039 (child of G-2013)
**Constraints** (binding, from STATE.md "v2.0 review position"): read-only, meaning no production code changes (`git diff main --stat -- src/ frontend/src/` is empty at PR review) and no paid LLM calls. Track B's raw retrospective (sessions, application rows, company names, dates, stall and recovery narrative) lives only in the private pipeline's repository, with the gitignored `private/retrospective/` in Kestrel for working notes; Kestrel's `.planning/` receives the anonymised verdict list only. Track A goldens are synthetic or scrubbed, never copied from the private pipeline's data. The CI PII scan is the second net, not the first.
**Success Criteria** (what must be TRUE):
  1. A committed script ledger has a row for every file under `tools/` and every private-pipeline script v2.0 ports, each with status (runs on a schedule / run by hand / dead), inputs, outputs and disposition (port / keep until Retire / delete); comparing `ls tools/` with the ledger shows no file without a row
  2. For each live output class v2.0 reproduces (scan arrivals, dedup verdicts, eligibility verdicts, scoring, digest, fact and voice gate verdicts) a golden fixture is committed with the git hash of the script revision that produced it, the fixtures are synthetic or scrubbed, and the CI PII scan passes on them; the protective `ai_providers` golden (seed the `integration_configs` row, `alembic upgrade head`, read the key back through the provider factory) is green on main
  3. Every target behaviour of the later phases has an input-to-output mapping table encoded as a strict-xfail test: `pytest --collect-only` lists them, and a full run reports each as xfail with none passing and none erroring
  4. Per-source arrival counts over the retrospective window (arrived, survived prefilter, scored, shortlisted, applied, by month) are committed as aggregates with no job-level rows
  5. The full June-to-October 2026 flow retrospective exists as a session doc in the private pipeline's repository and nowhere in Kestrel; Kestrel's `.planning/` holds the anonymised verdict list (per flow and per feature: keep / scope-and-plan / park / remove, a profile-specific-or-generic tag, a "works for a non-technical profile" column, counts and reasons; no company names, no person names, no dates finer than a month, no transcript quotes), the CI PII scan passes on it, and the Cut A and Retire cut lists cite one of its verdicts for every item

**Plans**: TBD
**Git delivery**: Branch `G-2039/map` off main; conventional commits scoped to the ticket (`test(G-2039): ...` for goldens and red tests, `docs(G-2039): ...` for the ledger, counts and verdict list); `review-push run` then `review-push sign` before push; one PR for the phase, opened once the verdict list is in; merge only when CI is green. Track B's raw retrospective is committed in the private pipeline's repository, never in this PR.

### Phase 12: Foundation

**Goal**: Deleting code and opening the database from new entry points becomes safe, and no unattended paid run can overspend: CI fails closed, every entry point resolves one `KESTREL_HOME`, the API listens on loopback unless told otherwise, and every paid call goes through a spend guard that tells provider errors apart and halts at budget.
**Depends on**: Phase 11 (the goldens, red mapping tests and ledger are the regression net; the MAP-05 golden must stay green through the credential-read and factory changes made here)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06, FOUND-07, FOUND-08, FOUND-09, FOUND-10, COST-01, COST-02, COST-03, COST-04, COST-05, COST-06
**Linear tickets**: G-2040 (wave 1), G-2041 (wave 2), children of G-2013
**Waves**: One phase, two waves, two separate PRs. Wave 1 "safety nets" is FOUND-01..10 and merges first. Wave 2 "cost guard" is COST-01..06 and starts after wave 1 merges. This phase lands before any cut (Phase 13 waits for both waves), and nothing unattended and paid (no cron scan, no shadow run) runs before wave 2 merges. Pushover is untouched here: no `notify()` seam, no callers moved (see REQUIREMENTS.md "Decisions carried into later phases").
**Planning note**: Wave 1 is standard patterns. Wave 2 needs `/gsd-plan-phase 12 --research-phase` before planning: capture real 402/429/400 response bodies per provider (only Anthropic, OpenAI and OpenRouter are verified from docs; the other seven get the conservative class until fixtures exist), design the spend ledger (reserve/settle under `BEGIN IMMEDIATE`), and settle batch-API cost accounting.
**Success Criteria** (what must be TRUE):
  1. CI fails closed: `CI Complete` turns red when any required job is skipped, cancelled or missing from `needs` (proven by a workflow-lint test and one deliberate skip in a scratch run); the review-trailer checker runs from its new home outside `tools/`; a wheel built in the same CI run installs into a fresh virtualenv, serves the current frontend build and imports every console entry point (G-2015 closed)
  2. A change that breaks an import, drops an endpoint, leaks across profiles or loses a credential silently fails a test: the import-all test imports every module under `career_os`, the OpenAPI snapshot pins the route set, the per-profile isolation test shows two profiles in one database never see each other's jobs, applications, settings or credentials through the service layer, and a missing or broken `integration_configs` row logs a warning instead of returning an empty string; the scoring prompt sent to a cloud provider carries no profile name, email, phone or address unless the provider passes the privacy boundary or the user opted in (G-1846 closed)
  3. Every entry point opens the right, migrated database: the CLI, the API and any headless process resolve the same data directory, database path and config through one `KESTREL_HOME` resolver; the CLI opening an unmigrated database without the server running migrates it through `ensure_schema()`; a CLI write while the API holds the database succeeds within `busy_timeout` (two-process contention test); `kestrel start` and the API bind `127.0.0.1` by default, and a non-loopback bind needs an explicit opt-in (environment variable, Docker override) and is refused while auth is off (G-2009 closed)
  4. A paid call cannot overspend or escalate: once the per-run or per-day budget is reached, the provider factory raises a halt exception that no caller swallows (guard test) and the spend ledger is persisted; a 402 is classified no-credits and a 429 rate-limited from status, body code and `Retry-After` against recorded per-provider fixtures (a provider without fixtures gets the conservative class and is not advertised as safe); a rate-limited response waits a bounded, `Retry-After`-capped time instead of falling through to a fallback or premium provider; an AST guard fails when a provider is constructed anywhere but the factory
  5. Readiness is known before anything is scored: the preflight reports each configured provider's readiness (key present, endpoint reachable, credits or quota) without scoring a job and exits non-zero when a required provider is not ready; the Free preset resolves only to models that are free at release time, the pricing table is corrected, and a test fails if the Free chain ever contains a paid model

**Plans**: TBD
**Git delivery**: Two PRs on two branches off main. Wave 1: `G-2040/foundation-safety-nets`, conventional commits scoped to its ticket (`ci(G-2040): ...`, `feat(G-2040): ...`, `test(G-2040): ...`). Wave 2, after wave 1 merges: `G-2041/foundation-cost-guard`, commits scoped to its ticket (`feat(G-2041): ...`, `test(G-2041): ...`). Each: `review-push run` then `review-push sign` before push; merge only when CI is green.

### Phase 13: Cut A

**Goal**: The sprawl with no port dependency is gone and the product runs lighter: TickTick, the Cloudflare worker and dashboard, BMAD scaffolding, consumer-less workflows and release channels, and the `icalendar` dependency are removed, each removal citing a Map verdict and each removing running behaviour or an outside dependency, with the frontend, docs, environment and CI cleaned in the same PR as the backend.
**Depends on**: Phase 12, both waves (the import-all, OpenAPI and wheel tests catch what a cut breaks; the `CI Complete` allow-list changes with every workflow deletion; the cut list and its verdicts come from Phase 11)
**Requirements**: CUT-01, CUT-02, CUT-03, CUT-04, CUT-05, CUT-06, CUT-07, CUT-08
**Linear tickets**: G-2042 (umbrella; one child per integration filed at planning time), child of G-2013
**Rules** (binding, from the Cut A review 2026-10-26): one integration per PR; every PR description cites the MAP-08 verdict for its item; a cut must remove running behaviour or an outside dependency, not just lines. Calendar code stays (only the `icalendar` dependency goes); sources (WARN, the board scrapers, JobSpy) and OAuth (OpenRouter PKCE) are not cut; `tools/` and `daily-scan.yml` stay until Retire; Pushover is untouched; every AI provider stays.
**Planning note**: Run the Alembic upgrade spike before `/gsd-plan-phase 13`: generate a real v0.28.2 database, run `alembic upgrade head` with SQLite foreign-key enforcement on and off, and confirm how `integration_configs` rows are handled; the MAP-05 golden is the regression net for every cut migration. Use `/gsd-plan-phase 13 --research-phase` if the spike leaves open questions.
**Success Criteria** (what must be TRUE):
  1. TickTick is gone: the API lifespan starts without the 15-minute scheduler, the hooks in applications, goals and follow-ups are removed, its endpoints are absent from the OpenAPI snapshot, its frontend parts are deleted, and a documented agent recipe for TickTick's official MCP replaces it
  2. With `icalendar` removed from `pyproject.toml`, `.ics` export and the prefilled Google Calendar and Fantastical links behave identically: the internal `.ics` writer passes a golden test against the previous output, and the follow-up flows that call it are unchanged
  3. `worker/`, `dashboard/` and the BMAD scaffolding (`_bmad/`, `.claude/skills/bmad-*`, its output directory, the CLAUDE.md section) are deleted with their workflows, lockfiles and audit allow-list entries; the consumer-less workflows (worker and dashboard CI, npm publish, homebrew bump) are gone; the npm, homebrew and GHCR channels carry a deprecation notice pointing to PyPI; the `CI Complete` allow-list is updated in the same PR and `CI Complete` is green afterwards
  4. Each cut's database change is a forward-only Alembic revision that deletes only that integration's rows from `integration_configs` by name; older revisions are byte-identical to main, orphan tables stay in place, and the MAP-05 golden passes after `alembic upgrade head` on a real v0.28.2 database
  5. Each cut PR deletes the feature's frontend pages, API clients and tests together with its backend, with `npm run build` and `npm run test` green; a committed keep/remove inventory covers every doc page, environment variable and CI secret of the cut features, and the removed ones no longer appear in `.env.example`, docs or workflow files

**Plans**: TBD
**Git delivery**: One PR per integration, each on its own branch off main (`<child>/cut-ticktick`, `<child>/cut-icalendar`, `<child>/cut-worker-dashboard`, `<child>/cut-bmad`, `<child>/cut-workflows`, each child of G-2042); conventional commits scoped to that integration's ticket (`refactor(<child>): ...`, `chore(<child>): ...`, `ci(<child>): ...`); `review-push run` then `review-push sign` before push; merge only when CI is green; each PR description cites its MAP-08 verdict.
**UI hint**: yes (deletions only: the frontend pages and API clients of cut features are removed and the frontend build stays green; no new UI is designed)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|-----------------|--------|-----------|
| 1. Feature Inventory | roadmap-m1 | 0/1 | Deferred to v1.1 | - |
| 2. Roadmap Foundation | roadmap-m1 | 2/2 | Complete | 2026-04-25 |
| 3. Forward Vision | roadmap-m1 | 2/2 | Complete | 2026-04-26 |
| 4. Milestone Deep Dives | roadmap-m1 | 2/2 | Complete | 2026-04-27 |
| 5. Contributor Experience | roadmap-m1 | 2/2 | Complete | 2026-05-07 |
| 6. Test honesty | v1.1 | 2/2 | Complete    | 2026-09-30 |
| 7. Wire the geo gate | v1.1 | 0/0 | Folded into v2.0 | - |
| 8. Over-admission rule | v1.1 | 0/0 | Folded into v2.0 | - |
| 9. Single authority | v1.1 | 0/0 | Folded into v2.0 | - |
| 10. Provider preflight | v1.1 | 0/0 | Folded into v2.0 | - |
| 11. Map | v2.0 | 0/TBD | Not started | - |
| 12. Foundation | v2.0 | 0/TBD | Not started | - |
| 13. Cut A | v2.0 | 0/TBD | Not started | - |
