# Automation Paths

Six ways to run Kestrel on autopilot — from a cron one-liner to a fully offline local-model pipeline.

All paths assume Kestrel is installed and the backend is reachable at `http://localhost:8100` (or wherever you host it). The REST API docs live at `/docs` (Swagger) and `/redoc`.

---

## 1. Cron Jobs (systemd timer / crontab)

The simplest path. The `kestrel` CLI talks directly to the local SQLite database — no running server required for most commands.

### Setup

1. Install Kestrel into a virtualenv:
   ```bash
   cd /opt/kestrel
   python -m venv .venv && source .venv/bin/activate
   pip install -e ".[dev]"
   alembic upgrade head
   ```
2. Create a wrapper script (`/opt/kestrel/scripts/daily-sweep.sh`):
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   cd /opt/kestrel
   source .venv/bin/activate

   # Run discovery with your preferred keywords
   kestrel discover --keywords "backend engineer,platform engineer" \
                    --location "Berlin" \
                    --output json > /tmp/kestrel-discovery-$(date +%F).json

   # Print pipeline stats (useful for email/log)
   kestrel pipeline stats
   ```
3. Add a crontab entry:
   ```cron
   # Every day at 07:00 UTC
   0 7 * * * /opt/kestrel/scripts/daily-sweep.sh >> /var/log/kestrel-cron.log 2>&1
   ```

   Or use a systemd timer for better logging:
   ```ini
   # /etc/systemd/system/kestrel-discover.timer
   [Unit]
   Description=Kestrel daily discovery

   [Timer]
   OnCalendar=*-*-* 07:00:00
   Persistent=true

   [Install]
   WantedBy=timers.target
   ```

### Available CLI commands for scripting

| Command | What it does |
|---------|-------------|
| `kestrel discover` | Run a discovery sweep across job boards |
| `kestrel discover --schedule daily` | Create a recurring search profile |
| `kestrel score <url>` | Score a single job posting |
| `kestrel pipeline list` | List all applications |
| `kestrel pipeline stats` | Pipeline statistics |
| `kestrel pipeline follow-ups` | Due/overdue follow-ups |
| `kestrel pipeline add` | Add an application |
| `kestrel pipeline update` | Update status/notes |
| `kestrel skills list` | Skills inventory |
| `kestrel skills gaps --aggregate` | Cross-application gap summary |
| `kestrel market` | Market intelligence |
| `kestrel research <company>` | Company research report |
| `kestrel coach` | Coaching suggestions |

Most commands support `--output json` for machine-readable output.

### Pros
- Zero dependencies beyond Kestrel itself
- Works offline (discovery needs network, everything else is local)
- Easy to monitor via standard log files

### Cons
- No retry/backoff logic without extra scripting
- Cron has no built-in alerting on failure

### Estimated cost
$0/mo (runs locally, AI calls use your configured provider).

---

## 2. GitHub Actions (Scheduled Workflow)

Use GitHub Actions as a free scheduler that calls the Kestrel REST API on a remote instance (or a self-hosted runner co-located with your Kestrel install).

### Setup

1. Deploy Kestrel somewhere reachable (e.g. a VPS, home server, or Tailscale network).
2. Store your Kestrel URL and API key as GitHub Actions secrets:
   - `KESTREL_URL` — e.g. `https://kestrel.example.com`
   - `KESTREL_API_KEY` — your auth key (only if `AUTH_ENABLED=true`)
3. Create `.github/workflows/kestrel-discover.yml`:

```yaml
name: Kestrel Daily Discovery

on:
  schedule:
    - cron: "0 7 * * *"   # 07:00 UTC daily
  workflow_dispatch:        # manual trigger

jobs:
  discover:
    runs-on: ubuntu-latest
    steps:
      - name: Run discovery sweep
        env:
          KESTREL_URL: ${{ secrets.KESTREL_URL }}
          KESTREL_API_KEY: ${{ secrets.KESTREL_API_KEY }}
        run: |
          # Trigger discovery
          curl -sf -X POST "$KESTREL_URL/api/discover" \
            -H "Content-Type: application/json" \
            -H "X-API-Key: $KESTREL_API_KEY" \
            -d '{
              "profile_id": 1,
              "keywords": ["backend engineer", "platform engineer"],
              "locations": ["Berlin"]
            }' | jq .

      - name: Fetch pipeline stats
        env:
          KESTREL_URL: ${{ secrets.KESTREL_URL }}
          KESTREL_API_KEY: ${{ secrets.KESTREL_API_KEY }}
        run: |
          curl -sf "$KESTREL_URL/api/applications?profile_id=1&page_size=5" \
            -H "X-API-Key: $KESTREL_API_KEY" | jq '.total, .applications[:3]'
```

