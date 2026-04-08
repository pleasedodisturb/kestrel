<h1 align="center">Kestrel</h1>

<p align="center">
  <strong>A job search system that runs on your computer.</strong><br>
  Finds jobs. Scores them. Tracks your pipeline. Your data stays yours.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Docker-one--click_setup-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/AI-built--in_(free)-22c55e?style=flat-square" alt="AI included">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="MIT License">
  <img src="https://img.shields.io/badge/No_coding_required-blue?style=flat-square" alt="No coding required">
</p>

---

## Install

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) (free). That's it.

```bash
git clone https://github.com/pleasedodisturb/kestrel.git && cd kestrel
bash setup.sh
```

Open [http://localhost:8101](http://localhost:8101). Done.

**Never used a terminal?** [Full step-by-step guide](docs/QUICKSTART.md) - takes 10 minutes, no coding.

---

## What it does

- **Discovers jobs** from multiple boards automatically (Indeed, LinkedIn, Glassdoor, Arbeitsagentur)
- **Scores them** against your profile with AI - stop guessing which jobs are worth applying to
- **Tracks your pipeline** on a Kanban board - drag applications between stages
- **Prepares you for interviews** - company research, mock questions, STAR story library
- **Runs daily scans** via GitHub Actions - wake up to a scored digest of new matches
- **Works offline** - Demo Mode included, zero cost to start. Add real AI when ready.

Everything runs on your machine. No account needed. No data leaves your computer (unless you connect an AI provider).

---

## Docs

| Guide | For |
|-------|-----|
| [Quickstart](docs/QUICKSTART.md) | First-time setup, step by step |
| [FAQ](docs/FAQ.md) | Common questions answered |
| [Help](docs/HELP.md) | Troubleshooting when something breaks |
| [AI Provider Guide](docs/AI-PROVIDERS.md) | Choosing and configuring an AI provider |
| [Comparison](docs/COMPARISON.md) | How Kestrel compares to other tools |
| [Features & API Reference](docs/REFERENCE.md) | Full feature list, architecture, CLI, API endpoints |
| [Deployment](DEPLOY.md) | Railway, Fly.io, VPS hosting |
| [Contributing](CONTRIBUTING.md) | Development setup and pull request guidelines |

---

## Quick look

**Web dashboard** with Kanban board, AI scoring, discovery, analytics, and more:

```
http://localhost:8101  - Dashboard (what you use)
http://localhost:8100/docs  - API docs (if you're curious)
```

**Add real AI** (optional - works fine without it):

1. Get an API key from [openrouter.ai](https://openrouter.ai)
2. Edit `.env`: set `AI_PROVIDER=openrouter` and `OPENROUTER_API_KEY=your-key`
3. Restart: `docker compose restart`

Costs about $1-3/month for typical usage.

---

## License

[MIT](LICENSE) - free forever, do whatever you want with it.
