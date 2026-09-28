---
phase: quick
plan: 260928-pbu
type: execute
wave: 1
depends_on: []
files_modified:
  - src/career_os/discovery/adapters.py
  - src/career_os/config.py
  - .env.example
  - tests/test_jobspy_adapter.py
  - tools/scraper.py
  - tools/specific_hunt.py
  - tools/README.md
  - tests/test_scraper.py
  - tests/test_specific_hunt.py
  - tools/source_registry.py
  - tools/scrape_resilient.py
  - tests/test_source_registry.py
  - tests/test_scrape_resilient.py
autonomous: true
requirements: [G-1802]

estimate:
  tokens: 75000
  raw_tokens: 75000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "The in-app JobSpy sweep requests Indeed only: every scrape_jobs call made by JobSpyAdapter receives a one-element site_name list, the Glassdoor and Google board names never appear in JobSpyAdapter.SITES, and the lowercase Glassdoor board string does not occur anywhere in src/career_os/discovery/adapters.py (AC1)"
    - "Each board is its own scrape_jobs call; when one board raises, the rows from every other board are still returned (AC2, proven by a test that raises for indeed and keeps linkedin's rows)"
    - "Every executor call is wrapped in asyncio.wait_for with settings.jobspy_timeout_seconds (env JOBSPY_TIMEOUT_SECONDS, default 60, must be > 0); a scraper that blocks past the timeout makes _scrape_all_adapters return in under 2 s with a jobspy warning containing 'timed out' (AC3)"
    - "The per-site search arguments are unchanged: search_term, location, results_wanted=limit_per_source, hours_old=168, country_indeed='Germany' (Indeed path and limit_per_source semantics preserved)"
    - "With python-jobspy not importable, JobSpyAdapter still raises the existing 'python-jobspy is not installed' RuntimeError, which the sweep records as a warning instead of crashing"
    - "tools/scraper.py rejects google (any case) with a message naming the site and the upstream reason, both from scrape_all (ValueError, no scrape_jobs call) and from the CLI (exit code 2); DEFAULT_SITES is exactly linkedin + indeed (AC4)"
    - "tools/specific_hunt.py has a module docstring stating LinkedIn descriptions come back blank (upstream issue #374) and what opting in costs; tools/README.md states Kestrel never scrapes LinkedIn from an authenticated session (AC6)"
    - "tools/scrape_resilient.scrape_with_browser refuses every Indeed host before Playwright is imported, returning an error entry whose reason is the one recorded in tools/source_registry.BROWSER_DISABLED_HOSTS (AC7)"
    - "CHANGELOG.md and README.md are untouched (release-please writes the changelog line from the fix(G-1802) squash title; see objective, AC5)"
    - "Full suite green (pytest tests/ -m 'not eval'); ruff check and ruff format --check clean on src/ tests/; no new ruff findings in the four tools files"
  artifacts:
    - path: src/career_os/discovery/adapters.py
      provides: "JobSpyAdapter with per-site calls, asyncio.wait_for timeout, Indeed-only SITES"
      contains: "asyncio.wait_for"
    - path: src/career_os/config.py
      provides: "jobspy_timeout_seconds setting (JOBSPY_TIMEOUT_SECONDS, default 60, gt=0)"
      contains: "jobspy_timeout_seconds"
    - path: tests/test_jobspy_adapter.py
      provides: "offline JobSpyAdapter tests (isolation, timeout, jobspy-absent, kwargs, settings)"
      contains: "_scrape_all_adapters"
    - path: tools/scraper.py
      provides: "UNSUPPORTED_SITES + validate_sites rejecting google"
      contains: "UNSUPPORTED_SITES"
    - path: tools/source_registry.py
      provides: "BROWSER_DISABLED_HOSTS reason record + browser_disabled_reason(url)"
      contains: "BROWSER_DISABLED_HOSTS"
    - path: tests/test_source_registry.py
      provides: "host-matching tests for browser_disabled_reason"
      contains: "browser_disabled_reason"
    - path: tools/README.md
      provides: "LinkedIn no-authenticated-session doc line"
      contains: "never scrapes LinkedIn from an authenticated session"
  key_links:
    - from: src/career_os/discovery/adapters.py
      to: src/career_os/config.py
      via: "JobSpyAdapter.scrape reads settings.jobspy_timeout_seconds at call time (lazy import, so monkeypatch works)"
      pattern: "jobspy_timeout_seconds"
    - from: src/career_os/discovery/adapters.py
      to: src/career_os/services/discovery.py
      via: "an all-sites-failed RuntimeError from JobSpyAdapter.scrape lands in _scrape_all_adapters warnings (run.warnings)"
      pattern: "_scrape_all_adapters"
    - from: tools/scrape_resilient.py
      to: tools/source_registry.py
      via: "scrape_with_browser calls source_registry.browser_disabled_reason before importing Playwright"
      pattern: "browser_disabled_reason"
    - from: tools/scrape_resilient.py
      to: tools/scraper.py
      via: "scrape_jobspy calls scraper.validate_sites before _retry_with_backoff so a rejected site is not retried"
      pattern: "validate_sites"
---

