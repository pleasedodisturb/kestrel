---
title: "Kestrel Feature Sync Matrix"
date: 2026-04-16
version: "1.0"
---

# Kestrel Feature Sync Matrix

This document catalogs every feature in Kestrel, organized by domain, for the purpose of
identifying what to port from the original codebase and in what order. Each feature includes its location
in the codebase, a brief description, a sync priority rating, and notes on CLI adaptation.

**Sync Priority Legend:**
- **high** — core scoring/discovery logic, high value for CLI
- **medium** — useful for CLI users, port when capacity allows
- **low** — Kestrel-specific (web/mobile UI), limited CLI value
- **skip** — not applicable to a CLI tool

---

## 1. Scoring

| Feature | Kestrel Location | Description | Sync Priority | Notes |
|---------|-----------------|-------------|---------------|-------|
| AI-powered job scoring | `services/scoring.py` → `score_job()` | Scores jobs against user profile (skills, goals, culture, salary, location) using AI provider | high | Core engine; needs prompt adaptation for CLI output format |
| Dual-score architecture (fit vs desire) | `services/scoring.py` → `compute_derived_desire_score()` | Separate "fit score" (objective match) and "desire score" (personal preference) per G-275 | high | Portable as-is; CLI can show both scores side by side |
| Dimensional scoring | `schemas/ai.py` → `ScoreResult` | Per-dimension breakdown: skills_match, career_alignment, culture_fit, salary_match, location_match | high | Each dimension scored independently with rationale |
| Configurable scoring weights | `services/scoring.py` → `get_or_create_weights()`, `update_weights()` | Per-profile weight customization for scoring dimensions | high | CLI config file or flags |
| Job family weight modifiers | `services/scoring.py` → `_weights_for_job_family()` | Auto-adjusts dimension weights based on job family (tech, finance, etc.) | high | Portable as-is |
| Batch scoring | `services/scoring.py` → `batch_score_discovery()` | Score multiple discovered jobs in one operation | high | CLI batch mode natural fit |
| Score context & percentiles | `services/scoring.py` → `compute_score_context()` | Percentile ranking, score distribution stats, confidence ranges per G-271 | high | Adds meaning to raw scores |
| Profile completeness check | `services/scoring.py` → `compute_profile_completeness()` | Validates profile has enough data for meaningful scoring | medium | Useful CLI pre-flight check |
| Stale score flagging | `services/scoring.py` → `flag_stale_scores()` | Marks scores outdated when profile/weights change | medium | Background job in CLI |
| User feedback loop | `services/scoring.py` → `submit_feedback()`, `record_implicit_feedback()` | User corrects scores ("too high"/"too low"), feeds back into model per G-274 | high | Core learning mechanism |
| Bayesian preference learning | `services/preference_learning.py` | Beta-distribution model that learns weight adjustments from feedback per G-279 | high | Portable math; no web dependency |
| Active query for preferences | `services/preference_learning.py` → `should_active_query()`, `get_active_query_dimensions()` | Identifies uncertain dimensions needing user input | medium | CLI prompt integration |
| Calibration examples in prompts | `services/scoring.py` → `_format_calibration_section()` | Includes past scored jobs as few-shot examples in scoring prompt | high | Improves scoring accuracy |
| ATS keyword extraction | `schemas/ai.py`, scoring prompt | Extracts ATS-relevant keywords from job descriptions during scoring | medium | Useful for resume tailoring |
| Confidence range | `services/scoring.py` → `apply_confidence_range()` | Computes score confidence interval (half-width band) | medium | Portable math utility |

## 2. Discovery

| Feature | Kestrel Location | Description | Sync Priority | Notes |
|---------|-----------------|-------------|---------------|-------|
| Job board scraping (python-jobspy) | `discovery/adapters.py` → `ScraperAdapter` | Abstract adapter pattern for multiple job board scrapers | high | Core discovery; CLI natural fit |
| Arbeitsagentur adapter | `discovery/adapters.py` → `ArbeitsagenturAdapter` | German federal job board scraper with pagination and retry | high | Region-specific; portable |
| Arbeitnow adapter | `discovery/adapters.py` → `_parse_arbeitnow_job()` | Arbeitnow job board parser | high | Portable |
| Retry with exponential backoff | `discovery/adapters.py` → `_request_with_backoff()` | Resilient HTTP requests for scraping | high | Reusable utility |
| Discovery scheduler | `discovery/scheduler.py` → `start_scheduler()` | Asyncio background task running periodic discovery sweeps | medium | CLI would use cron/launchd instead |
| Search profiles | `services/discovery.py`, `api/discovery.py` | Saved search configurations (keywords, location, filters) | high | CLI config file natural fit |
| Discovery runs tracking | `api/discovery.py` → `list_discovery_runs_endpoint()` | Tracks each discovery sweep's results and metadata | medium | CLI logging alternative |
| Deduplication | `services/discovery.py` | Prevents duplicate job listings across discovery runs | high | Essential for any client |
| Pipeline auto-feed | `services/discovery.py` | Auto-creates pipeline applications from high-scoring discovered jobs | medium | CLI could auto-add to tracking |

