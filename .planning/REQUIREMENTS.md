# Requirements: Kestrel v2.0 (Lean Kestrel)

**Defined:** 2026-10-26 (hybrid: settled phases only; later phases are added as each review closes)
**Core Value:** One loop a real person can run: Kestrel finds and triages jobs, helps you write in your own voice, and learns from every outcome. The maintainer runs his daily search on it; a technical stranger gets from clone to a first useful job list in 15 minutes.
**Linear epic:** G-2013

## How this file is built

The maintainer reviews each phase of the reconciled build order (`.planning/research/SUMMARY.md`, "Implications for Roadmap") as idea / process / results, one at a time. Requirements below exist only for phases whose review has closed: Phase 0 **Map**, Phase 1 **Foundation**, Phase 2 **Cut A**. GSD phase numbering continues from v1.1 (which ended at Phase 10), so Map is Phase 11, Foundation Phase 12, Cut A Phase 13. Each later phase (Find, Filter, Scan, Score, Track, Write, Connect, Apply, Retire, Install) gets its requirements and a `/gsd-phase add` when its review closes.

Every phase ships as its own PR (or a short series) on a `<ticket>/<slug>` branch: conventional commits scoped to the ticket, `review-push run` then `review-push sign` before push, merge only on green CI. Release-As 2.0.0 at milestone close.

## v2.0 Requirements

### Map (MAP)

Phase 0 of the build order. Read-only: no production code changes, no paid LLM calls. Two tracks.

**Track A: freeze what exists (in Kestrel)**

- [ ] **MAP-01**: A committed script ledger lists every script in `tools/` and every script of the private pipeline that v2.0 ports, each with status (runs on a schedule / run by hand / dead), inputs, outputs, and a disposition (port / keep until Retire / delete), so no port or deletion later happens without a ledger row
- [ ] **MAP-02**: For every live output that v2.0 reproduces (scan arrivals, dedup verdicts, eligibility verdicts, scoring, digest, fact and voice gate verdicts), a golden fixture is frozen with the git hash of the script revision that produced it; fixtures are synthetic or scrubbed, and the PII scan passes on them
- [ ] **MAP-03**: Every target behaviour of later phases has an input-to-output mapping table encoded as a strict-xfail test that CI collects today, so each phase turns red tests green instead of writing tests after the fact
- [ ] **MAP-04**: Per-source arrival counts over the retrospective window (arrived, survived prefilter, scored, shortlisted, applied, by month) are committed as aggregates, so the Find phase decides source ports and cuts on evidence
- [ ] **MAP-05**: A protective golden test seeds an `ai_providers` row in `integration_configs`, runs `alembic upgrade head`, and reads the key back through the provider factory path, so no cut migration can silently empty AI credentials

**Track B: flow retrospective (in the private repo)**

- [ ] **MAP-06**: The full June-to-October 2026 flow retrospective (sessions, produced artefacts, jobs applied and outcomes, stalls and pushes, energy, cost; per flow, a-to-z) is written as a session doc inside the private pipeline's repository, and nothing of it is committed to Kestrel
- [ ] **MAP-07**: Every flow and every feature carries a verdict (keep / scope-and-plan / park / remove) with a profile-specific-or-generic tag and a "works for a non-technical profile" column; under-use alone is never a reason to remove
- [ ] **MAP-08**: Kestrel's `.planning/` receives only the anonymised verdict list (per flow and per feature, with counts and reasons; no company names, no person names, no dates finer than a month, no transcript quotes), and the CI PII scan passes on it
- [ ] **MAP-09**: The Cut A and Retire cut lists cite a verdict from MAP-08 for every item, so nothing is cut without evidence

### Foundation (FOUND)

Phase 1a of the build order: safety nets that make deletion and new entry points safe. Lands before any cut.

