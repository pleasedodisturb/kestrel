# Phase 3: Demo Data - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-20
**Phase:** 03-demo-data
**Areas discussed:** Fixture format & seeding trigger, Job diversity & score spread, Relative dates mechanism, UI banner & demo lifecycle

---

## Fixture Format & Seeding Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| JSON fixture file | A demo_jobs.json in package data — easy to edit, version-controlled | ✓ |
| Python dicts in seed module | Like existing GHOST_SEED_RECORDS — inline, no file I/O | |
| YAML fixture file | More readable but adds PyYAML dependency | |

**User's choice:** JSON fixture file
**Notes:** Follows common fixture patterns, easy to maintain 10 detailed records

| Option | Description | Selected |
|--------|-------------|----------|
| Auto after kestrel init completes | Seamless — user finishes wizard, demo data appears | ✓ |
| Explicit kestrel seed-demo command | User must opt-in, more friction | |
| Both: auto + explicit command | Auto-seeds after init, also exposes explicit command | |

**User's choice:** Auto after init completes

| Option | Description | Selected |
|--------|-------------|----------|
| Doctor auto-fixes | Detects missing demo data and seeds automatically | ✓ |
| Doctor only reports | Says "missing" but doesn't fix | |

**User's choice:** Doctor auto-fixes (self-healing)

---

## Job Diversity & Score Spread

| Option | Description | Selected |
|--------|-------------|----------|
| 4 families: Tech, Marketing, Ops, Finance | 10 jobs split ~3/3/2/2 | |
| 3 families minimum | 10 jobs split ~4/3/3 | |
| You decide | Claude picks | |

**User's choice:** Other — 7 families: Tech, Marketing, Operations, Finance, Legal, Sales, Recruiting/HR
**Notes:** User explicitly added Legal, Sales, and Recruiting/HR to broaden beyond the suggested options

| Option | Description | Selected |
|--------|-------------|----------|
| Bell curve: 2 high, 6 mid, 2 low | Realistic spread showing differentiation | ✓ |
| Skewed positive | 7 high, 2 mid, 1 low | |
| Even spread | Scores 10-100 evenly distributed | |

**User's choice:** Bell curve distribution

| Option | Description | Selected |
|--------|-------------|----------|
| Specific & realistic | Real-sounding titles, plausible fictional companies | ✓ |
| Generic titles only | "Software Engineer", "Marketing Manager" | |
| You decide | Claude picks detail level | |

**User's choice:** Specific & realistic roles

| Option | Description | Selected |
|--------|-------------|----------|
| Mix of markets | US, UK, EU, Remote represented | ✓ |
| All Remote | Location-agnostic, simpler | |
| Single market (US) | All USD, US-centric | |

**User's choice:** Mix of markets, EU-first emphasis. Remote is a work-mode tag per market (e.g., "Berlin, Remote"), not a standalone category

---

## Relative Dates Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Store as day-offsets, compute at seed time | Fixture says "days_ago: 3", seeder computes absolute | ✓ |
| Recompute at display time | Store relative_days field, render dynamically | |
| Re-seed on each app startup | Delete and recreate every startup | |

**User's choice:** Day-offsets computed at seed time (matches existing GHOST_SEED_RECORDS pattern)

| Option | Description | Selected |
|--------|-------------|----------|
| Re-seed refreshes dates | Delete old, insert fresh on re-run | ✓ |
| Accept staleness | Fixed once seeded | |
| Background refresh | App detects old records, silently updates | |

**User's choice:** Re-seed refreshes dates

---

## UI Banner & Demo Lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| is_demo column on Application model | Boolean, default False, migration adds it | ✓ |
| source='demo' marker | Reuse existing source column | |
| Separate DemoJob model | Dedicated table | |

**User's choice:** is_demo Boolean column

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-clear when first real job arrives | Demo served its purpose, clean silently | ✓ |
| Manual clear only | User explicitly removes | |
| Clear after N days | Time-based expiry | |

**User's choice:** Auto-clear on first real job

| Option | Description | Selected |
|--------|-------------|----------|
| Top of pipeline view banner | Single dismissible message when demo records exist | ✓ |
| Per-record badge | [DEMO] tag on each row | |
| Both banner + badge | Maximum information | |

**User's choice:** Top banner only

---

## Claude's Discretion

- Exact fixture JSON structure and field names
- Company name generation
- Specific role titles per family
- Migration naming
- Auto-clear trigger implementation
- CLI banner formatting
- Test approach

## Deferred Ideas

None