## 3. Red Flags

| Feature | Kestrel Location | Description | Sync Priority | Notes |
|---------|-----------------|-------------|---------------|-------|
| Stale posting detection | `services/red_flags.py` → `_detect_stale_posting()` | Flags job postings older than 60 days | high | Stateless rule; portable as-is |
| Unrealistic requirements | `services/red_flags.py` → `_detect_unrealistic_requirements()` | Flags excessive years-of-experience demands vs tech age | high | Stateless rule; portable |
| Turnover language detection | `services/red_flags.py` → `_detect_turnover_language()` | Detects phrases suggesting high turnover ("fast-paced", "wear many hats") | high | Stateless rule; portable |
| Missing salary in mandate states | `services/red_flags.py` → `_detect_missing_salary()` | Flags missing salary in CO/CA/WA/NY/CT jurisdictions | high | Stateless rule; portable |
| Staffing agency detection | `services/red_flags.py` → `_detect_staffing_agency()` | Identifies recruiter/agency postings | high | Stateless rule; portable |
| Vague responsibilities | `services/red_flags.py` → `_detect_vague_responsibilities()` | Flags overly generic job descriptions | high | Stateless rule; portable |
| Excessive requirements | `services/red_flags.py` → `_detect_excessive_requirements()` | Flags job posts with unreasonable number of requirements | high | Stateless rule; portable |
| Ghost job detection | `services/red_flags.py` → `_detect_ghost_job_signals()` | Data-driven: identifies likely ghost postings via repost patterns, company/title frequency | high | Needs job history database |
| Multi-city blast detection | `services/red_flags.py` → `_detect_multi_city_blast()` | Data-driven: same company posting identical role across many cities | high | Needs job history database |
| WARN Act layoff integration | `services/red_flags.py` → `_detect_recent_layoffs()`, `services/warn_data.py` | Data-driven: cross-references job postings against WARN Act layoff filings per G-277 | high | Needs warnscraper + state filing data |
| Company/title normalization | `services/red_flags.py` → `normalize_job_title()`, `normalize_company_name()` | Fuzzy matching for deduplication and ghost detection | high | Reusable utility |

## 4. AI Providers

| Feature | Kestrel Location | Description | Sync Priority | Notes |
|---------|-----------------|-------------|---------------|-------|
| Provider abstraction (factory pattern) | `ai/factory.py` → `get_ai_provider()`, `ai/base.py` → `AIProvider` | Abstract base with `complete()` and `score()` async methods; factory selects by env var | high | Core abstraction; portable as-is |
| OpenRouter provider | `ai/openrouter_provider.py` | Multi-model routing via OpenRouter API (credits-based) | high | Primary production provider |
| Anthropic provider | `ai/anthropic_provider.py` | Direct Anthropic Claude API integration | high | Alternative provider |
| Ollama provider | `ai/ollama_provider.py` | Local LLM via Ollama (self-hosted, zero-cost) | high | Privacy-first option; ideal for CLI |
| Mock provider | `ai/mock_provider.py` | Deterministic responses for testing and dev | high | Essential for testing |
| Response caching | `ai/cache.py` → `CachedProvider` | SQLite-backed encrypted cache with TTL; wraps any provider | high | Cost savings; portable |
| PII masking | `ai/pii_masking.py` → `MaskedProvider`, `PIIMasker` | Regex-based PII detection and masking before sending to AI; unmasks on response | high | Privacy layer; portable |
| Privacy registry | `ai/privacy.py`, `privacy_registry.json` | Per-provider privacy metadata (data retention, GDPR, training opt-out) | medium | Informational; CLI help text |
| Provider health check | `services/ai_health.py`, `api/ai.py` → `ai_health()` | Tests provider connectivity and response quality | medium | CLI diagnostic command |
| OAuth flow (OpenRouter) | `api/oauth.py` | PKCE OAuth flow for OpenRouter API key acquisition with rate limiting | low | Web-specific; CLI uses direct API key |
| Quota/credits error handling | `ai/base.py` → `ProviderQuotaError` | Graceful degradation when provider credits exhausted | high | Essential error handling |