### Key API endpoints for automation

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/discover` | Trigger discovery sweep |
| POST | `/api/score` | Score a job against profile |
| GET | `/api/applications` | List pipeline applications |
| POST | `/api/applications` | Create an application |
| PATCH | `/api/applications/{id}` | Update application |
| GET | `/api/discovery/runs` | List past discovery runs |
| POST | `/api/score/batch` | Batch score discovered jobs |

### Pros
- Free tier: 2,000 minutes/month on public repos
- Built-in secrets management
- `workflow_dispatch` lets you trigger manually from the GitHub UI
- Logs, notifications, and retry built in

### Cons
- Kestrel must be reachable from GitHub's runners (public IP or self-hosted runner)
- Not great for latency-sensitive flows (cold start + network)
- Free tier minutes are shared across the repo

### Estimated cost
$0/mo on the GitHub free tier. Self-hosted runners: $0 (your hardware).

---

## 3. Claude Code MCP Server

The Kestrel MCP server (`tools/kestrel-mcp/`) exposes Kestrel tools directly inside Claude Code sessions. Ask Claude to check your pipeline, score a job, or run discovery — conversationally.

### Setup

1. Ensure the Kestrel backend is running:
   ```bash
   kestrel start  # or: uvicorn career_os.main:app --port 8100
   ```
2. Install MCP dependencies in the Kestrel venv:
   ```bash
   pip install mcp httpx
   ```
3. Add to `~/.claude/mcp.json` (global) or your project `.mcp.json`:
   ```json
   {
     "mcpServers": {
       "kestrel": {
         "command": "/path/to/kestrel/.venv/bin/python",
         "args": ["tools/kestrel-mcp/server.py"],
         "cwd": "/path/to/kestrel",
         "env": {
           "KESTREL_URL": "http://localhost:8100",
           "KESTREL_PROFILE_ID": "1"
         }
       }
     }
   }
   ```
4. Restart Claude Code. The tools appear automatically.

### Available MCP tools

| Tool | What it does |
|------|-------------|
| `list_pipeline` | List applications with optional status/search filters |
| `pipeline_stats` | Pipeline statistics (counts by status, trends) |
| `score_job` | Score a job description against your profile |
| `discover_jobs` | Run a discovery sweep across configured sources |

### Example usage in Claude Code

> "Score this job posting: https://example.com/jobs/backend-engineer"
>
> "Show me my pipeline — filter by status 'applied'"
>
> "Run a discovery sweep for product manager roles in Amsterdam"

### Pros
- Conversational interface — no scripting needed
- Claude can chain tools (discover, then score, then add to pipeline)
- Works from any directory, any project

### Cons
- Requires Kestrel backend running locally
- Limited to Claude Code sessions (no standalone scheduling)

### Estimated cost
$0 beyond your existing Claude Code subscription. AI scoring calls use your configured provider.

---

## 4. n8n / Zapier (Webhook Automation)

Kestrel's REST API works with any HTTP-based automation platform. n8n (self-hosted) and Zapier (cloud) are the most common choices.

### Setup (n8n example)

1. Install n8n:
   ```bash
   npm install -g n8n   # or Docker: docker run -p 5678:5678 n8nio/n8n
   ```
2. Create a workflow with these nodes:

   **Schedule Trigger** (daily at 08:00)
   → **HTTP Request** (POST to `http://kestrel:8100/api/discover`)
   ```json
   {
     "profile_id": 1,
     "keywords": ["data engineer"],
     "locations": ["Remote"]
   }
   ```
   → **IF** (check `new_jobs > 0`)
   → **HTTP Request** (POST to `http://kestrel:8100/api/score/batch`)
   ```json
   {
     "profile_id": 1,
     "min_score": null,
     "limit": 20
   }
   ```
   → **Slack / Email** (notify with results)

### Setup (Zapier example)

1. Create a Zap:
   - **Trigger:** Schedule (daily)
   - **Action:** Webhooks by Zapier → POST to `https://kestrel.example.com/api/discover`
   - **Action:** Filter → only continue if `new_jobs > 0`
   - **Action:** Webhooks by Zapier → POST to batch score endpoint
   - **Action:** Gmail/Slack → send summary

### Chaining example: discovery -> score -> notify

```
Discover → Filter high-scoring → Score batch → Notify via Slack
```

The key endpoints for webhook chains:

| Step | Endpoint | Body |
|------|----------|------|
| Discover | `POST /api/discover` | `{"profile_id": 1, "keywords": [...]}` |
| Batch score | `POST /api/score/batch` | `{"profile_id": 1}` |
| List top jobs | `GET /api/applications?profile_id=1&page_size=5` | — |

### Pros
- Visual workflow builder
- Built-in integrations (Slack, email, Google Sheets, Notion)
- n8n is self-hosted and free; Zapier has a generous free tier
- Easy to add conditional logic and branching

### Cons
- Kestrel must be network-accessible to the automation platform
- Zapier free tier has limited tasks/month (100)
- n8n requires hosting infrastructure

### Estimated cost
- **n8n (self-hosted):** $0/mo (runs on your server)
- **n8n Cloud:** $24/mo (starter)
- **Zapier:** $0/mo (free tier, 100 tasks) to $30/mo (starter)

---

## 5. Scheduled Claude Code Agents (Remote Triggers)

Use Claude Code's remote triggers to run periodic scoring, discovery, or pipeline reviews on a schedule — no local machine needed.

