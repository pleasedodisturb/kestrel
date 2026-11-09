# Stack Research: v2.0 Lean Kestrel

**Domain:** Self-hosted AI job-search tool (Python/FastAPI/SQLAlchemy/SQLite/Typer) gaining a TUI, a headless cron scan, ATS-API sources, cost safety, a digest, a profile dossier, an MCP server and a stranger-proof install
**Researched:** 2026-10-24 (replaces the 2026-04-19 onboarding-milestone file)
**Confidence:** MEDIUM-HIGH. Versions are HIGH (read from the PyPI JSON API and the GitHub releases API on 2026-10-24). ATS rate limits are LOW (no vendor publishes GET limits). Provider error semantics are MEDIUM (official docs for Anthropic and OpenRouter; secondary sources for OpenAI and Gemini).

> Tooling note: Context7 was not reachable from this research agent. Library behavior was verified from official documentation via WebFetch and from the registries directly. Each claim below carries its source in "Sources".

## Verdict in one paragraph

v2.0 needs **one new runtime dependency (`textual`)**, **one new optional extra (`mcp` 2.x, replacing a broken v1-era extra)**, **two dependencies declared that are already imported (`platformdirs`, `pyyaml`)**, and **zero new libraries for everything else**. Dedup, scheduling, spend halt, ATS adapters, digest delivery, dossier gates and file locking are all built on `httpx`, `rapidfuzz`, `sqlite3`/SQLAlchemy and the stdlib that Kestrel already has. Three existing dependencies can be removed (`aiosqlite`, `icalendar`, `warn-scraper` extra) and one (`python-jobspy`) must move from a hidden dev-only dependency to an explicit optional extra. The biggest stack risks are not new libraries; they are (a) the install path silently resolving "latest of everything" with no lockfile, (b) cwd-relative `data/` and `.env` defaults that break under cron and `uv tool install`, (c) the 402/429 conflation already present in every provider, and (d) the MCP SDK's v1 to v2 rename that has already broken `tools/kestrel-mcp/server.py` on a fresh install.

## Recommended Stack

### Core Technologies (new or changed)

| Technology | Version (verified 2026-10-24) | Purpose | Why Recommended | Serves core loop? |
|------------|-------------------------------|---------|-----------------|-------------------|
| `textual` | `>=8.2,<9` (latest 8.2.8, 2026-06-30) | The TUI: shortlist, follow-ups due, single-key status changes, report viewer | The only maintained Python library that gives a keyboard-first, event-driven, testable full-screen UI on macOS/Linux/Windows with a Rich-native look. Same author and render engine as Rich (already a dependency). `DataTable` (row cursor, `add_row(key=<pk>)`, `sort`), `BINDINGS`, `Markdown`/`MarkdownViewer` cover every listed TUI requirement without custom widgets. Headless testing via `App.run_test()` + `Pilot` works with the repo's existing `pytest-asyncio` `asyncio_mode = "auto"`. | Yes (Track) |
| `mcp` (official MCP Python SDK) | `>=2.3,<3` (latest 2.3.0, 2026-10-02), as optional extra `kestrel-app[mcp]` | MCP server so Claude Code and Codex draft through Kestrel state | Official SDK, v2.0.0 went stable 2026-07-28, and `pip install mcp` now resolves to 2.x. The high-level `MCPServer` class (renamed from `FastMCP`) is enough for a small tool surface. Ships an in-memory `Client(server)` for tests. | Yes (Connect), but optional extra, not core |
| `platformdirs` | `>=4.3` (latest 4.13.5, 2026-10-19) | Per-user data/config/state directories | Already installed transitively by Textual. Needed because `database_url = "sqlite:///data/career_os.db"`, `data_dir = Path("data")` and `env_file = ".env"` are all cwd-relative; a `uv tool install`ed binary run from cron has an unpredictable cwd and would silently create or read the wrong database. Declare it directly instead of relying on a transitive. | Yes (Install) |
| `pyyaml` | `>=6.0` (latest 6.0.3) | Already imported by `services/skills_parsing.py` | Currently an undeclared transitive of `uvicorn[standard]`. Declare it (one line) so the install does not depend on an extras side effect. | Hygiene |
| Python | `requires-python >=3.11` unchanged; CI matrix 3.11/3.12/3.13 (+3.14 non-blocking) | Runtime | 3.14 wheels exist on win/mac/linux for pydantic-core, cryptography, rapidfuzz, httptools, watchfiles, pyyaml, curl-cffi (checked on PyPI 2026-10-24). `uv` will pick a managed Python on a bare machine, so test what it picks. | Yes (Install) |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `rapidfuzz` (existing) | raise floor to `>=3.14` (latest 3.14.6, 2026-08-30) | Fuzzy dedup and repost fingerprint | Already a dependency and already used in 4 modules. Use `fuzz.token_sort_ratio` / `rapidfuzz.distance.Indel` inside a same-company bucket, not `token_set_ratio` (see Footguns). |
| `httpx` (existing) | `>=0.28.1` | ATS API clients, liveness probes | Existing adapters already use `httpx.AsyncClient`; tests already use `httpx.MockTransport`. No new HTTP lib. |
| `tomllib` (stdlib, 3.11+) | n/a | `companies.toml` and dossier `facts.toml` (read-only) | Zero dependency. Kestrel only reads user-authored files, so no TOML writer is needed. |
| `smtplib` + `email.message.EmailMessage` (stdlib) | n/a | Optional email digest | User supplies SMTP host/user/app-password. No vendor SDK. |
| `hashlib`, `unicodedata`, `random`, `datetime.astimezone()` (stdlib) | n/a | Fingerprints, text normalization, seeded audit sampling, local-time digest | `random.Random(seed=<date>)` makes the audit sample reproducible so "overturn" decisions can be replayed. Avoid `zoneinfo` (needs the `tzdata` wheel on Windows). |
| `python-jobspy` | keep `>=1.1.82,<1.2` until a replay says otherwise (PyPI now has 1.2.0 to 1.4.1, released 2026-10-02 to 2026-10-23) | Indeed adapter only | Move from the hidden `dev` extra to an explicit optional extra `kestrel-app[indeed]`. Do not bump in v2.0 without a replay (see Footguns). |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `astral-sh/setup-uv` | v10.3.2 (2026-10-22) in CI | Repo policy is SHA-pinned actions; resolve and peel the tag SHA at execution time with `gh api`, do not copy a SHA from research notes. |
| `uv` | 0.13.5 (2026-10-22) | The one supported install path | `uv tool install kestrel-app` creates an isolated env and puts `kestrel` on PATH; downloads a managed Python if none is found. |
| Textual `Pilot` | ships with `textual` | TUI tests | `async with app.run_test(size=(120, 40)) as pilot: await pilot.press("s")`; call `await pilot.pause()` before asserting. Default size is 80x24. |
| `httpx.MockTransport` (existing) | ATS and provider tests | Already the repo pattern (`tests/test_arbeitsagentur_adapter.py`, `tests/test_tier0_ats_poller.py`). |
| GitHub runners | `ubuntu-24.04`, `macos-26` (arm64, = `macos-latest`), `macos-15-intel`, `windows-2025` (= `windows-latest`) | `macos-14` is marked deprecated on the runner-images README (2026-10-24). |

