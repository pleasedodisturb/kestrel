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

## Data Tools (stable)

### update_sheet.py / validate_sheet.py
Google Sheets integration for daily scan logging. Requires Google service account credentials.

### research_jobs.py / research_remotely.py
Research tools for finding jobs on specific platforms.
