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

<p align="center">
  <a href="https://codespaces.new/pleasedodisturb/kestrel"><img src="https://github.com/codespaces/badge.svg" alt="Open in GitHub Codespaces" height="32"></a>
</p>

---

## Install

Pick whichever feels right. All three give you the same app.

### Option 1: pip install (no Docker needed)

```bash
pip install kestrel-app
kestrel start
```

Opens your browser automatically. Data stored in `~/.kestrel/`. Requires Python 3.13+.

### Option 2: Docker (isolated, one command)

```bash
git clone https://github.com/pleasedodisturb/kestrel.git && cd kestrel
bash setup.sh
```

### Option 3: Try in your browser (zero install)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/pleasedodisturb/kestrel)

Free with a GitHub account. Your own instance in 2 minutes. No install, nothing on your computer.

**Need more help?** [Step-by-step guide](docs/QUICKSTART.md) - no coding knowledge required.

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

1. Sign up at [openrouter.ai](https://openrouter.ai) and copy your API key
2. Open the settings file in your Kestrel folder:
   - **Mac:** Open Terminal, go to your Kestrel folder, type `open .env`
   - **Windows:** Open the Kestrel folder, type `.env` in the address bar
   - **Or any text editor:** the file is called `.env` (hidden file - [how to see it](docs/FAQ.md#hidden-files-on-mac))
3. Change these two lines:
   ```
   AI_PROVIDER=openrouter
   OPENROUTER_API_KEY=sk-or-paste-your-key-here
   ```
4. Save the file, then restart: `docker compose restart`

Costs about $1-3/month. Full guide: [AI Provider Guide](docs/AI-PROVIDERS.md)

---

## License

[MIT](LICENSE) - free forever, do whatever you want with it.
