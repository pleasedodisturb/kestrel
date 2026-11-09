# Feature Research: v2.0 "Lean Kestrel"

**Domain:** Self-hosted, local-first AI job-search tooling (find, triage, write in your voice, learn from outcomes)
**Researched:** 2026-10-24 (all source access dates below are 2026-10-24)
**Scope:** Only the NEW v2.0 features. Existing features (discovery adapters, scoring rubric, cost presets, pipeline state machine, geo engine, PII masking, extension capture and auto-log) are referenced only as dependencies.
**Overall confidence:** MEDIUM-HIGH

## How to read the confidence tags

The `classify-confidence` seam returns LOW for the `websearch` and `webfetch` providers (it has no registry for them). That tier describes the retrieval channel, not the evidence. To keep the tags useful, each claim below carries an evidence grade:

- **[P] Primary:** read directly from the artifact itself: vendor API docs, the MCP specification, or the source files and tests of the career-ops repository (fetched through the GitHub API at its current default branch). Treat as HIGH for "this is what the tool/spec does".
- **[S] Secondary:** blog posts, directory listings, vendor marketing, news coverage. Treat as LOW. Used only for market color, never for a design decision.
- **[J] Judgment:** the researcher's recommendation, derived from [P] evidence. Treat as a proposal to be tested in requirements.

Where a number comes from [S], it is labelled as such and no requirement should depend on it.

## Comparable tools studied

| Tool | Why it matters | Evidence |
|------|----------------|----------|
| career-ops (career-ops-hq/career-ops, ~77k stars, MIT, agent-skill driven, Go Bubble Tea dashboard) | The closest analogue and the current attention leader. Has ATS scanners, scan history, repost detector, liveness ladder, fact gate, outcome journal, calibrate report, reply proposals, Go TUI. | [P] repo files and docs read directly |
| JobOps (DaKheera47/job-ops, ~4.1k stars, AGPL + Commons Clause) | Self-hosted pipeline with Gmail reply ingestion that moves status automatically; explicitly "does not auto-apply". | [P] README via fetch |
| JobSync (Gsync/jobsync, ~1.4k stars, MIT) | Self-hosted tracker with scheduled Greenhouse/Lever/Ashby discovery, local relevance score before AI, accept/dismiss review, and an MCP server gated by approval and token. | [P] README via fetch |
| Simplify Copilot (hosted extension) | The extension-prefill reference: fills, never submits, tracker add only after submission is detected. | [P] vendor help article |
| Huntr, Teal (hosted trackers) | Kanban stage vocabulary (Applied, Interviewing, Offer, customizable). | [S] directory and review pages; Huntr help center for "preset stages, renamable" |
| python-jobspy | The scraper layer Kestrel already builds on; useful for what NOT to promise (rate limits, no dedup guidance). | [P] README |
| Greenhouse / Lever / Ashby public posting APIs | The v2.0 "Find" sources. | [P] vendor docs |

---

## Feature Landscape

### 1. FIND

#### 1a. ATS-API sources with a companies config

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | Greenhouse, Lever, Ashby public JSON boards, no API key | LOW per provider | [P] Greenhouse `GET boards-api.greenhouse.io/v1/boards/{token}/jobs`, "authentication is not required for any GET endpoints"; `content=true` adds description, departments, offices. Lever `GET api.lever.co/v0/postings/{site}?skip=&limit=`, EU host `api.eu.lever.co`. Ashby `GET api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true`. |
| Table stakes | A `companies.yml` the user owns: `name`, `ats`, `slug`, `enabled`, optional `region` (Lever EU), optional `aggregator: true` | LOW | career-ops uses `portals.yml` with the same shape; JobSync uses a directory plus "paste a board URL". Keep it a plain file, not a DB table, so it is diffable and shareable. |
| Table stakes | Per-source normalization into Kestrel's existing discovery adapter output | LOW | Fields available: Greenhouse `id`, `internal_job_id`, `absolute_url`, `updated_at`, `location.name`, offices/departments (only with `content=true`); Lever `id`, `text`, `categories` (location, commitment, team, department, `allLocations`), `workplaceType`, `hostedUrl`, `applyUrl`, `country`; Ashby `title`, `location`, `secondaryLocations`, `publishedAt`, `isListed`, `jobUrl`, `applyUrl`, `isRemote`/`workplaceType`. All [P]. |
| Table stakes | Respect `isListed=false` on Ashby (unlisted postings are reachable only by direct link) | LOW | [P] Ashby docs. Treat as "not an arrival". |
| Differentiator | Company resolver: given a company name or a pasted careers URL, find the ATS and slug and append to `companies.yml` after a preview | MEDIUM | career-ops ships `discover-ats.mjs` (preview by default, `--write` to append) and a `validate-portals` / `verify-portals` pair. Cheap, high value for the 15-minute path. [P] |
| Differentiator | Curated starter list (tens of companies, not thousands) so the first scan returns real rows in minutes | LOW | career-ops ships 100+ preconfigured; JobSync advertises directories of 1,160 Lever and 1,860 Ashby companies [S]. Curation matters more than count: a stale 2,000 list is a canary generator. |
| Anti-feature | Scraping career sites without a public API (Workday, SuccessFactors, generic HTML) in v2.0 | HIGH | career-ops carries a provider zoo (SuccessFactors, branded variants, Zoho) and ~100 KB of liveness patterns. Kestrel's three-ATS scope is the lean line. Extension capture already covers "any page the user is on". |
| Anti-feature | Paid scraping aggregators as default sources | n/a | Contradicts zero-key first run. JobSpy boards stay as an optional existing adapter. |

**Dependencies on existing:** `discovery/adapters.py` (normalization contract), `discovery/scheduler.py` (do not extend; headless cron replaces it for unattended use), geo engine (needs the multi-location arrays these APIs return).

**Facts to verify before requirements are frozen:** the Ashby docs page does not list an `id` field in the posting object, and none of the three vendors documents a rate limit for the public GET endpoints (Lever documents a 2 requests/second limit only on the application POST) [P]. Key identity on a verified live response, and pace requests conservatively per host (serial per host, small jitter) as a [J] default.

#### 1b. Headless `kestrel scan` on cron, persisting every arrival

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | Idempotent, unattended, no LLM spend by default | LOW | career-ops: "safe to run unattended, it is idempotent ... and costs nothing". [P] |
| Table stakes | Meaningful exit codes: 0 when at least one source was read; non-zero (career-ops uses 2) when every source failed | LOW | So a scheduler alerting on non-zero reports an outage without flagging a single dead board. [P] |
| Table stakes | `--dry-run --json` and `--company X` | LOW | career-ops documents exactly this as the way to verify a config edit without writing. [P] |
| Table stakes | Persist EVERY arrival, including the ones excluded, with a reason code | MEDIUM | career-ops `scan-history.tsv` is append-only with columns `url, first_seen, portal, title, company, status, location, fingerprint, posted_at, trust_score, trust_flags, normalized_company, requisition_id, language, listing_key`, and statuses `added`, `skipped_title`, `skipped_location`, `skipped_age`, `skipped_expired`, `skipped_no_apply_control`, `skipped_invalid_url`, `skipped_blocked_host`. Their `filter-audit` header says why it matters: the title filter silently decides ~78% of everything scanned and "reports nothing about how" until rejected titles were persisted. [P] This is the prerequisite of the whole audit loop (section 2d). |
| Table stakes | OS-scheduler recipes in docs (cron, launchd, systemd timer) | LOW | career-ops AUTOMATION.md ships cron/launchd/Task Scheduler recipes; "daily and let dedup absorb" is the stated recommendation. [P] |
| Differentiator | Per-run scan summary row (sources read, arrivals, new, excluded by reason, errors, duration) persisted, feeding canaries and the digest | LOW | Same table that holds canary baselines (1e). |
| Anti-feature | A second in-process scheduler or "scheduled scans web page" | MEDIUM | career-ops bolted on a 15-minute queue worker plus a web page; Kestrel already has an asyncio scheduler inside the app. Two schedulers is the sprawl the thesis cuts. Document the OS scheduler as the one path. |
| Anti-feature | Scoring inside `scan` by default | n/a | Scan is cheap and deterministic; scoring is separate and spend-guarded (section 6). |

**Dependencies on existing:** `discovery` engine, prefilter, DB models (new arrivals table), cost safety (6) must land BEFORE a cron job can ever score.

#### 1c. Dedup within batch and against history

What users and the comparable tools actually do (all [P] unless noted):

| Layer | Behaviour users expect | Source / evidence |
|-------|------------------------|-------------------|
| L0 URL normalization | Strip query noise (`utm_*`, `gh_src`), fragments, trailing slash, scheme, host case before comparing | career-ops `normalizeUrlForDedup`; their fingerprint doc: "scheme, query and fragment never contribute to identity" |
| L1 strong identity | Same `(ats_provider, board_slug, posting_id)` is the same posting regardless of URL rotation or branded domain. Opaque, case-sensitive IDs: `00123` is not `123`. If the triple cannot be resolved, produce NO key, never a guess | career-ops `listing-fingerprint` v1: SHA-256 of `["listing-fingerprint", 1, provider, board, id]`, versioned prefix `listing_v1_`; "equal host/path context is not proof of the same posting"; partial identity must never authorize a dedup |
| L2 seen set | Check against everything ever seen (history, pipeline, tracker) AND earlier items in the same run; first duplicate in a batch wins | career-ops `createAdmissionGate`: reasons tested in fixed order `seen, blacklisted, title, location`; the posting joins the run's seen set even when excluded, so a second copy in the same run is `seen` |
| L3 cross-source near-duplicate | Same job on an aggregator and on the employer's ATS is surfaced as ONE row, advisory only | career-ops keeps a 64-bit SimHash of JD text (`jd_fingerprint`) for advisory near-duplicate detection, explicitly "neither a stable posting identity nor" the strong key |
| L4 repost detection | A role that reappears later under a new URL is flagged "reposted", not presented as brand new, and is not silently hidden | career-ops `detect-reposts`: same normalized company + same SET of title words, 2+ distinct URLs, 2+ distinct first-seen dates, within 90 days, minimum span 1 day, only rows with status `added` |

