# Domain Pitfalls

**Domain:** Subsequent milestone (v2.0 "Lean Kestrel") on a working FastAPI / SQLAlchemy 2 / SQLite / Typer / WXT app with a public repo, CI, release-please and a PyPI package. Two halves: CUT a large surface, ADD a headless/paid/personal-data pipeline.
**Researched:** 2026-10-24 (replaces the April 2026 file written for the roadmap milestone)
**Overall confidence:** HIGH for repo-specific findings (each was verified by reading the tree, the CI config, branch protection via `gh api`, or the published 0.28.2 wheel). MEDIUM for external-service behaviour (read from vendor docs on 2026-10-24; vendors can change). LOW where marked "inferred".

Evidence tags used below: **[repo]** verified in this repo today, **[wheel]** verified by unzipping the published `kestrel_app-0.28.2` wheel, **[docs]** read on the vendor's own page, **[search]** secondary source only (do not treat as authoritative), **[inferred]** reasoned from the above, not observed.

## How to read this file

Phase labels are WORKING NAMES so the roadmapper can map them. Suggested ordering rationale is at the end of "Phase-Specific Warnings".

| Label | Scope |
|-------|-------|
| **Foundation** | Safety nets that must exist before anything is deleted or added: contract/import tests, wheel-content test, hardened `CI Complete`, relocation of CI-critical scripts, DB engine hardening, one path/config resolver |
| **Cut-A** | Cuts with no port dependency: worker, dashboard, BMAD, TickTick/calendar/OAuth/WARN/Pushover, npm/homebrew, unused workflows |
| **Find** | `kestrel scan`, ATS sources, dedup, liveness, canaries/floors |
| **Filter** | `assess()`, geo gate per profile, multi-office rule |
| **Cost** | Provider preflight, spend halt, 402/429 handling |
| **Score+Digest** | Calibrated scoring, daily digest, excluded-jobs audit, overturn to fixture |
| **Track** | Textual TUI, outcome states, ingestion |
| **Write** | Dossier, voice gate, fact gate, drafting, extension prefill |
| **Connect** | MCP server |
| **Install** | 15-minute fresh-machine test, README, bind default |
| **Retire** | Cut-B: delete `tools/` scripts and `daily-scan.yml` only after replay plus shadow run |

## Index (severity, phase)

| ID | Pitfall | Severity | Phase |
|----|---------|----------|-------|
| CUT-1 | Hidden importers: deferred imports and `except Exception` swallow | Critical | Foundation, Cut-A |
| CUT-2 | CI-critical code and 17+ test files depend on `tools/` | Critical | Foundation |
| CUT-3 | `CI Complete` fails open; two layers of branch protection | Critical | Foundation |
| CUT-4 | PyPI wheel ships a STALE frontend today; wheel is only smoke-tested on `/health` | Critical | Foundation, Install |
| CUT-5 | Alembic: history, downgrade roundtrip, SQLite FK/batch, shared `integration_configs` table | Critical | Cut-A |
| CUT-6 | Release plumbing: PyPI trusted publisher bound to `publish.yml`; release-please skips missing files silently; orphan packages | Critical | Cut-A |
| CUT-7 | Retiring the maintainer's live pipeline before parity | Critical | Retire |
| ADD-1 | Headless scan: cron CWD, relative DB path, `.env` lookup, default `mock` provider | Critical | Foundation, Find |
| ADD-2 | SQLite concurrency between cron scan, API server, TUI | Critical | Foundation, Find |
| ADD-3 | Double scan: in-process scheduler plus cron plus manual run | Critical | Find |
| COST-1 | Spend halt bypassable (concrete bypass list for this codebase) | Critical | Cost |
| COST-2 | 402 vs 429: all providers conflate them; "429 = wait" can loop on a spend cap | Critical | Cost |
| GEO-1 | Wiring geo per profile silently changes defaults (Ireland example fallback) | Critical | Filter |
| GEO-2 | The "blind" set stops being blind; n=277 is small for a rule measurement | Critical | Filter |
| DEDUP-1 | Dedup false positives blocking the first scan; sticky exclusions | Critical | Find |
| ATS-1 | ATS rate limits unknown, schema drift, mass-close on board migration | Critical | Find |
| REPLAY-1 | Port-by-replay traps: clocks, hash order, shared code, config fallbacks, drifting fixtures | Critical | Every port phase, Retire |
| SEC-1 | MCP server exposes personal data and bypasses the provider privacy boundary | Critical | Connect |
| SEC-2 | Prompt injection through scraped job descriptions | Critical | Find, Write, Connect |
| GATE-1 | Fact gate / voice gate give false confidence | Critical | Write |
| MIG-1 | Schema skew between entry points (`start`, `scan`, TUI, MCP) | Moderate | Foundation |
| TUI-1 | Textual: `asyncio.run` in CLI helpers, blocking DB calls, logging, flaky tests | Moderate | Track |
| DIGEST-1 | Audit sample bias; overturn to fixture leaks PII or overfits | Moderate | Score+Digest |
| INSTALL-1 | Fresh-image install test flakiness | Moderate | Install |
| BIND-1 | Fixing the `0.0.0.0` default breaks Docker if done naively | Moderate | Install |
| FE-1 | Frontend contract drift stays green because tests mock at the API boundary | Moderate | Cut-A |
| OUT-1 | New outcome states fan out to five consumers | Moderate | Track |
| DOS-1 | Dossier and drafts are personal data in a public repo's tree | Moderate | Write |
| PLUG-1 | "Private plugin" seam silently becomes a public API | Moderate | Retire |
| DEP-1 | Extras and dependency floors (`mcp`, `textual`, `python-jobspy`) | Moderate | Connect, Track, Install |
| DOC-1 | Docs, README, CLAUDE.md, Pages, repo secrets drift after the cut | Moderate | Cut-A, Install |
| PROC-1 | Review-trailer gate versus huge deletion PRs | Moderate | Cut-A |
| MIN-* | Minor pitfalls (stale `build/`, Greenhouse HTML escaping, Lever EU host, headless browser open) | Minor | various |

---

## Critical Pitfalls