## 5. Skills

| Feature | Kestrel Location | Description | Sync Priority | Notes |
|---------|-----------------|-------------|---------------|-------|
| Skills CRUD | `services/skills.py` | Create, list, get, update skills with proficiency levels | high | Core data; CLI natural fit |
| Skills ingestion | `api/skills.py` → `ingest_skills_endpoint()`, `services/skills_parsing.py` | Bulk extract skills from CV/docs with parsed proficiency | high | CLI pipe-friendly |
| Skill history tracking | `api/skills.py` → `get_skill_history_endpoint()` | Tracks proficiency changes over time | medium | Useful for progress tracking |
| ESCO skill normalization | `services/skill_normalizer.py` | Maps free-text skills to ESCO taxonomy via exact match → fuzzy match → embedding match per G-276 | high | Standardizes skill vocabulary |
| Profile skill enrichment | `services/skill_normalizer.py` → `enrich_profile_skill()`, `enrich_all_profile_skills()` | Batch-normalizes all profile skills to ESCO entries | high | Portable; improves matching |
| Job requirement enrichment | `services/skill_normalizer.py` → `enrich_job_requirement()` | Normalizes job requirement skills to ESCO | high | Enables accurate gap analysis |
| ESCO taxonomy model | `models/esco.py` | SQLAlchemy models for ESCO skills, cache, and mappings | high | Database schema; portable |
| Skills parsing engine | `services/skills_parsing.py` → `ParsedSkill` | Extracts structured skill data from unstructured text | high | Core NLP; portable |

## 6. Pipeline

| Feature | Kestrel Location | Description | Sync Priority | Notes |
|---------|-----------------|-------------|---------------|-------|
| Application CRUD | `services/applications.py` | Create, list, get, update, archive applications | high | Core tracking; CLI natural fit |
| Application state machine | `schemas/applications.py` → `VALID_TRANSITIONS` | Enforced status transitions (applied → screening → interview → offer → etc.) | high | Business logic; portable |
| Follow-up engine | `services/follow_ups.py` | Create/complete follow-ups with due dates; overdue tracking | high | CLI reminder integration |
| Activity logging | `services/activity.py` → `log_activity()` | Universal audit trail for all entity changes | medium | Useful for CLI history |
| Analytics/funnel stats | `services/analytics.py` → `get_analytics()` | Pipeline conversion rates, time-in-stage, weekly activity, score distribution | medium | CLI summary tables |
| Application readiness scoring | `api/applications.py` → `_enrich_with_readiness()` | Composite readiness score from skills gaps per application | medium | Derived from gap analysis |

## 7. Contacts

| Feature | Kestrel Location | Description | Sync Priority | Notes |
|---------|-----------------|-------------|---------------|-------|
| Contact CRUD | `services/contacts.py` | Create, list, get, update, archive contacts (Networking CRM) | medium | CLI addressbook |
| Contact-company grouping | `api/contacts.py` → `contacts_at_company()` | List all contacts at a given company | medium | Useful for research |
| Interaction logging | `api/contacts.py` → `log_interaction()` | Record meetings, emails, calls with contacts | medium | CLI interaction diary |
| Contact-application linking | `api/contacts.py` → `link_application()` | Associate contacts with specific job applications | medium | Relationship tracking |
| Contact follow-ups | `cli/contacts.py` → `follow_ups_cmd()` | Track networking follow-ups | medium | CLI natural fit |

## 8. Goals

| Feature | Kestrel Location | Description | Sync Priority | Notes |
|---------|-----------------|-------------|---------------|-------|
| Career goals CRUD | `services/goals.py` | Create, list, get, update, delete career goals | high | Core planning; CLI natural fit |
| Reality mapping | `services/goals.py`, `api/goals.py` → `get_reality_map_endpoint()` | Maps goals against current skills/experience gap | high | Actionable insights |
| Progress tracking | `api/goals.py` → `get_progress_endpoint()` | Tracks goal completion percentage and milestones | high | CLI progress bars |
| Goal recalibration | `services/goals.py`, `api/goals.py` → `recalibrate_goal_endpoint()` | Adjusts goal parameters based on market reality | medium | AI-powered adjustment |
| Alternative suggestions | `api/goals.py` → `get_alternatives_endpoint()` | Suggests alternative career paths when goals seem unreachable | medium | AI-powered exploration |