Hard-won rules from career-ops' repost detector that Kestrel should copy as requirements, because they were each added after a false positive [P]:

1. A cluster whose members all share one first-seen date (one sweep) is concurrent openings, not a repost. Minimum span of at least 1 day.
2. Title identity, not title similarity. A Jaccard-style fuzzy merge turned "Solutions Engineer - Munich" and "- Berlin" into a repost. Per-region and per-segment variants are distinct requisitions.
3. Multi-employer aggregators must be excluded by config (`aggregator: true`), because same company + same title does not imply same opening there, and "clusters are indistinguishable by shape".
4. `first_seen` is when the SCANNER saw the URL, not when the employer posted it; do not present it as posting age.

| Class | Feature | Complexity |
|-------|---------|------------|
| Table stakes | L0 + L1 + L2 before any paid call; dedup stats in the scan summary | MEDIUM |
| Table stakes | Re-seen posting with a changed `updated_at` is NOT re-alerted by default | LOW |
| Differentiator | L4 repost flag with the four rules above, shown as a column and as a score-neutral "reposted N times" note | MEDIUM |
| Differentiator | `listing_key` stored from day one, versioned (old rows keep their version, never silently recomputed) | LOW |
| Anti-feature | Fuzzy title/company merging as a dedup rule; auto-hiding reposts or labelling them "ghost jobs" | MEDIUM | Prevalence figures circulate (for example "18-22% of Greenhouse postings", "27.4% of US LinkedIn listings") but come from secondary coverage and single-vendor reports [S]; a repost is a signal, not a verdict. |
| Anti-feature | Dedup that deletes rows | LOW | Dedup must mark, never delete: the audit loop needs the history. |

**Dependencies:** arrivals table (1b), ATS adapters (1a) to supply the triple, `assess()` (2a) for where dedup sits in the gate order.

#### 1d. Liveness check with ATS re-resolution

career-ops' design is a "liveness ladder" [P]:

1. **Cheap rung (zero tokens, no browser):** hit the ATS per-job endpoint (Greenhouse, Lever) so a 200 proves live; for org-level boards (Ashby) a 200 only proves the board exists, so parse the board and confirm THIS posting is still listed.
2. **Conservative by design:** "a false 'expired' is worse than the status quo". Return `expired` only on a definitive signal (404/410 or a recognised closed marker). Anything ambiguous (unknown ATS, redirect, 429/5xx, timeout) returns unknown and falls to the next rung.
3. **Expensive rung:** a Playwright page check, with pattern lists in many languages for "no longer available" (about 28 KB of source, each pattern carrying a past incident).
4. **SSRF-safe by construction:** fixed API hosts, strict path-segment charset, no redirects followed.

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | Tri-state verdict `live / expired / unknown`; `unknown` never removes anything | LOW | Directly testable. |
| Table stakes | API rung for the three ATSs, run AFTER dedup and prefilter, BEFORE paid scoring, and again at shortlist/prefill time | MEDIUM | Order matters: spending tokens on a closed role is the cost the check exists to prevent. |
| Table stakes | SSRF-safe URL construction (fixed hosts, segment allowlist, redirects refused) | LOW | Extension and MCP both pass URLs into this path. |
| Differentiator | "ATS re-resolution": map a branded careers URL or an aggregator link to the `(provider, board, id)` triple, using ATS embeds, apply links or redirects, so L1 dedup and the API liveness rung work for postings that did not arrive via an ATS source | MEDIUM-HIGH | career-ops explicitly refuses to infer identity from a URL by heuristic ("do not establish a complete, stable namespace for every provider") and requires an authoritative response or verified alias. Follow that: unresolved stays unresolved. |
| Anti-feature | Browser-based liveness in v2.0 | HIGH | Playwright is a heavy install and conflicts with the 15-minute path. Report `unknown` and let the user click through; revisit in v2.1 if `unknown` rates are high. |
| Anti-feature | Auto-dropping `unknown` or auto-deleting `expired` | LOW | Mark and exclude with reason `expired`, keep the row for audit. |

**Dependencies:** 1a (ATS identity), 1c (listing key), extension (`extension_capture.py`) as a producer of branded URLs.

#### 1e. Canaries and floors (alert when a source goes silent or volume collapses)

Evidence [P]: career-ops `audit-portals` classifies each enabled board as `ok / small / empty / no-provider / error`, prints sample titles and locations because "a quiet board and a wrong board look identical from here", and with `--baseline prev.json` flags a board that lost at least 50% of its postings since the last run (default `DEFAULT_DRIFT_FRACTION = 0.5`), explaining that an ATS migration "reads as a near-total collapse (the old board keeps answering, empty), not a gentle decline". It also states its honest limit: "no heuristic reliably detects right company, wrong entity". The same repo's scan exits non-zero only when every target failed. Healthchecks-style dead-man's-switch monitoring (ping on success, alert on silence, separate start/fail signals) is the standard external pattern for "cron stopped running" [P: healthchecks.io docs].

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | Per-source verdict each run: `ok / small (< N, default 5) / empty / error / no-provider` | LOW | `no-provider` (enabled entry nothing claims) is the easiest to miss. |
| Table stakes | Baseline drift: flag a source whose count fell by 50% or more versus its last good run | LOW | One column in the scan summary table. |
| Table stakes | Global floor: scan produced zero arrivals across all sources for N consecutive runs, or has not run in N hours | LOW | The "cron silently stopped" case. |
| Table stakes | Canary results surface in the digest header and in `kestrel doctor`, not only in a log | LOW | A log nobody reads is not an alert. |
| Differentiator | Optional dead-man's-switch ping URL (user-configured, off by default, no Kestrel-owned endpoint) | LOW | Keeps the "no telemetry, no phone home" stance because the URL is the user's own. |
| Differentiator | Show 3 sample rows for any non-ok source so the human can tell quiet from wrong | LOW | career-ops' stated reason for printing samples. |
| Anti-feature | Auto-disabling or auto-"fixing" a failing source | LOW | Silent narrowing of coverage is the exact failure being detected. Alert, never mutate `companies.yml`. |
| Anti-feature | Statistical anomaly detection / forecasting | HIGH | Fixed thresholds with a baseline are sufficient and testable. |
| Naming note | Use "source canary" | n/a | Kestrel already has a scoring `drift_canary`; do not reuse the bare word in code or docs. |

**Dependencies:** arrivals + scan-summary tables (1b), digest (2d), `kestrel doctor` (existing `cli/doctor.py`).

---

### 2. FILTER and SCORE

#### 2a. One `assess()` for prefilter, scorer, triage and alerts

The strongest evidence for this feature is a bug report in career-ops' own source [P]: their `admission-gate.mjs` header says that `scan`, `scan-hn`, `scan-interamt`, `openrouter-runner` and plugin ingest "each built their own subset" of the admission rules, "the same portals.yml then gave a different verdict depending on which command added the row", and the fix was one gate assembled from the scanner's own pieces, injectable for tests, that "never writes".

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | A pure function `assess(posting, search_profile, context) -> Assessment` with NO I/O and NO LLM in the hard gates | MEDIUM | Gate order fixed and documented: seen, blocklist, title, geo, skill/industry prefilter, then (separately) score. First failing gate wins; all later gates may still be evaluated for diagnostics. |
| Table stakes | The result is structured: `decision` (admit / exclude / borderline), ordered `reason_codes`, `geo_class`, `stage`, `rule_version`, optional `score` | LOW | Reason codes are a stable, versioned vocabulary. career-ops' reasons are `seen, blacklisted, title, location` plus skip statuses. |
| Table stakes | Every surface calls it: prefilter, scorer pre-check, TUI, digest, extension inline score, MCP, alerts | MEDIUM | The testable statement is a differential/parity test: for a corpus, all call sites return the same decision. Kestrel already used a 277-case differential gate for the geo engine; reuse that method. |
| Table stakes | `kestrel why <job>` (or TUI key) prints the decision trail | LOW | Without it, "the filter dropped it" is unexplainable to the user. |
| Differentiator | `rule_version` stamped on each stored assessment so history is comparable and a rule change can be replayed over history | LOW | Needed by the audit loop's fixture replay. |
| Anti-feature | LLM calls inside the exclusion gates | n/a | LLM belongs to scoring. Hard gates must be deterministic, free, and replayable. |
| Anti-feature | A "digest-only" or "alerts-only" filter with different thresholds | LOW | This is the exact divergence the single entry point exists to kill. |
| Risk | The scoring service is a ~4,000-line monolith | HIGH | `assess()` must wrap it at a clean seam (score stage) rather than rewrite it; flag for phase research. |

**Dependencies on existing:** `discovery/prefilter.py` (`run_prefilter`), `services/geo/*` (classifier, profile, presets), `services/scoring.py`, `services/cascade_router.py` (shadow-first, off by default: keep out of `assess()` v2.0), `extension_capture.py` (inline score path must call the same function).