## Per-feature stack decisions

### 1. Textual TUI (feature 1)

**Decision: Textual, not Rich-only, not prompt_toolkit.**

- Rich is a renderer. It has no event loop, no focus model and no key handling; "single-key status changes" and a live shortlist with a cursor would need a hand-rolled `Live` + raw-terminal key reader that breaks on Windows. Rich stays for the non-interactive CLI (tables, `kestrel pipeline list`), which is unchanged.
- `prompt_toolkit` can do full-screen apps but is not in the dependency tree today (Typer uses click/Rich; `kestrel init` uses Rich prompts) and has no ready-made table or markdown widget. Textual brings both and shares Rich internals.
- Integration: `kestrel tui` becomes a Typer command that lazy-imports `career_os.tui`. The TUI calls the same module-level service functions the CLI calls (`services/applications.py`, `services/follow_ups.py`, `services/jobs.py`) with a `SessionLocal()` per action. It never calls the HTTP API, so `kestrel tui` works with no server running.
- Row identity: `DataTable.add_row(..., key=str(job_id))`; handle `RowSelected`/`RowHighlighted` by key. Status transitions go through the existing `VALID_TRANSITIONS` table in `schemas/applications.py` so the TUI cannot invent states.
- Opening postings: stdlib `webbrowser.open` (already used by `kestrel start`).
- Report viewer: Textual `MarkdownViewer`/`Markdown` over the digest and dossier Markdown files.

**Footguns**
- Textual 8.2.8 requires `rich>=14.2.0` and `pygments<3`; the repo floor is `rich>=13.9.0`. Raise the floor to `rich>=14.2` in the same PR or a stranger's resolver result differs from CI's. Rich is now at 15.0.0; Typer 0.27.3 only needs `rich>=13.8`, so there is no conflict.
- SQLAlchemy calls are synchronous. Calling them from message handlers freezes the UI. Run any query that can exceed a few ms under `@work(thread=True)` and push results back with `call_from_thread` or `post_message` (Textual docs: do not touch widgets from a thread). `check_same_thread=False` is already set in `database.py`.
- 8.x breaking changes are small: `Select.BLANK` renamed `Select.NULL` (8.0.0, 2026-02-16); dismissing a non-active screen no longer a no-op. Pin `<9`.
- Kitty key protocol support arrived in 8.2.7; env var `TEXTUAL_DISABLE_KITTY_KEY` disables it if a terminal misbehaves. Plain-letter bindings (`a`, `r`, `o`) are unaffected.
- Windows: use Windows Terminal; legacy conhost is the weakest target. State it in the install docs, do not engineer around it. (MEDIUM, no Textual-specific Windows statement found in the 8.x changelog.)
- Do not add `pytest-textual-snapshot` (1.1.0, last released 2025-01-23, hard-pins `syrupy==4.8.0`). Assert on widget state through `Pilot` instead; SVG snapshot churn is poor value for a solo maintainer. Also skip `textual-dev` as a hard dev dependency (pulls `aiohttp`); install ad hoc with `uvx --from textual-dev textual console` when debugging.

### 2. Headless `kestrel scan` on cron (feature 2)

**Decision: a one-shot Typer command, scheduled by the OS. No scheduler library.**

