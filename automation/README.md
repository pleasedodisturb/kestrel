# Automation — Daily Job Search Pipeline

Automated daily job discovery: scrape → score → deduplicate → digest.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SCHEDULER                             │
│  GitHub Actions (recommended) / cron / n8n / launchd    │
└───────────────┬─────────────────────────────────────────┘
                │ triggers daily
                ▼
┌─────────────────────────────────────────────────────────┐
│              daily_pipeline.py                            │
│                                                          │
│  Step 1: SCRAPE ──────────────────────────────────────┐ │
│    │  scrape_resilient.py (8 sources)                │ │
│    ├─ Germany APIs (Arbeitsagentur, Arbeitnow)  [API]  │ │
│    ├─ JobSpy (LinkedIn, Indeed, Glassdoor)       [HTTP] │ │
│    ├─ Remotive, RemoteOK, Jobicy              [API]  │ │
│    ├─ AI-Jobs.net                              [API]  │ │
│    ├─ WWR, GermanTechJobs                      [RSS]  │ │
│    └─ Browser fallback (Playwright)          [optional] │ │
│                                                          │
│  Step 2: SCORE ───────────────────────────────────────┐ │
│    │  GPT-4o-mini (or keyword fallback)               │ │
│    └─ fit_score, salary, effort, prep_level           │ │
│                                                          │
│  Step 3: DEDUP ───────────────────────────────────────┐ │
│    │  Compare against tracking/applications.csv       │ │
│    └─ Skip already-tracked (company + role match)     │ │
│                                                          │
│  Step 4: FILTER ──────────────────────────────────────┐ │
│    └─ Keep only score >= PIPELINE_MIN_SCORE           │ │
│                                                          │
│  Step 5: DIGEST ──────────────────────────────────────┐ │
│    ├─ tracking/daily-scan-YYYY-MM-DD.md               │ │
│    ├─ tracking/scraped_scored_YYYY-MM-DD.json         │ │
│    └─ GitHub Actions summary (if in Actions)          │ │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### Option 1: GitHub Actions (Recommended)

1. Add your OpenAI API key as a repo secret:
   - Go to Settings → Secrets and variables → Actions
   - Add `OPENAI_API_KEY`

2. Optionally set your location as a repo variable:
   - Settings → Secrets and variables → Actions → Variables
   - Add `PIPELINE_LOCATION` = `Your City`

3. The workflow runs Mon-Fri at 07:00 UTC automatically.
   Trigger manually: Actions → Daily Job Scan → Run workflow.

### Option 2: cron (Linux)

```bash
# Edit crontab
crontab -e

# Add this line (runs Mon-Fri at 7am local time):
0 7 * * 1-5 /path/to/kestrel/automation/cron_runner.sh >> /path/to/kestrel/logs/cron.log 2>&1
```

Make sure `OPENAI_API_KEY` is in your `.env` file or shell profile.

### Option 3: launchd (macOS)

```bash
# Edit the plist — update all paths marked "UPDATE THIS PATH"
vim automation/com.kestrel.daily-scan.plist

# Install
cp automation/com.kestrel.daily-scan.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.kestrel.daily-scan.plist
```

### Option 4: n8n

1. Import `automation/n8n_workflow.json` into n8n
2. Update all paths in the Execute Command nodes
3. Configure OPENAI_API_KEY in n8n environment
4. Enable notification nodes (Telegram/email) and configure credentials
5. Activate the workflow

## Configuration

All config via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | OpenAI API key for GPT-4o-mini scoring |
| `PIPELINE_MODE` | `api-only` | `api-only` / `api-plus` / `all` |
| `PIPELINE_MIN_SCORE` | `5` | Minimum fit score to include in digest |
| `PIPELINE_HOURS_OLD` | `24` | Max posting age in hours |
| `PIPELINE_LOCATION` | `Berlin` | Primary search location |
| `PIPELINE_DRY_RUN` | `0` | Set to `1` to skip CSV writes |

### Scraping Modes

| Mode | Sources | Risk | Speed |
|------|---------|------|-------|
| `api-only` | Germany APIs + JobSpy HTTP | Zero — pure APIs | Fast (~2 min) |
| `api-plus` | Above + career page browser scraping | Low — headless for specific URLs only | Medium (~5 min) |
| `all` | All sources including browser fallback | Medium — more network activity | Slow (~10 min) |

## About Browser Scraping (LinkedIn, etc.)

**The problem:** LinkedIn, Indeed, and other major job boards actively detect and block automated access. Using a headless browser to scrape them at scale risks:
- IP bans
- Account suspension
- Legal issues (ToS violations)
- CAPTCHAs and bot detection

**Our approach:**
1. **API-first:** python-jobspy uses HTTP requests to public listing pages — no login required, minimal detection risk
2. **Germany APIs:** Arbeitsagentur and Arbeitnow have official, free APIs — zero risk
3. **Browser fallback:** Only for specific company career pages you explicitly configure, with:
   - Random delays (2-5s between requests)
   - User-agent rotation
   - Viewport randomization
   - No webdriver flag
   - Exponential backoff on failures

**If you need authenticated LinkedIn data** (saved jobs, Easy Apply, recruiter messages), use the LinkedIn MCP or Browser MCP in an interactive Claude Code session — not in automated scraping.

## Output Files

| File | Purpose |
|------|---------|
| `tracking/daily-scan-YYYY-MM-DD.md` | Human-readable digest with ranked table |
| `tracking/scraped_raw_YYYY-MM-DD.json` | Raw scrape results (all sources) |
| `tracking/scraped_scored_YYYY-MM-DD.json` | Scored results with fit analysis |
| `logs/pipeline_YYYYMMDD_HHMMSS.log` | Full pipeline execution log |

## Cost

- **Germany APIs:** Free
- **JobSpy:** Free (public HTTP scraping)
- **AI Scoring:** ~$0.01-0.02 per job via GPT-4o-mini. 100 jobs/day ≈ $1-2/day ≈ $30-60/month
- **GitHub Actions:** Free for public repos. Private: 2000 min/month free tier.

## Troubleshooting

**Pipeline exits with code 2:**
Partial failure — some sources failed but digest was still generated. Check logs.

**No jobs found:**
- Check your internet connection
- Verify JobSpy is installed: `.venv/bin/pip install python-jobspy`
- Try running sources individually: `.venv/bin/python tools/germany_jobs.py --preset all`

**Scoring returns all 5s:**
- Check `OPENAI_API_KEY` is set and valid
- The fallback keyword scorer is being used — scores will be rough

**GitHub Actions not running:**
- Check the workflow is enabled (Actions tab → select workflow → Enable)
- Verify secrets are set correctly
- Check the Actions tab for error logs