## 9. Market Intelligence

| Feature | Kestrel Location | Description | Sync Priority | Notes |
|---------|-----------------|-------------|---------------|-------|
| Salary trends | `services/market.py` → `get_salary_trends()` | Salary range analysis from discovered job data by period | high | Data-driven; portable |
| Skill demand trends | `services/market.py` → `get_skill_trends()` | Tracks which skills appear most in job postings | high | Data-driven; portable |
| Hiring patterns | `services/market.py` → `get_hiring_patterns()` | Seasonal/temporal hiring activity analysis | medium | Needs sufficient data |
| Market positioning | `services/market.py` → `get_market_positioning()` | User's competitive position relative to market | high | Combines skills + market data |
| Opportunity radar | `services/market.py` → `get_opportunity_radar()` | Identifies emerging opportunities matching profile | medium | Discovery-dependent |
| Market data refresh | `services/market.py` → `refresh_market_data()` | Recalculates all market metrics from latest data | medium | CLI cron job candidate |

## 10. Interview

| Feature | Kestrel Location | Description | Sync Priority | Notes |
|---------|-----------------|-------------|---------------|-------|
| Interview prep generation | `services/interview_prep.py` | AI-generated prep materials (topics, questions, checklist) enriched with company research | high | CLI natural fit; high value |
| Company research integration | `services/interview_prep.py` → `_get_company_research_data()` | Pulls company research data into interview prep context | high | Enriches prep quality |
| Stale prep detection | `services/interview_prep.py` → `_is_prep_stale()` | Detects when prep materials need regeneration | medium | Auto-refresh trigger |
| Interview format analysis | `services/role_intelligence.py` → `get_interview_format()` | AI-powered analysis of likely interview format for a role | medium | Role-type heuristics |
| Salary benchmarking | `services/role_intelligence.py` → `get_salary_benchmarks()` | Market-data + AI fallback salary estimates for roles | high | Negotiation support |
| Interview pattern analysis | `services/role_intelligence.py` → `get_interview_patterns()` | Identifies common interview patterns by role/industry | medium | Pattern recognition |
| STAR stories CRUD | `services/star_stories.py` | Create, list, get, update, delete behavioral interview stories | high | CLI natural fit |
| Story recommendations | `services/star_stories.py` → `get_recommended_stories()` | Suggests relevant STAR stories for specific applications | medium | AI-powered matching |
| Story gap analysis | `services/star_stories.py` → `get_story_gaps()` | Identifies missing STAR story coverage areas | medium | Prep completeness check |

## 11. CLI

| Feature | Kestrel Location | Description | Sync Priority | Notes |
|---------|-----------------|-------------|---------------|-------|
| Pipeline management | `cli/main.py` → `pipeline_list()`, `pipeline_add()`, `pipeline_update()` | List, add, update pipeline applications with Rich tables | high | Direct port target |
| Pipeline stats | `cli/main.py` → `pipeline_stats()` | Funnel stats, conversion rates, stage counts | high | CLI summary command |
| Pipeline follow-ups | `cli/main.py` → `pipeline_follow_ups()` | List/manage pending follow-ups | high | CLI reminder system |
| Skills list/gaps | `cli/main.py` → `skills_list()`, `skills_gaps()` | Display skills inventory and gap analysis | high | Core CLI feature |
| Goals list/show/coach | `cli/main.py` → `goals_list()`, `goals_show()`, `coach()` | Goal management and AI coaching suggestions | high | Core CLI feature |
| Discovery CLI | `cli/main.py` → `discover()` | Run discovery sweeps, manage schedules from CLI | high | Core CLI feature |
| Score CLI | `cli/main.py` → `score()` | Score jobs/URLs from command line | high | Core CLI feature |
| Market CLI | `cli/main.py` → `market()` | Market intelligence reports in terminal | high | Rich table output |
| Company research CLI | `cli/main.py` → `research()` | AI-powered company deep-dive from CLI | high | Single-command research |
| Interview prep CLI | `cli/main.py` → `interview_prep_generate()` | Generate interview prep from CLI | high | Pre-interview workflow |
| STAR stories CLI | `cli/main.py` → `stories_list_default()`, `stories_add()`, etc. | Manage STAR stories from terminal | high | Interview prep companion |
| Contacts CLI | `cli/contacts.py` | Full contact management (add, list, show, update, archive, log, link) | medium | Networking from terminal |
| WARN data CLI | `cli/warn.py` → `update()`, `list_states()` | Update/query WARN Act layoff data | high | Data maintenance command |
| Server start | `cli/main.py` → `start()` | Launch uvicorn dev server with browser auto-open | skip | Kestrel-specific |
| Rich terminal output | All CLI modules | Rich library tables, colors, progress bars throughout | high | Reference implementation for Kestrel CLI |

