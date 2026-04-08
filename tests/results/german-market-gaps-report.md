# German/EMEA Job Market Gaps - Research & Implementation Report

Generated: 2026-03-30

## Summary

Added 6 new job sources and expanded keyword presets with 2 new role categories (DevRel, Leadership) and 7 additional keywords across existing categories. All new scrapers are integrated into the daily pipeline via `scrape_resilient.py` and will run automatically alongside existing sources.

## New Sources Implemented

| Source | Type | Auth | Rate Limits | Implementation |
|--------|------|------|-------------|----------------|
| Himalayas | Free JSON API | None | 20 results/request | `scrape_himalayas()` |
| Greenhouse | Public Job Board API | None | None documented | `scrape_greenhouse()` |
| Lever | Public Postings API | None | None documented | `scrape_lever()` |
| Ashby | Public Job Board API | None | None documented | `scrape_ashby()` |
| startup.jobs | Algolia search (public keys) | None | Standard Algolia | `scrape_startupjobs()` |
| TheHub.io | Internal JSON API | None | Unknown | `scrape_thehub()` |

## ATS Board Coverage (Greenhouse + Lever + Ashby)

This is the highest-value addition. Many target companies post exclusively on their ATS board and are NOT on Indeed/LinkedIn. The curated company lists cover 59 companies total:

**Greenhouse (31 companies):** Mistral, Hugging Face, Cohere, Anthropic, DeepMind, Figma, Linear, Vercel, Notion, Airtable, HashiCorp, Grafana, Postman, Snyk, Miro, Contentful, Datadog, Sourcegraph, GitLab, Anyscale, Replit, Together AI, Modal, Weights & Biases, DeepL, Celonis, Personio, Scalable Capital, tldraw, Sentry, Supabase

**Lever (18 companies):** Proton, Tuta, Lovable, Oxide, Fly.io, Railway, Retool, Render, Webflow, Cal.com, Descript, LiveKit, LangChain, Prefect, Zed, Netlify, Prisma, commercetools

**Ashby (10 companies):** Linear, Vercel, Resend, Clerk, Deno, Neon, Turso, Unkey, Inngest, Val Town

## Keyword Preset Expansions

### New presets added:
- **devrel**: Developer Relations, Developer Advocate, Developer Experience, DevRel, Entwickler-Community
- **leadership**: Head of Engineering, VP Engineering, Engineering Manager, Leiter Softwareentwicklung, Head of Product, AI Program Lead

### Expanded existing presets:
- **tpm**: +Technical Product Manager, +Technischer Produktmanager
- **ai**: +AI Operations, +MLOps, +KI-Betrieb
- **builder**: +Founding Engineer, +Staff Engineer, +Principal Engineer

## Sources Researched but NOT Implemented

| Source | Reason |
|--------|--------|
| StepStone.de | No public API. Requires paid partnership or browser scraping with anti-bot bypass. High legal risk (Axel Springer). Not worth the complexity. |
| XING/kununu | No public API. Requires authentication. New Work SE actively blocks scrapers. Jobs overlap heavily with LinkedIn. |
| Glassdoor Germany | Already covered by python-jobspy (JobSpy source). Adding a separate scraper would duplicate. |
| LinkedIn Jobs | Already covered by python-jobspy. Authenticated access would violate ToS and trigger bans. |
| remotely.de | Very small board, mostly duplicates from other sources. Not enough unique listings to justify a scraper. |

## Architecture

All new scrapers live in `tools/scrape_new_sources.py`, imported by `tools/scrape_resilient.py` as Source 8/9 in the pipeline. The import is conditional - if the file is missing or has import errors, the pipeline skips new sources and continues with the existing 7.

Each scraper:
- Returns `list[ScrapedJob]` (same dataclass as existing scrapers)
- Catches its own exceptions and returns `[]` on failure
- Uses the shared `_retry_with_backoff()` and `_random_delay()` from scrape_resilient
- Applies client-side keyword filtering for ATS board scrapers

## Test Coverage

32 new tests in `tests/test_new_sources.py`:
- Company list validation (4 tests)
- Himalayas: parse, empty, failure (3 tests)
- Greenhouse: parse, keyword filter, remote detection, empty (4 tests)
- Lever: parse, keyword filter, invalid response (3 tests)
- Ashby: parse, alternate keys, keyword filter, string compensation (4 tests)
- startup.jobs: parse, URL building, empty (3 tests)
- TheHub: parse, alternate response shape, failure (3 tests)
- Combined orchestrator: all sources called, graceful failure (2 tests)
- Keyword preset expansions (6 tests)

All 32 tests pass. Existing scraper tests (49/50) still pass - the one pre-existing failure is `TestBrowserFallback` which assumes Playwright is not installed.

## Files Changed

| File | Change |
|------|--------|
| `tools/scrape_new_sources.py` | **NEW** - 6 scrapers + company lists + orchestrator |
| `tools/scrape_resilient.py` | Added import and Source 8/9 integration (non-breaking) |
| `tools/germany_jobs.py` | Expanded PRESETS with 2 new categories + 7 new keywords |
| `tests/test_new_sources.py` | **NEW** - 32 unit tests |
| `tests/results/german-market-gaps-report.md` | **NEW** - This report |

## Next Steps

1. **Run a full live scan** with `PIPELINE_MODE=api-only .venv/bin/python tools/daily_pipeline.py` to see real results from new sources
2. **Tune ATS company lists** - add/remove companies based on actual job relevance after first scan
3. **Add startup.jobs Algolia key refresh** - the embedded key may rotate; verify it works on first run. If it fails, extract from their frontend JS
4. **Monitor TheHub** - their internal API is undocumented and may change format
5. **Consider adding Workable** - another popular ATS with a public API similar to Greenhouse/Lever