- [ ] **FOUND-01**: The review-trailer checker lives outside `tools/` and CI calls it from its new path, so Retire can delete `tools/` without breaking the PR gate
- [ ] **FOUND-02**: `CI Complete` fails when any required job is skipped, cancelled or missing from `needs` (success allow-list), proven by a workflow-lint test and one deliberate skip in a scratch run
- [ ] **FOUND-03**: A CI job builds the wheel in the same run, installs it in a fresh virtualenv, and fails when the bundled frontend is stale or a console entry point does not import (closes G-2015)
- [ ] **FOUND-04**: An import-all test imports every module under `career_os`, and an OpenAPI snapshot test pins the route set, so a cut that breaks an import or drops an endpoint fails CI
- [ ] **FOUND-05**: One `KESTREL_HOME` resolver decides the data directory, database path and config for every entry point, and `ensure_schema()` migrates the database when the CLI opens it without the API server running
- [ ] **FOUND-06**: SQLite runs with `busy_timeout` set and short transactions; a two-process contention test (CLI write while the API holds the database) passes
- [ ] **FOUND-07**: `kestrel start` and the API bind `127.0.0.1` by default; a non-loopback bind needs an explicit opt-in (environment variable, Docker override) and is refused while auth is off (closes G-2009)
- [ ] **FOUND-08**: A per-profile isolation test proves two profiles in one database never see each other's jobs, applications, settings or credentials through the service layer
- [ ] **FOUND-09**: The silent `except Exception: return ""` in the provider factory's database credential read becomes a logged warning, so a missing or broken `integration_configs` row is visible
- [ ] **FOUND-10**: The scoring payload carries no profile name, email, phone or address unless the active provider passes `check_privacy_boundary` or the user opts in through a documented setting; `score_job` runs the same boundary check as conversation mode and interview prep, a test asserts the serialised prompt for a cloud provider contains none of those fields, and the README and COMPARISON disclosure of the leak is removed (closes G-1846)

### Cost guard (COST)

Phase 1b of the build order: no unattended paid job runs before this exists. Absorbs v1.1 PROV-01..03.

- [ ] **COST-01**: Provider errors are classified by HTTP status, body error code and `Retry-After` into no-credits / rate-limited / spend-limit / other, with recorded fixtures per provider; a provider without fixtures gets the conservative class and is not advertised as safe
- [ ] **COST-02**: A spend guard at the provider factory halts every paid call once the per-run or per-day budget is reached, raises an exception no caller may swallow (guard test), and persists a spend ledger
- [ ] **COST-03**: A rate-limited response waits a bounded time (`Retry-After` capped) instead of escalating to a fallback or premium provider
- [ ] **COST-04**: A preflight reports each configured provider's readiness (key present, endpoint reachable, credits or quota) without scoring anything, and exits non-zero when a required provider is not ready
- [ ] **COST-05**: The Free preset resolves only to models that are free at release time, the pricing table is corrected, and a test fails if the Free chain ever contains a paid model
- [ ] **COST-06**: Providers are constructed only inside the factory (AST guard), so the spend guard cannot be bypassed

### Cut A (CUT)

Phase 2 of the build order: sprawl with no port dependency. Rule: a cut must remove running behaviour or an outside dependency, not just lines. One integration per PR. Each item cites its MAP-08 verdict.

- [ ] **CUT-01**: TickTick is gone: client, the 15-minute scheduler started in the API lifespan, the hooks in applications, goals and follow-ups, its endpoints, and its frontend parts; a documented agent recipe for TickTick's official MCP replaces it
- [ ] **CUT-02**: The `icalendar` dependency is replaced by a small internal `.ics` writer with a golden test; `.ics` export and the prefilled Google Calendar and Fantastical links behave identically
- [ ] **CUT-03**: The Cloudflare `worker/` and the `dashboard/` are removed together with their workflows, lockfiles and audit allow-list entries
- [ ] **CUT-04**: BMAD scaffolding (`_bmad/`, `.claude/skills/bmad-*`, its output directory and CLAUDE.md section) is removed
- [ ] **CUT-05**: Workflows and release channels without a consumer (worker and dashboard CI, npm package publish, homebrew bump) are deleted; the npm, homebrew and GHCR channels carry a deprecation notice pointing to PyPI; the `CI Complete` allow-list is updated in the same PR
- [ ] **CUT-06**: Database changes for cuts are forward-only Alembic revisions that delete only the cut integration's rows from `integration_configs` by name; older revisions stay byte-identical, orphan tables stay in place, and the MAP-05 golden still passes
- [ ] **CUT-07**: Frontend pages, API clients and tests for a cut feature are deleted in the same PR as their backend, with the frontend build and tests green
- [ ] **CUT-08**: A committed keep/remove inventory covers every doc page, environment variable and CI secret of the cut features, and the removed ones are gone from `.env.example`, docs and workflow files

## Decisions carried into later phases (not requirements yet)