## 12. Infrastructure

| Feature | Kestrel Location | Description | Sync Priority | Notes |
|---------|-----------------|-------------|---------------|-------|
| SQLite + WAL mode | `database.py`, `config.py` | SQLite database with WAL for concurrent reads | high | Lightweight; CLI ideal |
| Auto-migration (Alembic) | `main.py` → `_auto_migrate()`, `_alembic/` | Runs Alembic migrations on app startup | high | Seamless upgrades |
| API key auth middleware | `middleware.py` → `APIKeyAuthMiddleware` | Optional API key authentication (`AUTH_ENABLED`, `AUTH_API_KEY`) | low | Web/API specific |
| Rate limiting (SlowAPI) | `main.py` → OAuth rate limiter | Rate limiting on OAuth endpoints | skip | Web-specific |
| CORS middleware | `main.py` | Cross-origin resource sharing for web frontend | skip | Web-specific |
| Embeddings service | `services/embeddings.py` | Generate, store, and compare embeddings for profile/job similarity | high | Powers ESCO matching and similarity |
| Profile management | `api/profiles.py`, `models/models.py` | Multi-profile support with CRUD and default profile seeding | medium | CLI could support profiles via config |
| TickTick integration | `services/ticktick_sync.py`, `services/ticktick_client.py`, `services/ticktick_scheduler.py` | Bidirectional sync with TickTick task manager (push/pull/scheduler) | low | Kestrel-specific integration |
| Pushover notifications | `services/pushover.py`, `services/pushover_client.py` | Push notification delivery for follow-ups, ghosts, discovery, interviews | low | Kestrel-specific; CLI has terminal output |
| Calendar service | `services/calendar.py` | Interview calendar with iCal export, Google Calendar URLs, Fantastical deep links, prep reminders | low | Kestrel-specific; CLI users have their own calendar |
| Integration config management | `services/integrations.py`, `api/integrations.py` | CRUD for external service configurations (TickTick, Pushover, etc.) | low | Kestrel-specific UI |
| Company research (AI) | `services/company_research.py` | AI-powered company deep-dive (tech stack, funding, Glassdoor, values, hiring) | high | Standalone research; CLI natural fit |
| Gap analysis | `services/gap_analysis.py` | Compare job requirements against skills inventory | high | Core matching logic; portable |
| Learning paths | `services/learning.py` | Skill gap → learning resource recommendations with progress tracking | medium | Educational component |
| Coaching engine | `services/coaching.py` | Prioritized suggestions combining skills, gaps, goals, pipeline state | medium | AI-powered advice; CLI natural fit |
| Voice discussion mode | `services/voice.py` | Conversational AI sessions (cover letter, coaching, evaluation modes) | low | Web/mobile-specific UX |
| Salary parsing utilities | `services/salary.py` → `parse_salary_range()` | Extract structured salary data from free-text strings | high | Reusable utility |
| Privacy registry (JSON) | `privacy_registry.json` | Provider-level privacy/GDPR metadata | medium | Reference data; portable |

---

## Summary by Priority

| Priority | Count | Description |
|----------|-------|-------------|
| **high** | ~60 | Core scoring, discovery, red flags, AI providers, skills, goals, market, CLI — port first |
| **medium** | ~20 | Useful additions: analytics, contacts, learning, coaching, profile completeness |
| **low** | ~8 | Kestrel-specific: calendar, TickTick, Pushover, voice, OAuth, integrations UI |
| **skip** | ~4 | Web-only: CORS, rate limiting, server start |

## Next Steps

1. **Phase 2**: Audit features from the original codebase and map them into this matrix (reverse direction)
2. **Phase 3**: Identify gaps and overlaps, create porting tickets
3. **Phase 4**: Begin porting high-priority features, starting with scoring engine and discovery