#### 2b. Geo gate wired per search profile, `geo_class` visible; multi-office over-admission rule

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | Eligibility decided per search profile (the user's countries, remote scope, work authorization) | MEDIUM | Engine exists; the work is wiring and parity (absorbs v1.1 phases 7-9). |
| Table stakes | `geo_class` is a first-class column in CLI lists, TUI, digest, extension overlay and MCP output | LOW | "Visible" is the requirement: a user cannot overturn a geo exclusion they cannot see. |
| Table stakes | Multi-office postings: Greenhouse `offices`, Lever `categories.allLocations`, Ashby `secondaryLocations` are all evaluated, not just the headline location | MEDIUM | [P] fields exist in all three APIs. Note Greenhouse returns `offices` only with `content=true`. |
| Differentiator | Over-admission rule made explicit: a posting is admitted when ANY listed office is eligible, but the assessment records WHICH office qualified and carries a distinct class (for example `multi_office_partial`), so over-admission is visible and countable rather than silent | MEDIUM | [J] The exact rule is defined by the v1.1 geo design; requirements should copy that definition. Research view: over-admit then label, because under-admission is invisible (the user never sees what was lost), while over-admission costs one glance. Oversample this class in the audit sample (2d). |
| Anti-feature | A second geo authority in scripts or the extension | LOW | v1.1 phase "single geo authority". |
| Anti-feature | Hiding geo-ineligible jobs with no way to see them | LOW | They must be excluded-with-reason, sampled in the audit, and listable by `--include-excluded`. |

**Dependencies:** `services/geo` (existing, 7-way profile engine), `assess()` (2a), ATS location arrays (1a).

#### 2c. Calibrated scoring

Scoring calibration already exists (0-5 judge scale, per-provider calibration, drift canary, golden-set eval). What v2.0 adds is the OUTCOME side, and career-ops' `calibrate` is the useful design reference [P]: "Does your scoring predict YOUR outcomes?", with honesty rules that should become requirements:

- Advisory only: never edits scoring rules, thresholds or config; "there is no auto-tuning anywhere".
- In-flight applications (no recorded outcome) are excluded from every rate and counted separately.
- Sample floor per band (default 5): below it, print "(n too small)" and no percentage; "2 of 3 got interviews is an anecdote wearing a rate's clothes".
- Evidence precedence: outcome journal first, then the status-transition ledger, then current status (current status loses history, such as a declined offer that now reads as discarded).
- Verdict sentence in four words: separating / flat / inverted / insufficient.

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | Score bands are stable across providers (existing calibration) and a stored `assessment` records provider, model, rubric version | LOW | Mostly existing; make it queryable. |
| Differentiator | `kestrel calibrate`: score band x n x interview rate x offer rate with the four honesty rules | MEDIUM | Needs outcome states (3b) and enough data; ships with an "insufficient" verdict day one. |
| Anti-feature | Auto-retuning weights from outcomes | HIGH | That is "automated learning from edits and outcomes", deferred to v2.1. Existing `preference_learning.py` (Bayesian) stays unwired from v2.0 surfaces. |
| Anti-feature | New scoring dimensions in v2.0 | n/a | The loop is only worth tuning if the rubric holds still. |

**Open question for requirements:** what exactly "calibrated scoring" adds beyond the shipped Scoring Engine v2 is not specified in the milestone text; this research assumes it means the outcome-calibration report above plus `assess()` integration.

#### 2d. Daily digest with an audit sample of excluded jobs; overturn becomes a regression fixture

This is the milestone's most distinctive feature and the least precedented in the field. No comparable tool ships an overturnable sample. What exists, [P], is the raw material:

- career-ops persists skipped rows (`skipped_title`, `skipped_location`, ...) and ships `discard-analytics`, whose header states the philosophy to copy: the top-mismatch section "is deliberately dumb: it lists the URLs and lets the candidate judge whether a keyword is costing them real roles. It never infers which keyword to add; that is a guess wearing a number."
- `filter-audit` measures each keyword by `unique` hits (the offers it alone catches) instead of total hits, and says plainly that "what am I missing" is a separate, unbuilt tool.
- `coverage-check <url>` is the manual inverse: the user found a posting the scanner never showed and asks WHY; it names the filter or config gap and proposes the one config change, without editing.
- JobSync has accept/dismiss review of discovered jobs, which is the positive side only.

Sampling guidance from LLM-eval practice [P: Hamel Husain evals FAQ]: keep some purely random items in every batch (unbiased), add targeted sampling for rare failure modes, stop when new samples stop revealing new failure types, review roughly 10-20 per week as steady state, use binary pass/fail labels because scales invite hedging, write evaluators for errors actually observed, and keep a repeatable set containing confirmed failures, rerun on every change.

**Digest content**

| Class | Feature | Complexity |
|-------|---------|------------|
| Table stakes | New arrivals since last digest, grouped by `geo_class`, top-N by score with one-line why; funnel counts (arrived, deduped, excluded by reason, scored, shortlisted) | LOW |
| Table stakes | Source-canary banner (1e) and spend line ("spent X today, cap Y") (6) | LOW |
| Table stakes | Delivered as a file (Markdown, optionally HTML), terminal output and a TUI screen; optional push through the existing Pushover transport | LOW |
| Anti-feature | Building email (SMTP) delivery in v2.0 | MEDIUM | career-ops: "no mail transport anywhere in this codebase". File + terminal + TUI is enough for a technical user. |
| Anti-feature | Digest as a web page or hosted feed | MEDIUM | Parked web app; hosted anything. |

**Audit sample design (recommended, [J] derived from the [P] evidence above)**

| Decision | Recommendation | Why |
|----------|----------------|-----|
| What is eligible to be sampled | Only judgment-based exclusions: title, geo, prefilter strictness, score-below-threshold, multi-office partial | Hard exclusions (already seen, user blocklist, expired, invalid URL) are not user-overturnable noise and would waste the review budget. |
| How many per digest | Small fixed K (suggest 5 to 10), user-configurable, capped | Bounds the human cost; Hamel's steady state is 10-20 per WEEK. |
| Stratification | (a) a random slice across all eligible exclusions (unbiased false-exclusion estimate); (b) near-miss slice: excluded by exactly one soft rule, lowest margin, borderline score band, geo `multi_office_partial`, title near-match; (c) coverage rule: every active reason code appears at least once per N days | Random alone misses rare rules; targeted alone biases the estimate. "Keep some random traces in every batch." |
| Reproducibility | Record the selection seed and the slice each item came from in the digest metadata | Makes the audit itself auditable and testable. |
| No repeats | Never re-show an item already confirmed or overturned | Prevents review fatigue. |
| Item display | title, company, location(s), `geo_class`, reason codes with one-line why, source, link | Same fields the TUI list shows; no new vocabulary. |
| Actions | `overturn` (should have been admitted), `confirm` (correctly excluded), `skip` | Binary labels, as recommended. `confirm` also yields a measured false-exclusion rate. |
| Reporting | Show "k of n sampled exclusions were wrong" and withhold the percentage below a sample floor | Same honesty rule as calibrate. |

**Overturn becomes a regression fixture**

| Step | Requirement |
|------|-------------|
| Immediate effect | The overturned posting is admitted into the pipeline now (status `discovered`), with the overturn recorded as its source. |
| Fixture content | A frozen, profile-free snapshot: normalized posting fields as `assess()` consumed them (title, company, location array, work mode, source, ATS triple, a description excerpt or hash), the decision and `rule_version` at exclusion time, the user's verdict, a timestamp. No resume, no dossier, no personal data. |
| Expected output | Overturn fixture expects `decision != exclude` under the user's CURRENT search profile. It starts RED against the rule that excluded it. Changing config or rules until it turns green is the fix; this matches test-first discipline. |
| Confirmation fixtures | `confirm` verdicts are stored as the opposite polarity (must stay excluded). Without them, fixing one false exclusion can quietly reopen the floodgates. Hamel's guidance to track both TPR and TNR is the same idea. |
| Where they live | A user data directory as JSONL, runnable with a `kestrel verify-fixtures` command that replays `assess()`. Do not commit a user's fixtures to the public repo; project-owned synthetic fixtures live in `tests/`. [J] Decide in requirements whether an opt-in "contribute fixture" export exists. |
| Gate | `kestrel verify-fixtures` must pass before the user's profile/rule change is accepted by `kestrel scan` (warn first, block later). |
| Anti-features | Auto-editing filters from overturns (v2.1 learning); an LLM judge deciding if an exclusion was "wrong"; a per-item "are you sure" dialog; letting an MCP agent finalize an overturn without a human action (an agent may PROPOSE one). |

**Dependencies:** arrivals table with persisted reason codes (1b), `assess()` with `rule_version` (2a), geo class (2b), TUI review screen (3a), digest renderer. Hard prerequisite: 1b.

---

### 3. TRACK

#### 3a. Textual TUI over the CLI service layer

Facts about the existing surface [P: repo]: the CLI opens `SessionLocal()` and calls service functions in-process (no HTTP), so a TUI can sit on the same services and work with no server running.

Interaction conventions observed in career-ops' Bubble Tea dashboard [P: `pipeline.go`], to adopt because users of pipeline TUIs already know them:

| Convention | career-ops key | Textual equivalent |
|------------|----------------|--------------------|
| Move | `j`/`k` and arrows, `g`/`G` top/bottom, PgUp/PgDn | `DataTable` default arrow and page keys plus extra bindings |
| Search | `/` opens an incremental search pre-filled with the previous query; `esc` clears | `Input` docked on `/` |
| Filter tabs / view | `f`/`h`/`l` or arrows cycle 10 filter tabs; `v` toggles grouped vs flat | Tabs or a status filter binding |
| Sort | `s` cycles 8 sort modes | `DataTable.sort()` with a key function |
| Open | `enter` opens report/detail, `o` opens the job URL, `d` opens the attached PDF | detail pane, `o` |
| Change status | `c` opens a status picker (list, `enter` to apply) | modal `OptionList` |
| Discard with reason | picker of preset reasons plus "Other..." free text; `esc` SKIPS tagging but still commits the status | Same: reason is optional, never blocks the action |
| Columns | `C` toggles column visibility | optional |
| Refresh / quit / help | `r`, `q`, footer shows key hints | `BINDINGS` + `Footer`, command palette on `ctrl+p` |
| Safety | report text is untrusted; only `http(s)` is linked | strip control chars, never render job text as markup |

Textual facts [P]: bindings are declared in `BINDINGS` and the `Footer` displays them (clickable); `priority=True` for global keys; `DataTable` supports row keys that survive sorting, `cursor_type="row"`, fixed columns, `sort()`; the command palette (Ctrl+P) gives fuzzy command search for free and accepts custom `COMMANDS` providers; headless testing is `App.run_test()` with `Pilot.press()` and snapshot testing via `pytest-textual-snapshot`, with `asyncio_mode = auto`.

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | Shortlist/pipeline list with columns: score, `geo_class`, company, role, status, last change; filter by status; sort; `/` search | MEDIUM | |
| Table stakes | Detail pane: assessment trail (reason codes), JD excerpt, dossier facts used in a draft, gate report | MEDIUM | |
| Table stakes | Status change with enforced transitions (reuse `is_valid_transition`), undo of the last change | LOW | Never re-implement the state machine in the UI. |
| Table stakes | Follow-ups due panel (reuse `follow_ups` service) | LOW | |
| Table stakes | Footer key hints, `?` help, `q` quit, `r` refresh | LOW | |
| Table stakes | Pilot-driven tests for every binding; snapshot tests for the main screens | MEDIUM | Satisfies the "every feature tested" rule; Pilot is the standard path. |
| Differentiator | Audit review screen: one key to overturn or confirm, counters, next item (the digest's sample, interactive) | MEDIUM | This is where the audit loop becomes a 60-second daily habit. |
| Differentiator | One-key shortlist toggle and one-key "open the application page" | LOW | |
| Anti-feature | Forms for editing everything (profile, settings) | HIGH | Edit the dossier file in `$EDITOR`; TUI shows and validates. |
| Anti-feature | Charts / analytics / funnel dashboards | MEDIUM | career-ops has progress and stats screens; none serve the core loop. `kestrel calibrate` text output suffices. |
| Anti-feature | Theming engines, i18n catalogs, mouse-first kanban | MEDIUM | career-ops carries two themes and a language catalog; pure scope. |
| Anti-feature | In-TUI chat / LLM panel | HIGH | The MCP server (5) is the agent surface. |

**Dependencies:** services layer (applications, follow_ups, geo), `assess()`, new submission-state and outcome model (3b), dossier/gates for the draft view (4).

#### 3b. Shortlist and outcome states (prepared / submit attempted / submission confirmed)

**Shortlist.** Existing statuses are `discovered, interested, applied, interviewing, offer, accepted, rejected, ghosted`. [J] Treat `interested` as the shortlist rather than adding an entity; career-ops' triage writes a shortlist file but it is the same concept (a human-curated set between "scored" and "applied"). Requirement: a shortlist toggle is a status change through the existing state machine, shown everywhere, and the MCP "my shortlist" tool reads the same thing.

**Outcome-state model.** The three requested states are a SUBMISSION axis, not new lifecycle statuses. Evidence:

- Simplify [P]: autofill fills; the user clicks the employer's Submit; the tracker entry is added only after "a supported submission is detected", and "saving a job or seeing 'Application filled' is not the same as receiving the employer's submission confirmation."
- Kestrel's own extension auto-log already separates a submit signal from a per-ATS confirmation signal (Greenhouse confirmation URL/element/text, Lever and Ashby equivalents), behind a visible consent banner with "no silent path".
- career-ops [P]: lifecycle states `evaluated, applied, responded, assessment, interview, offer, rejected, discarded, skip, hired` live in one canonical YAML (writer and dashboard must agree); a SEPARATE outcome journal records what actually happened, with 7 canonical types and aliases; `discarded` is deliberately overloaded (declined offer, ghosted), and the code warns "state is a tracker position, not a result".

Recommended model [J]:

| Axis | Values | Written by | Notes |
|------|--------|------------|-------|
| Lifecycle (existing) | discovered, interested, applied, interviewing, offer, accepted, rejected, ghosted | state machine | Unchanged. `applied` is set when submission is confirmed, or manually with `source=manual`. |
| Submission (new) | none, prepared, submit_attempted, submission_confirmed (plus unknown/failed) | prefill, extension signals, user | `prepared`: drafts/answers ready and form prefilled, nothing sent. `submit_attempted`: a submit event or navigation observed (Kestrel never causes it). `submission_confirmed`: ATS confirmation page/text observed, or user attests. |
| Result (new, separate) | interview, offer, rejected, declined, no_response, ... | user, or accepted proposal | One vocabulary module, imported by writer AND readers. |

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | Every transition appends to a ledger with timestamp, source (`user`, `extension_signal`, `proposal`, `manual`) and optional evidence | MEDIUM | career-ops keeps a status-log ledger beside the tracker and ranks evidence journal > ledger > current status. |
| Table stakes | Manual override of any state, always allowed, always recorded | LOW | |
| Table stakes | Single outcome vocabulary module used by writer and every reader | LOW | career-ops shipped a private 7-entry copy of a 14-entry vocabulary in `calibrate.mjs`, so half the spellings were invisible and two types (`declined`, `ghosted`) were dropped. Their fix: one shared module plus a load-time coverage check. Make that a test. |
| Table stakes | `submit_attempted` without confirmation older than N hours raises a "did it go through?" prompt, never a silent `applied` | LOW | The whole point of the middle state. |
| Differentiator | Evidence attached to each state ("confirmation page matched Greenhouse rule v2") | LOW | Makes the model auditable. |
| Anti-feature | Adding `prepared` / `submit_attempted` as lifecycle statuses | MEDIUM | Collapses two independent axes and breaks `VALID_TRANSITIONS` semantics and every report that counts `applied`. |
| Anti-feature | Inferring `applied` from "form was filled" | LOW | The documented Simplify distinction. |

**Dependencies:** `schemas/applications.py` state machine, `models` migration (Alembic), extension `autolog.content.ts`, `follow_ups.py` (its ghost thresholds, 14 days applied / 7 days interviewing, become inputs to "no_response", but label them inferred).

#### 3c. Outcome ingestion (responses, rejections, interviews)

| Approach | Who does it | Assessment |
|----------|-------------|------------|
| Mailbox connector auto-moves status | JobOps: connect Gmail, an interview invite moves status to "Interviewing", a rejection to "Rejected" automatically [P] | Highest convenience, highest risk (misclassification silently rewrites state; needs mailbox OAuth). |
| Proposal + human accept | career-ops `reply-watch`: a producer drops one JSON file per proposed transition (schema v1, 64 KiB cap, verbatim evidence excerpt, `from_status`/`to_status` ids, application identity snapshot); the user reviews and accepts, all-or-by-row; the write re-checks the tracker hash under a lock; a receipt token makes replay impossible; "N and EOF defer without a durable rejection" [P] | Correct safety model; the drop-directory contract is also the plugin boundary. |
| Manual | Both | Always required as the floor. |

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | `kestrel outcome <job> <type> [--on DATE] [--note]` and a TUI key, writing to the ledger | LOW | `--on` matters: the real event date, not today. |
| Table stakes | Idempotent: recording the same outcome twice does not duplicate | LOW | |
| Differentiator | "Paste a reply" ingestion: user pastes email text, the LLM proposes a transition with the quoted evidence, the user accepts | MEDIUM | No OAuth, no mailbox access, fits the cut list (OAuth is being removed). Goes through the same spend guard and PII masking. |
| Differentiator | File-drop proposal contract (copy career-ops' shape: one object per file, extra fields rejected, evidence quoted as data never as instructions, receipt for replay protection) so a later mailbox plugin needs no core change | MEDIUM | Defines the boundary without building the connector. |
| Anti-feature (v2.0) | Gmail/IMAP connector in core | HIGH | Needs OAuth or app passwords; conflicts with "OAuth cut" and the privacy story. Defer to v2.1 or a private plugin. |
| Anti-feature | Auto-applying a classified transition with no human step | MEDIUM | Treat reply text as untrusted data (it may contain instructions). |

---

### 4. KNOW YOU and WRITE

#### 4a. Readable, versioned profile dossier

career-ops separates the pieces by file [P]: `cv.md` and `article-digest.md` (proof points) as the factual sources, `config/profile.yml` for targets and preferences, `writing-samples/` for voice, and a cached `## Writing Style` section extracted from samples. Its rules are the right invariants: style extraction "applies to tone and structure only. Do not import content, claims, or metrics from samples", "only extract what is demonstrably present", and store abstract descriptors, not verbatim sentences or personal identifiers.

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | Three separate stores: verified facts, preferences, writing samples | MEDIUM | Distinctness is the requirement: only verified facts may back a claim in a draft; preferences steer search/scoring; samples steer style only. |
| Table stakes | Plain-text files (Markdown/YAML) in the user data dir, human-editable, diffable | LOW | The "readable" requirement. DB is an index, not the source of truth. |
| Table stakes | Version stamp: dossier content hash and a monotonically increasing version, recorded on every draft | LOW | Lets a draft be traced to the exact facts it was written from; enables "regenerate with current facts". |
| Table stakes | `kestrel dossier show / diff / validate` | LOW | Validate: required fields, dates parse, no duplicate facts, every fact has a source. |
| Differentiator | Per-fact provenance and `verified` flag (who/what confirmed it, when) | MEDIUM | Gate input. Imported facts (for example from existing STAR stories) start unverified until the user confirms. |
| Differentiator | A guided "verify your facts" pass (TUI) that walks unverified facts once | MEDIUM | Turns the dossier from a dump into a trusted base. |
| Anti-feature | LLM-maintained free-form memory/personality blob | HIGH | The "richer person model" is v2.1 and carries a kill criterion. |
| Anti-feature | Inferring facts or preferences from writing samples | LOW | Explicit career-ops rule; also a fabrication vector. |
| Anti-feature | Storing the dossier only in the DB | LOW | Not readable, not versioned, not portable. |

**Dependencies:** existing `Profile` model/onboarding, `star_stories`, `skills`; PII boundary (`ai/privacy.py`, `pii_masking.py`): dossier text sent to any provider must pass the provider registry check.
**Naming note:** `services/voice.py` is a text "voice discussion mode" (cover-letter brainstorm, coaching chat) and is unrelated to the "voice gate". Rename or park it so the two are not conflated.

#### 4b. Voice gate

**What it should check.** Employers mostly punish generic text, not AI use per se: a TopResume survey of 600 US hiring managers (May 2025) reports 19.6% would reject a candidate for an AI-generated resume or cover letter and 33.5% say they can spot one in under 20 seconds [S: vendor survey, reported by secondary outlets]; other articles say detection relies on generic phrasing and templated structure rather than detector tools [S]. Detector accuracy claims are unreliable. So the gate should target genericness and mismatch with the user's own writing, and must NOT be sold as AI-detection evasion.

Mechanical checks that exist as documented signals [P: Wikipedia "Signs of AI writing" page, read directly; career-ops `_writing.md`]:

| Check | Type | Severity default | Notes |
|-------|------|------------------|-------|
| Banned phrase list ("passionate about", "results-oriented", "proven track record", "leveraged", "spearheaded", "synergies", "cutting-edge", "in today's fast-paced world", "demonstrated ability to") | lexical, user-extendable | block | career-ops' shipped fallback list. |
| AI-vocabulary DENSITY (delve, tapestry, pivotal, crucial, showcasing, intricate...) | lexical | warn | Wikipedia: one or two hits may be coincidence, so score density, not single words. |
| Negative parallelism ("not only ... but also", "not X, but Y") | regex | warn | |
| Significance inflation and copula avoidance ("stands as", "serves as", "boasts") | regex | warn | |
| Vague attribution ("experts say", "industry reports") | regex | warn | |
| Rule-of-three cadence, em-dash density | statistic | warn, low weight | The page itself flags em-dash as a weakening, dated indicator. |
| Boilerplate openers/closers ("I am writing to express my interest") | regex | block | |
| Specificity floor: letter contains no concrete noun/number/project from the dossier | structural | warn | The "generic" failure employers actually cite. |
| Voice-match deltas vs sample-derived profile: sentence length mean and variance, contraction rate, first-person rate, exclamation and parenthetical habits, Oxford comma, paragraph length | statistic | warn with magnitude | Only for conversational text (cover letter, outreach, follow-up); NOT for CV bullets, matching career-ops' two-tier scope. |

Precedence [P]: the user's own style (derived from their samples or explicit rules) always beats the generic guardrail. If the user writes em-dashes, the em-dash check is off for that user. Accuracy always beats style: the gate may never ask to drop or soften a real metric.

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | Deterministic lexical/regex layer with located spans and pass/warn/block | LOW-MEDIUM | Free, instant, testable with fixed strings. |
| Table stakes | Per-user style profile extracted from samples, stored as abstract descriptors in the dossier | MEDIUM | Re-extract only when samples change. |
| Table stakes | Bounded revise loop (max 2 passes) when a draft is blocked | LOW | Prevents unbounded spend. |
| Differentiator | Style-delta report with numbers ("sentences average 24 words vs your 13") | MEDIUM | Actionable, explainable, no LLM judge needed. |
| Differentiator | Optional LLM "sounds like you" judge, ADVISORY only, shipped only after validation against the user's own labelled examples (TPR/TNR) | HIGH | Per eval practice, an unvalidated judge is not a gate. |
| Anti-feature | "Humanizer" / detector-evasion features | MEDIUM | Unreliable arms race, dishonest framing. |
| Anti-feature | Hard-blocking on a single weak signal (one em-dash, one listed word) | LOW | Produces noise and trains users to override. |
| Anti-feature | Volume cover letters for every discovered job | MEDIUM | Draft only for shortlisted jobs; also the cost-safety line. |

#### 4c. Fact gate

career-ops' fact gate (`verify-cv-facts.mjs`, with tests named `cover-fact-gate`, `fact-gate-every-producer`, `fact-gate-missing-config`, `nonmetric-fact-gate`, `generate-pdf-batch-fact-gate`) is the best available blueprint [P]:

- Extracts claims of kinds: metrics (including currency in `$ € £`, with k/M suffixes normalized), employers, job titles, tools, and "delegated authorship" claims (claiming sole credit for team work).
- Verifies each against the user's source documents; `verdict: pass | block`, with `unsupportedFacts` and `invented` lists.
- Config with `allow_metrics`, `allow_facts` (explicit user exceptions), `forbidden_phrases` ("Fortune 500", "patented"), `warn_phrases`.
- "Every producer": a test enumerates every mode and renderer that produces a candidate-facing document and fails if one lacks the gate. It exists because of a real defect (issue #5348 in the test header): the PDF path was gated while the LaTeX and plain-text paths, which hand the user an equally sendable CV, ran nothing. Enumerate producers; do not name them.
- Missing config or unreadable source is a tested case; override exists (`--skip-fact-check`) but is explicit.
- Honest limit, stated in their README and issue tracker: "it cannot judge every rewording yet"; a fail-closed faithfulness check is still an open issue. Title changes warn rather than block "because reframing a title is sometimes your call".

What Kestrel's fact gate should check [J]:

| Claim class | Rule | Result if unsupported |
|-------------|------|-----------------------|
| Numbers: percentages, currency, counts, durations, multipliers | Must appear (after normalization) in a VERIFIED dossier fact | block |
| Employers, schools, certifications | Must match a verified fact | block |
| Job titles | Must match the verified title for that employer/date range; reframing flagged | warn |
| Tools/technologies named as used | Must appear in a verified fact | block |
| Years of experience / tenure | Recomputed from verified dates; stated value must not exceed it | block |
| Ownership verbs ("I led/built/owned") | Verified fact must support individual ownership, else suggest "contributed to" | warn |
| Claims about the TARGET company or role ("your recent funding", "your Berlin office") | Must be grounded in the stored JD or stored research for that job | warn (block for specific figures) |
| Forbidden / warn phrases | User list | block / warn |
| Gate precondition | Dossier readable, has verified facts, config parses; otherwise FAIL CLOSED, never pass | block |

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | Deterministic claim extraction and verification as above, one function `gate_draft(text, job, dossier)` | MEDIUM-HIGH | |
| Table stakes | Single choke point used by CLI drafting, MCP, extension prefill free-text, and TUI, with a test that enumerates producers | MEDIUM | career-ops' `fact-gate-every-producer` pattern. |
| Table stakes | Explicit logged override stored in draft metadata | LOW | Never silent. |
| Table stakes | Gate report shows each claim and the fact id that supports it ("fact ledger") | LOW | Traceability is a user-visible feature. |
| Differentiator | Optional LLM entailment check for paraphrase drift, advisory, with measured TPR/TNR on the user's own labelled examples before it is trusted | HIGH | Fills the gap career-ops leaves open; do not make it a hard gate in v2.0. |
| Anti-feature | Letting the model self-certify ("I checked, all facts are accurate") | n/a | |
| Anti-feature | Using writing samples or preferences as fact sources | LOW | Distinct stores (4a). |

#### 4d. Drafting cover letters and outreach in the user's voice

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | JD + dossier -> draft, saved with versions, editable, shows which facts it used | MEDIUM | |
| Table stakes | Gates run BEFORE the draft is shown; failures shown with the report | LOW | |
| Table stakes | "Ask, don't invent": when the dossier lacks a relevant fact, the draft asks the user or leaves a marked gap | LOW | career-ops rule "reformulate, never fabricate". |
| Table stakes | Outreach (LinkedIn note, email text) is text only: Kestrel never sends | LOW | |
| Differentiator | Voice conditioning with a few of the user's own samples plus the style profile | MEDIUM | |
| Differentiator | Draft metadata: dossier version, model, gate verdicts, override flags | LOW | |
| Anti-feature | Auto-send, scheduled sending, mail transport | MEDIUM | |
| Anti-feature | Per-job tailored CV/PDF generation in v2.0 | HIGH | A large separate surface (career-ops and JobOps both build it). The thesis is writing in your voice; a CV pipeline is a candidate for v2.1. Existing maintainer scripts for CV rendering are not ported unless proven in daily use. |
| Anti-feature | Interview prep, coaching, STAR practice in the core loop | MEDIUM | Existing features, parked from default surfaces (see anti-feature table). |

#### 4e. Extension prefill of application forms (prefill is NOT submit)

Reference behaviours [P]:

- **Simplify Copilot:** fills supported fields, user reviews each page, "you click the employer's final Submit button yourself"; reuses an answer only when the exact same question reappears and warns to check reused answers for outdated company names or dates; unsupported forms fall back to manual copy; tracker add happens only after a submission is detected.
- **career-ops `apply` mode (field-tested on Ashby, Greenhouse, Lever, Workable):** "Career-Ops never submits"; per-ATS quirks: Ashby merges candidates by email, so warn before reusing an email on a second application to the same company; Lever pops hCaptcha on programmatic checkbox/radio clicks, so fill only text, textarea and standard selects and LIST every skipped field; react-select recreates DOM per keystroke, so type with delays and re-snapshot; huge native dropdowns are selected by value or label rather than dumped; a **knock-out pre-scan** of the form (minimum years, degree, work authorization/visa, salary floor) halts BEFORE drafting if the profile answer would likely auto-reject; detect that the form is for a different role than the evaluated one and ask; run the liveness sweep first so no tab is opened for a dead posting.

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | Fills identity/contact/links/work-authorization fields from the dossier's verified facts for Greenhouse, Lever and Ashby (the same three ATSs the extension already recognises) | HIGH | React-controlled inputs need native-setter plus input/change events; file inputs and shadow DOM vary per ATS. |
| Table stakes | Never clicks Submit, never solves a captcha, never touches fields it cannot map; shows a "filled / skipped" list | MEDIUM | The anti-pattern list from Lever applies. |
| Table stakes | Free-text answers come from Kestrel (local server), run through the fact and voice gates, are shown for per-field accept before insertion | MEDIUM | |
| Table stakes | Sets submission state `prepared`; later `submit_attempted` / `submission_confirmed` come from the existing signals (3b) | LOW | |
| Table stakes | Narrow host permissions limited to the three ATS domains plus the local Kestrel origin, no telemetry | MEDIUM | Chrome Web Store review of a form-filling extension is a schedule risk; flag it. |
| Differentiator | Knock-out pre-scan before generating any answer | MEDIUM | Rare in the field; saves wasted effort and protects the user. |
| Differentiator | Duplicate-application warning (already applied to this company) | LOW | Kestrel has the pipeline; career-ops can only check its tracker. |
| Differentiator | Re-check liveness via the ATS API at fill time (1d) | LOW | |
| Anti-feature | Auto-submit, auto-click Apply, batch apply (opt-in auto-submit is v2.1) | n/a | |
| Anti-feature | Captcha solving, stealth/anti-detection, proxy rotation | HIGH | The repo's `tools/` directory contains such scripts from earlier work; they are not part of the product and should be deleted after any needed logic is ported and replay-verified, per the milestone's "delete only after port" rule. |
| Anti-feature | Filling unknown fields with LLM guesses | LOW | Unknown means blank plus a listed note. |
| Anti-feature | Workday and other long-tail ATSs in v2.0 | HIGH | Already deferred in the extension plan. |

**Dependencies:** extension capture and auto-log (existing), local API endpoint for dossier answers, dossier + gates (4a-4c), state model (3b), PII boundary (answers contain personal data and travel over localhost only; any LLM call goes through masking).

---

### 5. CONNECT: MCP server for the user's coding agents

Existing: `tools/kestrel-mcp/server.py` exposes four tools (`list_pipeline`, `pipeline_stats`, `score_job`, `discover_jobs`) as an HTTP proxy to the running API, with an API key and profile id from env. v2.0 turns this into a first-class, state-owning server.

How comparable tools handle it:

- **career-ops:** no first-party MCP server found in the tree (only a plugin-registry entry for a Workspace MCP); it works as agent instruction files (`AGENTS.md`, `SKILL.md`, mode prompts) that the user's coding CLI executes against local files. Notable safety habit: its triage prompt tells the agent to treat every field in the pipeline file as untrusted third-party data, not instructions, and to read and write only named files. [P]
- **JobSync:** MCP server lets agents add applications and Question Bank entries "with your approval"; setup uses a generated token and either `mcp-remote` or direct streamable-http. [P README, no tool list published]
- **Directory listings [S]:** local-first SQLite trackers with ~19 tools; servers that mix read tools (search, list) with write tools (log to Notion); no server found that is read-only, personal-data-aware AND drafts. Treat as evidence that scoping is under-designed in the field.

Rules from the specification and its security guidance [P: MCP spec 2025-11-25, "Tools" and "Security Best Practices"]:

- Tools are model-controlled; there SHOULD be a human in the loop able to deny invocations.
- Tool annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) are hints; "clients MUST consider tool annotations to be untrusted unless they come from trusted servers". Enforce permissions server-side.
- Servers MUST validate all inputs, implement access controls, rate limit, and sanitize outputs.
- Use `stdio` for local servers; if HTTP, require an authorization token or a restricted socket; beware DNS rebinding on localhost.
- Scope minimization: minimal initial read-only scope, step up for privileged operations; avoid omnibus scopes.
- Define `outputSchema` and return `structuredContent` so agents parse results reliably; report recoverable problems as `isError` results with an actionable message so the model can retry.

Recommended tool surface [J]:

| Group | Tools | Mode |
|-------|-------|------|
| Read: pipeline | `list_shortlist`, `get_job` (JD, assessment trail, `geo_class`, reason codes, liveness), `list_followups`, `pipeline_summary` | read-only |
| Read: you | `get_dossier(section)` returning verified facts, preferences or style profile, with section-level control; unverified facts marked as such | read-only |
| Draft support | `get_drafting_context(job_id, kind)` (JD excerpt + relevant verified facts + style profile + banned phrases), `check_draft(job_id, text)` -> gate report | read-only (no LLM spend in Kestrel) |
| Write (opt-in) | `save_draft(job_id, text, kind)` (runs gates, stores only on pass or recorded override), `set_status` (through the state machine), `record_outcome`, `propose_overturn` (creates a pending item for the human) | write, behind a capability flag |
| Never exposed | submit/apply, send email/message, delete, raw SQL, file read/write, provider keys or config secrets, bulk scoring without a budget argument, finalizing an overturn | none |

Design choices:

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | `stdio` transport by default; `kestrel mcp` command; one-line client config snippet in the README | LOW | HTTP transport only with a bearer token and loopback bind (also resolves the default `0.0.0.0` bind issue for the API). |
| Table stakes | Capability levels as server launch flags (`read-only` default for first run; `--allow-write` enables the write group), enforced in code, with annotations as courtesy | MEDIUM | Annotations alone are not a control. |
| Table stakes | Every JD/company field in results is marked as untrusted data, length-capped, control characters stripped | LOW | A job description is attacker-controlled text that lands in an agent's context. |
| Table stakes | Local append-only audit log of tool calls (tool, args hash, result status) and per-minute rate limit | LOW | Spec says log tool usage and rate limit. |
| Table stakes | Spend guard applies to anything that could call a paid provider | LOW | The agent supplies the LLM; Kestrel's own paid calls (scoring) need `max_cost` arguments and the global halt. |
| Differentiator | The agent drafts with its OWN model but through Kestrel's state: facts, style, gates, persistence, versioning | MEDIUM | No other tool in this set exposes deterministic gates to an agent. Document the privacy consequence: dossier content travels to whatever model that agent uses. |
| Differentiator | Resources for the dossier sections so clients can attach them explicitly | LOW | |
| Anti-feature | A large tool catalogue mirroring the REST API (150 endpoints) | HIGH | Tool selection quality degrades with catalogue size [J, unverified]; keep roughly a dozen tools. |
| Anti-feature | Token passthrough or storing third-party tokens in the MCP layer | MEDIUM | Spec forbids token passthrough. |
| Anti-feature | Hosted/remote MCP | HIGH | Local only. |

**Dependencies:** services layer, dossier, gates, `assess()`, state model, cost safety. Natural last functional phase.

---

### 6. COST SAFETY: preflight, spend halt, 402 vs 429

Provider behaviour is NOT uniform, so "402 means no credits, 429 means rate limit" is not a safe rule. Verified [P: each provider's own error docs]:

| Provider | Out of credits / spend limit | Rate limited | Notes |
|----------|-----------------------------|--------------|-------|
| OpenRouter | HTTP 402 "Insufficient credits"; not a wait-and-retry case without `Retry-After` | HTTP 429, wait `Retry-After` | SDKs back off on 429 and 5xx but do not retry a 402. Errors can also arrive mid-stream after a 200. |
| OpenAI | HTTP 429 with a billing/quota `error.code` (`credit_balance_exhausted`, `organization_spend_limit_exceeded`, `project_spend_limit_exceeded`, `organization_usage_limit_exceeded`; type `insufficient_quota`); "retrying will not restore access" | HTTP 429 without those codes, `Retry-After` or exponential backoff with jitter | Same status, opposite action. Discriminate on `error.code`. |
| Anthropic | HTTP 402 `billing_error`; HTTP 400 when an org or workspace spend limit you set is reached; HTTP 429 when a usage tier monthly spend cap is reached, and that 429 has no `retry-after` and keeps failing | HTTP 429 `rate_limit_error` (with `retry-after` normally); 529 `overloaded_error` is transient | A 429 can be a cap, so absence of `retry-after` plus persistence is a quota signal. |

Other providers in the registry (Together, Groq, xAI, Gemini, Mistral, Hugging Face, Ollama) were not verified here; requirements should require recorded real error-body fixtures per provider rather than assumptions.

Recommended classification [J]: `RATE_LIMITED` (wait; honor Retry-After; bounded total wait), `QUOTA_EXHAUSTED` (halt; no retry; no provider fallback), `TRANSIENT` (5xx/529/timeout: bounded retry, fallback allowed), `AUTH` (halt), `BAD_REQUEST` (fail the item, not the run). A 429 with no Retry-After that persists past N attempts is reclassified as suspected `QUOTA_EXHAUSTED`.

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | Error classifier keyed on (status, provider error type/code, Retry-After presence), table-tested with recorded fixtures per provider | MEDIUM | Extends the existing `ProviderQuotaError` / `CreditsExhaustedError` (currently OpenRouter-specific). |
| Table stakes | 429 waits (bounded) instead of falling through to another or pricier provider | LOW | Escalating on 429 is how a transient limit becomes spend. |
| Table stakes | Preflight (`kestrel preflight`, run automatically before scan-with-scoring and batch): key present, cheap authenticated probe, classified result, estimated cost of the pending batch against the preset and cap | MEDIUM | Existing `ai_health.py` covers mock and OpenRouter only. Do not assume a balance API exists for every provider. |
| Table stakes | Spend halt as a CODE INVARIANT: all provider calls go through one guard that tracks cumulative cost per run/day/month and raises a non-retryable halt; a test proves no provider call path bypasses it | MEDIUM | The point of "invariant" is an architectural test (for example a static test that provider classes are only constructed by the guarded factory), plus a mutation probe that removes the guard and expects the test to fail. |
| Table stakes | Cost line in digest and TUI; default cap ON with a conservative default | LOW | Safe defaults for a stranger. |
| Differentiator | Cheap-first ordering is enforced: dedup, liveness, prefilter and `assess()` run before any paid call, and the cascade/batch path is the default for bulk | LOW | Mostly existing mechanisms; v2.0 makes the ordering a tested property of `scan`. |
| Anti-feature | Auto top-up, auto-switch to a more expensive model under pressure, silent premium fallback | LOW | A fallback chain where an unconfigured provider silently uses its expensive default is a known leak pattern; require an explicit model for every provider in the chain. |
| Anti-feature | Unbounded retry loops or retries on quota errors | LOW | |
| Anti-feature | A spend dashboard | MEDIUM | One digest line is enough. |

**Dependencies:** `ai/base.py`, `ai/fallback.py`, `ai/factory.py`, `services/presets.py`, `services/ai_health.py`, `async_batch.py`. Must land before any cron-driven scoring.

---

### 7. INSTALL (15 minutes) and README that leads with "learns you"

| Class | Feature | Complexity | Notes |
|-------|---------|------------|-------|
| Table stakes | One documented install path for a technical stranger (pip/pipx or equivalent single command) and a `kestrel init` that creates the data dir, `companies.yml` starter, and a dossier skeleton | MEDIUM | PROJECT already says keep one path. |
| Table stakes | A first useful list WITHOUT an LLM key: ATS scan is keyless, `assess()` triage (geo, title, dedup, liveness) is deterministic | LOW | The key to the 15-minute budget: no signup step in the critical path. Scoring is the optional second step. |
| Table stakes | `kestrel doctor` verifies each stage and prints the next command | LOW | Existing `cli/doctor.py`. |
| Table stakes | Measured on a clean machine or container in CI, with the timing recorded | MEDIUM | "Tested on a fresh machine" is the requirement; make it automated, not a manual claim. |
| Table stakes | README states what Kestrel will not do: no auto-submit, no sending email, no telemetry, local data | LOW | This is now the genre norm. career-ops lists "what it will not do" and a manifesto ("A human decides. Local-first."). |
| Differentiator | README leads with "learns you", with ONLY claims that are true in v2.0: a dossier it reads, a voice it checks drafts against, a filter it lets you correct (overturn -> fixture), a calibration report on your outcomes. State plainly that automated learning from edits and outcomes is not in v2.0 | LOW | Project accuracy rule: every claim verifiable against the code. |
| Differentiator | A short recorded demo (terminal capture) of digest -> audit sample -> overturn -> fixture turning green | LOW | The loop is the product. |
| Anti-feature | Docker or desktop installer as a primary path; hosted version | HIGH | Non-technical path is v2.1. |
| Anti-feature | README leading with provider count, test count or feature inventory | LOW | |
| Open decision | The web onboarding wizard is "kept working as the start of the 15-minute path" in the milestone text, which conflicts with "one install path" if it needs the API server | n/a | Requirements should choose: CLI `init` primary, web onboarding optional. |

---

## Anti-Features: existing Kestrel features to PARK or leave unextended in v2.0

The milestone text already names some of these for removal; the rest are recommendations [J] to keep the default surface (README, CLI help, TUI, MCP) on the core loop. "Park" means: hide from default surfaces, keep the test suite green, do not extend, and do not mention in the README lead.

| Feature | Status in milestone | Recommendation |
|---------|---------------------|----------------|
| Planning-framework scaffolding, Cloudflare worker and dashboard, TickTick / calendar / OAuth / WARN integrations, unused deploy and release surface | Named for cutting | Cut. |
| React web app (11 pages, kanban, analytics) | Parked behind the TUI, kept working | Park; no new pages; only what the 15-minute path needs. |
| Mobile scaffold, Hosted version, Desktop app, Voice Mode roadmap items | Roadmap "Next/Later" | Remove from the "Next" list in ROADMAP.md; the roadmap currently promises Desktop App as v0.13 and a Mobile App, which contradicts the thesis. |
| Interview prep, STAR story practice, coaching, gap analysis / skills coaching, market analysis, company research, salary tools | Not named | Park. STAR stories may feed the dossier as unverified facts; the practice surfaces do not belong in the loop. |
| Voice discussion mode (`services/voice.py`) | Not named | Park and rename to avoid the "voice gate" collision. |
| Bayesian preference learning, embeddings pre-filter, cascade router, async batch variants as user-facing features | Shadow/flagged already | Leave flagged off. Learning automation is v2.1. |
| 11-provider breadth as a selling point | Shipped | Keep the code; stop leading with it. Test only providers whose error bodies have fixtures. |
| Maintainer batch scripts in `tools/` (auto-apply, captcha solver, scrapers) | Port, replay-verify, then delete | Port only logic proven in daily use (ATS poller, dedup, liveness, canaries, cost guards). Do not port captcha solving or auto-apply. |

## Feature Dependencies

```
Cost safety (6: classifier, SpendGuard, preflight)
    └──gates──> any unattended scoring (scan on cron, batch)

ATS sources (1a) ──> persisted arrivals + listing_key (1b) ──> dedup (1c) ──> liveness (1d)
                                   │                                   │
                                   ├──> source canaries (1e) ──────────┤
                                   └──> excluded rows with reason codes ──> audit sample (2d)

assess() (2a) ──requires──> geo gate wiring (2b)
assess() (2a) ──feeds────> digest (2d) ──> audit sample ──> overturn ──> fixtures ──> verify-fixtures
assess() (2a) ──feeds────> TUI (3a), extension inline score, MCP get_job

State model (3b: submission axis + ledger) ──> outcome recording (3c) ──> calibrate (2c)
State model (3b) ──requires──> extension signals (existing auto-log)

Dossier (4a) ──> fact gate (4c) + voice gate (4b) ──> drafting (4d) ──> MCP draft tools (5)
                                                  └──> extension prefill (4e) ──> state `prepared` (3b)
Liveness (1d) ──enhances──> prefill (4e)

15-minute install (7) ──requires──> keyless scan + deterministic assess() + doctor
README "learns you" (7) ──requires──> dossier + voice gate + overturn loop + calibrate (so claims are true)

Conflicts:
  Gmail/IMAP connector in core ──conflicts──> "OAuth cut" and local-first privacy story
  Browser liveness (Playwright) ──conflicts──> 15-minute install
  Automated learning from overturns/outcomes ──conflicts──> v2.0 scope (deferred to v2.1)
  `prepared`/`submit_attempted` as lifecycle statuses ──conflicts──> existing VALID_TRANSITIONS and `applied` reports
```

### Dependency notes

- **Cost safety is the first prerequisite**, not the last: a headless cron that can score is a standing spend risk.
- **Persisting excluded arrivals (1b) is the single most load-bearing data decision**: dedup, canaries, the audit sample, fixtures and calibration all read it. If it is added late, the audit loop has no history.
- **`assess()` before everything that filters**: building the digest, TUI and MCP on three different filters is the career-ops defect.
- **Gates before drafting before agents**: the MCP server and extension prefill must call the same `gate_draft()`; add a test that enumerates producers.

## MVP Definition

### Launch with (v2.0)

- [ ] Provider error classifier, SpendGuard, preflight (6)
- [ ] ATS sources + companies config + persisted arrivals with reason codes + `listing_key` (1a, 1b)
- [ ] Dedup L0-L2 (L4 repost flag as stretch), API liveness rung, source canaries and floors (1c-1e)
- [ ] `assess()` single entry point, geo wiring with `geo_class` visible, multi-office rule (2a, 2b)
- [ ] Digest with audit sample, overturn -> fixture, `verify-fixtures` (2d)
- [ ] Textual TUI: list, detail, status change, follow-ups, audit screen (3a); shortlist = `interested`; submission axis and ledger; manual and paste-a-reply outcomes (3b, 3c)
- [ ] Dossier (three stores, versioned), fact gate, voice gate, drafting with traceability (4a-4d)
- [ ] Extension prefill for Greenhouse/Lever/Ashby, never submit (4e)
- [ ] MCP server: read + draft-support tools, write behind a flag (5)
- [ ] `kestrel init`, doctor, clean-machine timing test, README rewrite (7)
- [ ] `kestrel calibrate` advisory report (2c)

### Add after validation (v2.0.x)

- [ ] L3 cross-source near-duplicate (SimHash) advisory column
- [ ] LLM entailment check and "sounds like you" judge, advisory, after TPR/TNR validation on the maintainer's own labelled examples
- [ ] Mailbox connector as an optional plugin on the proposal-file contract
- [ ] Knock-out pre-scan if not in the first prefill cut

### Future consideration (v2.1+)

- [ ] No-terminal path, richer person model with kill criterion, automated learning from edits and outcomes, Firefox build, opt-in auto-submit (all named v2.1)
- [ ] Browser-based liveness, tailored CV/PDF generation, Workday and long-tail ATSs

## Feature Prioritization Matrix

| Feature | User value | Cost | Priority |
|---------|-----------|------|----------|
| Provider error classifier + SpendGuard + preflight | HIGH | MEDIUM | P1 |
| ATS sources + persisted arrivals + dedup L0-L2 | HIGH | MEDIUM | P1 |
| `assess()` + geo gate + `geo_class` | HIGH | MEDIUM-HIGH | P1 |
| Source canaries and floors | HIGH | LOW | P1 |
| API liveness rung | MEDIUM-HIGH | MEDIUM | P1 |
| Digest + audit sample + overturn fixtures | HIGH (distinctive) | MEDIUM | P1 |
| Textual TUI core | HIGH | MEDIUM | P1 |
| Submission-state axis + outcome ledger | HIGH | MEDIUM | P1 |
| Dossier + fact gate | HIGH | MEDIUM-HIGH | P1 |
| Voice gate (deterministic layer) | MEDIUM-HIGH | LOW-MEDIUM | P1 |
| Drafting in voice | HIGH | MEDIUM | P1 |
| MCP server (draft-support, scoped) | HIGH | MEDIUM | P1 |
| 15-minute install + README | HIGH | MEDIUM | P1 |
| Extension prefill (3 ATS) | HIGH | HIGH | P2 (schedule risk; sequence late) |
| Repost flag (L4) | MEDIUM | MEDIUM | P2 |
| `kestrel calibrate` | MEDIUM | MEDIUM | P2 (needs data to be useful) |
| Paste-a-reply outcome ingestion | MEDIUM | MEDIUM | P2 |
| Re-resolution of branded URLs | MEDIUM | MEDIUM-HIGH | P2 |
| LLM judges (voice, entailment) | LOW-MEDIUM | HIGH | P3 |
| Mailbox connector | MEDIUM | HIGH | P3 |

## Competitor Feature Analysis

| Feature | career-ops | JobOps / JobSync | Simplify | Kestrel v2.0 approach |
|---------|-----------|------------------|----------|-----------------------|
| ATS polling | Ashby, Greenhouse, Lever, Wellfound + others via `portals.yml`, 100+ preconfigured | JobSync: Greenhouse/Lever/Ashby directories, scheduled | n/a | 3 ATSs, companies file, starter list, resolver |
| Persist excluded arrivals | `scan-history.tsv` with skip statuses | not documented | n/a | Required, with stable reason codes |
| Dedup | URL normalization, strong listing key, SimHash advisory, repost detector with min-span and title identity | not documented | n/a | L0-L2 required, L4 with same four rules |
| Liveness | API rung then Playwright, conservative | n/a | n/a | API rung only, tri-state |
| Source health | `audit-portals` verdicts + baseline drift; exit code when all fail | n/a | n/a | Per-run verdicts, 50% drift, global floor, optional dead-man ping |
| One admission gate | `createAdmissionGate` (added to fix divergence) | n/a | n/a | `assess()` with parity test |
| Audit of excluded items | Raw log + analytics + `coverage-check` (manual inverse); no overturn loop | JobSync: accept/dismiss of discovered only | n/a | Sampled, overturnable, becomes fixture |
| TUI | Go Bubble Tea: tabs, sort, search, status picker, discard-reason picker, stats screens | web UIs | n/a | Textual: same conventions, no stats/theme/i18n |
| Outcome states | Lifecycle YAML + separate outcome journal + reply proposals with receipts | JobOps: Gmail auto-moves status | Tracker add only after detected submission | Submission axis + ledger + proposals, manual and paste-a-reply first |
| Fact gate | Yes (metrics, employer, title, tool, authorship; fail-closed on config; override flag); semantic drift open issue | n/a | n/a | Same plus company-claim grounding, years recompute, single choke point |
| Voice | `voice-dna.md` banned list + style extraction from samples (LLM-driven, prompt-level) | n/a | Simplify+ drafts essays | Deterministic voice gate with numbers, user style wins |
| Prefill | Playwright-driven, never submits, knock-out pre-scan, per-ATS quirks | n/a | Chrome extension, user submits, auto-track on detection | In-extension, 3 ATSs, never submits, consent for logging (built) |
| MCP | none first-party found | JobSync: approval + token | n/a | Scoped, read-first, gates exposed, audit log |
| Cost safety | token-budget docs, free-tier mode | n/a | n/a | Code-level halt, per-provider classifier |

## Open questions for requirements and phase research

1. Ashby `id` field and unlisted-posting semantics: verify on a live board response before choosing the listing key. Rate limits for Greenhouse and Ashby GET endpoints are undocumented; set an explicit pacing default.
2. Definition of the multi-office over-admission rule: copy from the v1.1 geo design notes, not from this document.
3. What "calibrated scoring" must add in v2.0 beyond the shipped Scoring Engine v2 (this document assumes the outcome-calibration report).
4. Whether the fixture export is ever shared publicly; default is user-private.
5. Whether `assess()` can wrap the 4k-line scoring service without a refactor (phase-level research flag).
6. Extension prefill: Chrome Web Store policy for form-filling, permission scope, and per-ATS DOM stability; needs a spike per ATS before the phase is planned.
7. CLI-first init versus web onboarding as the 15-minute path.
8. Provider coverage for the error classifier beyond OpenRouter, OpenAI and Anthropic.

## Sources

Primary [P]
- career-ops repository (files read via GitHub API: `README.md`, `templates/states.yml`, `scan.mjs`, `lib/scan-history-columns.mjs`, `lib/admission-gate.mjs`, `docs/listing-fingerprint.md`, `detect-reposts.mjs`, `filter-audit.mjs`, `discard-analytics.mjs`, `audit-portals.mjs`, `liveness-core.mjs`, `liveness-api.mjs`, `calibrate.mjs`, `modes/calibrate.md`, `lib/outcome-types.mjs`, `docs/REPLY_PROPOSALS.md`, `docs/APPLY_AUTOFILL.md`, `docs/AUTOMATION.md`, `docs/KEEPING_PORTALS_LIVE.md`, `modes/_writing.md`, `modes/followup.md`, `config/cv-facts.example.json`, `tests/nonmetric-fact-gate.test.mjs`, `dashboard/README.md`, `dashboard/internal/ui/screens/pipeline.go`): https://github.com/career-ops-hq/career-ops (accessed 2026-10-24)
- Greenhouse Job Board API: https://docs.greenhouse.io/job-board.html (accessed 2026-10-24)
- Lever Postings API: https://github.com/lever/postings-api (accessed 2026-10-24)
- Ashby public job posting API: https://developers.ashbyhq.com/docs/public-job-posting-api (accessed 2026-10-24)
- MCP specification, Tools (2025-11-25): https://modelcontextprotocol.io/specification/2025-11-25/server/tools (accessed 2026-10-24)
- MCP Security Best Practices: https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices (accessed 2026-10-24)
- Textual DataTable, input and bindings, command palette, testing: https://textual.textualize.io/widgets/data_table/ , https://textual.textualize.io/guide/input/ , https://textual.textualize.io/guide/command_palette/ , https://textual.textualize.io/guide/testing/ (accessed 2026-10-24)
- OpenRouter errors: https://openrouter.ai/docs/api/reference/errors-and-debugging (accessed 2026-10-24)
- OpenAI error codes: https://developers.openai.com/api/docs/guides/error-codes (accessed 2026-10-24)
- Anthropic API errors: https://platform.claude.com/docs/en/api/errors (accessed 2026-10-24)
- Simplify Copilot autofill help article: https://help.simplify.jobs/articles/2415391-using-copilot-to-autofill-applications (accessed 2026-10-24)
- JobOps: https://github.com/DaKheera47/job-ops (accessed 2026-10-24)
- JobSync: https://github.com/Gsync/jobsync (accessed 2026-10-24)
- python-jobspy README: https://github.com/speedyapply/JobSpy (accessed 2026-10-24)
- Healthchecks.io docs (dead man's switch model): https://healthchecks.io/docs/ (accessed 2026-10-24)
- Hamel Husain, Evals FAQ (sampling, binary labels, TPR/TNR, failures into repeatable set): https://hamel.dev/blog/posts/evals-faq/ (accessed 2026-10-24)
- Wikipedia, Signs of AI writing: https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing (accessed 2026-10-24)
- Kestrel repository files read for dependency mapping: `src/career_os/schemas/applications.py`, `src/career_os/cli/main.py`, `src/career_os/services/*`, `extension/entrypoints/autolog.content.ts`, `tools/kestrel-mcp/README.md`

Secondary [S] (market color only; no requirement depends on these)
- TopResume AI-in-hiring survey: https://topresume.com/career-advice/ai-in-hiring-survey
- Ghost-job prevalence coverage: https://www.entrepreneur.com/business-news/one-quarter-of-jobs-posted-online-are-fake-ghost-jobs-study/ ; https://www.fox4news.com/news/ghost-jobs-greenhouse-analysis
- Huntr stages: https://help.huntr.co/en/articles/10042685-the-job-board
- MCP job-tracker directory listings: https://glama.ai/mcp/servers/vafod8r2b0 and similar listings (descriptions are self-reported)

---
*Feature research for: Kestrel v2.0 "Lean Kestrel"*
*Researched: 2026-10-24*
