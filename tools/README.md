# Job Search Tools

## Setup

```bash
pip install -r requirements.txt
```

## Scripts

### scraper.py

Pre-configured job scraper using [python-jobspy](https://github.com/cullenwatson/JobSpy). Searches multiple job boards for TPM/Product/AI roles in Frankfurt and remote Europe.

```bash
python tools/scraper.py
```

Output: `tracking/scraped_jobs_{date}.csv`

### job_scorer.py

Scores scraped jobs against your profile criteria using OpenAI API. Requires `OPENAI_API_KEY` environment variable.

```bash
export OPENAI_API_KEY=your_key_here
python tools/job_scorer.py tracking/scraped_jobs_2026-02-22.csv
```

Output: Adds `fit_score` and `fit_reasoning` columns to the CSV.
