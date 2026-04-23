<p align="center">
  <img src="assets/illustrations/hero-navy.webp" alt="Kestrel" width="280">
</p>

<h1 align="center">Kestrel</h1>

<p align="center">
  <strong>Stop spray-and-praying. Start running your job search like a system.</strong><br>
  Kestrel scrapes job boards, scores every posting against your profile, and tracks your pipeline — all on your machine.
</p>

<p align="center">
  <a href="https://github.com/pleasedodisturb/kestrel/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/pleasedodisturb/kestrel/ci.yml?branch=main&style=flat-square&label=build" alt="CI"></a>
  <a href="https://github.com/pleasedodisturb/kestrel/releases/latest"><img src="https://img.shields.io/github/v/release/pleasedodisturb/kestrel?style=flat-square&label=release&color=22c55e" alt="Latest Release"></a>
  <a href="https://pypi.org/project/kestrel-app/"><img src="https://img.shields.io/pypi/v/kestrel-app?style=flat-square&label=pypi&color=22c55e" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square" alt="AGPL-3.0 License">
</p>

<p align="center">
  <a href="https://codespaces.new/pleasedodisturb/kestrel"><img src="https://github.com/codespaces/badge.svg" alt="Open in GitHub Codespaces" height="32"></a>
</p>

---

<p align="center">
  <strong>Pipeline — drag applications across stages</strong><br><br>
  <img src="docs/images/preview-pipeline.svg" alt="Kanban board showing job applications across pipeline stages" width="820">
</p>

<p align="center">
  <strong>Discovery — AI-scored job matches</strong><br><br>
  <img src="docs/images/preview-discovery.svg" alt="Discovery page showing scored job listings from multiple boards" width="820">
</p>

---

## What it does

You tell Kestrel what you're looking for. It does the rest.

- **Scrapes job boards** — Indeed, LinkedIn, Glassdoor, Arbeitsagentur. Runs daily. You wake up to new matches.
- **Scores every posting** — AI reads the job, compares it to your profile, and gives you a fit score (0-10) and a desire score (0-10). Two numbers, because "can you do it?" and "do you want it?" are different questions.
- **Tracks your pipeline** — Kanban board. Drag jobs between stages. See where everything stands.
- **Preps you for interviews** — Company research, mock questions, a STAR story library you build over time.
- **Runs on your machine** — Your data stays on your disk. No account, no cloud, no tracking. Unless you choose otherwise.

Demo Mode works offline, for free, right now. Real AI scoring costs [$1-5/month](docs/guides/ai-providers-guide.md) with the built-in optimizations (prompt caching, model routing, response caching — [8 techniques stacked](docs/guides/how-token-optimization-works.md)).

## Why Kestrel

Job search tools fall into two camps. The SaaS apps (Huntr, Teal, Simplify) want $30/month and your data on their servers. The open-source tools are either abandoned or developer-only CLI scripts.

Kestrel is neither. It's a full app — web dashboard, REST API, mobile app (in progress) — that runs locally. You own the data, pick your own AI provider (or use none), and pay nothing for the software itself.

[Full comparison →](docs/guides/COMPARISON.md)

## Install

Pick one. They all give you the same app.

```bash
# One command (detects OS, installs, opens browser)
curl -fsSL https://raw.githubusercontent.com/pleasedodisturb/kestrel/main/install.sh | bash

# Or with pip
pip install kestrel-app && kestrel start

# Or with Node.js
npx kestrel-app

# Or with Homebrew
brew install pleasedodisturb/kestrel/kestrel && kestrel start

# Or with Docker (nothing touches your system)
git clone https://github.com/pleasedodisturb/kestrel.git && cd kestrel && bash setup.sh
```

**Zero install option:** [Open in GitHub Codespaces](https://codespaces.new/pleasedodisturb/kestrel) — your own instance in 2 minutes, free with a GitHub account.

Need hand-holding? The [step-by-step guide](docs/guides/QUICKSTART.md) assumes you've never used a terminal.

## Add AI (optional)

Kestrel works without AI. Demo Mode gives you the full UI with simulated scores — enough to explore everything and decide if it's for you.

When you're ready for real scoring: go to Settings, click "Connect to OpenRouter," log in. Done. Free-tier models (Llama 3.3 70B) score jobs at zero cost.

Want more control? Kestrel supports 6 providers — from free local models to the best commercial APIs. You can even run multiple at once.

| Provider | Cost | Privacy | Good for |
|----------|------|---------|----------|
| **Demo Mode** | Free | Perfect | Trying it out |
| **OpenRouter** | $0-10/mo | Good | Most people — one account, 300+ models |
| **Anthropic** | $1-10/mo | Excellent (7-day retention) | Best quality, prompt caching |
| **Together AI** | $1-5/mo | Good (ZDR available) | Bulk scoring on a budget |
| **Ollama** | Free | Perfect | Nothing leaves your machine |
| **OpenAI** | $1-10/mo | Good | GPT models direct |

[Full guide with the electricity analogy →](docs/guides/ai-providers-guide.md) · [Technical comparison + API keys →](docs/reference/AI-PROVIDERS.md) · [Privacy deep dive →](docs/research/llms-tokens-privacy.md)

## Docs

| | |
|---|---|
| [Quickstart](docs/guides/QUICKSTART.md) | First-time setup, zero assumptions |
| [FAQ](docs/guides/FAQ.md) | Common questions answered |
| [Help](docs/guides/HELP.md) | Something broke? Start here |
| [How Scoring Works](docs/guides/how-scoring-works.md) | What "fit score" means, how Kestrel decides |
| [How Testing Works](docs/guides/how-testing-works.md) | 2,800+ automated checks explained |
| [Comparison](docs/guides/COMPARISON.md) | Kestrel vs Huntr, Teal, Simplify, and others |
| [All docs →](docs/index.md) | Full index of 40+ documents |

## Contributing

[Contributing guide](CONTRIBUTING.md) · [Deployment](DEPLOY.md) · [API Reference](docs/reference/REFERENCE.md)

## License

[AGPL-3.0](LICENSE) — free and open source. If you modify Kestrel and offer it as a service, share your changes under the same license.
