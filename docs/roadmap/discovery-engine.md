# Discovery Engine

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Find relevant job postings automatically so you do not have to check every board manually.

## What This Delivers

Kestrel scans multiple job boards on a schedule and brings the results to you. Instead of visiting Indeed, LinkedIn, Glassdoor, and Arbeitsagentur separately every day, you configure your search once and the discovery engine handles the rest. New postings appear in your pipeline ready for scoring.

Before any job reaches the AI scoring step, a pre-filter runs to eliminate obvious mismatches. If you are looking for product management roles, a machine learning engineer posting gets dropped without spending a single AI token. This filtering eliminates roughly 60% of results, which saves money and keeps your pipeline focused on jobs worth evaluating.

Each job board has its own adapter that normalizes the data into a consistent format. When one board changes its structure or goes down temporarily, the others keep running. You see a warning in the logs, not a broken pipeline. The adapters are independent by design so that a problem with one source never blocks the rest.

Discovery runs as a background task while Kestrel is running. The default schedule is weekly, but you can trigger a manual scan anytime. Results flow directly into the scoring queue, so the full cycle from discovery to scored pipeline entry happens without intervention.

## How It Works

Under the hood, Kestrel uses the python-jobspy library to scrape job board listings. Each configured board gets its own adapter that translates the raw scraping output into a standard format. The scheduler fires as an asyncio background task during the application's lifecycle, calling each adapter in sequence and deduplicating results against jobs already in your database.

The pre-filter step runs before scoring. It uses keyword matching and title analysis to drop postings that clearly do not match your search profile. Jobs that pass the filter move into the scoring queue.

## Current Status

*Shipped in [v0.3.0](../../CHANGELOG.md#030-2026-04-13)*

Multi-board discovery is fully functional with adapters for Indeed, LinkedIn, Glassdoor, and Arbeitsagentur. Pre-filtering, background scheduling, and deduplication are all active. The adapter pattern makes it straightforward to add new job board sources.

## Related Milestones

- **[Scoring Engine](scoring-engine.md)** -- Discovered jobs flow into scoring for evaluation
- **[Browser Extension](browser-extension.md)** -- Extension adds jobs that discovery cannot reach

---

*For Contributors*

## Architecture

The discovery engine lives in `src/career_os/discovery/` with two main files:

- `src/career_os/discovery/adapters.py` (494 lines) -- Source normalization. Each adapter converts raw python-jobspy output into a unified `RawJobResult` format. Adapter failures are caught and logged individually so one failing source does not block others.
- `src/career_os/discovery/scheduler.py` -- Asyncio background task that fires on a 7-day interval during the application lifespan. Calls `run_scheduled_discovery()` for each profile.

Supporting modules:

- `src/career_os/services/discovery.py` -- Service layer: orchestrates scraping, deduplication, and storage of discovered jobs
- `src/career_os/models/discovery.py` -- `DiscoveredJob` and `SearchProfile` ORM models
- `src/career_os/discovery/prefilter.py` -- Pre-filter logic configurable via `PREFILTER_STRATEGY` env var (strict, moderate, or off)
- `src/career_os/api/discovery.py` -- REST endpoints for manual search triggers and result retrieval

The discovery adapters depend on `python-jobspy >= 1.1.82`, which pins `pandas < 3.0`. This transitive constraint blocks the pandas 3.x upgrade across the project.

## Research & Decisions

Annotated links to research and reference documents:

- [Cost Optimization Strategy](../research/cost-optimization-strategy.md) -- The scoring funnel: 1,500 scraped to 600 after pre-filter to AI scored. Shows discovery's role in the cost pipeline
- [Job Search Tools](../research/job-search-tools.md) -- Tool matrix of scrapers, MCP servers, and Germany-specific sources evaluated for the discovery system
- [Scoring Research](../research/scoring-research.md) -- Scoring rubric design that the discovery pipeline feeds into

## BMAD Integration

**PRD Status:** Not started

A PRD would define the board adapter expansion strategy, pre-filter tuning methodology, scheduling configuration options, and adapter error isolation patterns.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