<objective>
G-1802: harden the python-jobspy integration. It is production breakage, verified live on 2026-09-28. python-jobspy 1.1.82 answers Glassdoor with HTTP 400 and 0 rows (upstream PRs #384 and #347) and Google Jobs with 0 rows (a JavaScript bootstrap shell, upstream issue #302). `JobSpyAdapter._scrape_keyword` asks for Indeed plus Glassdoor in ONE `scrape_jobs` call, so half of every in-app sweep has been a silent zero. One board raising inside that single call drops every board's rows (upstream PR #388, unmerged). The `run_in_executor` call has no timeout, so the Indeed page-2 hang from CI IPs (upstream issue #385; jobspy's own `timeout=10` never fires) can stall the scheduler sweep.

Purpose: the in-app sweep talks only to the board that works (Indeed), one board failing never costs another board's rows, and a hung scrape can never stall the sweep. The standalone tools stop offering dead paths (Google in `tools/scraper.py`, the Indeed Playwright fallback in `tools/scrape_resilient.py`) and say plainly what they do with LinkedIn.

Output: a hardened `JobSpyAdapter` plus a `JOBSPY_TIMEOUT_SECONDS` setting, a google rejection in `tools/scraper.py`, a docstring for `tools/specific_hunt.py`, the Indeed refusal in `tools/scrape_resilient.py` with its reason recorded in `tools/source_registry.py`, and offline tests for each.

AC5 (CHANGELOG): planner finding, no CHANGELOG edit. `CHANGELOG.md` is generated by release-please (`release-please-config.json`, `changelog-path: CHANGELOG.md`). It has no Unreleased section. In the file's history the only two non-release commits (9ed771a G-1475, 13771fd G-392) trimmed or rewrote generated blocks; there is no precedent for adding a line by hand before a release. The changelog line comes from the squash-merge title instead. `fix` maps to "Bug Fixes", so the PR title must be a user-readable `fix(G-1802): ...` sentence, and the orchestrator owns that. README.md is also untouched: the ticket sends the README discovery claim to the sibling docs truth-pass ticket.

Claude's discretion (documented choices):
- `JobSpyAdapter.SITES = ("indeed",)` is a class attribute rather than a constructor parameter. `ADAPTER_REGISTRY` builds adapters with `cls()`, and tests override it with `monkeypatch.setattr(JobSpyAdapter, "SITES", ...)`. The ticket recommends Indeed-only whatever the fork/vendor decision turns out to be.
- Failure recording: each (keyword, site) failure is logged at WARNING with the site and the reason. If EVERY call in a scrape fails, `scrape()` raises one RuntimeError listing each failure, and the existing `_scrape_all_adapters` puts it into the sweep's warnings (and `run.warnings`). When some calls fail and others return rows, the rows are returned and the failures stay in the log only. Getting partial failures into `run.warnings` would require editing `services/discovery.py`, and the ticket's stop condition forbids reworking the scheduler beyond the timeout wrap. With the production default (Indeed only), a timeout on a single-keyword sweep always reaches `run.warnings`.
- The timeout applies to each executor call, as AC3 words it. A timed-out worker thread cannot be killed in Python, so it runs until jobspy returns or the process exits. The sweep stops waiting for it, and a code comment must say so.
- `tools/scraper.py` DEFAULT_SITES also drops Glassdoor (not just Google), because it is the same verified silent zero. Glassdoor is still accepted when requested explicitly; only `google` is rejected, which is all AC4 asks for.
- `tools/specific_hunt.py`: document the blank descriptions (AC6 option B) instead of turning on `linkedin_fetch_description`. Opting in adds one guest request per LinkedIn posting and makes LinkedIn's guest rate limit more likely. The docstring says how to opt in and what it costs, and a test pins the doc to the real call.
- `scrape_resilient.py` had no literal indeed.com fallback URL. Its Playwright path takes arbitrary `--browser-urls`. "Hard-disabled" therefore means refusing any URL whose host has an `indeed` label, before Playwright is imported, with the reason text held in `source_registry.BROWSER_DISABLED_HOSTS`.
- `scrape_resilient.scrape_jobspy` validates sites before `_retry_with_backoff`. Without this, a rejected `google` would be retried 3 times with about 7 s of sleeps.
- Pre-existing gap flagged, not fixed: `tools/source_registry.py` had no test file at all. Only the new helper gets tests here.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
@docs/reference/TESTING.md
@src/career_os/discovery/adapters.py
@src/career_os/services/discovery.py
@tools/scraper.py
@tools/scrape_resilient.py
@tools/source_registry.py

Git: you are in an isolated worktree on branch `G-1802/jobspy-hardening` (off main). Do NOT switch branches, do NOT merge main, do NOT push (the orchestrator runs the review gate and pushes). Commit after each task, staging files BY NAME (never `git add -A`). Commit titles are `fix(G-1802): ...` or `test(G-1802): ...`, each with a body explaining what changed and why, and each ends with the attribution lines from the session's system reminder. All commands below run from the checkout root.

Sibling coordination: G-1717 is editing the `ArbeitsagenturAdapter` section of `src/career_os/discovery/adapters.py` concurrently and rewrites its `from urllib.parse import ...` import line. This plan must NOT touch the adapters.py module docstring, the import block (lines 10-20), or anything outside `class JobSpyAdapter` and `_parse_jobspy_row`'s neighbourhood. The design below needs no new import in adapters.py (`asyncio` is already imported, and `settings` is imported lazily inside the method, the same way `services/discovery.py` does it at line 128).

Test rules enforced by hooks (docs/reference/TESTING.md): every test function has a docstring and at least 2 `assert` statements; no `assert True`/`assert False`; no bare `assert x is not None`; mock only external boundaries. Adapter tests must NOT import real jobspy and must NOT touch the network. Inject a fake `scrape_jobs` by setting the INSTANCE attribute (`monkeypatch.setattr(adapter, "_import_jobspy", lambda: fake)`); `self._import_jobspy()` finds the instance attribute before the staticmethod. The fake returns a tiny frame stand-in: an object with an `empty` property and an `iterrows()` that yields `(index, dict)` pairs. `_parse_jobspy_row` only uses `in` and `.get`, so plain dicts work and pandas is not needed. `tests/conftest.py` puts `tools/` on sys.path (tests import `scraper`, `scrape_resilient`, `source_registry` as top-level modules). pytest uses `asyncio_mode = "auto"` and a 30 s per-test timeout; CI runs `pytest tests/ -m "not eval"` and lints only `src/ tests/`.

Baseline (planner-measured 2026-09-28 on main): `pytest tests/ -k 'discovery or jobspy'` 137 passed, 2 skipped; `pytest tests/test_scraper.py tests/test_scrape_resilient.py tests/test_registry_integration.py` 60 passed; `ruff check src/ tests/` clean and `ruff format --check src/ tests/` clean (377 files). The four tools files carry exactly 14 PRE-EXISTING ruff findings: scraper.py F821 x1 (the string annotation `"pd.DataFrame"`), and scrape_resilient.py B023 x1, E501 x5, F401 x7. specific_hunt.py and source_registry.py have none. `tools/scrape_resilient.py` and `tools/source_registry.py` are NOT ruff-formatted today. Do NOT run `ruff format` on either one; that would rewrite unrelated lines. Write new lines in the surrounding style, under 100 chars. `tools/scraper.py` and `tools/specific_hunt.py` ARE formatted and must stay that way.
</context>

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: End-to-end JobSpy sweep hardening (setting -> JobSpyAdapter per-site wait_for -> _scrape_all_adapters warning)</name>
  <files>src/career_os/discovery/adapters.py, src/career_os/config.py, .env.example, tests/test_jobspy_adapter.py</files>
  <read_first>src/career_os/discovery/adapters.py lines 364-449 (`_parse_jobspy_row` and the whole `JobSpyAdapter` class), src/career_os/services/discovery.py lines 198-214 (`_scrape_all_adapters`: adapter exception becomes a {"source", "error": str(exc)} warning), src/career_os/config.py lines 17-70 (Settings field and comment style; `Field` is already imported), .env.example lines 60-63 (Pipeline section)</read_first>
  <behavior>
    - Default config: scrape(ScrapeParams(keywords=["pm", "tpm"], locations=["Berlin"], limit_per_source=25)) makes exactly 2 scrape_jobs calls, and each call's kwargs equal exactly {site_name: ["indeed"], search_term: <kw>, location: "Berlin", results_wanted: 25, hours_old: 168, country_indeed: "Germany"}. JobSpyAdapter.SITES == ("indeed",), and neither the Glassdoor nor the Google board name is in it.
    - Isolation (AC2): with SITES monkeypatched to ("indeed", "linkedin") and a fake that raises RuntimeError("indeed exploded") for site_name ["indeed"] and returns one linkedin row, scrape returns exactly that one row (source "jobspy", literal title and url asserted), the fake saw site_name lists [["indeed"], ["linkedin"]] in that order, and caplog holds a WARNING naming indeed and "indeed exploded".
    - All calls fail: with two sites that both raise, scrape raises RuntimeError whose message contains both site names and both error texts.
    - Timeout (AC3): with settings.jobspy_timeout_seconds monkeypatched to 0.05 and a fake that blocks on a threading.Event (wait(5)), awaiting services.discovery._scrape_all_adapters([adapter], ScrapeParams(keywords=["pm"])) returns in under 2.0 s (time.monotonic) with jobs == [], sources_queried == [], and exactly one warning whose source is "jobspy" and whose error contains "timed out" and "indeed". The Event is set in a finally block so the worker thread exits and pytest-asyncio loop teardown does not wait on it.
    - Partial timeout: with SITES ("indeed", "linkedin"), indeed blocking and linkedin returning one row, scrape returns that row within 2 s and caplog has a WARNING containing "timed out" and "indeed".
    - jobspy absent: with monkeypatch.setitem(sys.modules, "jobspy", None) and no _import_jobspy override, _scrape_all_adapters([JobSpyAdapter()], ...) returns jobs == [] and one warning {"source": "jobspy", "error": <contains "python-jobspy is not installed">}.
    - Setting: Settings.model_fields["jobspy_timeout_seconds"].default == 60; Settings(_env_file=None, ai_provider="mock", auth_enabled=False) picks up JOBSPY_TIMEOUT_SECONDS=7 from the environment as 7.0; a value of 0 raises pydantic ValidationError.
  </behavior>
  <action>
RED first: create tests/test_jobspy_adapter.py. Give it a module docstring stating purpose, "offline: fake scrape_jobs injected via _import_jobspy, never imports jobspy or touches the network", and the ticket G-1802. Add one test class per behavior group (TestJobSpySiteRequests, TestJobSpySiteIsolation, TestJobSpyTimeout, TestJobSpyMissingDependency, TestJobSpyTimeoutSetting), covering every bullet in the behavior block. Import `settings` and `Settings` from career_os.config, `JobSpyAdapter` and `ScrapeParams` from career_os.discovery.adapters, and `_scrape_all_adapters` from career_os.services.discovery. Expected values are hard-coded literals. Run the file, confirm it FAILS against the current code, and record the failure summary line for the SUMMARY.

GREEN, in src/career_os/config.py: add `jobspy_timeout_seconds: float = Field(default=60.0, gt=0)` immediately above the `# Cache settings` comment. Put a short comment block over it saying: per-call wall-clock limit for each python-jobspy scrape_jobs call made by the discovery sweep (G-1802); upstream issue #385 (the Indeed page-2 request from CI IPs hangs and jobspy's own timeout never fires); env JOBSPY_TIMEOUT_SECONDS; must be > 0. In .env.example, add a section right after the Pipeline section: a header line in the file's existing `# -- Name ----` style titled Discovery (G-1802), one explanatory comment line, then `JOBSPY_TIMEOUT_SECONDS=60`.

GREEN, in src/career_os/discovery/adapters.py, inside `class JobSpyAdapter` only:
- Replace the class docstring with one saying it wraps python-jobspy and requests only the boards in SITES (Indeed), one scrape_jobs call per board.
- Add a class attribute `SITES: tuple[str, ...] = ("indeed",)`. Put a comment above it with the reasons, citing upstream refs: Glassdoor returns HTTP 400 / 0 rows on jobspy 1.1.82 (PRs #384, #347); Google Jobs returns 0 rows (issue #302); a single multi-board scrape_jobs call loses every board's rows when one board raises (PR #388). The goal is that `grep -n` for the lowercase Glassdoor board string matches nothing, so capitalise Glassdoor in all prose and never write the board name as a quoted lowercase string. Do not vendor any Glassdoor patch (ticket stop condition).
- `scrape()`: keep the `_import_jobspy()` call first (so a missing jobspy still raises the existing RuntimeError), and keep the keywords default ([""]) and the location default ("Germany"). Lazily import settings inside the method (`from career_os.config import settings`) and read `settings.jobspy_timeout_seconds` once per scrape. Loop over keywords and call `_scrape_keyword` for each, collecting rows and failure strings and counting attempts. If at least one attempt was made and every attempt failed, raise RuntimeError whose message begins "JobSpy: all N site call(s) failed: " followed by the failure strings joined with "; ". Otherwise return the collected rows. If some attempts failed, log one WARNING summarising how many. Drop the `asyncio.get_event_loop()` call.
- `_scrape_keyword(self, scrape_jobs, keyword, location, limit, timeout)`: loop over `self.SITES` and await `_scrape_site` for each. Catch builtin `TimeoutError` first (on Python 3.11+ it is what asyncio.wait_for raises; ruff UP041 rejects the asyncio alias): record the failure string "<site> ('<keyword>'): timed out after <timeout formatted with :g>s" and log it at WARNING. Then catch `Exception`: record "<site> ('<keyword>'): <ExceptionClassName>: <exc>" and log it at WARNING in the existing style ("JobSpy scrape error for site '%s', keyword '%s': %s"). Return (rows, failures, attempts). Do NOT re-raise, because re-raising is exactly what wiped the other boards' rows.
- New `async def _scrape_site(self, scrape_jobs, site, keyword, location, limit, timeout) -> list[RawJobResult]`: get the loop with asyncio.get_running_loop() and await asyncio.wait_for(loop.run_in_executor(None, <zero-arg lambda calling scrape_jobs with site_name=[site], search_term=keyword, location=location, results_wanted=limit, hours_old=168, country_indeed="Germany">), timeout=timeout). The lambda closes over function parameters, not a loop variable, so B023 does not apply and no functools import is needed. Keep the None/empty-frame guard and the `_parse_jobspy_row(row, self.source_name)` list comprehension. Add a comment saying a timed-out executor thread cannot be cancelled: it keeps running until jobspy returns, and the sweep simply stops waiting for it.
Leave `_import_jobspy`, `_parse_jobspy_row`, the registry, and every other adapter untouched.

Run the new test file (GREEN), then tests/test_discovery.py (must stay green), then ruff check and ruff format --check on src/ tests/. Commit: fix(G-1802): Indeed-only JobSpy sweep with per-site calls and a hard timeout. The body covers the three upstream failures, per-site isolation, JOBSPY_TIMEOUT_SECONDS, and the fact that partial failures are logged while all-failed goes to run.warnings.
  </action>
  <verify>
    <automated>PYTHONPATH=src /Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/python -m pytest tests/test_jobspy_adapter.py tests/test_discovery.py -q</automated>
    <automated>! grep -n 'glassdoor' src/career_os/discovery/adapters.py && grep -n 'asyncio.wait_for' src/career_os/discovery/adapters.py && grep -n 'jobspy_timeout_seconds' src/career_os/config.py && grep -n '^JOBSPY_TIMEOUT_SECONDS=60$' .env.example</automated>
    <automated>/Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/ruff check src/ tests/ && /Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/ruff format --check src/ tests/</automated>
  </verify>
  <done>New adapter tests pass after failing first (RED line recorded); test_discovery.py still green; adapters.py has no lowercase Glassdoor string and has asyncio.wait_for; the setting exists with default 60 and gt=0 and is documented in .env.example; ruff is clean on src/ tests/; the adapters.py diff is confined to class JobSpyAdapter (no import-block change); one fix(G-1802) commit with a body.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: tools/scraper.py rejects google; specific_hunt.py LinkedIn description doc; LinkedIn no-auth line in tools/README.md</name>
  <files>tools/scraper.py, tools/specific_hunt.py, tools/README.md, tests/test_scraper.py, tests/test_specific_hunt.py</files>
  <read_first>tools/scraper.py (whole file, 104 lines), tests/test_scraper.py (whole file; `test_default_sites` at line 27 pins the old list), tools/specific_hunt.py (whole file, 84 lines, no module docstring today), tools/README.md lines 1-25</read_first>
  <behavior>
    - DEFAULT_SITES == ["linkedin", "indeed"] and "google" not in DEFAULT_SITES (replaces the old test_default_sites expectation)
    - validate_sites(["linkedin", "indeed"]) returns without raising, and so does an explicitly requested Glassdoor board
    - scrape_all(keywords=["kw"], sites=["indeed", "google"]) raises ValueError whose message contains "google" and "#302", and the patched scraper.scrape_jobs is never called
    - scrape_all(sites=["Google"]) is rejected the same way (case-insensitive)
    - main() with sys.argv ["scraper.py", "--sites", "indeed", "google"] exits with SystemExit code 2, stderr contains "google" and "#302", and scrape_jobs is never called
    - tests/test_specific_hunt.py (AST only, no import of specific_hunt, so jobspy is never imported): the module docstring mentions linkedin_fetch_description, "blank" and "#374"; the file has exactly one scrape_jobs call, its site_name list contains "linkedin", and it passes no linkedin_fetch_description keyword (so the doc matches the code; flipping the flag without updating the doc fails this test)
  </behavior>
  <action>
RED first: in tests/test_scraper.py, update TestDefaults.test_default_sites to the new two-board list and add the "google" not-in assertion. Add a TestSiteValidation class with the scrape_all and main() cases from the behavior block: patch scraper.scrape_jobs as the file already does, use monkeypatch for sys.argv, and use capsys for stderr. Create tests/test_specific_hunt.py: module docstring; read tools/specific_hunt.py through Path(__file__).resolve().parent.parent / "tools" / "specific_hunt.py"; parse it with ast; take the docstring with ast.get_docstring; find Call nodes whose func is the Name scrape_jobs. Run both files and confirm they FAIL, recording the summary line.

GREEN, tools/scraper.py (per AC4):
- Module docstring: say it searches LinkedIn and Indeed by default, that google is rejected (python-jobspy returns 0 rows for Google Jobs), and that Glassdoor is off by default because jobspy 1.1.82 answers it with HTTP 400.
- Set DEFAULT_SITES to linkedin, indeed. Add a comment giving the Glassdoor reason (upstream PRs #384, #347) and saying it can still be requested explicitly.
- Add module-level `UNSUPPORTED_SITES: dict[str, str]` holding a single key "google". Its value names the reason: python-jobspy 1.1.x returns 0 rows for Google Jobs because the page is a JavaScript bootstrap shell (upstream issue #302).
- Add `validate_sites(sites: list[str]) -> None` with a docstring. It checks each entry case-insensitively (strip + lower) against UNSUPPORTED_SITES. If any match, raise ValueError with one clear message naming each rejected site with its reason and listing the supported defaults.
- scrape_all calls validate_sites(sites) right after `sites = sites or DEFAULT_SITES`, before the keyword loop. It must sit OUTSIDE the per-keyword try/except, because that block swallows exceptions into a print.
- main() calls validate_sites(args.sites) right after parse_args; on ValueError it calls parser.error(str(exc)), which prints to stderr and exits 2.
Leave the per-keyword call shape, the dedup, and the F821 annotation as they are.

GREEN, tools/specific_hunt.py (per AC6, documentation option): add a module docstring as the first statement, lines under 100 chars. It must say: what the script does (targeted jobspy searches over LinkedIn and Indeed, JSON to stdout); that python-jobspy returns LinkedIn rows with a blank description by default (upstream issue #374) because this script does not pass linkedin_fetch_description; that passing linkedin_fetch_description=True fills them in but costs one extra guest request per LinkedIn posting and makes LinkedIn's guest rate limit (HTTP 429) more likely; and that the script only reads LinkedIn's public guest listings and never uses a logged-in session or cookies. No code change.

tools/README.md: rewrite the scraper.py description line to match the new behavior (LinkedIn + Indeed by default, google rejected, Glassdoor off by default). Directly under it add exactly this sentence: "Kestrel never scrapes LinkedIn from an authenticated session: python-jobspy and every tool here read LinkedIn's public guest listings only, with no login or cookies." No other README edits, and do not touch the repo-root README.md.

Run the two test files (GREEN), then the ruff gates in verify. Commit: fix(G-1802): reject google in tools/scraper.py and document LinkedIn behaviour, with a body.
  </action>
  <verify>
    <automated>PYTHONPATH=src /Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/python -m pytest tests/test_scraper.py tests/test_specific_hunt.py -q</automated>
    <automated>grep -n 'never scrapes LinkedIn from an authenticated session' tools/README.md && grep -n 'UNSUPPORTED_SITES' tools/scraper.py && grep -n 'linkedin_fetch_description' tools/specific_hunt.py</automated>
    <automated>/Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/ruff check tools/specific_hunt.py tests/test_scraper.py tests/test_specific_hunt.py && /Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/ruff format --check tools/scraper.py tools/specific_hunt.py tests/test_scraper.py tests/test_specific_hunt.py && /Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/ruff check tools/scraper.py --output-format json | /Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/python -c "import json,sys,collections; c=collections.Counter(f['code'] for f in json.load(sys.stdin)); print(dict(c)); assert c == collections.Counter({'F821': 1})"</automated>
  </verify>
  <done>google is rejected from both scrape_all and the CLI with a message naming the reason, and scrape_jobs is never reached; DEFAULT_SITES is linkedin + indeed; the specific_hunt.py docstring documents blank LinkedIn descriptions and a test ties the doc to the actual call; tools/README.md has the no-authenticated-session line; tools/scraper.py still has only its pre-existing F821; one fix(G-1802) commit with a body.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Hard-disable the Indeed Playwright fallback with the reason recorded in source_registry; validate jobspy sites before retry</name>
  <files>tools/source_registry.py, tools/scrape_resilient.py, tests/test_source_registry.py, tests/test_scrape_resilient.py</files>
  <read_first>tools/source_registry.py lines 1-130 (module doc, FLOOR_SOURCES, JOBSPY_BOARDS, status vocabulary), tools/scrape_resilient.py lines 1-16 (module docstring), 95-111 (`_retry_with_backoff` retries every exception with sleeps), 173-235 (`scrape_jobspy`), 686-778 (`scrape_with_browser`), 849 (JobSpy comment in scrape_all_sources), tests/test_scrape_resilient.py lines 1-20 and 473-483 (import style; the existing browser test expects [] for example.com when Playwright is absent)</read_first>
  <behavior>
    - source_registry.browser_disabled_reason returns BROWSER_DISABLED_HOSTS["indeed"] for https://www.indeed.com/jobs?q=pm, https://de.indeed.com/viewjob?jk=1, https://indeed.de/, https://www.indeed.co.uk/x, https://WWW.INDEED.COM/x, and the scheme-less indeed.com/jobs
    - It returns None for https://example.com/careers, https://notindeed.com/, https://example.com/?q=indeed (only the host counts), and "not a url"
    - BROWSER_DISABLED_HOSTS["indeed"] mentions "Cloudflare 403", "G-1802" and that Indeed stays available through python-jobspy
    - scrape_with_browser(["https://de.indeed.com/jobs?q=pm", "https://www.indeed.com/viewjob?jk=1"]) returns 2 entries, each with content "" and an error starting "disabled: " that contains the registry reason. Playwright is never imported: stub modules for "playwright" and "playwright.sync_api" are installed with monkeypatch.setitem, and the stub's sync_playwright records calls; zero calls are asserted
    - Mixed ["https://de.indeed.com/jobs", "https://example.com"] with Playwright absent (monkeypatch.setitem(sys.modules, "playwright.sync_api", None)) returns exactly the one indeed refusal entry
    - The existing test_returns_empty_without_playwright (example.com -> []) still passes unchanged
    - scrape_resilient.scrape_jobspy(sites=["google"]) returns [] with scraper.scrape_jobs and scrape_resilient.time.sleep both patched and never called, and caplog has an ERROR mentioning google
  </behavior>
  <action>
RED first: create tests/test_source_registry.py with a module docstring noting it is the first test file for tools/source_registry.py and covers only browser_disabled_reason / BROWSER_DISABLED_HOSTS (G-1802). Add a TestBrowserDisabledReason class covering the host cases above. In tests/test_scrape_resilient.py, extend TestBrowserFallback with the refusal and mixed cases, and add a TestJobspySiteValidation class for the scrape_jobspy google case. Use types.ModuleType for the Playwright stubs, patch("scraper.scrape_jobs") and patch("scrape_resilient.time.sleep") in the style the file already uses, and caplog for the log. Run both files and confirm they FAIL, recording the summary line.

GREEN, tools/source_registry.py (per AC7, the reason is recorded here): below JOBSPY_BOARDS, add `BROWSER_DISABLED_HOSTS: dict[str, str]` with a comment explaining that it lists hosts the headless-browser fallback must never visit, keyed by hostname label. Its single "indeed" entry's text says: Indeed HTML scraping via headless Playwright is dead, because every request gets a Cloudflare 403 from a bot-fingerprint check before any listing HTML is served (verified 2026-09-28, G-1802), and Indeed postings still arrive through the python-jobspy HTTP path (board indeed). Add `browser_disabled_reason(url: str) -> str | None` with a docstring. It takes the lowercased hostname via urllib.parse.urlsplit; if that hostname is None, it re-parses with "//" prepended so scheme-less input is still caught (fail closed). It returns the reason when any dot-separated hostname label equals a key, else None. Put the urlsplit import in the existing stdlib import group in sorted order. Do not change JOBSPY_BOARDS, the status vocabulary, _load, or anything else.

GREEN, tools/scrape_resilient.py:
- In scrape_with_browser, BEFORE the Playwright import: split urls into refused and allowed using source_registry.browser_disabled_reason. For each refused URL, log a WARNING "Browser fallback refused for <url>: <reason>" and add an entry with url, content "" and error "disabled: <reason>". If nothing is allowed, return the refused entries without importing Playwright. On ImportError of Playwright, return the refused entries (an empty list when there are none, which keeps the existing test's [] result). Otherwise seed results with the refused entries and loop only over the allowed URLs. Update its docstring: the IMPORTANT line becomes "Indeed hosts are hard-refused (see source_registry.BROWSER_DISABLED_HOSTS); LinkedIn must not be browsed either". The module docstring's Playwright bullet gains "(never for Indeed, hard-disabled)".
- In scrape_jobspy, extend the existing lazy import to also import validate_sites from scraper. Before _retry_with_backoff, if sites is truthy, call validate_sites(sites); on ValueError, log it at ERROR ("JobSpy: <message>") and return the empty list, so a deterministic rejection is not retried with sleeps.
- Update the three stale "(LinkedIn, Indeed, Glassdoor, Google)" mentions (the section comment above scrape_jobspy, its docstring, and the source-2 comment in scrape_all_sources) to say LinkedIn + Indeed by default per scraper.DEFAULT_SITES.
Do NOT run ruff format on either tools file (pre-existing drift). Keep new lines under 100 chars.

Run the two test files (GREEN), then the ruff gates in verify. Commit: fix(G-1802): hard-disable the Indeed Playwright fallback and record why, with a body naming the Cloudflare 403, the registry record, and the retry-skip for rejected jobspy sites.
  </action>
  <verify>
    <automated>PYTHONPATH=src /Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/python -m pytest tests/test_scrape_resilient.py tests/test_source_registry.py -q</automated>
    <automated>/Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/ruff check tests/test_scrape_resilient.py tests/test_source_registry.py && /Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/ruff format --check tests/test_scrape_resilient.py tests/test_source_registry.py && /Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/ruff check tools/scrape_resilient.py tools/source_registry.py --output-format json | /Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/python -c "import json,sys,collections; c=collections.Counter((f['filename'].rsplit('/',1)[-1], f['code']) for f in json.load(sys.stdin)); print(dict(c)); assert c == collections.Counter({('scrape_resilient.py','B023'):1, ('scrape_resilient.py','E501'):5, ('scrape_resilient.py','F401'):7})"</automated>
    <automated>grep -n 'BROWSER_DISABLED_HOSTS' tools/source_registry.py && grep -n 'browser_disabled_reason' tools/scrape_resilient.py && grep -n 'validate_sites' tools/scrape_resilient.py</automated>
  </verify>
  <done>Indeed URLs are refused before Playwright is imported, and the refusal shows up as an error entry carrying the reason recorded in source_registry.BROWSER_DISABLED_HOSTS; host matching is covered by tests including subdomains, ccTLDs, uppercase, and scheme-less input; a rejected jobspy site is not retried; the existing browser test is unchanged and passing; tools ruff findings equal the pre-existing 13 in scrape_resilient.py and 0 in source_registry.py; one fix(G-1802) commit with a body.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| python-jobspy (third-party, unmaintained) -> discovery sweep | Blocking synchronous calls into an upstream library that can hang or raise run inside the app's asyncio scheduler |
| operator env (.env / JOBSPY_TIMEOUT_SECONDS) -> Settings | Operator-supplied config controls how long the sweep waits |
| CLI args (--sites, --browser-urls) -> tools scrapers | User-supplied site names and URLs pick which external hosts get hit and how |
| tools -> external job boards (Indeed, LinkedIn) | Automated requests against third-party sites with anti-bot controls and ToS limits |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-260928-pbu-01 | Denial of Service | JobSpyAdapter._scrape_site executor call | medium | mitigate | asyncio.wait_for bounded by settings.jobspy_timeout_seconds (default 60); Task 1 timeout test proves the sweep returns in under 2 s with a recorded warning. Residual: the abandoned worker thread runs until jobspy returns (Python threads cannot be killed); documented in a code comment and accepted. |
| T-260928-pbu-02 | Denial of Service | JobSpyAdapter multi-board call | medium | mitigate | One scrape_jobs call per board with per-call exception capture; Task 1 isolation test proves one board raising keeps the other board's rows. |
| T-260928-pbu-03 | Tampering | Settings.jobspy_timeout_seconds | low | mitigate | Field(gt=0) rejects 0 or negative at startup, so a misconfiguration cannot turn every call into an instant timeout or an invalid wait; covered by a Task 1 test. |
| T-260928-pbu-04 | Spoofing | scrape_resilient.scrape_with_browser (anti-detection headless browser) | medium | mitigate | Every Indeed host is refused before Playwright is imported, and the reason is recorded in source_registry.BROWSER_DISABLED_HOSTS. Host matching is label-based, lowercased, and fail-closed on scheme-less input; tested in Task 3. |
| T-260928-pbu-05 | Information Disclosure | LinkedIn access from tools | low | mitigate | No code path passes cookies or a logged-in session (scrape_with_browser uses fresh contexts; jobspy uses guest endpoints). tools/README.md and the specific_hunt.py docstring state it explicitly (Task 2). |
| T-260928-pbu-06 | Denial of Service | tools/scraper.py + scrape_resilient retry loop | low | mitigate | google is rejected up front by validate_sites; scrape_resilient validates before _retry_with_backoff so a deterministic rejection is not retried with sleeps (Task 3 test asserts sleep is never called). |
| T-260928-pbu-SC | Tampering | npm/pip/cargo installs | high | accept | This plan installs no packages and does not change the python-jobspy pin (>=1.1.82,<1.2), per the ticket constraint. |
</threat_model>

<verification>
Run from the checkout root after all three tasks:

1. `PYTHONPATH=src /Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/python -m pytest tests/ -k jobspy -v` (ticket's gate; the new tests/test_jobspy_adapter.py tests are selected and pass)
2. `PYTHONPATH=src /Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/python -m pytest tests/ -m "not eval" -q --tb=short` (CI-equivalent full suite; fully green)
3. `/Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/ruff check src/ tests/` and `/Users/pleasedodisturb/Projects/apps/kestrel/.venv/bin/ruff format --check src/ tests/` (both clean)
4. Tools lint gate: `ruff check tools/scraper.py tools/specific_hunt.py tools/scrape_resilient.py tools/source_registry.py --output-format json` gives exactly the 14 pre-existing findings (scraper.py F821 x1; scrape_resilient.py B023 x1, E501 x5, F401 x7)
5. The ticket's grep checks, output pasted into the SUMMARY: `grep -n 'glassdoor' src/career_os/discovery/adapters.py` (no output), `grep -n 'wait_for' src/career_os/discovery/adapters.py` (the executor wrap), `grep -n 'google' tools/scraper.py` (the UNSUPPORTED_SITES entry and docstring, not a DEFAULT_SITES passthrough), `grep -rn 'indeed' tools/scrape_resilient.py` (comments and the refusal path only, no Playwright call site that can reach Indeed)
6. `git diff --name-only main...HEAD` lists exactly the 13 files in files_modified; CHANGELOG.md and README.md are absent from it
7. `git diff main...HEAD -- src/career_os/discovery/adapters.py` shows hunks only inside class JobSpyAdapter (no import-block or ArbeitsagenturAdapter change, to keep the G-1717 merge clean)
8. `git log --format='%s%n%b' main..HEAD` shows 3 commits, each titled `fix(G-1802): ...` (or `test(G-1802): ...` if a RED commit was split out) with a non-empty body
</verification>

<success_criteria>
- AC1: no Glassdoor in the adapter's site_name (SITES is Indeed only; test plus grep)
- AC2: one scrape_jobs call per board; a test raises for one board and asserts the other board's rows survive
- AC3: asyncio.wait_for around run_in_executor with JOBSPY_TIMEOUT_SECONDS (default 60); a test proves a hung scraper makes the sweep return and record "timed out"
- AC4: tools/scraper.py rejects google with a clear message (scrape_all ValueError + CLI exit 2), tested
- AC5: no manual CHANGELOG line (no release-please precedent, see objective); the changelog entry comes from the fix(G-1802) squash title. README untouched.
- AC6: specific_hunt.py docstring documents blank LinkedIn descriptions (#374) plus the opt-in cost, tested against the real call; tools/README.md states Kestrel never scrapes LinkedIn from an authenticated session
- AC7: the Indeed Playwright fallback is hard-refused before import, with the reason recorded in tools/source_registry.py (BROWSER_DISABLED_HOSTS)
- Adapter still works with jobspy absent (warning, no crash); no test imports real jobspy for the adapter or touches the network; full suite and ruff gates green
</success_criteria>

<output>
Create `.planning/quick/260928-pbu-g-1802-jobspy-adapter-hardening/260928-pbu-SUMMARY.md` when done. Include the RED failure lines from each task, the ticket grep outputs from verification step 5, the full-suite pass count, the AC5 CHANGELOG finding (so the orchestrator writes a changelog-worthy `fix(G-1802): ...` PR title), and the flag that tools/source_registry.py had no tests before this change.
</output>
