# Job Search Tools — Research Summary

Condensed from Claude research (see [compass_artifact_wf-650799d3-fa9c-4c82-b9a9-252070be77df_text_markdown.md](../compass_artifact_wf-650799d3-fa9c-4c82-b9a9-252070be77df_text_markdown.md)). Focus: Germany/EU, MCP, free tools.

---

## Tool Matrix (What We Use)

| Tool | Purpose | Install | Notes |
|------|---------|---------|-------|
| **tools/germany_jobs.py** | Arbeitsagentur + Arbeitnow APIs | `pip install httpx` | No Docker. Germany-focused. |
| **JobSpy MCP** (borgius) | Multi-board (Indeed, LinkedIn, etc.) | Clone + Docker | Requires `docker build -t jobspy` |
| **Himalayas MCP** | Remote jobs | Goose config (SSE) | Hosted at mcp.himalayas.app |
| **CV Forge MCP** | Tailored CV + cover letter | `npx -y cv-forge` | Parse job, generate PDF/HTML |
| **tools/scraper.py** | python-jobspy CLI | `pip install python-jobspy` | Fallback when JobSpy MCP unavailable |
| **Brave Search** | Web search | pass-cli + mcp-credentials | For ad-hoc job search |

---

## When to Use What

| Scenario | Tool |
|----------|------|
| Germany PM/TPM roles | tools/germany_jobs.py |
| Multi-board (Indeed, LinkedIn, Glassdoor) | JobSpy MCP (if Docker) or tools/scraper.py |
| Remote-only jobs | Himalayas MCP |
| Tailored application package | CV Forge MCP |
| Quick web search | Brave Search |

---

## Free APIs (Wired Up)

- **Arbeitsagentur**: `GET .../pc/v4/jobs` with `X-API-Key: jobboerse-jobsuche` — [jobsuche.api.bund.dev](https://jobsuche.api.bund.dev/)
- **Arbeitnow**: `GET https://www.arbeitnow.com/api/job-board-api` — no key
- **Remotive**, **RemoteOK**, **Adzuna** — documented in full research; not yet in tools

---

## JobSpy MCP Setup (Docker)

```bash
cd jobspy-mcp-server
npm install
docker build -t jobspy -f jobspy/Dockerfile jobspy/
```

Goose config uses `node src/index.js` with `ENABLE_SSE=0` for stdio. When `search_jobs` is called, it runs `sudo docker run jobspy ...`.

---

## CV Forge

- **Install**: `npm install -g cv-forge` or `npx -y cv-forge`
- **Tools**: parse_job_requirements, generate_cv_data, generate_cover_letter, generate_complete_application
- **Output**: PDF (default), HTML, Markdown

---

## Memory Bank (Cursor ↔ Goose)

Both Cursor and Goose use `@modelcontextprotocol/server-memory` (Knowledge Graph Memory). To share memory between them:

- **Shared path:** `Projects/Jobs/.memory/memory.jsonl`
- **Cursor** (`~/.cursor/mcp.json`): Memory MCP has `env.MEMORY_FILE_PATH` set to this path
- **Goose** (`~/.config/goose/config.yaml`): `knowledgegraphmemory` has `envs.MEMORY_FILE_PATH` set to this path

Entities stored in Cursor (preferences, target companies, etc.) are visible to Goose when running recipes, and vice versa. Restart both after config changes.

---

## Out of Scope (Our Choices)

- **Notion MCP**: We use Linear + TickTick
- **LinkedIn MCP**: Skipped (account ban risk); use JobSpy anonymous or browsermcp
- **Adzuna MCP**: Optional later
