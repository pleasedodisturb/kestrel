<p align="center">
  <img src="assets/illustrations/hero-navy.webp" alt="Kestrel" width="280">
</p>

<h1 align="center">Kestrel</h1>

<p align="center">
  <strong>A job search system that runs on your computer.</strong><br>
  Finds jobs. Scores them. Tracks your pipeline. Your data stays yours.
</p>

<p align="center">
  <a href="https://pypi.org/project/kestrel-app/"><img src="https://img.shields.io/pypi/v/kestrel-app?style=flat-square&label=pip%20install&color=22c55e" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/AI-built--in_(free)-blue?style=flat-square" alt="AI included">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="MIT License">
  <img src="https://img.shields.io/badge/No_coding_required-gray?style=flat-square" alt="No coding required">
</p>

<p align="center">
  <a href="https://codespaces.new/pleasedodisturb/kestrel"><img src="https://github.com/codespaces/badge.svg" alt="Open in GitHub Codespaces" height="32"></a>
</p>

---

## Install

Pick whichever feels right. They all give you the same app.

### Quick install (one command)

```bash
curl -fsSL https://raw.githubusercontent.com/pleasedodisturb/kestrel/main/install.sh | bash
```

Detects your OS, checks for Python 3.12+, installs Kestrel, and opens it in your browser.

Or if you have Node.js:
```bash
npx kestrel-app
```

Or with Homebrew (macOS):
```bash
brew install pleasedodisturb/kestrel/kestrel
kestrel start
```

### Option 1: pip install (simplest)

```bash
pip install kestrel-app
kestrel start
```

Opens your browser automatically. Data stored in `~/.kestrel/`.

Requires Python 3.12+. Don't have Python? Install it from [python.org/downloads](https://www.python.org/downloads/) (Mac/Windows installer, takes 2 minutes). Or use Option 2 or 3 below instead.

### Option 2: Docker (isolated, nothing touches your system)

```bash
git clone https://github.com/pleasedodisturb/kestrel.git && cd kestrel
bash setup.sh
```

Requires [OrbStack](https://orbstack.dev) (recommended for Mac) or [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Mac/Windows). Both are free. Don't know what Docker is? The [step-by-step guide](docs/QUICKSTART.md) explains everything.

### Option 3: Try in your browser (zero install)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/pleasedodisturb/kestrel)

Free with a GitHub account. Your own instance in 2 minutes. Nothing installed on your computer.

**Lost?** [Step-by-step guide](docs/QUICKSTART.md) or [FAQ](docs/FAQ.md).

---

## Preview

<p align="center">
  <strong>Pipeline — drag applications across stages</strong><br><br>
  <img src="docs/images/preview-pipeline.svg" alt="Kanban board showing job applications across pipeline stages" width="820">
</p>

<p align="center">
  <strong>Discovery — AI-scored job matches</strong><br><br>
  <img src="docs/images/preview-discovery.svg" alt="Discovery page showing scored job listings from multiple boards" width="820">
</p>

<p align="center">
  <strong>Settings — connect your integrations</strong><br><br>
  <img src="docs/images/preview-settings.svg" alt="Settings page showing integration configuration" width="820">
</p>

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

**Getting started:**

| Guide | What you'll learn |
|-------|-------------------|
| [Quickstart](docs/QUICKSTART.md) | First-time setup, step by step — zero assumptions |
| [FAQ](docs/FAQ.md) | "Can I...?" "What if...?" "Why does...?" — all answered |
| [Help](docs/HELP.md) | Something broke? Start here. We'll fix it together. |

**Understanding AI in Kestrel:**

| Guide | What you'll learn |
|-------|-------------------|
| [How Kestrel Uses AI](docs/ai-providers-explained.md) | The electricity analogy — what AI providers are, what they cost, and which to pick |
| [AI Provider Setup](docs/AI-PROVIDERS.md) | Technical details — API keys, privacy policies, provider comparison tables |
| [LLM Landscape Research](docs/LLMs%20and%20tokens%20and%20privacy.md) | Deep dive — 2026 pricing, privacy audits, GDPR, EU sovereignty (for the curious) |

**Going deeper:**

| Guide | What you'll learn |
|-------|-------------------|
| [Comparison](docs/COMPARISON.md) | How Kestrel stacks up against Huntr, Teal, Simplify, and others |
| [Features & API Reference](docs/REFERENCE.md) | Full feature list, architecture, CLI, and API endpoints |
| [Deployment](DEPLOY.md) | Host Kestrel on Railway, Fly.io, or your own VPS |
| [Contributing](CONTRIBUTING.md) | Development setup and pull request guidelines |

---

## Add real AI (optional)

Kestrel works out of the box in Demo Mode — free, offline, no account needed. When you're ready for real AI-powered scoring, you have options:

| Option | Cost | Privacy | Best for |
|--------|------|---------|----------|
| **OpenRouter** | ~$3-10/mo | Good | Most users — one click to connect, 300+ models |
| **Anthropic (Claude)** | ~$4-10/mo | Excellent (7-day retention) | Power users who want the best privacy-cost balance |
| **Ollama** | Free | Perfect — nothing leaves your machine | Privacy maximalists, offline users |

**Quickest path:** Go to Settings → click "Connect to OpenRouter" → log in → done. No API keys to copy.

**Want to understand the options?** Read [How Kestrel Uses AI](docs/ai-providers-explained.md) — it explains everything in plain English, no jargon.

**Already technical?** Jump to the [AI Provider Setup](docs/AI-PROVIDERS.md) for detailed configuration.

---

## License

[MIT](LICENSE) - free forever, do whatever you want with it.
