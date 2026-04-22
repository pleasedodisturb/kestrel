# Phase 3: Demo Data - Context

**Gathered:** 2026-04-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Pre-baked sample jobs with pre-computed scores that deliver the "aha moment" immediately after onboarding completes. No API key required, works offline, proves scoring differentiates jobs across multiple career paths. Backend-only phase (seeder, model changes, fixture data) — the "Sample Results" banner rendering is Phase 4/5 (web) or already in CLI pipeline output.

</domain>

<decisions>
## Implementation Decisions

### Fixture Format & Seeding Trigger
- **D-01:** JSON fixture file (`demo_jobs.json`) shipped in package data — version-controlled, easy to edit, loaded by seeder at runtime
- **D-02:** Auto-seed after `kestrel init` completes — seamless, no extra command needed. User finishes wizard and demo data appears
- **D-03:** `kestrel doctor` auto-fixes missing demo data — detects absence, seeds automatically as remediation (self-healing, matches Phase 2 resolution philosophy)
- **D-04:** Re-seeding replaces old demo records with fresh timestamps — idempotent delete-then-insert. Running init again or doctor auto-fix refreshes stale dates

### Job Diversity & Score Spread
- **D-05:** 7 job families across 10 jobs: Tech, Marketing, Operations, Finance, Legal, Sales, Recruiting/HR — distribution is 1-2 jobs per family, proving scoring works for ANY career path
- **D-06:** Specific & realistic roles — real-sounding titles, fictional but plausible companies, with context (e.g., "Growth Marketing Lead, Series B Fintech" not "Marketing Manager")
- **D-07:** Bell curve score distribution: 2 high (85-95), 6 mid (50-75), 2 low (20-40) — immediately shows scoring differentiates, user sees which jobs match best
- **D-08:** Mix of geographic markets with EU emphasis — EU, UK, US represented. Remote is a work-mode tag alongside any market (e.g., "Berlin, Remote" / "London, Hybrid" / "New York, On-site"), not a standalone market category
- **D-09:** Salary ranges in appropriate currencies per market (EUR for EU, GBP for UK, USD for US)

### Relative Dates Mechanism
- **D-10:** Store day-offsets in fixture, compute absolute dates at seed time — fixture says `"days_ago": 3`, seeder computes `now - 3 days`. Same pattern as existing `GHOST_SEED_RECORDS` in `migration/seed.py`
- **D-11:** Re-seed refreshes dates — when re-seeding occurs (via init re-run or doctor), old demo records are deleted and re-created with fresh computed timestamps. No background refresh needed

### UI Banner & Demo Lifecycle
- **D-12:** `is_demo` Boolean column on Application model (default False) — requires Alembic migration. Queries can filter/detect demo records easily
- **D-13:** Auto-clear demo data when first real job arrives — once user discovers or manually adds a real job (is_demo=False), all demo records are silently deleted. Natural transition from demo to real pipeline
- **D-14:** "Sample Results" banner at top of pipeline view when any demo records exist — single dismissible message: "These are sample results to show how scoring works. They'll disappear once you add real jobs." Applies to both CLI table header and web UI (web rendering is Phase 4)

### Claude's Discretion
- Exact fixture JSON structure and field names
- Company name generation (fictional but plausible)
- Specific role titles per job family
- Migration naming and revision ID
- Auto-clear trigger point (discovery service hook vs application create hook)
- CLI banner formatting (Rich Panel vs simple print)
- Test fixture approach for seeder tests

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Seed Pattern (follow this)
- `src/career_os/migration/seed.py` -- Existing seeder with idempotent pattern (check existing, skip if present). GHOST_SEED_RECORDS uses days_ago offsets. Follow this exact pattern for demo seeder

### Application Model
- `src/career_os/models/models.py` lines 89-134 -- Application model fields (company, role, url, source, status, salary_range, fit_score, created_at). New is_demo column goes here

### CLI Integration Points
- `src/career_os/cli/init.py` -- Wizard command that must trigger demo seeding after completion
- `src/career_os/cli/doctor.py` -- Doctor command that must detect and auto-fix missing demo data

### Phase 1 Infrastructure
- `src/career_os/services/onboarding.py` -- Onboarding state service (mark demo_seeded step)

### Project Requirements
- `.planning/REQUIREMENTS.md` section Demo Data -- DEMO-01 through DEMO-05

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `migration/seed.py` pattern: idempotent seeding with source-marker detection, days_ago offset for timestamps
- `SessionLocal()` + `db.query()` pattern for all DB operations
- Application model already has fit_score (Float, nullable) — can store pre-computed scores directly
- `importlib.resources` or `pkg_resources` for loading package data files

### Established Patterns
- **Idempotency:** Check `db.query(Model).filter(marker).count() > 0` before inserting (see seed_ghost_detection_records)
- **Timestamps:** `datetime.now(UTC) - timedelta(days=N)` for relative date computation
- **CLI output:** `console.print("[green]\u2713[/green] Demo data seeded (10 sample jobs)")` pattern

### Integration Points
- `kestrel init` completion → call demo seeder
- `kestrel doctor` check → verify demo records exist, auto-seed if missing
- Application creation (discovery or manual add) → check if is_demo records exist, delete them (auto-clear trigger)
- Pipeline list views (CLI + web) → detect is_demo presence, show banner

</code_context>

<specifics>
## Specific Ideas

- Demo jobs should feel like real job board results, not test data — specific titles, plausible companies, varied markets
- EU-first market emphasis reflects the target user base
- Remote is a work mode, not a geographic market — "Amsterdam, Remote" not just "Remote"
- The 7-family spread is deliberately broad to counter the "this is just for developers" perception
- Auto-clear on first real job is the cleanest lifecycle — no user action needed, demo has served its purpose

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-demo-data*
*Context gathered: 2026-04-20*
