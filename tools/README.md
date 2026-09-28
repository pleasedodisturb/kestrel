# Kestrel Tools

CLI automation scripts for job search operations. These run standalone or are called by the daily pipeline.

## Setup

```bash
pip install -r requirements.txt
```

## Discovery & Scoring (stable)

### scraper.py
Multi-board job scraper using [python-jobspy](https://github.com/cullenwatson/JobSpy). Searches Indeed, LinkedIn, Glassdoor.

```bash
python tools/scraper.py
```

### germany_jobs.py
Searches Arbeitsagentur and Arbeitnow (German job boards, no API key needed).

```bash
python tools/germany_jobs.py
```

### job_scorer.py
Scores scraped jobs against your profile using AI. Requires `OPENAI_API_KEY` or `OPENROUTER_API_KEY`.

```bash
python tools/job_scorer.py tracking/scraped_jobs_2026-01-15.csv
```

### daily_pipeline.py
Runs the full discovery + scoring pipeline. Used by the GitHub Actions daily-scan workflow.

```bash
python tools/daily_pipeline.py
```

### local_scorer.py
Scores jobs using a local LLM (Ollama). No API key needed.

```bash
python tools/local_scorer.py
```

### source_registry.py
Scan-source registry: every source is reported on every run with a count or a `ZERO` plus reason, so a broken source never looks like a source with nothing to return. Called from `scrape_resilient.py`.

### tier0_ats_poller.py
Polls the public Greenhouse, Lever and Ashby JSON endpoints of your dream companies directly, ahead of aggregator lag.

### batch_probe.py
Authoritative geo-eligibility gate plus ATS office introspection for a batch of scored jobs.

### blocklist.py
Word-boundary company blocklist and soft flags from `config/blocklist.yaml` (copy `config/blocklist.example.yaml`).

## Labelling & Calibration (stable)

Measure the pre-filter against your own ground truth. Two to five hundred labels is calibration, not training.

### build_label_set.py
Builds a stratified, blind label set from your own discovered jobs.

### annotate.py
Blind two-axis annotation of that set: could you win it cold, and do you want it.

### calibrate.py
Precision and recall report for the filter against your labels, and a sanity check on the labels themselves.

## CV & Cover Letter Tools (stable)

### render_tailored_cvs.py
Generates multiple tailored CV variants from your base cv.yaml using RenderCV.

### render_cover_letter_html.py
Renders cover letter markdown to styled HTML.

### md_to_pdf_cover_letter.py
Converts cover letter markdown to PDF using WeasyPrint.

### generate_batch_covers.py
Batch-generates cover letters for multiple companies.

## Auto-Apply Tools (experimental)

> **Status: Work in progress.** These tools can fill out job application forms automatically,
> but form filling is not 100% reliable across all ATS platforms. Captcha solving depends
> on anti-captcha.com credits and has known issues with session binding on some sites
> (especially Lever). Use with caution and always review before submitting.

### batch_apply_browser.py
Browser-based form filling using Playwright. Reads applications from YAML config, fills out ATS forms (Greenhouse, Ashby, Workable), optionally solves captchas.

Requires:
- `config/personal.yaml` (your details)
- `ANTICAPTCHA_KEY` in `.env` (optional, for captcha solving)
- A submission YAML file (see `applications-to-submit.yaml.example`)

### captcha_solver.py
hCaptcha solver using anti-captcha.com API. Called by `batch_apply_browser.py` when captchas are encountered.

Requires `ANTICAPTCHA_KEY` environment variable. Sign up at https://anti-captcha.com ($10 of credits lasts a long time).

### auto_apply.py
Hybrid API + browser auto-apply. Attempts API submission first, falls back to browser automation.

### scrape_form_questions.py
Scrapes ATS form fields before submission to prepare answers in advance.

## Apply Kit (tiered operating model)

### kit_builder.py
Builds T2 rapid-fire application kits: one numbered folder per application with a `SUBMIT.txt` and rendered cover PDFs.

### t3_lane.py
T3 lane: auto-fills an apply form up to, but never past, the submit button, then queues it for a human to confirm.

### open_question_probe.py
Detects required free-text questions on an ATS apply form (authoritative for Greenhouse) so those roles are routed away from the T3 lane.

## Data Tools (stable)

### update_sheet.py / validate_sheet.py
Google Sheets integration for daily scan logging. Requires Google service account credentials.

### research_jobs.py / research_remotely.py
Research tools for finding jobs on specific platforms.

## Ops

### snapshot_db.py
Atomic, rotating SQLite online-backup snapshots of the Kestrel database.

## Agent

### kestrel-mcp/
MCP server that exposes `list_pipeline`, `pipeline_stats`, `score_job` and `discover_jobs` to Claude Code. See `tools/kestrel-mcp/README.md`.
