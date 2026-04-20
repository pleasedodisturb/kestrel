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
  <img src="https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square" alt="AGPL-3.0 License">
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

Detects your OS, checks for Python 3.11+, installs Kestrel, and opens it in your browser.

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

Requires Python 3.11+. Don't have Python? Install it from [python.org/downloads](https://www.python.org/downloads/) (Mac/Windows installer, takes 2 minutes). Or use Option 2 or 3 below instead.

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
| [LLM Landscape Research](docs/llms-tokens-privacy.md) | Deep dive — 2026 pricing, privacy audits, GDPR, EU sovereignty (for the curious) |

**How it works under the hood:**

| Guide | What you'll learn |
|-------|-------------------|
| [How Scoring Works](docs/how-scoring-works.md) | What "fit score" actually means, and how Kestrel decides which jobs match you |
| [How Testing Works](docs/how-testing-works.md) | 2,800+ automated checks — the kitchen analogy for quality assurance |

**Going deeper:**

| Guide | What you'll learn |
|-------|-------------------|
| [Comparison](docs/COMPARISON.md) | How Kestrel stacks up against Huntr, Teal, Simplify, and others |
| [Features & API Reference](docs/REFERENCE.md) | Full feature list, architecture, CLI, and API endpoints |
| [Deployment](DEPLOY.md) | Host Kestrel on Railway, Fly.io, or your own VPS |
| [Contributing](CONTRIBUTING.md) | Development setup and pull request guidelines |

---

## Add real AI (optional)

Kestrel works out of the box in Demo Mode — free, offline, no account needed. When you're ready for real AI-powered scoring, you have options. Think of AI providers like electricity companies: the light switch works the same no matter who supplies the power.