### CUT-1: Hidden importers survive the delete (Pushover is the textbook case)
**What goes wrong:** Removing `services/pushover.py` and friends looks safe because `ruff` and the import-time test run pass. But Pushover is referenced from six places, and three of them are NOT import-time:
- `services/drift_canary.py:195` imports `send_drift_alert` inside the `if result["alert"] and notify:` branch. It only explodes when the drift alarm fires, i.e. exactly when you need it. [repo]
- `services/analytics.py:263` imports `NotificationLog` inside `_compute_notification_metrics()`; the analytics endpoint 500s only when that endpoint is hit. [repo]
- `api/scoring.py:196` calls `send_credits_exhausted_alert` inside `try ... except Exception: logger.warning(...)`. If the import is ever made deferred, an `ImportError` is swallowed and the "credits exhausted" alert silently becomes a no-op. [repo]
- Also coupled: `main.py` (router include + `start_ticktick_scheduler`/`stop_ticktick_scheduler` in the lifespan), `models/__init__.py` (re-exports `NotificationLog`, `TickTickSyncTask`), `schemas/integrations.py` (registry entries for ticktick/calendar/pushover), `config.py`, `cli/scoring.py`, the frontend Integrations settings page and its test, `.github/workflows/daily-scan.yml` (Pushover secrets), `.env.example`, and the Alembic revision files. [repo]
Worse: Pushover is the ONLY out-of-band alert channel the code has. Cutting it without a replacement removes the delivery path for "credits exhausted" and "scoring drift", the two signals the new spend-halt and canary features are supposed to raise.
**Why it happens:** Static tools only see top-level imports; the project style uses function-local imports and broad `except` to keep optional features non-fatal (the same style the repo's own AST guard was written against).
**Prevention (acceptance criteria):**
1. Before deleting, add a test that imports EVERY module under `career_os` (`pkgutil.walk_packages`) and calls `app.openapi()`; it must pass before and after each cut PR.
2. Delete leaf-first: callers (routes, schedulers, CLI, frontend, registry entries), then services, then models, then migrations strategy (see CUT-5). One integration per PR.
3. After each delete, `grep -rniE "<name>|<Name>"` across `src tests frontend/src docs .github *.md` and require zero hits except the migration history and CHANGELOG. Include string references (`name="pushover"`, config keys, env var names).
4. Replace the alert sink first: define one `notify()` seam (log + digest line + nonzero exit code from `kestrel scan`; optional webhook later) and move `send_credits_exhausted_alert`/`send_drift_alert` call sites onto it in the same PR that removes Pushover. Add a test that the credits-exhausted and drift paths each produce a notification through the seam.
5. Never wrap a deferred import for a removed feature in a broad `except`; delete the call.
**Detection:** `pytest` green but `GET /api/analytics` 500; a drift run logging `ModuleNotFoundError`; zero Pushover-style alerts after a real credit exhaustion.
**Phase:** Foundation (import-all test, `notify()` seam), Cut-A (the deletes).

### CUT-2: CI-critical code and many tests live in `tools/`; the gate guards hard-code its paths
**What goes wrong:** `tools/` is not only "maintainer scripts" (~15.6k lines). Today: [repo]
- `ci.yml` job `review-trailers` runs `python tools/check_review_trailers.py`. Delete `tools/` in a PR and that required job fails inside the same PR, so `CI Complete` goes red and the PR cannot merge.
- `ci.yml` step "Run tool-script tests" runs `pytest tools/tests/` after `pip install -e ".[mcp]"`; the MCP server itself lives at `tools/kestrel-mcp/server.py`.
- `tests/conftest.py:19` puts `tools/` on `sys.path`, and at least 17 files under `tests/` import tools modules directly (`tier0_ats_poller`, `job_scorer`, `batch_apply_browser`, `snapshot_db`, `specific_hunt`, ...; counted with a stem-anchored grep, so path-loaded ones are extra). Collection errors fail the whole `pytest tests/` run, not just those files.
- `tests/test_no_import_masking_skips.py` hard-codes `SWEEP_ROOTS = (tests, tools/tests)`, computes the "first-party module" set from `tools/*.py` stems, and references `tools/tests/test_config_loaders.py` by path at lines ~4602/4613. Deleting `tools/` changes what the guard considers first-party and can break or weaken it.
- `tests/test_billing_safety.py` hard-codes `SCHEDULED_SCORING_WORKFLOWS = ["daily-scan.yml"]`. If that workflow is deleted and the list is not replaced, the "no scheduled chain contains a premium provider" invariant either errors or becomes vacuous (the COE-2026-07-19 invariant disappears from CI without anyone deciding that).
- `sonar-project.properties` excludes `tools/**`; `.gitignore` names `tools/mcp_sanity_check.py`.
**Why it happens:** Scripts accrued CI duties over time; nothing lists them.
**Prevention:**
1. First PR (Foundation): move `check_review_trailers.py` and its test to a surviving home (for example `scripts/` or `.github/scripts/`) and repoint `ci.yml`. Prove with a throwaway PR that the `Review trailers` job still runs and still fails on a bad trailer.
2. `grep -rn "tools/" .github tests pyproject.toml sonar-project.properties .pre-commit-config.yaml .gitignore CLAUDE.md` is a checklist; every hit gets a disposition in the PR description.
3. Delete tests together with the code they test, with a deletion ledger (the repo already did this for `test_parse_scoring_response.py`, G-1382). Do not `importorskip` or mask missing tools modules; the AST guard is there to refuse exactly that.
4. Rewrite the billing invariant to target the new surface: assert that the `kestrel scan` command and any shipped cron/launchd/Actions template cannot construct a premium chain (see COST-1), and add an assertion that the scheduled-workflow list is non-empty so the test cannot pass vacuously.
**Detection:** red `Review trailers` or collection errors on the deletion PR; a billing test with zero parametrized cases.
**Phase:** Foundation (relocate, repoint), Retire (final tools/ delete).

### CUT-3: `CI Complete` fails open, and branch protection exists in two layers
**What goes wrong:** Branch protection (read via `gh api`, 2026-10-24) has a classic rule requiring contexts `CI Complete` and `Lint commit messages`, plus a repository ruleset `Main` requiring `CI Complete`. [repo] `ci-complete` (in `ci.yml`) loops over jobs and only fails on `failure` or `cancelled`. An empty result (a job removed from `needs:` or renamed, so `needs.<job>.result` is an empty string) and `skipped` both pass. A deleted/renamed/path-skipped job makes the gate green with that job never having run. GitHub documents the mirror image: a required check whose workflow never triggers sits at "Waiting for status to be reported" forever, and a skipped job reports Success. [docs: GitHub troubleshooting required status checks] The Dependabot auto-merge workflow merges patch/minor bumps once the required checks pass, so a fail-open gate becomes an unreviewed merge path.
This repo's own COE says "a permanently-green check is a smell" (`docs/coe/2026-07-09_initial-commit-pii-exposure.md`).
**Why it happens:** Cutting sonar/smoke/etc. edits `ci.yml`'s job list; the aggregator was written to tolerate skips because `review-trailers` is skipped on push.
**Prevention:**
1. Change the aggregator to an allow-list: every job in `needs` must be `success`, except an explicit, named set that may be `skipped` (`review-trailers` on non-PR events). Anything else, including empty, is a failure. Add a workflow-lint test (the repo already parses workflows in `test_billing_safety.py`) asserting that the `needs:` list equals the job list and that every `needs.X.result` referenced exists.
2. Never rename the contexts `CI Complete` or `Lint commit messages`. Do not add `paths:`/`branches:` filters to `ci.yml` or `commitlint.yml`.
3. After the workflow cut merges, re-run `gh api repos/<owner>/<repo>/branches/main/protection` and `.../rulesets` and confirm every required context is still produced by a surviving workflow. Record the output in the PR.
4. Do the workflow cut as its own PR(s), after the aggregator hardening has merged.
**Detection:** a PR that never shows `CI Complete`; `CI Complete` green in under a minute; a step summary listing fewer jobs than before.
**Phase:** Foundation (harden), Cut-A (workflow deletes).

### CUT-4: The published wheel ships a stale frontend (verified); the only wheel test checks `/health`
**What goes wrong:** Verified by unzipping `kestrel_app-0.28.2-py3-none-any.whl` from PyPI: it contains BOTH `career_os/_frontend_dist/index.html` + `assets/index-KDnWhwGY.js` (the committed April copy) AND `career_os/_frontend_dist/dist/index.html` + `dist/assets/index-CDTSlhz3.js` (the fresh build). [wheel] Cause: `src/career_os/_frontend_dist/` is tracked in git (3 files, from commit "pip install support") and `publish.yml` runs `cp -r frontend/dist src/career_os/_frontend_dist`; when the destination already exists, `cp -r` nests the source as `_frontend_dist/dist` (reproduced locally). `main.py` serves `_frontend_dist/index.html`, so `pip install kestrel-app` serves a months-old UI. It is also the same wheel the 15-minute install path depends on.
`smoke.yml` job `pypi-wheel` builds with `python -m build --wheel` WITHOUT building the frontend and only checks `/health`, so it cannot see any of this. Cutting `smoke.yml` (planned) removes the only wheel boot test.
Also: `pyproject.toml` package-data globs `_frontend_dist/**/*` while `MANIFEST.in` mentions `frontend/dist`; the local `build/lib` dir is stale (see MIN-1).
**Why it happens:** Two sources of truth for the bundle; no assertion on wheel contents.
**Prevention (acceptance criteria):**
1. `git rm -r src/career_os/_frontend_dist` and gitignore it; the publish job does `rm -rf` the target and copies with `cp -r frontend/dist/. src/career_os/_frontend_dist/` (or builds into place).
2. A required CI job (part of `CI Complete`, no path filter) that builds the frontend, builds the wheel, then asserts: `_frontend_dist/index.html` exists at the root; no `_frontend_dist/dist/`; every `/assets/...` URL in `index.html` is a file in the wheel; no files from cut modules (`pushover`, `ticktick`, `calendar`, `oauth`, `warn`); `entry_points.txt` lists exactly the intended console scripts; `*.dist-info/METADATA` extras match expectations. `check-wheel-contents` can do part of this. [search: pypi.org/project/check-wheel-contents]
3. Install that wheel in a clean venv (not editable, no repo CWD), run `kestrel --help`, start the server, `curl /` and assert the HTML references an asset that returns 200 and a JS content type. The same job is the seed of the Install-phase fresh-machine test.
4. Keep ONE Dockerfile but make it consume the same bundle step so Docker and wheel cannot drift.
**Detection:** unzip the wheel; `GET /` returns an `index-<hash>.js` that differs from `frontend/dist`'s hash.
**Phase:** Foundation (job + git rm), Install (extend to full fresh-machine path).

### CUT-5: Alembic and SQLite: dropping tables and columns on real user databases
**What goes wrong (several distinct traps):**
1. **Editing or deleting old revisions.** Users' DBs are stamped at some of the 38 revisions; removing `j1e2f3g4h5i6_add_pushover_notification_tables.py` (or editing it) makes `alembic upgrade head` fail with "can't locate revision" for anyone on an older stamp. Cut features need a NEW forward revision, never an edit. [repo]
2. **CI's downgrade roundtrip.** `ci.yml` runs `alembic downgrade base` then `upgrade head`. A new "drop pushover tables" revision whose `downgrade()` is `pass` makes the older revision's `downgrade()` (`drop_table`) fail because the table does not exist. [repo, inferred from the step]
3. **FK enforcement.** SQLite: with foreign keys enabled, `DROP TABLE` performs an implicit `DELETE FROM` that fires FK actions, so a `CASCADE` can silently delete child rows. [docs: sqlite.org/lang_droptable.html] Alembic's batch mode (`render_as_batch=True` is set in `_alembic/env.py`) recreates tables via copy-and-drop and documents that it does not work with enforced FKs; the pragma must be disabled during the migration. [docs: alembic batch] The app engine turns `PRAGMA foreign_keys=ON` on every connection (`database.py`); `env.py` builds its own engine without that listener, so migrations currently run with FKs off, but `create_test_engine` and any future "migrate through the app engine" refactor flips it. Tests that build schema with `Base.metadata.create_all` never exercise this.
4. **Shared table.** `integration_configs` stores credentials for `ticktick`, `calendar`, `pushover`, `voice` AND `ai_providers` (`schemas/integrations.py`; read by `services/ai_health.py`). Dropping the table, or batch-recreating it, destroys users' AI-provider and voice settings. Leaving the cut rows keeps stale third-party tokens in users' databases. [repo]
5. **Model/metadata drift.** Deleting `models/pushover.py` etc. while old revisions still create those tables means `alembic check`/autogenerate will propose drops forever, and a fresh DB (upgrade head) has tables no model owns.
6. **Concurrent migration.** `main.py:_auto_migrate()` runs in app startup; `kestrel start` ALSO shells out to `python -m alembic upgrade head` from the CWD (which can migrate a different DB than the app uses, because `alembic.ini` hard-codes `sqlalchemy.url`; the subprocess failure is only printed as a warning). See MIG-1.
**Prevention (acceptance criteria):**
1. Decide explicitly per table: (a) stop using it in v2.0 and drop in a later release (safest; a few orphan tables cost nothing), or (b) add one forward revision that drops it. For (b) the revision's `downgrade()` must recreate the table (so the roundtrip stays honest), OR change the CI roundtrip to downgrade to a named floor revision and document why.
2. Data revision for the shared table: `DELETE FROM integration_configs WHERE name IN ('ticktick','calendar','pushover')` and scrub nothing else; assert `ai_providers`/`voice` rows survive.
3. A migration test that starts from a REAL old database: build a fixture DB by running the old code (`pip install kestrel-app==0.28.2`, seed rows including pushover/ticktick/integration rows and a profile with children), then upgrade to head and assert row counts of untouched tables are unchanged and the PRAGMA `foreign_key_check` is clean. Run it with the app's FK-on connection settings as well as env.py's.
4. Keep old revision files byte-identical (the repo already excludes `_alembic` from ruff/pre-commit rewriting; add a test that hashes them).
5. Run `alembic heads` single-head check as today and add `alembic check` (model vs migrations) once models are removed.
**Detection:** `alembic upgrade head` raising `Can't locate revision`; row counts in `profiles`-children dropping after upgrade; AI provider settings missing after upgrade.
**Phase:** Cut-A.

### CUT-6: Release plumbing: PyPI trusted publisher, release-please, and orphaned distribution channels
**What goes wrong:**
- **PyPI trusted publishing is bound to the workflow filename** (owner, repo, workflow filename; environment optional). [docs: docs.pypi.org/trusted-publishers/adding-a-publisher] `publish.yml` uses environment `pypi` and `id-token: write`. Renaming, merging into another workflow ("consolidate the release workflows") or deleting it breaks uploads with an OIDC mismatch, discovered only at the next tag. The cut list says "keep release-please" and PyPI packaging but not which file names must survive.
- **release-please silently skips missing `extra-files`:** the code logs `file <path> did not exist` and continues. [docs: release-please `src/github.ts` buildChangeSet, read 2026-10-24] `release-please-config.json` lists `npm-package/package.json` and `frontend/package.json` plus `src/career_os/__init__.py`. Deleting `npm-package/` leaves a dead entry (harmless but a sign nothing validates the list); the dangerous direction is a typo or move that stops a version from bumping with no error. `bump-minor-pre-major: true` means a `feat!:` mass-deletion commit bumps 0.28.x to 0.29.0, not "2.0.0"; the milestone name "v2.0" and the package version will diverge unless someone deliberately uses a `Release-As:` footer.
- **Orphaned channels:** `npm-package/` is published to npm as `kestrel-app` by `publish-npm.yml`; `homebrew/kestrel.rb` has a placeholder sha and MIT license (the project is AGPL); `docker-publish.yml` pushes to GHCR on every main push and weekly. Cutting the workflows leaves old artifacts live (an npm wrapper that installs a version of Kestrel with removed features, a `latest` image with the old surface) and silently ends the weekly `apt-get upgrade` rebuild the Dockerfile comment relies on for base-image CVEs; Dependabot's docker ecosystem entry will keep proposing base-image bumps for an image nobody publishes.
- `release-gate.yml` currently auto-merges release-please PRs after checks; cutting it makes release PRs manual. That is fine but is a behaviour change to state explicitly.
**Prevention:**
1. Freeze these filenames/names in the cut spec: `publish.yml` (+ environment `pypi`), `release-please.yml`, `ci.yml`, `commitlint.yml`, contexts `CI Complete`/`Lint commit messages`. Add a test (like the existing workflow-parsing tests) asserting they exist.
2. Add a CI test that every path in `release-please-config.json` `extra-files` exists and that the version in `pyproject.toml`, `.release-please-manifest.json`, `src/career_os/__init__.py` and `frontend/package.json` agree.
3. For npm/homebrew/GHCR: publish a final deprecation (`npm deprecate`, README pointer, mark GHCR image deprecated in its description) BEFORE deleting the publisher workflow, or explicitly decide to leave them and say so in the CHANGELOG.
4. Decide the version story up front (e.g. `Release-As: 1.0.0`-style footer on the milestone-closing commit, or keep 0.x and name the milestone separately) and write it in the roadmap.
**Detection:** tag push with a failed `publish` job (OIDC claim error); release PR with an unchanged version in a file you expected to move.
**Phase:** Cut-A (spec + tests), Install (version story shown in README).

### CUT-7: Deleting the maintainer's live pipeline before the new one has parity
**What goes wrong:** `daily-scan.yml` (scheduled `0 7 * * 1-5`, gated by repo variable `DAILY_SCAN_ENABLED`) runs `tools/daily_pipeline.py`, `update_sheet.py`, `validate_sheet.py` and is the thing that currently does the maintainer's daily search. [repo] Deleting `tools/` first leaves a scheduled job failing every weekday (or, if the variable is off, hides that it was the acceptance test), and a pipeline that is the acceptance test for "the maintainer runs his daily search on Kestrel's engine" becomes unrunnable the day before the replacement is proven.
**Prevention:** Two-stage cut. Cut-A removes everything with no port dependency. `tools/` and `daily-scan.yml` are removed only in Retire, after (a) REPLAY-1 green for every ported behaviour, (b) a shadow period where `kestrel scan` and the old pipeline run on the same days and their structured outputs are diffed with a ledger of explained differences, (c) the last script revision is preserved as a git tag (for example `pre-v2-tools`) so replays remain reproducible after deletion.
**Detection:** the daily workflow red; the maintainer reaching for the old script.
**Phase:** Retire.

### ADD-1: Headless scan runs in the wrong place with the wrong provider and reports success
**What goes wrong:** Verified in `config.py`: `database_url` defaults to the RELATIVE `sqlite:///data/career_os.db`, `env_file` is the relative `.env`, `ai_provider` defaults to `mock`, `data_dir` defaults to relative `data`. [repo] `kestrel start` papers over this by setting `DATABASE_URL` to `~/.kestrel/data/career_os.db` if unset, but that code lives only in the `start` command. Cron/launchd/systemd run with CWD=`$HOME` (or `/`) and a minimal environment, so `kestrel scan` would (1) not find `.env`, (2) silently use the `mock` provider and persist fake scores as real, (3) create a new empty `data/career_os.db` in the wrong directory, (4) find zero profiles, and (5) likely exit 0. The user sees a green cron and an empty digest.
**Prevention (acceptance criteria):**
1. One path/config resolver (`KESTREL_HOME`, default `~/.kestrel`) used by `start`, `scan`, TUI and MCP; it sets DB URL, data dir and env-file location absolutely. Test: run each entry point from a temp CWD and assert the same DB file.
2. `kestrel scan` prints (and logs) resolved DB path, provider, model and chain at the start of every run, and refuses to run with `mock` unless `--allow-mock` is passed.
3. Preflight (Cost phase) failing = nonzero exit. "Zero arrivals" is an error unless the source canary says the sources are healthy and quiet (see ATS-1).
4. Ship a documented, tested example cron line / launchd plist that sets `KESTREL_HOME` explicitly. Note that the repo's launchd guidance forbids wrapping scripts in `/bin/bash`; keep it direct-exec.
**Detection:** digest with no jobs and no error; a `data/` folder appearing in `$HOME`.
**Phase:** Foundation (resolver), Find (scan).

### ADD-2: SQLite concurrency between a cron `scan`, the API server, the TUI and MCP
**What goes wrong:** Facts: the engine sets WAL and FKs per connection but no `busy_timeout`/`timeout` beyond the driver default, uses `check_same_thread=False`, and Python's sqlite3/pysqlite default transaction handling starts a transaction lazily before the first DML. [repo; docs: SQLAlchemy sqlite dialect "Transactions with SQLite and the sqlite3 driver"] Consequences:
1. **BUSY_SNAPSHOT on read-then-write.** In WAL mode a deferred transaction that read, then tries to write after another connection committed, fails immediately; the busy timeout does not help; the transaction must be rolled back and restarted. The fix is to start write transactions with `BEGIN IMMEDIATE`. [search: sqlite.org test suite + Simon Willison 2025-02-17; the SQLite WAL page itself does not describe this case, so treat the mechanism as MEDIUM and test it]
2. **Long transactions across LLM calls.** A scan that dedups, scores in batches and commits at the end holds a write lock for minutes, so API/TUI writes time out ("database is locked"). The repo already had a scheduler "lost results on session close" bug fixed by committing internally (`CONCERNS.md`); do not regress to one big transaction.
3. **WAL growth.** Overlapping long-lived readers (a TUI session, an MCP server holding a session open, the API) prevent checkpoints; the WAL grows without bound. [docs: sqlite.org/wal.html "checkpoint starvation"]
4. **Shared Session across threads/tasks.** SQLAlchemy sessions are not thread-safe even though the driver flag permits it.
**Prevention (acceptance criteria):**
1. In `database.py` connect hook: `PRAGMA busy_timeout` (for example 30000 ms), `PRAGMA synchronous=NORMAL`; set pysqlite `timeout` to match; use the documented `connect`/`begin` event recipe to emit `BEGIN IMMEDIATE` for sessions that write (or a dedicated "writer" engine/session factory).
2. Rule: no transaction open across network I/O. Scan persists arrivals in short transactions (commit per batch of arrivals; commit after each scored batch), idempotently (unique key; see ADD-3).
3. Session-per-unit-of-work in TUI/MCP/scan workers; never share a Session across threads; readers close promptly.
4. Periodic `PRAGMA wal_checkpoint(TRUNCATE)` at scan end when no readers are active, with a WAL-size warning in `kestrel doctor`.
5. A CI test with two real processes (multiprocessing, not threads): process A runs a scan-shaped write workload while process B hammers the API write path; assert no `OperationalError: database is locked` and bounded latency. Include a test where B holds a read snapshot then writes (the BUSY_SNAPSHOT case).
**Detection:** `database is locked` in API logs during a scan; `-wal` file larger than the DB.
**Phase:** Foundation (engine hardening + contention test), Find.

### ADD-3: Double scan, double spend
**What goes wrong:** The API server's lifespan already starts a background discovery scheduler (`discovery/scheduler.py`, with a known non-idempotent `start_scheduler()`), and v2 adds cron `kestrel scan` plus manual runs and the TUI. Two overlapping scans score the same arrivals twice (paid) and race on dedup. [repo]
**Prevention:** (1) a `scan_runs` table or OS file lock with heartbeat so a second scan exits immediately with a clear message (stale lock detection by heartbeat age, not PID alone); (2) unique constraint on a stable arrival key (source, source_job_id, content hash) so a re-run is idempotent; (3) the in-process scheduler either removed or made to call the same locked entry point; (4) scoring is keyed by (arrival, rules version, model) so a re-run reuses results (cache-aware spend accounting, see COST-1).
**Detection:** two `scan_runs` overlapping; duplicate score rows for one arrival.
**Phase:** Find.

### COST-1: A spend halt that can be bypassed (concrete bypass list)
**What goes wrong:** The repo's own COE (`docs/coe/2026-07-19_premium-anthropic-fallback-billing-regression.md`) shows a cost floor held by discipline eroding through three locally-correct changes, and that a broken path masked the hazard. A "spend halt" implemented in the scan command alone would be bypassable in this codebase by:
1. Any other caller of `score_job` / `complete()`: `/api/score`, batch submit, interview-prep, voice, extension capture, TUI, MCP, `kestrel score`. No limiter exists on these routes today (`CONCERNS.md`).
2. `FallbackProvider._try_chain` moving to the next provider on any `ProviderQuotaError`/`HTTPStatusError` with no budget check, so one halted provider is "healed" by the next, possibly pricier one. [repo]
3. Check-then-act races: N concurrent calls each read "under budget" and all proceed.
4. Spend tracked only in process memory: each cron run resets it. Per-run caps without a per-day/month persisted ledger.
5. Unknown or unpriced models counted as $0. (`openrouter_model` defaults to `anthropic/claude-sonnet-5`; provider defaults are premium; `AI_ALLOW_PREMIUM_FALLBACK=1` re-opens the premium chain.)
6. Extra calls that are not "the score": shadow scoring, borderline re-scoring, cascade escalation, batch-to-individual fallback on parse failure (10x calls), provider SDK/httpx internal retries. [repo: CONCERNS.md]
7. The Async Batch API (50% off, submitted in bulk): money is committed at submit time but results arrive later; a halt that looks only at completed calls misses it.
8. Cached results: cache hits must not count as spend but cache misses after a model bump must.
**Prevention (acceptance criteria):**
1. Exactly ONE choke point: a `BudgetGuard` wrapper composed at the outermost layer of `get_ai_provider()` (outside Fallback, so a halt cannot be "healed" by falling through) that every AI call goes through. Add a test that statically asserts no module outside `career_os/ai/` makes HTTP calls to a known LLM host and that every `AIProvider` subclass is reachable only through the factory.
2. Reserve-then-settle: before a call, atomically reserve the worst-case cost (`BEGIN IMMEDIATE` on a persisted `spend_ledger`); settle with actual usage after. Unknown model price = fail closed (halt with a clear message), not $0.
3. Caps at three horizons (per call/batch, per run, per day/month), persisted; state "halted" is persisted and visible in `kestrel doctor`, digest and TUI.
4. Extend `tests/test_billing_safety.py` rather than replacing it; add chaos tests: a stub provider that always returns 429/500 must produce a bounded number of calls and bounded simulated spend; a premium chain must be refused even if env says otherwise unless an explicit, logged opt-in.
5. Log winning provider and per-provider job counts every run into the digest (the COE's own follow-up).
**Detection:** spend ledger total differs from provider invoice by more than a stated tolerance; a call site found by grep that bypasses the guard.
**Phase:** Cost. Must land BEFORE or WITH `kestrel scan` on cron (the first unattended paid job).

### COST-2: 402 versus 429: every provider here conflates them, and "429 = wait" can loop forever
**What goes wrong:** In `src/career_os/ai/` the providers (Anthropic, OpenAI, OpenRouter, Mistral, Groq, xAI, Together, HuggingFace) treat `status in (402, 429)` as `ProviderQuotaError`; Gemini checks 429 only. [repo] `FallbackProvider` then moves straight to the next provider with no wait. The required v2 behaviour ("429 waits instead of escalating", "402 vs 429") is not enough, because the status code alone does not discriminate:
- Anthropic: 402 `billing_error`; a spend limit YOU set returns **400** `invalid_request_error`; hitting the tier monthly cap returns **429** `rate_limit_error` with NO `retry-after` and `error.details.error_code = enforced_spend_limit_reached`; "retrying, including the SDK's automatic retries, fails until access resumes". [docs: platform.claude.com/docs/en/api/errors and /rate-limits, read 2026-10-24]
- OpenAI: billing/quota exhaustion arrives as 429 with `insufficient_quota`; the exception class alone is not a reliable signal; retrying will not restore access. [docs/search: help.openai.com article 5955604, OpenAI cookbook]
- OpenRouter: 402 insufficient credits; failures after the provider accepts the request come back as HTTP 200 with an `error` object (or an SSE error event). [docs: openrouter.ai/docs/api-reference/errors]
So a naive "429 -> sleep and retry" waits forever on a spend cap while holding the scan lock and possibly a DB transaction, and a naive "429 -> next provider" is the premium re-escalation from the COE. Reported retry-loop incidents in the wild share this shape (retries that ignored the provider's stop signal) but those accounts are secondary. [search]
**Prevention (acceptance criteria):**
1. A per-provider error classifier returning one of `RATE_LIMITED(retry_after?)`, `OUT_OF_CREDIT`, `SPEND_CAP`, `TRANSIENT`, `FATAL`, driven by status AND body fields (`error.type`, `error.code`, `details.error_code`) and presence of `retry-after`. Contract tests with captured real error bodies per provider (fixtures), including the 200-with-error OpenRouter shape and the Anthropic 400 spend-limit shape.
2. Wait policy is bounded: honor `retry-after`, exponential backoff with jitter, a max total wait and max attempts per run; `RATE_LIMITED` without `retry-after` gets a small bounded retry then the run ends "incomplete", never an unbounded sleep. `OUT_OF_CREDIT`/`SPEND_CAP` never retry; they halt (COST-1) and surface.
3. Rate-limit waiting happens with no DB transaction open and releases/renews the scan heartbeat.
4. After a wait, retry the SAME provider/model; falling to another provider is allowed only inside the cost-class-preserving chain (never to a more expensive class) and is counted in the ledger.
5. Disable SDK/httpx hidden retries or count them (Anthropic's SDK retries twice by default).
**Detection:** a run whose duration is dominated by sleeps; provider call count per arrival above 1 + configured retries.
**Phase:** Cost.

### GEO-1: Wiring the geo gate per profile changes default behaviour silently (and the example config is Ireland)
**What goes wrong:** Today the engine in `src/career_os/services/geo/` is OPT-IN: `PrefilterConfig.geo_profile=None` means inert; the gate annotates `geo_class` and counts "foreign" but keeps the job unless `geo_drop_foreign` is set; `off` strategy bypasses it. [repo: `discovery/prefilter.py`] The private-pipeline copy differs: `tools/job_scorer.py::_default_geo_profile()` builds the profile from `config/geo.yaml`, falling back to `config/geo.example.yaml`, whose illustrative home region is Ireland, via a memoized module global. [repo] Port that behaviour verbatim and every fresh install silently treats Ireland as home. Wiring the gate "per profile" also changes what existing profiles' results look like (jobs now carry `geo_class`; if drop is enabled, jobs vanish).
**Prevention:**
1. A profile with no geo configuration gets NO gate and class `unknown` for every role (today's behaviour), proven by a differential test: with no geo config, the full result set equals the pre-change result set on a recorded sweep.
2. Never fall back to an example file at runtime. Example configs are documentation, and a test fails if runtime config resolution can reach `*.example.*`.
3. Dropping is a separate, explicit, per-profile opt-in; the first time it is enabled, show how many currently-visible jobs it would hide. The digest's audit sample (DIGEST-1) must include geo-excluded jobs.
4. Data migration for existing profiles: leave `geo_profile` empty; do not infer home from the profile's location text.
5. Keep "absence of geo signal must never bury a role" as an invariant test (`unknown` and maybe-classes are never dropped).
**Detection:** a new user with no geo config seeing `geo_class` values other than `unknown`; results count changing after upgrade for an unchanged profile.
**Phase:** Filter.

### GEO-2: The 277-item "blind set" is no longer blind, and is small
**What goes wrong:** `tests/eval/geo/fixtures/` holds the 277-item blind set with human GO/SKIP judgements and a FROZEN reference generated from the old private implementation (`reference_assignments.json`, produced by `generate_reference.py`). The multi-office over-admission rule will be designed by looking at failures on that set, then "measured" on it. Once you tune on it, the number is an in-sample number. With n=277 and only a subset being multi-office roles, the confidence interval on an over-admission rate is wide (a handful of items moves the headline). The frozen reference encodes the old implementation's behaviour, including its bugs; equality with it proves equivalence, not correctness. [repo + inferred]
**Prevention:** (1) Before designing the rule, split the set once: a design half and a held-out half whose results are not looked at until the rule is frozen; record the split in the fixtures README. (2) Report counts and a Wilson (or similar) interval, not just a percent, and set the acceptance criterion on the interval bound (or add items: collect additional multi-office cases from real scans, scrubbed). (3) Keep the differential gate (port must equal reference) separate from the quality gate (rule must meet precision/recall against HUMAN judgements); a PR may change one but must say which. (4) Re-scrub any new items with the existing `scrub_patterns` before they enter the public repo.
**Detection:** a rule that fits all 277 items exactly; recall claims quoted without n.
**Phase:** Filter.

### DEDUP-1: Dedup blocks the first scan, hides the wrong twin, and makes exclusions sticky
**What goes wrong:** Specific to this pipeline: [inferred from repo + docs]
- `rapidfuzz` is already a dependency; `token_set_ratio` returns 100 whenever one string's tokens are a subset of the other's, so "Senior Engineer" matches "Senior Engineer, Platform Security" and "Data Engineer (Berlin)" matches "Data Engineer (London)" if location is not part of the key. [docs: rapidfuzz fuzz usage]
- Multi-office twins: the same title/company posted per office is several jobs for a geo-gated user. If dedup runs before geo/location normalization, the surviving twin can be the out-of-region one and the in-region job is dropped before scoring.
- "Against history" includes the user's own history: if an arrival matches a job that was previously EXCLUDED under an old or broken rule, the exclusion is inherited forever (sticky). Reposts that are legitimate re-openings (same role, months later) are hidden.
- First scan: history import plus a large first batch means the highest dedup rate happens when the user is judging whether the product works. A bad false positive here is the "first useful job list" failure.
- Fuzzy matching on titles across sources (ATS API vs board mirror) is correct to merge; across different companies with similar names it is not.
**Prevention (acceptance criteria):**
1. Two tiers: exact identity (ATS + source job id, or canonical URL) is a certain duplicate; fuzzy matches only PROPOSE a link (`duplicate_of`) and are applied before paid scoring only when company, normalized location set and a conservative (not `token_set`) similarity all agree.
2. Never delete: persist every arrival (a stated requirement) with `duplicate_of`/reason so the digest can audit and the user can undo. Survivor selection prefers the arrival that passes geo/eligibility, not the first seen.
3. Dedup-against-history keys on (content fingerprint, rules version): a verdict from rules version N is not inherited under N+1.
4. A dedup-specific canary: per-source dedup ratio with a ceiling (for example more than a configured share of a first scan collapsing triggers a warning and disables fuzzy dedup for that run).
5. A labelled set of confusable non-duplicates (same title, different office; same company, adjacent seniority) as a regression test, built from real data and scrubbed.
**Detection:** first-scan arrival count minus unique count unusually high; the audit sample showing "duplicate of" links across offices.
**Phase:** Find (with Filter's location normalization as a dependency).

### ATS-1: Greenhouse/Lever/Ashby: unknown rate limits, schema drift, and mass-close on migration
**What goes wrong:** What the vendor docs say, read 2026-10-24: Greenhouse's Job Board API page mentions no rate limit or caching, GET needs no auth, `content=true` adds descriptions; Lever's README documents only a 2 requests/second limit on application POSTs (with a note that it may change without notice) and says nothing about GET limits, uses `skip`/`limit` paging, has a separate EU host (`api.eu.lever.co`), and only `published` postings are public; Ashby's public posting API (`GET https://api.ashbyhq.com/posting-api/job-board/{name}`) documents no rate limit, includes `isListed`, and says "if a field is missing in Ashby, it is also missing in the response". [docs] So limits are UNKNOWN, versioning is thin (Lever `v0`, Ashby `apiVersion`), and fields are optional. Failure modes:
1. **Mass-close false positive.** A company migrates ATS (Greenhouse to Ashby, or changes board token): the old board returns 404 or an empty list. A naive liveness check marks every one of its jobs "closed" in one run. This is exactly why the plan has "liveness with ATS re-resolution".
2. **Schema drift reads as zero jobs.** A renamed field makes parsing yield 0 jobs and the run "succeeds".
3. **Politeness.** Polling many boards in a tight loop, or per-job liveness pings, risks blocks (secondary sources also advise scheduled, not aggressive, polling [search]).
4. **Data shape gotchas:** Lever EU boards need the EU host; Ashby `isListed=false` postings must be skipped; descriptions arrive as HTML (see MIN-2).
**Prevention (acceptance criteria):**
1. Defensive client: per-host concurrency of 1 to 2, jitter, conservative timeouts, respect `Retry-After`/429 if it appears, no per-job liveness requests when the list endpoint already proves liveness.
2. Validate responses with a schema that tolerates unknown fields and requires the minimal fields (id, title, URL); parse failures and shape changes raise a typed error and count against the source canary, never "0 jobs".
3. Liveness safeguards: a job is only declared closed if its board was fetched successfully this run AND the board still lists other jobs; if more than X% of a company's open jobs vanish at once, or the board 404s, quarantine (state `unverified`) and try re-resolution via the other ATS adapters before closing. Quarantined jobs are never deleted and never re-scored.
4. Floors and canaries: per-source expected-minimum arrivals (from the previous N runs) with an alert when under; a few "known alive" canary boards; fixtures captured from real responses with a nightly `live`-marked refresh test (the repo already has a `live` pytest marker that never runs in CI).
5. Store a hash of each raw payload so a replay can reproduce a day.
**Detection:** a source whose arrivals drop to zero while its siblings are normal; sudden closed-count spike for one company.
**Phase:** Find.

### REPLAY-1: Port-by-replay traps
**What goes wrong:** "Same input, same output" verification of the ports fails to prove equivalence when: [repo + inferred]
1. **Clocks.** The scripts call `datetime.now()` directly (`daily_pipeline.py`, `scraper.py`, `tier0_ats_poller.py` verified). Any date-dependent behaviour (recency windows, stale cutoffs, filenames) differs between replay day and original day.
2. **Hash/iteration order.** `set` iteration (for example `tracked_keys: set[tuple[str,str]]` in `daily_pipeline.py`) varies with `PYTHONHASHSEED`; ties in sorts rely on insertion order.
3. **Shared code makes the test vacuous.** If the "new" path still imports from `tools/` (the tests today do `sys.path.insert(... "tools")`), old equals new by construction.
4. **Config fallbacks and module-level caches.** `_GEO_PROFILE`/`batch_probe._CONFIG` are memoized globals loaded from `config/geo.yaml` with a fallback to the example file (see GEO-1); the replay environment must pin config explicitly or both sides read whatever is on disk.
5. **LLM and network nondeterminism.** Replay must use recorded provider responses and recorded ATS payloads; any live call makes a diff meaningless.
6. **Fixtures that drift.** A golden file regenerated after a script edit (as `generate_reference.py` allows) silently re-baselines the test to the new behaviour. Inputs hand-written for the test miss the real distribution.
7. **Ordering and timezone/locale** of output files, float formatting, and Unicode normalization differences.
**Prevention (acceptance criteria):**
1. Replay inputs are captured production inputs (scrubbed) for at least N real days, plus hand-made edge cases, stored as fixtures with a manifest (source, date, hash).
2. Inject the clock (`now` parameter or a fixture) and run replays with `PYTHONHASHSEED=0` AND a random seed; both must pass (detects order dependence).
3. A test asserting the new module graph does not import `tools.*` / the old modules; replay executes old and new as separate processes.
4. Diffs are compared structurally with an explicit, reviewed ledger of INTENDED differences (each with a reason). Unexplained diff = failure.
5. Golden/reference files are append-only in review: any regeneration requires a PR note and a diff summary; CI checks the file hash against a committed manifest.
6. Delete a script only when its replay has been green and its shadow run (CUT-7) has completed; tag the last script revision.
**Detection:** replay green while the shadow run shows divergent output.
**Phase:** every port phase (Find, Filter, Cost, Score+Digest), final gate in Retire.

### SEC-1: MCP server: personal-data exposure, privacy-boundary bypass, tool scoping, transport
**What goes wrong:**
- **Privacy boundary bypass.** Kestrel's `ai/privacy.py` blocks personal-data features (cover letters, interview prep, voice) from non-ZDR providers (`check_privacy_boundary`). An MCP tool that returns the dossier or a draft hands personal data to whatever model the user's coding agent (Claude Code, Codex, Pi) happens to use, outside Kestrel's provider-tier logic, and the client may log tool results. [repo + inferred]
- **Lethal trifecta.** The agent that calls the tools also reads untrusted text (scraped job descriptions returned by the server) and usually has shell/network tools. Private data + untrusted content + external communication is the combination Willison calls the lethal trifecta; his guidance is to avoid the combination, not to rely on guardrails. [docs/search: simonwillison.net 2025-06-16]
- **Transport.** The MCP spec's security guidance for local servers: prefer `stdio`; if HTTP, require an authorization token or use a restricted IPC mechanism; DNS rebinding can reach an insecure localhost HTTP server. [docs: modelcontextprotocol.io security best practices] The Python SDK had CVE-2025-66416 (DNS rebinding on unauthenticated localhost HTTP/SSE servers, fixed in `mcp` 1.23.0). [search: NVD/GitLab advisory] `pyproject.toml` currently declares `mcp>=1.0.0`, which allows the vulnerable range. [repo]
- **Unauthenticated REST as a side door.** The REST API is unauthenticated by default and bound to `0.0.0.0` (G-2009); an MCP server that proxies to `localhost:8100` inherits that.
- **Over-broad tools.** A single "get_profile"/"dump_dossier" tool, or any tool that can submit, send or mark outcomes without confirmation.
**Prevention (acceptance criteria):**
1. Default transport `stdio` only. Any HTTP mode binds `127.0.0.1`, requires a bearer token, and sets the SDK's transport security (allowed hosts/origins). Raise the floor to `mcp>=1.23.0`.
2. The MCP layer calls the SERVICE layer in-process, not the REST API.
3. Read-first tool set with minimal fields: list/get jobs, get an assembled "drafting context" for ONE job (only the dossier facts needed), propose-draft/save-draft. No dossier dump, no raw credentials/keys, no submit/send tool. Write tools (overturn, mark outcome) are explicit and logged.
4. Job-description text returned by tools is length-limited, stripped of HTML/hidden text and clearly labelled as untrusted data (see SEC-2).
5. Route personal-data tool results through the same privacy check or require an explicit per-session acknowledgement that the connected agent is a third party; document this in README.
6. A golden manifest test of the tool list/schemas so adding a tool is a visible diff; tool call logging that does not write personal data.
**Detection:** a tool whose output contains dossier fields unrelated to the requested job; the server listening on a non-loopback interface.
**Phase:** Connect.

### SEC-2: Prompt injection through scraped job descriptions
**What goes wrong:** Job descriptions come from third parties and flow into scoring, drafting, and (via MCP) a coding agent. Hidden-text injection is already common on the resume side: a Duke-led study reported hidden prompts in roughly 1% of ~196k resumes, growing about sevenfold between July 2024 and November 2025, with most hidden text not containing explicit commands (secondary coverage; the paper itself was not opened). [search: pratt.duke.edu, letsdatascience.com, 2026] The mirror attack (employer or a compromised/lookalike posting targeting a candidate's agent) is plausible and cheaper than usual because Kestrel feeds JD text to LLMs with the user's dossier in context. Realistic effects here: inflated or deflated scores ("rate this 10/10"), fabricated claims in drafts ("state that you hold clearance X"), instructions leaking dossier content into a draft that is later pasted somewhere, or, via MCP, tool-using agents following embedded instructions. [inferred]
**Prevention:**
1. Normalize descriptions at ingest: strip scripts/styles/hidden elements (display:none, zero-size, off-screen), collapse Unicode tricks, cap length; store both raw and cleaned.
2. Prompt structure: JD is passed as delimited, labelled data; the drafting call has no tools and no access to secrets; instructions say JD content is data.
3. The fact gate (GATE-1) is the backstop: drafts are checked against verified facts regardless of what the JD said. Add an injection-corpus test (JDs containing instructions to fabricate, to exfiltrate, to score 10/10) asserting the gate catches fabrications and the score clamp/outlier flag fires.
4. Heuristic flag for instruction-like text in JDs; surface "this posting contains instruction-like text" in the digest/TUI instead of silently dropping.
5. Extension prefill answers come from dossier facts only, never from JD-derived text; per-job namespacing already called out in `CONCERNS.md`.
**Detection:** score distributions with a spike at the maximum for one source; drafts asserting facts not in the dossier.
**Phase:** Find (normalize), Write (prompt/gate), Connect (tool output labelling).

### GATE-1: Fact gate and voice gate give false confidence
**What goes wrong:** Gates that pass vacuously or are unmeasured become a quality seal people stop checking: [inferred, consistent with this repo's own COE "permanently-green check" lesson]
- Empty or unverified dossier => zero claims to check => PASS.
- Claim extraction by an LLM is itself an LLM judgement: it misses paraphrases ("led 5 engineers" vs "managed a team of five"), numbers, dates, tool names, employers, and implicit claims; self-grading is correlated with the drafter.
- Voice gate thresholds fitted to a few writing samples pass generic text that merely avoids the user's known tics, or fail genuine variation. A single score displayed as "voice match 87%" implies precision it does not have.
- Gate version drift: dossier edited after a draft was approved.
**Prevention (acceptance criteria):**
1. Fail closed: no verified facts => drafting blocked with an explanation; a draft with ANY unsupported claim cannot be marked ready; the UI shows "checked X claims, Y unsupported, Z not checkable" rather than a pass badge.
2. Measure the gate with planted fabrications: a labelled set of drafts with injected false claims (numbers, employers, dates, skills, certifications); the gate must catch at least a stated fraction, and the measured rate is published in docs with its limits. Negative controls run in CI with the mock/recorded model.
3. Prefer deterministic checks first (entity, number, date, tool-name matching against the dossier; allow-lists for generic phrases); LLM checks only add flags, never remove them.
4. Voice gate is advisory, calibrated on held-out samples from the user (and says how many samples it saw); minimum sample count before it reports at all.
5. Drafts store dossier version and gate version; editing the dossier marks dependent drafts "needs recheck".
6. Never auto-submit (already a project stance); the outcome states ("prepared", "submit attempted", "submission confirmed") must be set by human action or verified ingestion only.
**Detection:** gate pass rate near 100%; users editing facts into drafts after "pass".
**Phase:** Write.

---

## Moderate Pitfalls

### MIG-1: Schema skew between entry points
**What goes wrong:** Only the API lifespan runs `_auto_migrate()`; `kestrel start` also shells to `python -m alembic upgrade head` (CWD-relative `alembic.ini`, failure printed as a warning); other CLI commands do not migrate and `doctor` only reports. After `pip install -U kestrel-app`, `kestrel scan` from cron, the TUI or the MCP server can run new code against an old schema ("no such column") mid-scan, after a paid call. [repo]
**Prevention:** one `ensure_schema()` that compares the DB revision with the package head; `scan`/TUI/MCP fail fast with a clear message BEFORE any paid work if behind, and only `start`/`kestrel migrate` mutate the schema, under a file lock so two processes cannot migrate simultaneously. Delete the `python -m alembic` subprocess in `start`. Test: old-stamped DB + new code for each entry point.
**Phase:** Foundation.

### TUI-1: Textual specifics
**What goes wrong:** (a) The CLI's helpers wrap async services in `asyncio.run(...)` (`_run_discovery_async`, `_run_score_async`; they are "patched in tests", so tests never exercise the real path); calling them from Textual's running loop raises `RuntimeError: asyncio.run() cannot be called from a running event loop`. [repo] (b) Sync SQLAlchemy calls on the UI thread freeze the app; Textual says anything slower than a few ms belongs in a worker, sync functions need `thread=True`, UI updates from threads go through `call_from_thread` (which raises if called from the app thread) or `post_message`, and thread workers cannot be cancelled like coroutines. [docs: textual.textualize.io/guide/workers, api/app] (c) `print()`/`console.print`/logging handlers writing to the terminal corrupt the display; the CLI callback prints a stderr panel. (d) A still-running thread worker at exit can hold a SQLite write transaction. (e) Tests: `run_test()` + `Pilot` needs `await pilot.pause()` after input or assertions are racy; snapshot tests (pytest-textual-snapshot) fail on first run and churn across Textual versions and terminal sizes. [docs: textual testing guide]
**Prevention:** the TUI imports the service layer directly (never `cli/main.py` helpers); a `run_in_thread` helper opens a fresh Session per call and closes it; logging redirected to a file while the TUI runs; `exclusive=True` workers for list refreshes; thread workers check `get_current_worker().is_cancelled`; pin Textual; Pilot tests with explicit size and injected clock; keep snapshot tests few and non-blocking in required CI until stable. Add a test that fails if `asyncio.run` or blocking `time.sleep` appears under `career_os/tui/`.
**Phase:** Track.

### DIGEST-1: Audit sample bias; overturn becomes a fixture
**What goes wrong:** (a) A uniform random sample of excluded jobs is dominated by the easy bulk (obvious non-matches) and rarely shows the near-threshold or geo-excluded cases where errors live. (b) A sample regenerated on each view shows different jobs after refresh, so the user cannot "finish" the audit. (c) "Overturn becomes a regression fixture" copies real job text and the user's profile context into test data; in a public repo that is the 2026-07-09 PII incident pattern (`docs/coe/`). (d) Fitting rules to single overturns overfits; an overturn may mean "this job" not "this rule". (e) The digest channel: Pushover is gone; email/stdout/file each have different privacy exposure.
**Prevention:** stratify the sample by exclusion reason and by distance to threshold with a seed persisted per digest date; every sampled item shows the reason and the rule version; overturn records are stored in the user's data dir (`KESTREL_HOME/fixtures`) in the fixture format and never auto-committed; a documented "contribute a scrubbed case" path runs `scrub_patterns` and the CI PII gate; overturns create a candidate for review and re-run of the rule suite, not an automatic rule change; track overturn rate per rule as the quality signal.
**Phase:** Score+Digest.

### INSTALL-1: Fresh-image install test flakiness
**What goes wrong:** The test must prove "clone to first triaged job list in 15 minutes" yet it depends on: PyPI/CDN propagation delay if it installs the just-published release; pip resolver time with scientific stacks; ATS network calls (external, flaky, rate limited); a browser opener that no-ops or hangs headless (`kestrel start` calls `webbrowser.open` in a thread); port 8100 collisions; leftover `~/.kestrel`; environment leakage (`AI_PROVIDER`, API keys) from the runner; Python minor differences (CI uses 3.11, `publish.yml` builds on 3.13); wall-clock assertions on shared runners; and README drift (the test follows a script that no longer matches the README). `install.sh` is `curl | bash`, so the test must also run the PR's version, not `main`'s. [repo + inferred]
**Prevention:** two jobs: (1) required, deterministic: install the wheel built in the same CI run into a clean venv with a clean `HOME` and `KESTREL_HOME`, ATS traffic served by recorded fixtures through a local stub, `--no-browser`, random free port; assert steps (not wall-clock) and a step-duration budget with generous margin; (2) non-blocking scheduled: install from PyPI and hit real ATS canary boards, reporting but not gating. Extract the commands to run from the README (or from one file the README includes) so they cannot drift. Run on Python 3.11 and the newest supported minor. Clear provider env in the job.
**Phase:** Install.

### BIND-1: Fixing the `0.0.0.0` default breaks Docker if done naively
**What goes wrong:** `host` defaults to `0.0.0.0` in `config.py`, in `kestrel start`'s option, and in the Dockerfile `CMD`/`ENV`, with `AUTH_ENABLED=false` and `FRONTEND_URL="*"` in the image. Changing only the Python default is invisible to Docker (the CMD hardcodes it); changing the CMD makes the container unreachable through port mapping. [repo]
**Prevention:** bare-metal default `127.0.0.1`; the Dockerfile sets `HOST=0.0.0.0` explicitly and the compose/README examples publish `127.0.0.1:8100:8100`; refuse to start on a non-loopback host with `AUTH_ENABLED=false` unless `--insecure-bind` is given; test both a loopback and a Docker start (the existing prod compose smoke test is being cut, so keep one equivalent).
**Phase:** Install (Foundation for the refusal test).

### FE-1: Frontend contract drift passes CI
**What goes wrong:** The frontend's types are maintained by hand, and frontend tests mock at the `@/api/*` boundary, so removing endpoints/fields (Integrations settings, `NotificationMetrics` in analytics) leaves Vitest green while the page 404s. [repo: CLAUDE.md, CONCERNS.md]
**Prevention:** delete the pages, API clients and tests in the same PR as the backend; generate an OpenAPI snapshot and diff it in CI; add one real-bundle smoke (the CUT-4 job) that loads the built UI against the real backend and visits each remaining route without console errors.
**Phase:** Cut-A.

### OUT-1: New outcome states fan out to five consumers
**What goes wrong:** Transitions are enforced in `schemas/applications.py::VALID_TRANSITIONS` (not the service layer); there is startup status normalization; the web app, TUI, MCP, extension and analytics each render/accept statuses. "prepared / submit attempted / submission confirmed" added to one of them breaks the others or lets MCP set "confirmed" without evidence. [repo]
**Prevention:** one enum + transition table + display metadata module imported by all consumers; a test that every consumer handles every state; ingestion (parsing an email or page to infer "confirmed") only proposes a transition for human confirmation; migration test for existing rows.
**Phase:** Track.

### DOS-1: Dossier and drafts are personal data in a public repo's working tree
**What goes wrong:** A "readable, versioned dossier" is naturally written as markdown in the repo directory. The repo already tracks profile-shaped paths (`profile/sample/`, `cv/sample/`, sample files only) and has a COE about exactly this (instructed personal files must be gitignored in the same PR). [repo: docs/coe]
**Prevention:** dossier lives under `KESTREL_HOME` by default; any in-repo path is gitignored in the same PR that introduces it; the CI PII gate must have patterns (it fails loudly when empty); versioning via files plus a content hash in SQLite rather than committing history.
**Phase:** Write.

### PLUG-1: The "private plugin" seam silently becomes a public API
**What goes wrong:** The private pipeline shrinks to "config, data and private plugins". Every extension point you expose (entry points, hook names, config keys) becomes something a private repo depends on; renames in the public repo then break the maintainer's daily run, and the failure is invisible to public CI.
**Prevention:** define the seam explicitly (entry-point group, versioned config schema with a `schema_version`, a contract test in the public repo that loads a minimal fake plugin), pin the private repo to released versions, and document deprecation policy. The public repo must not name private things (PII/marker audit lesson from the 2026-07-09 COE).
**Phase:** Retire.

### DEP-1: Extras and dependency floors
**What goes wrong:** `pandas` and `python-jobspy` are in the `dev` extra, not runtime dependencies, so a plain `pip install kestrel-app` cannot run the jobspy adapter (the adapter must degrade loudly, not to zero results); `mcp` is an extra with a vulnerable floor (SEC-1); adding `textual` to base dependencies slows the install and adds a UI dependency to headless servers; removing `icalendar`, `slowapi` (used only for OAuth endpoints) and `warn-scraper` extras must be reflected in lock/audit and docs; `pip-audit` scans only the extras the CI job installed (`dev`, then `mcp`), so a new `tui` extra must be installed in that job or it is never audited. [repo]
**Prevention:** decide extras explicitly (`tui`, `mcp`) vs base; fresh-install test asserts `kestrel scan` works with base install plus ATS sources only; adapters that need an extra raise a clear "install kestrel-app[x]" error and count in the source canary; drop dead dependencies in the cut PRs and keep `pip-audit` strict.
**Phase:** Cut-A (drops), Track/Connect (new extras), Install (assert).

### DOC-1: Docs, Pages, README and repo settings drift
**What goes wrong:** 40+ docs and the root README/CLAUDE.md/`ROADMAP.md` reference removed features (grep shows Pushover in README, REFERENCE.md, testing-strategy, COMPARISON). The repo has a GitHub Pages workflow (`pages-build-deployment`) and `_config.yml`, and CLAUDE.md lists BMAD skills and GSD/BMAD workflow rules that will be stale. Repository secrets and variables outlive workflows: some must survive (`RELEASE_APP_ID`/`RELEASE_APP_KEY` for release-please, `PII_PATTERNS` for the PII gate), others should be removed (provider keys, `SONAR_TOKEN`, `DAILY_SCAN_ENABLED`). Inbound links to deleted docs 404. [repo]
**Prevention:** a docs link-check and a "removed feature names" grep gate (extend the PII gate pattern idea) over tracked markdown; a secrets/variables inventory in the cut PR description with keep/remove per item; do the README rewrite after the cut so it describes the product that exists.
**Phase:** Cut-A, Install.

### PROC-1: The review-trailer gate versus huge deletion diffs
**What goes wrong:** Every PR commit needs a `Reviewed-by ... patch:<id>` trailer bound to its patch-id; any amend/rebase changes the id; the gate also rejects merge commits. A 20k-line deletion commit is slow and noisy to review, and one late fix re-triggers the review loop. A PR over 100 commits cannot be rebase-merged. [repo: CLAUDE.md + CI config]
**Prevention:** one concern per PR; delete in the order from CUT-1; no force-pushed reshuffles after signing; keep deletion commits mechanical (pure `git rm`) separate from edits so review can verify "only deletions" via `git diff --diff-filter=D`.
**Phase:** Cut-A.

---

## Minor Pitfalls

### MIN-1: Stale `build/` and `egg-info`
**What goes wrong:** setuptools reuses `build/lib` and can package deleted modules into a new wheel locally (pypa/wheel#147 style behaviour; a stale `build/lib/career_os` exists in the working tree now). A local "the wheel no longer has pushover" check can be wrong; CI is clean. **Prevention:** `rm -rf build dist src/*.egg-info` before local wheel checks; the CI wheel test runs from a fresh checkout. [search]

### MIN-2: ATS description encoding
**What goes wrong:** Greenhouse's `content` is HTML (reported as entity-escaped), Ashby gives HTML and plain text, Lever gives HTML and plain variants; stripping before unescaping leaves markup or literal entities in prompts and fingerprints. **Prevention:** one normalizer with fixtures per ATS (the repo has `test_html_stripping.py`); fingerprint the normalized text. [search/inferred; verify against live payloads]

### MIN-3: Lever EU, `isListed`, board tokens
**What goes wrong:** Lever EU companies return nothing from the global host; Ashby unlisted postings appear in feeds; board tokens differ from company names. **Prevention:** adapter config carries `region`; skip `isListed=false`; resolve tokens from the careers URL. [docs]

### MIN-4: Headless browser open and port use in smoke tests
**What goes wrong:** `webbrowser.open` after a 2 s sleep in `kestrel start` is noise or a hang on CI. **Prevention:** `--no-browser` everywhere in tests; random port.

### MIN-5: Commit and release-note noise
**What goes wrong:** many `feat!`/`refactor` commits across the cut produce a giant CHANGELOG and, with `bump-minor-pre-major`, a surprise version (CUT-6). **Prevention:** use `chore`/`refactor` types for deletions with a single `feat!:` summary commit if a breaking-change note is wanted; hidden sections in `release-please-config.json` already hide `refactor`, `ci`, `chore`.

---

## Phase-Specific Warnings

| Phase | Likely pitfall | Mitigation |
|-------|----------------|------------|
| Foundation | CUT-2, CUT-3, CUT-4, ADD-1 (resolver), ADD-2 (engine), MIG-1 | Land first, each as its own small PR: relocate `check_review_trailers`, harden `CI Complete`, wheel-content + fresh-venv job, `ensure_schema`, SQLite pragmas + two-process contention test, import-all + OpenAPI tests |
| Cut-A | CUT-1, CUT-5, CUT-6, FE-1, DOC-1, PROC-1 | One integration per PR, leaf-first; forward-only migrations with real-old-DB fixture; freeze publish/release filenames; protection re-check via `gh api` after each workflow deletion |
| Cost | COST-1, COST-2 | Ship the single `BudgetGuard` choke point and error classifier with captured-body contract tests BEFORE the first unattended `kestrel scan` |
| Find | ADD-1, ADD-3, DEDUP-1, ATS-1, SEC-2 (normalize) | Persist every arrival; idempotent keys; scan lock; quarantine-before-close; dedup proposes, never deletes |
| Filter | GEO-1, GEO-2 | No geo config = no gate; held-out split before designing the multi-office rule; report intervals |
| Score+Digest | DIGEST-1, COST-1 (attribution) | Stratified, seeded sample; overturns stay local; provider/spend line in the digest |
| Track | TUI-1, OUT-1 | Service layer only; worker rules; one state table |
| Write | GATE-1, SEC-2, DOS-1 | Fail-closed gates measured with planted fabrications; dossier outside the repo tree |
| Connect | SEC-1, SEC-2 | stdio default, minimal tools, `mcp>=1.23.0`, in-process service calls, tool manifest test |
| Install | INSTALL-1, BIND-1, DEP-1 | Deterministic wheel-based required job + non-blocking live job; README commands extracted; loopback default with Docker override |
| Retire | CUT-7, REPLAY-1, PLUG-1 | Replay over captured days, shadow period with diff ledger, tag last script revision, then delete `tools/` and `daily-scan.yml` |

**Phase ordering rationale (for the roadmapper):**
- Foundation before everything: it is the only way to know a cut did not break the install path or the gate.
- Split the cut. Cut-A early (shrinks the surface the new code must coexist with, and removes Pushover only after the `notify()` seam exists). Cut-B/Retire last, because `tools/` holds the code to be ported and the live daily pipeline.
- Cost before Find ships on cron: the first unattended paid job must already be behind the guard.
- Filter depends on Find's normalized locations (DEDUP-1) and feeds the digest (DIGEST-1).
- Write depends on Cost (paid calls) and the privacy boundary; Connect depends on Write's gates because MCP exposes drafts.

**Research flags for phases:**
- **Cost:** needs deeper research per provider: capture real 402/429/400 bodies for each of the 10 providers (only Anthropic, OpenAI and OpenRouter were checked here from docs); decide ledger design (reserve/settle under `BEGIN IMMEDIATE`).
- **Find:** needs live probing of each ATS for actual rate limits and edge responses (404 board, empty board, EU hosts); vendor docs are silent or thin.
- **Write:** gate efficacy is an open empirical question; plan a small measurement spike for fact-gate recall on planted fabrications and for voice-gate sample requirements.
- **Connect:** re-check MCP spec and SDK security guidance at implementation time (the spec "draft" page was read; versions move quickly).
- **Cut-A (Alembic):** needs a spike that generates a real v0.28.2 database and runs the upgrade with FK settings on and off.
- **Foundation, Track, Install, Filter:** standard patterns; unlikely to need separate research beyond the acceptance criteria above (GEO-2 needs a data-splitting decision, not research).

## Confidence note on sources

The seam's provider tiers rate `websearch` and `webfetch` as LOW by default. Claims marked [docs] were read directly on the vendor's or project's own page on 2026-10-24 (so they are as good as that page is today); claims marked [search] come only from search summaries or third-party writeups and are LOW. Repo and wheel claims are first-hand observations and are not subject to that tiering.

## Sources

Repo (first-hand, 2026-10-24): `.github/workflows/ci.yml`, `publish.yml`, `smoke.yml`, `release-please.yml`, `daily-scan.yml`, `dependabot-automerge.yml`, `release-please-config.json`, `.github/dependabot.yml`, `pyproject.toml`, `src/career_os/{config.py,database.py,main.py,ai/fallback.py,ai/*_provider.py,cli/main.py,discovery/prefilter.py,services/geo/,services/drift_canary.py,services/analytics.py,api/scoring.py,schemas/integrations.py,models/integrations.py}`, `tools/job_scorer.py`, `tools/daily_pipeline.py`, `tests/{conftest.py,test_billing_safety.py,test_no_import_masking_skips.py}`, `tests/eval/geo/`, `docs/coe/*.md`, `.planning/codebase/CONCERNS.md`; branch protection and ruleset via `gh api repos/pleasedodisturb/kestrel/branches/main/protection` and `/rulesets/14971549`; published wheel `kestrel_app-0.28.2-py3-none-any.whl` from files.pythonhosted.org (unzipped listing).

External:
- SQLite DROP TABLE and foreign keys: https://www.sqlite.org/lang_droptable.html (read 2026-10-24)
- SQLite WAL (checkpoint starvation, SQLITE_BUSY cases): https://www.sqlite.org/wal.html (read 2026-10-24)
- SQLAlchemy SQLite dialect, pysqlite transaction control and event recipe: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html (read 2026-10-24)
- Simon Willison on SQLITE_BUSY / BEGIN IMMEDIATE (secondary): https://www.simonwillison.net/2025/Feb/17/sqlite-busy (2025-02-17)
- Alembic batch migrations and foreign keys: https://alembic.sqlalchemy.org/en/latest/batch.html (read 2026-10-24)
- release-please missing extra-file handling (source): https://raw.githubusercontent.com/googleapis/release-please/main/src/github.ts (read 2026-10-24)
- PyPI trusted publisher fields: https://docs.pypi.org/trusted-publishers/adding-a-publisher/ and https://docs.pypi.org/trusted-publishers/using-a-publisher/ (read 2026-10-24)
- GitHub required status check troubleshooting: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks (read 2026-10-24)
- Claude API errors: https://platform.claude.com/docs/en/api/errors ; rate limits and spend caps: https://platform.claude.com/docs/en/api/rate-limits (read 2026-10-24)
- OpenAI 429 quota versus rate limit: https://help.openai.com/en/articles/5955604-troubleshooting-api-rate-limits-and-429-errors and https://cookbook.openai.com/examples/how_to_handle_rate_limits (search summary, LOW-MEDIUM)
- OpenRouter errors: https://openrouter.ai/docs/api-reference/errors (read 2026-10-24)
- Greenhouse Job Board API: https://docs.greenhouse.io/job-board.html ; Lever postings API: https://github.com/lever/postings-api ; Ashby public posting API: https://developers.ashbyhq.com/docs/public-job-posting-api (all read 2026-10-24)
- RapidFuzz fuzz usage (`token_set_ratio` subset behaviour): https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html (read 2026-10-24)
- Textual workers guide: https://textual.textualize.io/guide/workers/ ; testing guide: https://textual.textualize.io/guide/testing/ ; App API (`call_from_thread`): https://textual.textualize.io/api/app/ (read 2026-10-24)
- MCP security best practices: https://modelcontextprotocol.io/specification/draft/basic/security_best_practices (read 2026-10-24)
- CVE-2025-66416 (MCP Python SDK DNS rebinding, fixed in 1.23.0): https://nvd.nist.gov/vuln/detail/CVE-2025-66416 and https://advisories.gitlab.com/pkg/pypi/mcp/CVE-2025-66416/ (search summary, 2025-12-02)
- The lethal trifecta: https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/ (2025-06-16)
- Hidden prompt injection in resumes (Duke-led study, secondary coverage): https://pratt.duke.edu/news/thwarting-prompt-injection/ and https://letsdatascience.com/news/researchers-measure-resume-screening-prompt-injections-7032c127 (2026; the paper was not opened)
- LLM agent retry-cost amplification writeups (secondary, LOW): https://tianpan.co/blog/2026-04-16-retry-budget-llm-agent-cost-amplification
- Stale `build/` contents in wheels: https://github.com/pypa/wheel/issues/147 and https://pypi.org/project/check-wheel-contents/ (search summary, LOW)
