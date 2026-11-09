<p align="center">
  <img src="assets/illustrations/hero-navy.webp" alt="Kestrel" width="280">
</p>

<h1 align="center">Kestrel</h1>

<p align="center">
  <strong>A job search system that runs on your computer.</strong><br>
  Finds jobs. Scores them against your profile. Tracks your pipeline. Your data stays yours.
</p>

---

**Status, 2026-11-09.** The current release is [v0.28.2](CHANGELOG.md). Kestrel is being rebuilt as **v2.0 "Lean Kestrel"**: one loop you run from the terminal, instead of a platform that tries to do everything. This page says what works today, what is being built, what is being removed, and what is still only a plan. Nothing here is aspirational unless it sits under a heading that says so.

**[Walkthrough](#walkthrough)** · **[Install](#install)** · **[Status](#status)** · **[AI and privacy](#ai-and-privacy)** · **[Docs](#docs)**

---

## What it is

- **Finds jobs** on Indeed, Arbeitnow and Arbeitsagentur (the German federal job board), and takes any posting you paste.
- **Scores each one** against your profile with an LLM of your choice, or with the built-in mock provider at zero cost. The scorer is measured: a [golden-set eval harness](tests/eval/README.md) runs the production code path in nightly CI and fails the build on a regression.
- **Tracks the search** in a local SQLite file: applications, statuses, notes, follow-ups, contacts.

What it will not do: auto-apply across job boards, scrape a logged-in LinkedIn session, send telemetry, or share anything about you with anyone. Kestrel drafts and tracks. You decide and you send.

Looking for something bigger and more established? [career-ops](https://github.com/career-ops-hq/career-ops) solves the same problem as a skill layer for AI coding CLIs, with a large community. Kestrel is a different shape: a running system with its own state, evals and cost guards.

## Walkthrough

Five frames, in the order you would use them. Every block is real output from the code on `main`, run with the mock provider on a fresh database (no API key, no cost). The companies are the built-in sample data plus three made-up entries. A terminal recording will replace these frames once the v2.0 terminal UI exists.

**1. Start.** The first run creates the database, applies migrations, adds a default profile and ten sample jobs, and serves the local web app.

```console
$ kestrel start --host 127.0.0.1
$ kestrel doctor
Kestrel Doctor -- Health Check
  check Python 3.14.10
  check Database connected
  check Migrations applied
  check Default profile: Kestrel User
  check Demo data restored (10 jobs)
  5/5 checks passed
```

**2. Find.** Sweep the job boards for your keywords. This one needs the network, so no output is shown here.

```console
$ kestrel discover --keywords "program manager" --location Berlin
```

**3. Triage.** Everything found lands in one list, scored, newest first (output trimmed).

```console
$ kestrel pipeline list
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━┓
┃ ID ┃ Company                 ┃ Role                        ┃ Status     ┃ Score ┃ Date       ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━┩
│ 13 │ Harbor Analytics        │ Product Operations Lead     │ discovered │     — │ 2026-11-09 │
│ 12 │ Lumen Health            │ Senior Product Manager      │ discovered │     — │ 2026-11-09 │
│ 11 │ Northwind Robotics      │ Technical Program Manager   │ discovered │     — │ 2026-11-09 │
│  8 │ Quantum Robotics Ltd    │ Senior Backend Engineer     │ discovered │  88.6 │ 2026-11-08 │
│  1 │ Vantage Analytics GmbH  │ Senior Data Engineer        │ discovered │  91.2 │ 2026-11-07 │
│  2 │ NovaPay Solutions       │ Growth Marketing Lead       │ discovered │  72.4 │ 2026-11-06 │
└────┴─────────────────────────┴─────────────────────────────┴────────────┴───────┴────────────┘
```

**4. Track.** Add a posting by hand, move it through the stages, read the numbers. Status changes follow a fixed state machine, so a job cannot jump from discovered to applied without passing through interested (statistics output trimmed).

```console
$ kestrel pipeline add --company "Northwind Robotics" --role "Technical Program Manager"
✓ Added application #11: Northwind Robotics — Technical Program Manager (status: discovered)
$ kestrel pipeline update 11 --status interested --notes "Strong match on programme scope"
✓ Updated application #11 (Northwind Robotics): status → interested, notes
$ kestrel pipeline stats
Pipeline Statistics
  Total applications: 13
  Average fit score:  58.0
  Date range:         2026-11-02 to 2026-11-09
```

**5. Score one posting.** Paste a URL and get the fit score with its reasoning.

```console
$ kestrel score https://example.com/jobs/technical-program-manager
```

`kestrel --help` lists the rest: `coach`, `market`, `research`, `skills`, `goals`, `interview-prep`, `contacts`, `extension`.

## Install

Requires Python 3.11 or newer. Two paths work today.

**From source** (recommended while v2.0 is in progress):

```bash
git clone https://github.com/pleasedodisturb/kestrel.git && cd kestrel
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
kestrel start --host 127.0.0.1
```

**From PyPI:**

```bash
pip install kestrel-app
kestrel start --host 127.0.0.1
```

The PyPI package gives you the same CLI. Its bundled web interface is an older build than the one in this repository.

Two things to know before the first run:

- Run `kestrel start` once before any other command. It is the step that creates and migrates the database; the other commands do not do that yet.
- Pass `--host 127.0.0.1`. Without it the server listens on every network interface, and authentication is off unless you set `AUTH_ENABLED=true` and `AUTH_API_KEY`.

Step-by-step help: [Quickstart](docs/guides/QUICKSTART.md) and [FAQ](docs/guides/FAQ.md).

## Status

### Works today

| Area | What you get |
|------|--------------|
| Discovery | Three sources in the app (Indeed, Arbeitnow, Arbeitsagentur), a pre-filter that drops clear mismatches before any paid call, weekly scheduled sweeps |
| Scoring | Role-fit gate, batch scoring, calibration, ESCO occupation signals, a nightly eval gate on the production scorer ([how scoring works](docs/guides/how-scoring-works.md)) |
| Geo eligibility | Seven classes (home, relocate, visa-free, visa-required, remote-eligible, foreign, unknown) checked against a committed reference set ([guide](docs/guides/geo-eligibility.md)) |
| Pipeline | Applications with an enforced status state machine, notes, follow-ups, statistics, contacts and referrals |
| CLI | Every command in the walkthrough, plus skills and gap analysis, goals, interview prep, company research, market summary |
| AI providers | Ten behind one interface (Anthropic, OpenAI, Mistral, Gemini, Groq, Together, OpenRouter, Ollama, Hugging Face, xAI) plus the mock provider, with fallback chains, cost presets and response caching |
| Browser extension | Chrome, version 1: capture a posting on LinkedIn jobs, Greenhouse, Lever or Ashby, see the fit score, send it to the pipeline. No form filling |
| Web app | FastAPI and React, served by `kestrel start`. It works and it is frozen: v2.0 does not build on it |

### In progress: v2.0 Lean Kestrel

The goal is one loop a real person can run: find and triage jobs, write in your own voice, learn from every outcome. The maintainer moves his own daily search onto it, and a technical stranger should get from clone to a first useful job list in 15 minutes.

| Phase | What it does | Progress |
|-------|--------------|----------|
| Map | Freeze today's behaviour as evidence before anything is ported or cut: script ledger, golden outputs, red tests for every later behaviour, a verdict for every flow and feature | 4 of 6 plans done |
| Foundation | Safety nets first: CI that fails closed, one home folder, loopback bind by default, no identifying profile fields in cloud scoring prompts, a spend limit no caller can bypass | Planned |
| Cut A | Remove what nothing depends on, one pull request per item | Planned |
| Find, Filter, Scan, Score, Track, Write, Connect, Apply, Retire, Install | The loop itself, built in this order, each phase reviewed before it starts | Not yet planned in detail |

**Being removed in Cut A:** the one-click cloud deploy template, the browser-IDE demo environment, TickTick sync, the side packages `worker/` and `dashboard/`, and release channels nobody uses. The web app stays in the repository but is no longer built, tested or shipped.

### Want to do

- A terminal UI for the whole loop: single-key status changes, open the posting, read the scoring report.
- **Learns you.** A model of your voice and of you as a person, built from your own writing and from what you keep, rewrite or throw away. It then shapes scoring explanations, drafts and interview prep.
- Writing help in your voice: CV, cover letters, outreach.
- Extension version 2: fill application forms for review and stop at the submit button. A Firefox build.
- `kestrel demo`: the whole loop on synthetic data with no keys, and a terminal recording of it on this page.
- A path for people who do not use a terminal, and profiles other than the maintainer's (planned for v2.1).

### Should do

Known gaps in what ships today. Each one has a place in the v2.0 plan.

- The CLI cannot set up a fresh install by itself. Only `kestrel start` applies migrations, and `kestrel init --skip` refuses to run without an interactive terminal.
- `kestrel start` listens on all interfaces with authentication off by default.
- The scoring prompt includes your profile name and email next to your skills and goals. Score with Ollama or Anthropic if that matters to you (see below).
- The PyPI package ships an older web interface build than the repository.
- Discovery through JobSpy is fixed to Indeed and Germany.

The longer view, with every shipped milestone, is in [ROADMAP.md](ROADMAP.md). It predates the v2.0 decision.

## AI and privacy

Kestrel runs out of the box with the mock provider: free, offline, no account. For real scoring you bring your own key. Set `AI_PROVIDER` and the matching key in `.env`; a cost preset (Free, Budget, Quality, Private, Custom) picks the model, the pre-filter strictness and the batch size in one setting.

- **Cost.** The Budget preset scores a month of discovery for under a dollar. If you chain providers with `AI_PROVIDER_FALLBACK`, order them cheap first: whatever sits last is what you pay when the cheaper ones run out of quota. Details and worked numbers: [cost guide](docs/guides/cost-optimization.md).
- **Where your data lives.** In one SQLite file on your machine. Nothing leaves it unless you configure an AI provider or an integration.
- **What is enforced.** The two features the code classes as personal, conversation mode and interview prep, refuse to run on any provider outside the allowlist in `src/career_os/ai/privacy.py` (Ollama and Anthropic, plus the mock providers). Everything else, scoring included, is classed as job-market data and runs on any provider. The check goes by provider name; it does not verify the retention settings of your own account.
- **Choosing.** Ollama keeps everything local. OpenRouter gives one account for many models. Per-provider retention and pricing: [AI providers](docs/reference/AI-PROVIDERS.md) and the [plain-language guide](docs/guides/ai-providers-guide.md).

## Docs

| Start here | Go deeper |
|------------|-----------|
| [Quickstart](docs/guides/QUICKSTART.md) | [Features and API reference](docs/reference/REFERENCE.md) |
| [FAQ](docs/guides/FAQ.md) | [How scoring works](docs/guides/how-scoring-works.md) and the [eval harness](tests/eval/README.md) |
| [Comparison with other tools](docs/guides/COMPARISON.md) | [Cost optimisation](docs/guides/cost-optimization.md) |
| [Contributing](CONTRIBUTING.md) | [Security policy](SECURITY.md) and [changelog](CHANGELOG.md) |

## License

[AGPL-3.0](LICENSE). Free and open source. If you modify Kestrel and offer it as a service, you must share your changes under the same license.

**Data sources.** ESCO (European Skills, Competences, Qualifications and Occupations): the bundled skills and occupations taxonomies are © European Union, [esco.ec.europa.eu](https://esco.ec.europa.eu), reused under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) per Commission Decision 2011/833/EU. Kestrel ships processed, English-only subsets; changes are described in each fixture's metadata.