| Option | Cost | Privacy | Speed | Best for |
|--------|------|---------|-------|----------|
| **Demo Mode** | Free | Perfect | Instant | Exploring before committing |
| **OpenRouter (free tier)** | **$0/mo** | Good | Varies | Start here — Llama 3.3 70B scores jobs for free |
| **OpenRouter (paid models)** | $1-30+/mo | Good | Varies | Premium models (Claude, GPT). Cost depends on model and volume — see note below |
| **Anthropic (Claude)** | $1-10/mo | Excellent | ~200ms | Best quality + prompt caching savings. Can spike if scoring high volumes without caching |
| **Together AI** | ~$1-5/mo | Good ([ZDR available](https://www.together.ai/blog/soc-2-compliance)) | ~213ms | Budget-friendly bulk scoring |
| **Ollama** | Free | Perfect | Depends on hardware | Nothing leaves your machine, ever |

> **Cost depends on model and volume.** A typical daily scan scrapes 1,000-1,500 jobs from multiple boards. That's a lot of AI calls. Here's what it actually costs:
>
> | Model | Cost per job | 1,500 jobs/day | Monthly (30 days) |
> |---|---|---|---|
> | Llama 3.3 70B (OpenRouter free) | $0 | $0 | **$0** |
> | Llama 3.1 8B (Together AI) | $0.0002 | $0.30 | **$9** |
> | GPT-4o-mini (OpenRouter) | $0.0006 | $0.90 | **$27** |
> | Llama 3.3 70B (Together AI) | $0.002 | $3.00 | **$90** |
> | Claude Sonnet (OpenRouter) | $0.02 | $30.00 | **$900** |
>
> Kestrel defaults to free-tier models for bulk scanning. Premium models like Claude Sonnet are best reserved for deep analysis of shortlisted roles, not bulk filtering. The optimizations below help keep costs in check regardless of which model you use.

**Quickest path:** Go to Settings → click "Connect to OpenRouter" → log in → done. No API keys to copy. Free-tier models like Llama 3.3 70B handle job scoring at zero cost — add $10 of credits to unlock 1,000 requests/day.

### How Kestrel keeps costs low

AI APIs charge per token (roughly per word). Scoring 50 jobs a day could get expensive — unless you're smart about it. Kestrel stacks several tricks that compound:

| What Kestrel does | How it helps | Savings |
|-------------------|-------------|---------|
| **Prompt caching** | Your profile is sent once, then "remembered" by the API. Scoring 50 jobs doesn't resend your CV 50 times. | [90% off input tokens](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) |
| **Response caching** | Asked the same question twice? Kestrel serves it from local cache. Zero API calls, encrypted at rest. | 100% (free) |
| **Token-efficient tool use** | When Kestrel calls AI tools, it uses a compact format that cuts output size. | [70% off output tokens](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/token-efficient-tool-use) |
| **Smart model selection** | Not every task needs the biggest brain. Simple yes/no classification uses a smaller, cheaper model. Complex analysis uses the full thing. | [60-95% on simple tasks](https://github.com/lm-sys/RouteLLM) |
| **Batch scoring** | Scoring a big backlog overnight? Batch APIs give a flat 50% discount for non-urgent work. | [50% off everything](https://docs.anthropic.com/en/api/creating-message-batches) |

**The math:** Naive approach = $15-30/month. With all optimizations = **$1-5/month** for the same results. [Deep dive on token economics →](docs/llms-tokens-privacy.md)

### Choosing a provider

**Don't want to think about it?** Use OpenRouter. It's the universal adapter — one account gives you Claude, GPT, Gemini, and open-source models. You can always switch later.

**Care about privacy?** Anthropic has [7-day data retention](https://docs.anthropic.com/en/docs/about-claude/pricing) (shortest in industry). Together AI has a [one-click ZDR toggle](https://www.together.ai/blog/soc-2-compliance) (SOC 2 Type 2 certified). Ollama keeps everything on your machine.

**On a tight budget?** Together AI runs open-source models (Llama 3.3, Mixtral) on their own GPUs — no middleman markup. If you're in Europe, their **Frankfurt data center** means lower latency too. Great for bulk scoring where you don't need Claude-level intelligence.

**Want the best of everything?** Kestrel can use multiple providers at once — route simple scoring to Together (cheap), complex analysis to Anthropic (quality), and never worry about which is which.

**Want to understand more?** Read [How Kestrel Uses AI](docs/ai-providers-explained.md) — it explains everything in plain English, no jargon. For the full technical comparison with pricing tables and privacy audits, see the [AI Provider Setup](docs/AI-PROVIDERS.md) guide or the [LLM landscape research](docs/llms-tokens-privacy.md).

### Privacy and free/cheap models

Free and cheap AI models often train on your data or have weaker privacy guarantees. That's fine for some tasks and dangerous for others. Kestrel distinguishes between the two:

**Safe to send without ZDR** (generic, non-identifying):
- Job descriptions (public postings)
- Career preferences (target roles, salary range, location)
- Scoring criteria and rubrics

**Never sent without ZDR** (personally identifying):
- Your name, email, phone number, or address
- CV/resume content and work history
- Cover letters and application materials
- Interview preparation with personal STAR stories
- Contact details and networking notes

**Currently:** Kestrel does not enforce this boundary automatically - it's your responsibility to choose an appropriate provider for sensitive features. If you disable ZDR for cheap scoring, be mindful of which features you use with that provider.

**Planned:** Automatic routing that blocks personal data from reaching non-ZDR providers, so you can use free models for scoring without worrying about accidentally leaking personal data through other features.

**Rule of thumb:** If it's about the job market, cheap models are fine. If it's about *you*, use Ollama (local), Anthropic (strong privacy), or a provider with ZDR enabled.

---

## How we build

**Human-first, data-driven.** Every infrastructure decision — testing, CI/CD, scoring — is backed by deep research. We investigate thoroughly, then choose the sanest path: not the most sophisticated, but the most sustainable.

Our proof is in the research artifacts. Before building anything, we run parallel research agents, synthesize findings, and publish the decision rationale so anyone can understand *why* things work the way they do.

| Topic | For users | For developers | Raw research |
|-------|-----------|---------------|--------------|
| **Scoring** | [How Scoring Works](docs/how-scoring-works.md) | [Scoring Strategy](docs/research/scoring-research.md) | [Raw Findings](docs/research/scoring-raw-research.md) |
| **Testing** | [How Testing Works](docs/how-testing-works.md) | [Testing Strategy](docs/research/testing-research.md) | [Raw Findings](docs/research/testing-raw-research.md) |
| **CI/CD** | [How CI/CD Works](docs/how-cicd-works.md) | [CI/CD Strategy](docs/research/cicd-research.md) | [Raw Findings](docs/research/cicd-raw-research.md) |
| **Observability** | [How Observability Works](docs/how-observability-works.md) | [Observability Strategy](docs/research/observability-research.md) | [Setup Guide](docs/observability.md) |
| **[LLM Token Costs](https://github.com/pleasedodisturb/awesome-llm-token-optimization)** | [Quick Wins](https://github.com/pleasedodisturb/awesome-llm-token-optimization#quick-wins) | [Tools & Strategies](https://github.com/pleasedodisturb/awesome-llm-token-optimization#contents) | [52 Papers + Sources](https://github.com/pleasedodisturb/awesome-llm-token-optimization/tree/main/research) |

## License

[AGPL-3.0](LICENSE) — free and open source. If you modify Kestrel and offer it as a service, you must share your changes under the same license.