### Setup

1. Create a trigger via the Claude Code CLI:
   ```bash
   claude triggers create \
     --name "kestrel-daily-score" \
     --schedule "0 8 * * *" \
     --prompt "Use the Kestrel MCP tools: run discover_jobs for 'software engineer' in 'Berlin', then run pipeline_stats and summarize what changed since yesterday." \
     --mcp-config ~/.claude/mcp.json
   ```
2. The trigger runs as a remote Claude Code session on Anthropic's infrastructure.
3. Results appear in your Claude Code dashboard and can be forwarded via webhooks.

### Example trigger prompts

**Daily discovery + scoring:**
> Run discover_jobs for keywords "backend, infrastructure" in location "EU Remote". Then score any new jobs with score_job. Summarize the top 3 matches.

**Weekly pipeline review:**
> Use list_pipeline to show all applications. Flag any that have been in "applied" status for more than 14 days. Suggest next actions for each.

**Market intelligence:**
> Call the Kestrel API at GET /api/market?profile_id=1 and summarize salary trends and top skills for my target roles.

### Pros
- Fully remote — no local machine needs to be on
- Claude can reason over results, not just fetch data
- Combines MCP tools with natural language analysis

### Cons
- Requires Kestrel backend accessible from Anthropic's infrastructure (public URL or tunnel)
- Remote trigger usage billed separately from interactive sessions
- MCP server must be configured in the trigger's context

### Estimated cost
Depends on Claude Code pricing for remote triggers. Each run uses ~500-2000 tokens for simple queries.

---

## 6. Ollama Local (Fully Offline Pipeline)

Run the entire pipeline — discovery, scoring, and analysis — using local models via Ollama. No data leaves your machine.

### Setup

1. Install Ollama:
   ```bash
   curl -fsSL https://ollama.ai/install.sh | sh
   ollama pull llama3.1:8b    # or any model you prefer
   ```
2. Configure Kestrel to use Ollama as the AI provider:
   ```bash
   # In .env or environment
   export AI_PROVIDER=ollama
   export OLLAMA_BASE_URL=http://localhost:11434
   export OLLAMA_MODEL=llama3.1:8b
   ```
3. Start Kestrel:
   ```bash
   kestrel start
   ```
4. Run discovery and scoring as normal:
   ```bash
   kestrel discover --keywords "devops engineer" --location "Munich"
   kestrel score https://example.com/jobs/devops-lead
   ```

### Combine with cron for a fully offline daily pipeline

```bash
#!/usr/bin/env bash
# /opt/kestrel/scripts/offline-daily.sh
set -euo pipefail
cd /opt/kestrel && source .venv/bin/activate

export AI_PROVIDER=ollama
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3.1:8b

# Ensure Ollama is running
pgrep -x ollama > /dev/null || ollama serve &
sleep 2

kestrel discover --keywords "backend engineer" --output json \
  > /tmp/kestrel-discover-$(date +%F).json

kestrel pipeline stats
kestrel coach
```

### Supported Ollama models

Any model that Ollama supports works. Recommended:

| Model | Size | Quality | Speed |
|-------|------|---------|-------|
| `llama3.1:8b` | 4.7 GB | Good for scoring | Fast |
| `llama3.1:70b` | 40 GB | Best local quality | Slow (needs beefy GPU) |
| `mistral:7b` | 4.1 GB | Decent alternative | Fast |
| `qwen2.5:14b` | 8.9 GB | Strong reasoning | Medium |

### Pros
- Zero data leaves your machine — full privacy
- No API costs, no rate limits
- Works without internet (after initial model download)
- No vendor lock-in

### Cons
- Lower quality scores vs. cloud models (GPT-4, Claude)
- Requires GPU for reasonable speed (CPU works but is slow)
- 8B models may struggle with nuanced scoring rubrics
- You manage model updates yourself

### Estimated cost
$0/mo. Hardware cost: whatever GPU you already have. A Mac with 16GB+ RAM runs 8B models comfortably.

---

## Comparison Matrix

| Path | Internet Required | Scheduling | AI Quality | Setup Effort | Monthly Cost |
|------|:-:|:-:|:-:|:-:|:-:|
| Cron + CLI | For discovery only | Built-in | Your provider | Low | $0 |
| GitHub Actions | Yes | Built-in | Your provider | Low | $0 |
| Claude Code MCP | No (local) | Manual | Your provider | Medium | $0 |
| n8n / Zapier | Yes | Built-in | Your provider | Medium | $0-30 |
| Scheduled Agents | Yes | Built-in | Claude | Low | Variable |
| Ollama Local | For discovery only | Add cron | Local model | Medium | $0 |

## Combining Paths

These paths are not mutually exclusive. A practical setup:

- **Daily:** Cron runs `kestrel discover` at 07:00
- **On demand:** Claude Code MCP for interactive scoring and pipeline review
- **Weekly:** n8n workflow sends a Slack summary of pipeline status
- **Sensitive roles:** Ollama scoring for jobs where privacy matters