- **Pushover is untouched** until Phase Retire; it already degrades to a logged "failed" when unconfigured. The `notify()` seam is introduced by the first phase that needs a new sink (Score digest), without moving Pushover callers.
- **Sources** (WARN, the board scrapers, JobSpy): all ported, judged on MAP-04 counts in Find.
- **OAuth and AI credentials**: OpenRouter PKCE stays (it feeds the web start path); AI credentials move out of the shared `integration_configs` table (dedicated table or YAML config) in Connect.
- **Calendar in Track**: Kestrel owns dates; sinks are `.ics` always, Apple Calendar/Reminders by default on a Mac behind an outbox with retry on the next interactive TUI start (macOS Automation permission needs a one-time GUI grant), any task manager through the user's agent and its MCP, Google Calendar through the prefilled link with full sync via an agent plus a Google Calendar MCP. Track's verification includes a scheduled run (LaunchAgent and SSH).
- **Connect** exposes due follow-ups and upcoming dates through the Kestrel MCP.
- **Multi-profile**: v2.0 carries the per-profile isolation constraint (FOUND-08); real friend-profile searches and an anonymised showcase are v2.1.
- **Agents are swappable model suppliers** (Claude Code on subscription, API key in the TUI, Codex or Pi via MCP or CLI twins); gates and state live in Kestrel.

## Future Requirements

Deferred to v2.1 or later, tracked in Linear, not in this roadmap.

- **MOM-01**: A non-technical person gets to a first job list without a terminal (desktop bundle or web-only path)
- **PERSON-01**: Richer person model with a kill criterion; automated learning from edits and outcomes
- **EXT-02**: Firefox target for the extension
- **APPLY-02**: Opt-in auto-submit (scripts kept, never deleted, never default)
- **SHOW-01**: Real friend-profile searches and an anonymised showcase

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full private clone of the repo for the milestone | Declined 2026-10-26: end-of-milestone scrub is the shape of the repo-split incident; the public repo would go dark; every PR would flow twice. Track B runs inside the private repo instead |
| Email digest | Not on the 15-minute path; file, terminal and TUI sinks only in v2.0 |
| Cutting any AI provider | Maintainer decision 2026-10-23: every provider stub stays; they give other people a choice |
| Cutting the writing and prefill tools, or the voice service | Maintainer correction 2026-10-23: core, not sprawl |
| Deleting `tools/` or `daily-scan.yml` in Cut A | They are the live pipeline and the porting source; Retire deletes them after replay verification |
| Moving Pushover callers in any early phase | Handled last, in Retire, after everything else is verified working |
| PII purge of public history (G-1448) | Human decision on remediation path after GitHub Support declined |

## Traceability

Filled by the roadmapper.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MAP-01 | Phase 11 | Pending |
| MAP-02 | Phase 11 | Pending |
| MAP-03 | Phase 11 | Pending |
| MAP-04 | Phase 11 | Pending |
| MAP-05 | Phase 11 | Pending |
| MAP-06 | Phase 11 | Pending |
| MAP-07 | Phase 11 | Pending |
| MAP-08 | Phase 11 | Pending |
| MAP-09 | Phase 11 | Pending |
| FOUND-01 | Phase 12 | Pending |
| FOUND-02 | Phase 12 | Pending |
| FOUND-03 | Phase 12 | Pending |
| FOUND-04 | Phase 12 | Pending |
| FOUND-05 | Phase 12 | Pending |
| FOUND-06 | Phase 12 | Pending |
| FOUND-07 | Phase 12 | Pending |
| FOUND-08 | Phase 12 | Pending |
| FOUND-09 | Phase 12 | Pending |
| FOUND-10 | Phase 12 | Pending |
| COST-01 | Phase 12 | Pending |
| COST-02 | Phase 12 | Pending |
| COST-03 | Phase 12 | Pending |
| COST-04 | Phase 12 | Pending |
| COST-05 | Phase 12 | Pending |
| COST-06 | Phase 12 | Pending |
| CUT-01 | Phase 13 | Pending |
| CUT-02 | Phase 13 | Pending |
| CUT-03 | Phase 13 | Pending |
| CUT-04 | Phase 13 | Pending |
| CUT-05 | Phase 13 | Pending |
| CUT-06 | Phase 13 | Pending |
| CUT-07 | Phase 13 | Pending |
| CUT-08 | Phase 13 | Pending |

**Coverage:**
- v2.0 requirements so far: 32 total (Map 9, Foundation 9, Cost guard 6, Cut A 8)
- Mapped to phases: 32
- Unmapped: 0 ✓
- Phases 3 to 12 of the build order: requirements pending their review

---
*Requirements defined: 2026-10-26 for Phases 0-2*
*Last updated: 2026-10-26 after the Phase 2 Cut A review closed*
