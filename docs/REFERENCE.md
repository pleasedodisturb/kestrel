<h1 align="center">
  <br>
  Kestrel
  <br>
</h1>

<p align="center">
  <strong>A self-hosted job search platform.</strong><br>
  Precision over volume.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React 19">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLite-3-003B57?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/Tests-1773_passing-22c55e?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="MIT License">
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> -
  <a href="#features">Features</a> -
  <a href="#architecture">Architecture</a> -
  <a href="#cli-reference">CLI</a> -
  <a href="#api-reference">API</a> -
  <a href="#configuration">Config</a> -
  <a href="#daily-scan-automated-job-discovery">Daily Scan</a>
</p>

---

## What is this?

Kestrel is a self-hosted job search platform that treats your job hunt like a system, not a spreadsheet. It discovers jobs from multiple boards, scores them against your profile using AI, tracks your pipeline on a Kanban board, and automates the tedious parts. Runs entirely on your machine - your data stays yours. Works offline with a mock AI provider, or connect OpenRouter for real scoring.

Named after the small falcon that hovers with precision before striking. The philosophy here is the same - find the right opportunities instead of carpet-bombing applications.

---

## Quick Start

No coding required. You just need [Docker Desktop](https://www.docker.com/products/docker-desktop/) (free).

### If you're comfortable with the command line

```bash
git clone https://github.com/pleasedodisturb/kestrel.git && cd kestrel
./setup.sh
```

### If you've never used a terminal before

1. **Install Docker Desktop** - download from [docker.com](https://www.docker.com/products/docker-desktop/), install like any other app. Free for personal use, skip the account creation if it asks.
2. **Open Docker Desktop** and wait for the whale icon in your menu bar to stop animating. Keep it running.
3. **Download Kestrel** - click the green **Code** button at the top of this page, then **Download ZIP**. Unzip the file.
4. **Open Terminal** - press Cmd+Space, type "Terminal", press Enter.
5. **Type these two commands** (press Enter after each):
   ```
   cd ~/Downloads/kestrel-main
   bash setup.sh
   ```
6. **Wait 2-3 minutes** for the first build. Don't close the window.
7. **Open your browser** to [http://localhost:8101](http://localhost:8101)

That's it. Your job search dashboard is running.

> **New to all this?** See the full [Quickstart Guide](docs/QUICKSTART.md) with detailed explanations at every step, or check the [FAQ](docs/FAQ.md) if you get stuck.

If `setup.sh` fails, it will tell you what went wrong and how to fix it. The most common issue is Docker not running - just open Docker Desktop and try again.

---

## What you get out of the box

- **Kanban pipeline** - drag-and-drop application tracking across stages
- **AI job scoring** - multi-factor fit scoring (0-10) against your profile
- **Multi-board discovery** - automated scraping from Indeed, LinkedIn, Glassdoor, and more
- **Interview prep** - company research dossiers, mock questions, STAR story library
- **Skills gap analysis** - compare your skills to target roles with coaching suggestions
- **Cover letter tools** - AI-assisted generation and voice review mode
- **Calendar integration** - iCal feed for interviews, deadlines, and follow-ups
- **Push notifications** - alerts for overdue follow-ups and new high-scoring matches
- **Mock AI provider** - everything works offline, zero cost to start

---

## How to add real AI

The mock provider returns realistic but static data. To get actual AI-powered scoring, research, and coaching:

1. Sign up at [OpenRouter](https://openrouter.ai) and grab an API key
2. Edit your `.env` file:
   ```
   AI_PROVIDER=openrouter
   OPENROUTER_API_KEY=sk-or-...
   ```
3. Restart: `docker compose restart`

OpenRouter gives you access to Claude, GPT, Gemini, and others through a single key. You can also connect directly to Anthropic, OpenAI, Gemini, or Together AI - see the [Configuration](#configuration) section.

---

## How to customize

**Set up your profile** - Edit files in `profile/` to tell the AI about your experience, target roles, and preferences. The scoring engine uses this to evaluate fit.

**Configure search profiles** - Define what roles, locations, and salary ranges to search for. The discovery system uses these to find relevant postings.

**Customize scoring** - The AI scoring considers technical fit, seniority alignment, compensation, location, and career trajectory. Weights are adjustable.

**Add your CV** - Drop your CV into `cv/` for the cover letter tools and application tracking.

---

## Features

### Pipeline Management

| Capability | Description |
|:---|:---|
| Kanban Board | Drag-and-drop application tracking across stages (bookmarked - offer - accepted) |
| Application CRUD | Full lifecycle management with company, role, salary, notes, and status transitions |
| Follow-Up Engine | Automated reminders with overdue detection and snooze support |
| Ghost Detection | Identifies stale applications that have gone silent |
| Analytics Dashboard | Pipeline velocity, conversion funnels, status distribution, and activity trends |

### Skills Intelligence

| Capability | Description |
|:---|:---|
| Skills Parsing | Extract and categorize skills from job descriptions and profiles automatically |
| Gap Analysis | AI-powered comparison of your skills against target roles with severity scoring |
| Coaching Suggestions | Prioritized action plans with estimated hours, difficulty, and focus areas |
| Career Goals | Goal setting with milestone tracking, recalibration, and market-data-backed adjustments |
| Learning Paths | Curated resource recommendations matched to your skill gaps |

### Discovery and Scoring

| Capability | Description |
|:---|:---|
| Job Discovery | Automated scraping with configurable search profiles and scheduled sweeps |
| AI Fit Scoring | Multi-factor scoring (0-10) with detailed breakdown, readiness %, and career alignment |
| Market Intelligence | Salary data, demand trends, role comparisons, and geographic insights |
| Role Intelligence | Technology landscape analysis, skill demand patterns, and career trajectories |
| Advanced Search | Full-text search with filters across salary, location, score, and status |

### Interview Preparation

| Capability | Description |
|:---|:---|
| Company Research | AI-generated dossiers - tech stack, funding, Glassdoor signals, hiring patterns, ATS detection |
| Interview Formats | Company-specific round breakdowns with duration estimates and process descriptions |
| Mock Questions | Role-tailored practice questions organized by category and difficulty |
| STAR Stories | Structured situation-task-action-result story library with full CRUD |
| Prep Checklists | Prioritized preparation items with time estimates and total hours calculation |

### Integrations and Voice

| Capability | Description |
|:---|:---|
| TickTick Sync | Bi-directional task synchronization with automatic follow-up to task mapping |
| Calendar Export | iCal feed generation for interviews, deadlines, and follow-ups |
| TimingsApp | Time tracking integration for job search effort analytics |
| Pushover Notifications | Push alerts for overdue follow-ups, status changes, and discovery results |
| Voice Mode | Real-time AI voice discussions - cover letter review, coaching, and job evaluation |
| AI Health Monitor | Provider status dashboard with latency tracking and feature availability |

---

## Architecture

```
                  +--------------+
                  |   React 19   |  :8101
                  |  Vite - TW4  |
                  +------+-------+
                         | HTTP/JSON
                  +------+-------+
                  |   FastAPI    |  :8100
                  |  Uvicorn     |
                  +--------------+
                  |  AI Provider |---> Mock | OpenRouter | Anthropic | OpenAI | Gemini | Together
                  +--------------+
                  |  SQLAlchemy  |
                  |  + Alembic   |
                  +------+-------+
                         |
                    +----+----+
                    | SQLite  |
                    +---------+
```

### Project Structure

```
kestrel/
├── src/career_os/
│   ├── ai/                    # AI provider abstraction
│   │   ├── base.py            #   Abstract interface (complete, score)
│   │   ├── factory.py         #   Provider factory
│   │   ├── mock_provider.py   #   Full offline mock (all 13 features)
│   │   └── openrouter_provider.py
│   ├── api/                   # FastAPI route handlers (25 routers)
│   │   ├── applications.py    #   Pipeline CRUD + status transitions
│   │   ├── discovery.py       #   Job scraping + search profiles
│   │   ├── scoring.py         #   AI fit scoring
│   │   ├── skills.py          #   Skills inventory
│   │   ├── gaps.py            #   Gap analysis
│   │   ├── coaching.py        #   AI coaching
│   │   ├── goals.py           #   Career goals
│   │   ├── interview_prep.py  #   Interview preparation
│   │   ├── star_stories.py    #   STAR story management
│   │   ├── voice.py           #   Voice mode sessions
│   │   ├── ticktick.py        #   TickTick integration
│   │   ├── calendar.py        #   iCal export
│   │   ├── pushover.py        #   Push notifications
│   │   ├── timingsapp.py      #   Time tracking
│   │   └── ...                #   analytics, market, research, etc.
│   ├── cli/main.py            # Typer CLI (full-featured)
│   ├── discovery/             # Background job scheduler
│   ├── migration/             # Alembic + seed data
│   ├── models/                # SQLAlchemy models (17 modules)
│   ├── schemas/               # Pydantic schemas (29 modules)
│   ├── services/              # Business logic (33 modules)
│   ├── config.py              # Pydantic settings
│   ├── database.py            # Session factory
│   └── main.py                # App entry + lifespan
├── frontend/src/
│   ├── pages/                 # Route pages
│   │   ├── Pipeline.tsx       #   Kanban board
│   │   ├── ApplicationDetail.tsx  # Deep-dive view
│   │   ├── Discovery.tsx      #   Job discovery
│   │   ├── Skills.tsx         #   Skills management
│   │   ├── Learning.tsx       #   Learning paths
│   │   ├── Analytics.tsx      #   Charts and metrics
│   │   ├── VoiceDiscussion.tsx    # Voice mode UI
│   │   ├── AIHealthDashboard.tsx  # Provider monitoring
│   │   └── SettingsPage.tsx   #   Integration config
│   ├── components/            # Reusable UI components
│   │   ├── KanbanBoard.tsx    #   Drag-and-drop board
│   │   ├── InterviewPrepSection.tsx
│   │   ├── StarStoriesSection.tsx
│   │   ├── CalendarSection.tsx
│   │   ├── IntegrationPanel.tsx
│   │   └── ...
│   └── api/                   # API client layer (17 modules)
├── alembic/                   # Database migrations
├── tests/                     # 42 test modules, 1773 tests
├── docker-compose.yml         # Backend + Frontend orchestration
├── Dockerfile                 # Backend image
├── Dockerfile.frontend        # Frontend image
└── pyproject.toml             # Project metadata + dependencies
```

### AI Provider System

The AI layer uses an abstract provider pattern. All providers implement `complete()` and `score()` with typed responses for 13 feature types:

```
AIFeature
├── complete                    General completions
├── score                       Job fit scoring
├── gap_analysis                Skills gap analysis
├── coaching                    Career coaching suggestions
├── goal_recalibration          Market-based goal adjustment
├── interview_prep              Interview topics + questions
├── company_research            Company dossier generation
├── learning_recommendations    Resource curation
├── interview_format            Round-by-round breakdowns
├── interview_patterns          Role-specific question patterns
├── voice_cover_letter          Cover letter voice review
├── voice_coaching              Voice coaching sessions
└── voice_job_evaluation        Voice job evaluation
```

Switch providers with a single environment variable:

```bash
AI_PROVIDER=mock              # Offline, deterministic (default)
AI_PROVIDER=openrouter        # Claude, GPT via OpenRouter
AI_PROVIDER=anthropic         # Direct Anthropic API
AI_PROVIDER=openai            # Direct OpenAI API
AI_PROVIDER=gemini            # Google Gemini
AI_PROVIDER=together          # Together AI
```

---

## CLI Reference

Kestrel ships a comprehensive Typer CLI with Rich formatting.

```bash
kestrel --help                         # Show all commands

# -- Pipeline --
kestrel pipeline list                  # List all applications
kestrel pipeline list -s applied       # Filter by status
kestrel pipeline add                   # Add new application
kestrel pipeline update <id> --status interviewing
kestrel pipeline stats                 # Conversion stats
kestrel pipeline follow-ups            # Pending follow-ups

# -- Skills --
kestrel skills list                    # Your skill inventory
kestrel skills gaps <app_id>           # Gap analysis for a role

# -- Goals --
kestrel goals show                     # Current goals and progress

# -- Coaching --
kestrel coach <app_id>                 # AI coaching for application

# -- Discovery --
kestrel discover --role "Engineer"     # Run a discovery sweep
kestrel discover --location "Remote" --min-salary 120000

# -- Scoring --
kestrel score <app_id>                 # AI fit score breakdown

# -- Market Intelligence --
kestrel market <role>                  # Salary and demand data

# -- Research --
kestrel research <app_id>             # Company research dossier

# -- Interview Prep --
kestrel interview-prep <app_id>        # Generate full prep package
kestrel interview-prep stories add     # Add a STAR story
kestrel interview-prep stories view    # Browse story library
kestrel interview-prep stories edit <id>
```

---

## API Reference

The backend exposes a RESTful API at `http://localhost:8100`. Interactive docs at `/docs` (Swagger) and `/redoc`.

### Endpoints by Feature

<details>
<summary><strong>Pipeline and Applications</strong></summary>

```
GET     /api/applications           List applications (filterable)
POST    /api/applications           Create application
GET     /api/applications/{id}      Get application detail
PUT     /api/applications/{id}      Update application
DELETE  /api/applications/{id}      Delete application
PATCH   /api/applications/{id}/status   Transition status
GET     /api/analytics/summary      Pipeline analytics
```
</details>

<details>
<summary><strong>Follow-Ups</strong></summary>

```
GET     /api/follow-ups             List follow-ups (overdue, upcoming)
POST    /api/follow-ups             Create follow-up
PUT     /api/follow-ups/{id}        Update follow-up
DELETE  /api/follow-ups/{id}        Delete follow-up
```
</details>

<details>
<summary><strong>Skills and Coaching</strong></summary>

```
GET     /api/skills                 List skills
POST    /api/skills                 Add skill
PUT     /api/skills/{id}            Update skill
GET     /api/gaps/{app_id}          Gap analysis
GET     /api/coaching/{app_id}      Coaching suggestions
GET     /api/goals                  List goals
POST    /api/goals                  Create goal
PUT     /api/goals/{id}             Update goal
GET     /api/learning               Learning recommendations
```
</details>

<details>
<summary><strong>Discovery and Scoring</strong></summary>

```
POST    /api/discovery/search       Run discovery sweep
GET     /api/discovery/results      Get discovery results
GET     /api/discovery/profiles     List search profiles
POST    /api/scoring/{app_id}       Score application
GET     /api/market/{role}          Market intelligence
GET     /api/intelligence/{role}    Role intelligence
```
</details>

<details>
<summary><strong>Interview Prep</strong></summary>

```
GET     /api/interview-prep/{app_id}    Full prep package
GET     /api/research/{app_id}          Company research
GET     /api/star-stories               List STAR stories
POST    /api/star-stories               Create story
PUT     /api/star-stories/{id}          Update story
DELETE  /api/star-stories/{id}          Delete story
```
</details>

<details>
<summary><strong>Integrations</strong></summary>

```
GET     /api/integrations/status        All integration statuses
PUT     /api/integrations/configure     Update integration config
GET     /api/calendar/feed.ics          iCal calendar feed
POST    /api/ticktick/sync              Trigger TickTick sync
GET     /api/ticktick/status            Sync status
POST    /api/timingsapp/track           Log time entry
GET     /api/timingsapp/summary         Time tracking summary
POST    /api/pushover/test              Test notification
POST    /api/voice/session              Start voice session
GET     /api/ai/health                  AI provider health check
```
</details>

---

## Configuration

Copy the example config and edit as needed:

```bash
cp .env.example .env
```

### Key Environment Variables

| Variable | Default | Description |
|:---|:---|:---|
| `AI_PROVIDER` | `mock` | AI backend - `mock` works fully offline, no key needed |
| `OPENROUTER_API_KEY` | (empty) | Required when `AI_PROVIDER=openrouter` |
| `OPENROUTER_MODEL` | `anthropic/claude-sonnet-4` | Which model to use via OpenRouter |
| `DATABASE_URL` | `sqlite:///data/career_os.db` | SQLite database path |
| `HOST` | `0.0.0.0` | API server bind address |
| `PORT` | `8100` | API server port |
| `FRONTEND_URL` | `http://localhost:8101` | CORS origin for frontend |
| `AUTH_ENABLED` | `false` | Protect your instance with an API key |
| `AUTH_API_KEY` | (empty) | Required when `AUTH_ENABLED=true` |
| `PUSHOVER_USER_KEY` | (empty) | Pushover push notifications (optional) |
| `PUSHOVER_APP_TOKEN` | (empty) | Pushover app token (optional) |
| `TICKTICK_API_TOKEN` | (empty) | TickTick task sync (optional) |

See `.env.example` for the full list including Mailgun, Google Sheets, and Anti-Captcha options.

---

## Daily Scan (Automated Job Discovery)

Kestrel includes a GitHub Actions workflow that runs an automated job discovery pipeline on a schedule. It scrapes job boards, scores results against your profile, and commits a daily digest to the repo.

### What it does

1. Runs `tools/daily_pipeline.py` - scrapes configured job boards and scores results
2. Generates a markdown digest in `tracking/daily-scan-YYYY-MM-DD.md`
3. Sends a Pushover notification with top-scoring roles
4. Optionally sends an email summary via Mailgun
5. Optionally logs results to a Google Sheet
6. Commits the digest to the repo

### Schedule

By default it runs Monday through Friday at 07:00 UTC. Edit `.github/workflows/daily-scan.yml` to change the schedule:

```yaml
on:
  schedule:
    - cron: '0 7 * * 1-5'   # Mon-Fri at 07:00 UTC
```

You can also trigger it manually from the GitHub Actions tab with custom parameters (mode, minimum score, max posting age, dry run).

### Required Secrets

Set these in your GitHub repo under Settings - Secrets and variables - Actions:

| Secret | Required | Purpose |
|:---|:---|:---|
| `OPENAI_API_KEY` | Yes | Powers the AI scoring in CI |
| `PUSHOVER_APP_TOKEN` | No | Push notification on scan completion |
| `PUSHOVER_USER_KEY` | No | Push notification recipient |
| `MAILGUN_API_KEY` | No | Email digest delivery |
| `MAILGUN_DOMAIN` | No | Mailgun sending domain |
| `NOTIFY_EMAIL` | No | Where to send email digests |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | No | Google Sheets logging |
| `GOOGLE_SHEET_ID` | No | Target spreadsheet ID |

### Repository Variables

| Variable | Default | Purpose |
|:---|:---|:---|
| `PIPELINE_LOCATION` | `Remote` | Default location filter for job search |

At minimum you need `OPENAI_API_KEY` for the scoring to work. Everything else is optional - the pipeline will still scrape and score without notifications.

---

## Troubleshooting

**"docker: command not found"**
Install [Docker Desktop](https://docker.com) or [OrbStack](https://orbstack.dev) (Mac). Then run `./setup.sh` again.

**"Cannot connect to Docker daemon"**
Docker is installed but not running. Open Docker Desktop or OrbStack and wait for it to start.

**"Port 8100 already in use"**
Something else is using that port. Either stop it, or change `PORT` in your `.env` file and restart with `docker compose up -d`.

**"Database is locked"**
SQLite can get stuck if a process crashes mid-write. Fix it:
```bash
docker compose down -v
docker compose up -d
```
This recreates the container volumes. Your data is in `data/career_os.db` on the host, not in the container volume, so nothing is lost.

**"Frontend can't connect to API"**
The backend takes a few seconds to start. Wait 30 seconds and refresh. If it still doesn't work:
```bash
docker compose logs backend
```
Look for errors in the output.

**"AI scoring returns mock data"**
Check your `.env` - `AI_PROVIDER` is probably still set to `mock`. Set it to `openrouter` and add your API key. Then `docker compose restart`.

---

## Known Limitations

- **Voice coaching feedback loop** - Voice mode currently supports single-turn discussions; multi-turn coaching with real-time feedback is not yet implemented
- **Discovery-to-pipeline score propagation** - AI scores from discovery results are not automatically carried forward when adding a discovered job to the pipeline
- **Archive cascade cleanup** - Archiving an application does not cascade-delete related follow-ups, calendar entries, or TickTick tasks

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, and pull request guidelines.

---

## License

[MIT](LICENSE)