- `kestrel scan` is a plain process: migrate, acquire a lease, run adapters, persist, exit with a meaningful code (suggested: 0 ok, 1 partial source failure, 2 spend-halted, 75 another scan holds the lease). Cron, launchd and Task Scheduler all just run it. Do not add APScheduler (3.11.3; the 4.x line is a rewrite) or Celery/RQ/Redis; one job per day does not justify a scheduler.
- **macOS: prefer launchd over cron.** The launchd man page says that unlike cron it starts a `StartCalendarInterval` job at the next wake if the Mac slept through it and coalesces missed intervals; cron simply skips them. Caveat from an Apple developer thread: a full power-off at the scheduled time is not caught up. Linux: cron or a systemd user timer with `Persistent=true`. Windows: `schtasks` / Task Scheduler. Ship `kestrel scan --print-schedule {launchd|cron|systemd|schtasks}` that prints a ready-to-install snippet; do not auto-install system schedulers in v2.0.
- **Overlap protection: a lease row in SQLite, not a lock-file library.** `BEGIN IMMEDIATE` on a `scan_lease(holder, heartbeat_at)` row works on all three OSes and survives the data dir being relocated. `fcntl` is POSIX-only and `msvcrt` Windows-only, and `filelock` would be a new dependency for one use.
- **Retire the in-lifespan asyncio scheduler as a default** (`discovery/scheduler.py`, started in the API lifespan). Two schedulers (API-lifespan and cron) double-scan and double-spend. Keep both calling the same service function `run_scan()`; leave the lifespan scheduler off unless explicitly enabled.
- **Persist every arrival.** New table `job_arrivals(id, scan_run_id, source, external_id, canonical_url, fingerprint, disposition, reason, seen_at)` with dispositions `new | dup_batch | dup_history | repost | filtered | liveness_dead`. This is what the digest's audit sample and the "overturn becomes a regression fixture" requirement read from. Alembic already auto-migrates; the CLI path must run `_auto_migrate` too (a cron-first install has no API startup to do it).
- **Data location:** default DB and config to `platformdirs.user_data_dir("kestrel")` / `user_config_dir("kestrel")`, overridable by `DATABASE_URL`/`KESTREL_HOME`. Build the URL with `sqlalchemy.engine.URL.create("sqlite", database=str(path))` instead of string-replacing `sqlite:///`, which is fragile for Windows drive paths. Never put the DB in an iCloud/Dropbox/Syncthing folder: SQLite documents that WAL does not work over network filesystems, and sync tools copy the `-wal` file out of step.
- **SQLite concurrency (cron scan + TUI + MCP all open the DB):** `database.py` sets WAL and foreign keys but no `busy_timeout` (pysqlite's default is 5 s). Add `PRAGMA busy_timeout=30000`; keep scan write transactions short (commit per company or per batch); keep read transactions short so WAL checkpoints can complete (SQLite docs: overlapping readers starve checkpoints). `synchronous=NORMAL` is a durability trade-off in WAL (last transactions can roll back after power loss); acceptable for a re-scrapable job list, not for the dossier, which lives in files (see 6).

### 3. ATS-API sources and liveness (feature 3)

**Decision: three small adapters on the existing `httpx` + `ScraperAdapter` ABC, configured by `companies.toml`. No new libraries.** The repo already contains working, field-verified code in `tools/tier0_ats_poller.py` and `tools/scrape_new_sources.py`; the v2.0 task is to port it into `src/career_os/discovery/` with replay tests, not to re-research the APIs.

| ATS | Endpoint | Auth | Response shape (verified) | Closed-job signal | Documented rate limit |
|-----|----------|------|---------------------------|-------------------|-----------------------|
| Greenhouse | `GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs` (`?content=true` adds HTML description, departments, offices); `GET .../jobs/{id}` (`?questions=true`, `?pay_transparency=true`) | None for GET | `{"jobs":[{id, internal_job_id, title, updated_at, requisition_id, location:{name}, absolute_url, language, metadata}], "meta":{total}}`; `first_published` only on the single-job endpoint | `GET /jobs/{id}` returns 404 when the post is gone (HIGH from repo experience, MEDIUM from docs) | None published |
| Lever | `GET https://api.lever.co/v0/postings/{site}?mode=json` (EU tenants: `https://api.eu.lever.co/v0/postings/{site}`); `skip`/`limit`; filters `location`, `team`, `commitment` (case sensitive, OR-ed) | None | List of `{id, text, categories{location,team,commitment,allLocations}, descriptionPlain, workplaceType, hostedUrl, applyUrl, salaryRange?, createdAt(ms)}` | `GET /v0/postings/{site}/{id}` 404 (MEDIUM) | Only application POSTs (2/s, then 429). GET not documented |
| Ashby | `GET https://api.ashbyhq.com/posting-api/job-board/{name}` (`?includeCompensation=true`) | None | `{apiVersion, jobs:[{id, title, location, secondaryLocations, department, team, employmentType, isRemote, workplaceType, publishedAt, isListed, jobUrl, applyUrl, descriptionPlain, descriptionHtml}]}`; whole board in one response, no pagination | No per-job endpoint documented; re-fetch the board and check id presence and `isListed` | None published |

(Docs omit the Ashby `id` field, but the repo's poller reads it successfully; keep it as the external id and cover it with a recorded fixture.)

**Integration plan**
- New adapters `GreenhouseAdapter`, `LeverAdapter`, `AshbyAdapter` implement `ScraperAdapter.scrape()` and return `RawJobResult` plus a new `external_id` and `ats` field. Add `external_id` (and a `(source, external_id)` unique index) to the job table.
- `companies.toml`: `[[company]] name=, ats="greenhouse|lever|ashby", slug=, region="us|eu"` (Lever needs `region`; Ashby slugs can contain dots, percent-escapes or capitals and must be used verbatim). Read with `tomllib`. The public repo ships `companies.example.toml` with fictional companies only; the real file lives in the user config dir.
- Cheap polling pattern: list endpoint without `content=true`; fetch full detail only for ids not yet in `job_arrivals` (Greenhouse `content=true` returns full HTML for every job on every poll). For Ashby the list already includes descriptions.
- Pacing: one request per company per scan, 1 to 1.5 s between companies (the existing poller uses 1.5 s), jitter, honor `Retry-After` on 429, identify with a real User-Agent. These are conservative defaults, not vendor limits (LOW; Greenhouse blogs say "no hard limits but aggressive polling can get blocked").
- Liveness with ATS re-resolution: map a stored posting URL to `(ats, slug, id)` (hosted URL patterns `boards.greenhouse.io/{token}/jobs/{id}`, `jobs.lever.co/{site}/{id}`, `jobs.ashbyhq.com/{name}/{id}`; custom career sites often carry a `gh_jid` query parameter for Greenhouse, MEDIUM) and probe the ATS API, not the marketing page. A scraped aggregator link that 200s but whose ATS posting 404s is dead. Run liveness before paid scoring and cache the result for the scan.

**Footguns**
- The current uniqueness rule `uq_discovered_job_dedup (profile_id, title_normalized, company_normalized, location_normalized)` will collapse distinct requisitions that share a title and location (five "Software Engineer, Berlin" reqs at one company become one row). With ATS data this is a data-loss bug, not a nicety. Add `external_id` and make `(profile_id, source, external_id)` the strong key; keep the normalized triple as the cross-source soft key, enforced in the dedup service rather than by a unique constraint, in an Alembic migration that backfills.
- 404 from Ashby/Greenhouse for a board means "wrong slug or company left the ATS", not "no jobs". Surface it in `kestrel doctor` as a company-config warning; never silently treat it as zero postings (a canary/floor check: a company that had N jobs yesterday and 0 today is suspicious).
- Lever US host against an EU tenant returns nothing useful; carry `region` in config.
- The documented Lever 2/s limit is for application POSTs; v2.0 does no auto-submit, so none of that applies.

### 4. Cost safety (feature 4)

**Decision: no library. A small `SpendGuard` at the single `AIProvider` choke point plus a status classifier.** Tenacity (9.2.1) is not needed: the repo already has backoff constants in `discovery/adapters.py`, and the interesting logic here is classification, not retry decoration.

**The conflation is real and sits in every provider.** `ProviderQuotaError` is raised for `status in (402, 429)` in anthropic, openai, openrouter, mistral, together, groq, xai and huggingface providers (`ai/base.py:69`, 15+ sites). The "429 = wait" rule cannot be implemented on status alone, because:

| Provider | What the docs say | Implication |
|----------|-------------------|-------------|
| Anthropic | 402 `billing_error`. 429 `rate_limit_error` is used for real rate limits **and** for the tier monthly spend cap: that 429 has **no `retry-after` header**, carries `error.details.error_code == "enforced_spend_limit_reached"`, and keeps failing until access resumes. A user-set org/workspace spend limit returns **400** `invalid_request_error` ("You have reached your specified API usage limits"). | 429 without `retry-after` must not be waited on forever; 400 with that message is a halt. |
| OpenRouter | 402 insufficient credits (no retry; a 402 carries `Retry-After` only when `error.metadata.limit_source == "openrouter_in_flight_budget"`); 429 rate limited, wait `Retry-After`. Errors can also arrive inside a 200 body. | Clean 402/429 split; check body of 200s. |
| OpenAI | Billing/quota errors can arrive as **429** with `insufficient_quota` (also `credit_balance_exhausted`, `organization_spend_limit_exceeded`, `project_spend_limit_exceeded`); retrying them does not help. | Must inspect `error.code`. (MEDIUM; secondary sources for exact code strings, verify against a recorded fixture.) |
| Gemini | 429 `RESOURCE_EXHAUSTED` covers per-minute and per-day quotas; `QuotaFailure.quotaId` names which (e.g. `...PerDay...`); `retryDelay` hints can be wrong for daily quotas. | Daily quota = halt until reset, not wait. (MEDIUM-LOW; forum evidence.) |
| Others (Mistral, Together, Groq, xAI, HF) | Not verified in this research. | Default to the conservative rule below and add recorded fixtures per provider. |

**Classifier contract** (`classify_provider_error(provider, status, headers, body) -> Wait(seconds) | Halt(reason) | Retry | Fatal`):
1. 402, or any body code in the billing set above, or Anthropic `enforced_spend_limit_reached`, or Anthropic/other 400 spend-limit message: **Halt**.
2. 429 with `Retry-After` (seconds or HTTP-date; parse with `email.utils.parsedate_to_datetime`): **Wait**, with a per-scan total-wait cap (say 10 minutes). Past the cap, exit the scan with a "deferred" status and let the next cron run resume, instead of looping inside a cron job.
3. 429 without `Retry-After` and without a recognizable rate-limit body: bounded exponential wait, then **Halt** after N tries (never infinite).
4. 5xx and 529 (`overloaded_error`): backoff retry, then fallback chain.

**Spend halt as a code invariant:** a persistent `spend_halt` row (provider, reason, set_at, resets_at) checked inside `AIProvider.complete/score/batch_score` wrappers, so no code path, including MCP drafting and the nightly batch, can call a paid provider while halted. Cleared only by `kestrel resume` or a passing preflight. The ledger already exists: `models/ai_usage.py` stores `estimated_cost_usd` per call; add a configurable daily/monthly budget that the guard checks before each call using the estimate.

**Preflight (`kestrel doctor`/`kestrel scan --preflight`):** there is no public balance endpoint for Anthropic (balance is console-only; the Admin Usage and Cost API reports spend, not remaining credit, and needs an Admin key). So preflight = key validity via a free list-models call per provider + OpenRouter `GET /api/v1/key` (`limit`, `limit_remaining`, `usage`) + local ledger vs budget. State plainly in the UI that "balance unknown" is a first-class result.

### 5. Daily digest and email (feature 5)

**Decision: terminal (Rich) and Markdown file are the default sinks; email is an optional sink via stdlib `smtplib`.**
- Build the digest as a plain data structure rendered by three sinks: Rich table to terminal, Markdown file in the data dir (also what the TUI report viewer opens), optional HTML+text email through `email.message.EmailMessage` + `smtplib.SMTP_SSL`/`starttls`. Templates are f-strings; no Jinja2.
- The audit sample of excluded jobs reads `job_arrivals WHERE disposition IN ('filtered','dup_history','liveness_dead')`, sampled with `random.Random(seed=today)`, each row carrying its `reason` and an "overturn" id that the TUI/CLI resolves.
- Push: the existing Pushover integration is not in the v2.0 cut list; keep it as the push sink if it is kept at all. The `daily-scan.yml` Mailgun path is part of the old pipeline and goes with the workflow cut.
- Do not add `aiosmtplib` (5.1.3), `resend` (2.50.0), Mailgun/SendGrid SDKs, or an email-template library. One daily email does not need async SMTP or a vendor lock-in.
- Footgun: consumer mailboxes (Gmail and similar) require app passwords or OAuth for SMTP; document "use an app password" and keep email strictly optional so the 15-minute path never depends on it. Never log the SMTP password; read it from env/config with `0600` permissions (the repo already uses `os.open(..., 0o600)` for secrets in `extension_pairing.py`).

### 6. Profile dossier, voice gate, fact gate (feature 6)

**Decision: plain files + stdlib; deterministic gates; no NLP stack.**
- Layout in the user data dir: `facts.toml` (verified facts: employers, titles, dates, metrics, education, each with an optional `evidence` note), `preferences.toml`, `samples/*.md` (writing samples). Kestrel reads these with `tomllib`/plain reads and never rewrites a user-authored file (so no TOML writer dependency, and the files stay human-readable and git-friendly). Machine proposals (suggested facts, extracted preferences) go in a separate `proposals/` directory so verified, preference and sample material stay distinct.
- "Versioned": record `(path, sha256, saved_at)` in a `dossier_revisions` table on each load/change so a draft can cite the exact dossier revision it used. Do not require `git` on the user's machine.
- Fact gate: extract checkable claims from a draft (numbers, years, company names, titles) with regex and `rapidfuzz` matching against `facts.toml`; any claim not matched is flagged, not auto-fixed. Voice gate: banned-phrase list plus simple style statistics (sentence length, punctuation habits) compared with the samples. Both are pure functions, unit-testable, and run for CLI, TUI and MCP drafting alike.
- Existing: `models/voice.py` and `services/voice.py` already exist; extend rather than replace.
- Not spaCy, NLTK, `language-tool-python` or any local LLM here. The April 2026 research proposed spaCy for CV parsing (150 to 200 MB); that is explicitly not carried into v2.0.

### 7. MCP server (feature 7)

**Decision: official `mcp` SDK 2.x `MCPServer`, stdio transport, optional extra, thin adapter over the same service functions as the CLI.**

- FastMCP vs low-level: the standalone `fastmcp` package (4.1.3, 2026-10-20) now depends on `fastmcp-slim` and on the MCP SDK v2 itself and adds middleware, composition and proxying. Kestrel's tool surface is a handful of read tools, a few narrow write tools and some prompts; the SDK's own `MCPServer` (`from mcp.server.mcpserver import MCPServer`) covers `@mcp.tool()`, resources and structured output. The low-level `Server` lost its decorator methods in v2 (`on_*` kwargs now) and is only for protocol-level needs. Use `MCPServer`.
- **`mcp 2.x` is a breaking line.** v1's `FastMCP` class and `mcp.server.fastmcp` import path are gone (`ModuleNotFoundError`); `httpx`+`httpx-sse` are replaced by `httpx2>=2.5`; new floors `pydantic>=2.12`, `sse-starlette>=3`, `opentelemetry-api>=1.28`, `pyjwt[crypto]`, `starlette`, and `pywin32>=311` on Windows; `MCP_*` env vars and `pydantic-settings` use removed. Constructor positionals changed: pass only `name` positionally and everything else by keyword (a v1 positional `instructions` silently lands in `title`). Transport options moved from the constructor to `run()`.
- **The existing optional extra is already broken.** `pyproject.toml` has `mcp = ["mcp>=1.0.0"]` and `tools/kestrel-mcp/server.py` does `from mcp.server.fastmcp import FastMCP`. A fresh `pip install kestrel-app[mcp]` today resolves `mcp 2.3.0` and the server fails on import. Replace with `mcp>=2.3,<3` and move the server into `src/career_os/mcp_server.py` behind `kestrel mcp`. (v1.30.0, 2026-09-07, is maintenance-only if a v1 pin is ever needed: `mcp>=1.28,<2`.)
- Integration: do **not** keep the current design that wraps the REST API (`tools/kestrel-mcp/server.py` calls `KESTREL_URL`). Call the service layer directly with a session per tool call so the MCP server runs without the API server, like the TUI.
- Registration is one line per client: Claude Code `claude mcp add --transport stdio kestrel -- kestrel mcp` (scopes local/project/user; project scope writes `.mcp.json`); Codex `codex mcp add kestrel -- kestrel mcp` or a `[mcp_servers.kestrel]` table in `~/.codex/config.toml`. **Pi has no built-in MCP** (its core is four tools and MCP is an extension concern), so Pi, and any agent without MCP, must reach Kestrel through the CLI. Therefore every MCP tool must have a CLI twin with `--json` output; MCP is an adapter, the CLI is the contract. (MEDIUM: Pi position from secondary sources, not Pi's own docs.)

**Footguns**
- stdout is the protocol channel on stdio. A stray `print`, a module-level Rich `Console()` write, or `logging` to stdout corrupts the stream (the SDK only diverts *flushed* stray stdout). Log to stderr, and do not import `career_os.cli.main` from the MCP entry point.
- Codex's default `startup_timeout_sec` is 10 s and `tool_timeout_sec` is 60 s. Keep the entry point lazy (import SDK, SQLAlchemy and services on demand), do not run Alembic migrations at MCP startup (fail with a clear "run `kestrel doctor`" message instead), and document `startup_timeout_sec = 20`.
- Claude Code warns above 10,000 tokens per MCP tool result and caps at 25,000 by default. Job descriptions and reports are large: paginate and truncate in the tool, return ids plus summaries, add a `get_job(id)` for detail.
- Job descriptions and employer pages are untrusted third-party text flowing into a coding agent that can also call write tools. Mark such fields as untrusted in tool output, give write tools narrow scope (status change, save draft), annotate read-only tools with `readOnlyHint`, and expose **no** tool that submits an application or edits the verified-facts file. The fact and voice gates run inside the draft tools, not in the agent.
- Testing: SDK v2 supports `async with Client(mcp) as client:` against the server object in memory; use it for contract tests instead of spawning a subprocess.

### 8. Install path and CI (feature 8)

**Decision: `uv tool install` is the single supported path. pipx is documented only as "if you already use it", not tested as a first-class path.**
- Why uv over pipx: both isolate the app, but pipx 1.18.4 requires an existing Python >= 3.11, which a fresh Windows machine does not have, while uv downloads a managed CPython when none is found (default `python-preference = "managed"` uses a system Python if present, otherwise downloads). One tool that also installs Python removes the largest 15-minute-path failure.
- Stranger flow: install uv (`curl -LsSf https://astral.sh/uv/install.sh | sh` on macOS/Linux; `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` on Windows; both can pin a version in the URL), then `uv tool install kestrel-app` (add `--python 3.12` if the docs standardize on one), then `kestrel init`, `kestrel scan`, `kestrel tui`. Installer puts uv in `~/.local/bin` (`$HOME\.local\bin` on Windows); `uv tool update-shell` fixes PATH.
- **CI fresh-image matrix** (new workflow, replaces the Docker-centric `release-verify.yml`/`smoke.yml` steps for install verification; the existing `smoke.yml` wheel job only does `python -m venv` on ubuntu):
  - Rows: `ubuntu-24.04`, `macos-26`, `macos-15-intel`, `windows-2025`; Python 3.11, 3.12, 3.13 (3.14 allowed-to-fail).
  - GitHub runners ship preinstalled Pythons, so they are not "fresh" by default. Force the stranger path with `uv --managed-python` (or `UV_PYTHON_PREFERENCE=only-managed`) and install uv from the official installer script in a step, not from the runner's toolcache.
  - Also one container job on a bare `ubuntu:24.04` / `debian:stable-slim` with only `curl` to prove the no-Python case.
  - Each cell: install the **built wheel** on PRs and the **PyPI release** after publish; then run `kestrel --version`, `kestrel doctor`, `kestrel init --demo` (or equivalent non-interactive seed), `kestrel scan --source fixture`, and a Textual `Pilot` smoke (`python -m career_os.tui --selftest` or equivalent), plus `kestrel mcp` handshake via the in-memory/`stdio` client if the extra is installed.
  - **Scheduled canary:** a nightly job that installs `kestrel-app` from PyPI with an unconstrained resolve on the matrix. Reason: there is no lockfile for `uv tool install` (it resolves fresh each time), so every upstream release (in October 2026 alone: mcp 2.3.0 on 10-02, typer 0.27.3 on 10-06, jobspy 1.2.0 to 1.4.1 from 10-02 to 10-23) reaches a stranger before it reaches CI. The canary is the early-warning system; cap fragile deps with `<next-major>` upper bounds where they have bitten before.
- Packaging corrections to fix before any stranger test:
  - `python-jobspy` is imported lazily by `JobSpyAdapter._import_jobspy()` but only declared in the `dev` extra, so a clean install has no Indeed adapter. Make it `kestrel-app[indeed]` and make the ATS adapters the zero-extras default source. `pandas` stays a transitive of that extra only.
  - `aiosqlite>=0.21.0` is declared but imported nowhere in `src/`, `tests/` or CI (grep 2026-10-24); remove it. (The "async via aiosqlite" line in `CLAUDE.md` is inaccurate.)
  - Add `platformdirs`, `pyyaml` as direct deps; raise `rich` floor; replace the `mcp` extra.
  - Keep `uvicorn[standard]` (the parked web app is the start of the later non-terminal path), keep `slowapi` (also used by `api/extension.py` pairing, not only OAuth), keep `cryptography` (AI response cache `ai/cache.py`).
- Footgun: `host: str = "0.0.0.0"` default and the `kestrel start --host 0.0.0.0` default (G-2009) mean a stranger who runs the parked web app exposes it on the LAN. Fix to `127.0.0.1` before the install test goes public.

### 9. Fuzzy dedup and repost fingerprint (feature 2/3)

**Decision: tiered, cheap-first, using existing `rapidfuzz` + stdlib. No FTS5, no MinHash, no vector DB, no dedup framework.**

| Tier | Key | Mechanism | Cost |
|------|-----|-----------|------|
| 0. Within-batch | `(source, external_id)` then canonical URL | Python `dict` | O(n) |
| 1. Against history, exact | `(profile_id, source, external_id)`; then normalized `(company, title, location)` | Indexed lookup (the `*_normalized` columns are already indexed) | O(log n) per job |
| 2. Fuzzy, same company only | `company_normalized` bucket (load that company's last ~90 days), title compare with `fuzz.token_sort_ratio >= ~92`, **and** same location class **and** no seniority/level token mismatch | `rapidfuzz.process.extractOne(..., score_cutoff=)` | O(bucket), tiny |
| 3. Repost fingerprint | `blake2b` over `company_norm + title_core + location_class + sorted salient description tokens`; secondary check `rapidfuzz.distance.Indel.normalized_similarity` on the first ~2,000 normalized description characters inside the company bucket | stdlib + rapidfuzz | O(bucket) |

Normalize with `unicodedata.normalize("NFKC")`, `casefold()`, punctuation strip, legal-suffix strip ("GmbH", "Inc"), and `rapidfuzz.utils.default_process`.

**Footguns**
- `fuzz.token_set_ratio` returns **100.0 whenever one string's token set is a subset of the other** (RapidFuzz docs). "Engineer" vs "Senior Staff Engineer" scores 100 and would merge distinct roles. Use `token_sort_ratio` (no subset special-casing) plus an explicit level-token check, and never use a fuzzy match across companies.
- The thresholds (92, 0.9) are starting points, not truths. Tune them with the replay corpus (the user's real arrival history plus the audit-overturn fixtures), and record every fuzzy merge in `job_arrivals.reason` so a wrong merge is visible and reversible.
- Reposts are a product decision, not just a hash: a repost of a job the user already rejected must resurface only if materially changed; store `first_seen_at`/`last_seen_at` and a `repost_of` pointer rather than deleting.

**FTS5: not needed.** Dedup against history is key lookup plus a per-company fuzzy scan; neither is full-text search. FTS5 is also build-dependent (the SQLite docs: enabled in the amalgamation default build, but other builds must define `SQLITE_ENABLE_FTS5`), so depending on it adds a fresh-image failure mode for no feature gain. If TUI free-text search is wanted, use `LIKE` on `title`/`company` (tens of thousands of rows is trivial). Schema additions are limited to: `external_id`, `ats`, `canonical_url`, `fingerprint` (indexed), `first_seen_at`, `last_seen_at`, `closed_at`, `repost_of`, plus the `job_arrivals`, `scan_lease`, `spend_halt` and `dossier_revisions` tables.

### 10. Cutting sprawl safely (feature 9) - stack consequences

| Remove | Dependency effect | Notes |
|--------|-------------------|-------|
| TickTick / calendar integration | Drop `icalendar>=7.0.0` (imported only by `services/calendar.py`) | Verified by grep 2026-10-24. |
| WARN integration | Drop the `warn` extra (`warn-scraper`) and `cli/warn.py` | Optional extra today, so no runtime effect. |
| OAuth endpoints | Do **not** drop `slowapi` | `api/extension.py` (extension pairing, kept) and `main.py` still use it. Re-check after the OAuth router is deleted. |
| Cloudflare worker, dashboard | None in Python; Node lockfiles and workflows go | Takes Node 22 dependabot surface with it. |
| `aiosqlite` | Remove (never imported) | See 8. |
| BMAD scaffolding | None | `_bmad/`, `.claude/skills/bmad-*`, and the CLAUDE.md sections. |
| Script logic (`tools/tier0_ats_poller.py`, `scrape_new_sources.py`, `daily_pipeline.py`, `normalize.py`, `job_scorer.py`) | `tools/` imports `yaml`, `playwright` | Delete only after the port exists in `src/` and a replay of recorded fixtures through both old and new code produces matching output. Keep `tools/` out of the wheel. |

## Installation

```bash
# End user (the one supported path)
uv tool install kestrel-app                 # core: API, CLI, TUI, ATS sources, digest
uv tool install "kestrel-app[mcp]"          # + MCP server for Claude Code / Codex
uv tool install "kestrel-app[indeed]"       # + Indeed via python-jobspy (optional)

# pyproject.toml dependency changes
#   add:    "textual>=8.2,<9", "platformdirs>=4.3", "pyyaml>=6.0"
#   raise:  "rich>=14.2", "rapidfuzz>=3.14"
#   remove: "aiosqlite", "icalendar"
#   extras: mcp = ["mcp>=2.3,<3"]   (was "mcp>=1.0.0")
#           indeed = ["python-jobspy>=1.1.82,<1.2"]   (was dev-only)
#           drop the "warn" extra

# Developer
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,mcp,indeed]"
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Textual | Rich `Live` + hand-rolled keys | Never for interactive lists; fine for a one-off progress display. |
| Textual | `prompt_toolkit` full-screen | If Textual were dropped for bundle size; it has no table or markdown widget and is not in the tree today. |
| Official `mcp` `MCPServer` | standalone `fastmcp` 4.x | If Kestrel later needs middleware, server composition, or proxying other MCP servers. |
| Official `mcp` v2 | `mcp>=1.28,<2` | Only if a client in the field cannot negotiate the 2026-07-28 protocol revision; v1 is maintenance-only. |
| `uv tool install` | `pipx` | A user who already has pipx and Python >= 3.11; supported by docs, not by the CI matrix. |
| OS scheduler (launchd/cron/systemd/schtasks) | APScheduler / Celery / `schedule` | A long-running daemon use case; the API-lifespan scheduler already covers "server is up". |
| stdlib `smtplib` | Resend/Mailgun/SendGrid SDK | A hosted multi-user deployment sending to many recipients; not this product. |
| rapidfuzz in a company bucket | `datasketch` 2.0.0 MinHash/LSH, `dedupe`, `recordlinkage`, embeddings | Corpus orders of magnitude larger with cross-company near-duplicates; not the case at one user's volume. |
| SQLite lease row | `filelock` | If a non-SQLite lock is needed (e.g. before the DB exists); use only then. |
| `LIKE` search | SQLite FTS5 | Only if full-text ranking over descriptions becomes a feature, and then probe `sqlite_compileoption_used('ENABLE_FTS5')` at runtime. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `fuzz.token_set_ratio` for title dedup | Returns 100.0 for any subset ("Engineer" matches "Senior Staff Engineer") | `token_sort_ratio` + level-token and location guards, same-company bucket only |
| Status-code-only 402/429 handling | Anthropic spend-cap 429 has no `retry-after`; OpenAI billing errors arrive as 429; Gemini 429 may be a daily quota | Classifier over status + headers + body code, with bounded waits |
| `from mcp.server.fastmcp import FastMCP` | Removed in mcp 2.x; the existing `tools/kestrel-mcp/server.py` breaks on a fresh install | `from mcp.server.mcpserver import MCPServer`, pin `mcp>=2.3,<3` |
| MCP server that wraps the REST API | Requires the API server running; a second auth path; double hop | Call the service layer directly, same as CLI/TUI |
| Printing to stdout in any stdio MCP code path | Corrupts the protocol stream | stderr logging only |
| `pytest-textual-snapshot` | Hard-pins `syrupy==4.8.0`; last release 2025-01-23; SVG snapshot churn | `Pilot` assertions on widget state |
| `textual-dev`, `textual-serve`, `textual-web` as dependencies | Pull `aiohttp`; serve the TUI in a browser, which is the parked web app's job | `uvx --from textual-dev textual console` ad hoc |
| APScheduler, Celery, RQ, Redis, Prefect, Airflow | Infrastructure for one daily job | cron/launchd/systemd/schtasks calling `kestrel scan` |
| SQLite FTS5, Whoosh, Meilisearch, a vector DB for dedup | Not needed for key lookup + per-company fuzzy; FTS5 is build-dependent | Indexed columns + rapidfuzz |
| `datasketch`, `dedupe`, `jellyfish`, `thefuzz`, `unidecode`, `ftfy` | Overlap rapidfuzz + stdlib `unicodedata`; extra wheels on a fresh machine | rapidfuzz + stdlib |
| `tenacity`, `backoff` | The repo already has backoff constants; the hard part is classification | `SpendGuard` + classifier in `ai/base.py` |
| `respx`, `pytest-httpx` | `httpx.MockTransport` is already the repo pattern | Existing pattern |
| spaCy, NLTK, `language-tool-python`, local LLMs for the gates | 150 MB+ installs on the 15-minute path for work that is regex + string matching | Deterministic fact/voice gates |
| Resend / Mailgun / SendGrid SDKs, `aiosmtplib`, Jinja2 | One optional daily email | `smtplib` + f-strings |
| Playwright, browser automation in core | Auto-submit is deferred to v2.1; the extension is the hand | Keep out of `dependencies` |
| `questionary`, `InquirerPy` (April 2026 recommendation) | Not needed: `kestrel init` uses Rich prompts; TUI replaces wizard needs | Rich `Prompt` / Textual |
| `pipx` as a second tested path | Two install paths double the support matrix and pipx needs a pre-existing Python | `uv tool install` only |
| PyInstaller / Briefcase / Tauri / Electron bundles | v2.1 non-technical path | Defer |
| `keyring` for provider keys | Platform backends differ (headless Linux cron has none); last release 2025-11 | `.env`/config file at `0600` in the user config dir; revisit in v2.1 |
| Lockfile-less "latest of everything" without a canary | Strangers hit upstream breakage first | Nightly unconstrained-install canary + upper bounds on risky deps |
| Docker as the stranger install path | Not the 15-minute technical path; keep for server mode | `uv tool install` |
| `python-jobspy` 1.2 to 1.4.1 in v2.0 | Released 2026-10-02 to 2026-10-23 with a new `curl_cffi` dependency and no repo replay; the repo's Indeed fix is verified against 1.1.82 | Stay `<1.2` until a replay proves a bump |

## Stack Patterns by Variant

**If the user only wants the terminal loop (default):**
- Core install only: `textual`, `typer`, `rich`, `httpx`, `rapidfuzz`, `sqlalchemy`, `alembic`.
- The API server, `uvicorn` and the web app are not needed at runtime (the wheel still bundles `_frontend_dist` for the parked web path).

**If the user drives Kestrel from Claude Code or Codex:**
- Add the `[mcp]` extra; register with `claude mcp add` / `codex mcp add` pointing at `kestrel mcp`.
- Tools return ids and summaries; large text via paginated `get_*` tools.

**If the user's agent has no MCP (Pi and similar):**
- Use the CLI with `--json`; document the commands in a short `AGENTS.md` snippet. The CLI is the contract, MCP is one adapter.

**If the machine sleeps overnight (laptop):**
- macOS: launchd `StartCalendarInterval` (catches up on wake). Linux: systemd user timer with `Persistent=true`. Avoid plain cron.

**If email is wanted:**
- Configure SMTP with an app password; the digest also always lands as a Markdown file so a failed send loses nothing.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `textual 8.2.8` | `rich >=14.2.0`, `pygments >=2.19.2,<3`, `platformdirs >=3.6,<5` | Raise the repo's `rich>=13.9` floor; `typer 0.27.3` needs only `rich>=13.8`. |
| `mcp 2.3.0` | `pydantic >=2.12`, `httpx2 >=2.10` (not `httpx`), `pywin32 >=311` on win32, `opentelemetry-api >=1.28` | `httpx` and `httpx2` coexist as distinct distributions; the repo keeps `httpx` for its own clients. `pip-audit`/Dependabot will see both. |
| `pandas 3.1.0` | `numpy >=2.0.2` (<3.14) / `>=2.3.3` (>=3.14); `numpy 2.5.4` itself needs Python >=3.12 | Relevant only to the `[indeed]` extra; Python 3.11 resolves an older numpy. |
| `python-jobspy 1.4.1` | `pandas >=2.1.2` (no `<3` cap), `curl_cffi >=0.16.2` | The repo's `<1.2` pin predates this; do not lift without replay. |
| `uvloop 0.23.0` | macOS/Linux wheels only | No Windows wheel, by design; `uvicorn[standard]` marks it non-win32. |
| `sqlalchemy 2.1.6` | `sqlalchemy>=2.0` floor resolves to 2.1.x on fresh installs | CI already resolves latest; confirm in the install matrix. |
| `setup-uv v10.3.2` | `uv 0.13.5` | `python-version` input sets `UV_PYTHON`. |

## Sources

- PyPI JSON API, queried 2026-10-24: textual 8.2.8 (2026-06-30), mcp 2.3.0 (2026-10-02, release list incl. 2.0.0 on 2026-07-28 and 1.30.0 on 2026-09-07), fastmcp 4.1.3 (2026-10-20), httpx2 2.16.0, rapidfuzz 3.14.6, uv 0.13.5, pipx 1.18.4, typer 0.27.3, rich 15.0.0, platformdirs 4.13.5, python-jobspy 1.4.1 (and 1.2.0/1.3.0/1.4.0), pandas 3.1.0, numpy 2.5.4, uvicorn 0.54.0, kestrel-app 0.28.2, plus wheel-availability checks for cp314 on key dependencies - HIGH.
- GitHub releases API (`gh api`), 2026-10-24: astral-sh/setup-uv v10.3.2, astral-sh/uv 0.13.5, Textualize/textual v8.2.8, modelcontextprotocol/python-sdk v2.3.0 - HIGH.
- Textual changelog (raw.githubusercontent.com/Textualize/textual/main/CHANGELOG.md), workers guide (textual.textualize.io/guide/workers/), testing guide (/guide/testing/), DataTable (/widgets/data_table/) - MEDIUM (official docs, fetched via summarizer).
- MCP Python SDK: migration guide https://py.sdk.modelcontextprotocol.io/migration/index.md ; docs https://py.sdk.modelcontextprotocol.io/ ; FastMCP 4 relationship https://gofastmcp.com/getting-started/upgrading/from-low-level-sdk-v2 - MEDIUM.
- Claude Code MCP docs https://code.claude.com/docs/en/mcp (scopes, token limits) ; Codex MCP docs https://learn.chatgpt.com/docs/extend/mcp?surface=cli (config.toml, 10 s startup / 60 s tool timeouts) - MEDIUM.
- Pi MCP stance: implicator.ai and agentic-ai.readthedocs.io write-ups (secondary; one source contradicts) - LOW-MEDIUM.
- Greenhouse Job Board API https://docs.greenhouse.io/job-board.html ; Lever Postings API https://github.com/lever/postings-api ; Ashby https://developers.ashbyhq.com/docs/public-job-posting-api ; rate-limit absence corroborated by 100hires/getknit/apis.io write-ups - MEDIUM for shapes, LOW for rate limits.
- Repo evidence (HIGH, read 2026-10-24): `tools/tier0_ats_poller.py`, `tools/scrape_new_sources.py`, `src/career_os/discovery/adapters.py`, `src/career_os/models/discovery.py`, `src/career_os/database.py`, `src/career_os/config.py`, `src/career_os/ai/base.py` and providers, `tools/kestrel-mcp/server.py`, `pyproject.toml`, `.github/workflows/smoke.yml`.
- Anthropic errors https://platform.claude.com/docs/en/api/errors and rate limits https://platform.claude.com/docs/en/api/rate-limits (spend-cap 429 without `retry-after`, `enforced_spend_limit_reached`, user limit as 400) - MEDIUM-HIGH (vendor docs).
- OpenRouter errors https://openrouter.ai/docs/api-reference/errors and key endpoint https://openrouter.ai/docs/api-reference/limits - MEDIUM-HIGH.
- OpenAI 429 `insufficient_quota` via help.openai.com article translations and cookbook (secondary) - MEDIUM. Gemini 429 behavior via discuss.ai.google.dev threads - LOW-MEDIUM.
- Anthropic balance API absence via GitHub issue anthropics/claude-code#47574 and the Usage and Cost API docs - MEDIUM.
- uv docs: https://docs.astral.sh/uv/guides/tools/ , /concepts/python-versions/ , /getting-started/installation/ ; runner labels https://github.com/actions/runner-images - MEDIUM-HIGH.
- launchd vs cron: Apple scheduling guide and launchd man-page quotes via search results; shutdown-not-caught caveat from Apple Developer Forums thread 52369 - MEDIUM.
- SQLite WAL https://sqlite.org/wal.html (one writer, no network filesystems, checkpoint starvation, synchronous=NORMAL trade-off) ; FTS5 https://sqlite.org/fts5.html (build-dependent) - HIGH.
- RapidFuzz `token_set_ratio` subset behavior https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html - MEDIUM-HIGH.

---
*Stack research for: Kestrel v2.0 Lean Kestrel (new capabilities only; existing FastAPI/SQLAlchemy/Typer/provider stack not re-researched)*
*Researched: 2026-10-24*
