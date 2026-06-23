---
layout: default
permalink: /DEPLOY
title: Kestrel Deployment Guide
---

# Kestrel Deployment Guide

Single-container deployment: FastAPI serves both the API (`/api/*`, `/health`, `/docs`) and the React frontend (all other routes) on **one port** (8100).

## Quick Start (Docker)

```bash
# Production build — single container
docker compose -f docker-compose.prod.yml up --build

# Open http://localhost:8100
```

## Local Development (Docker)

```bash
# Two containers: backend (hot-reload) + frontend (Vite dev server)
docker compose up --build

# Backend:  http://localhost:8100
# Frontend: http://localhost:8101 (proxies /api to backend)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///data/career_os.db` | SQLite connection string |
| `AI_PROVIDER` | `mock` | AI backend: `mock` or `openrouter` |
| `OPENROUTER_API_KEY` | (empty) | Required when `AI_PROVIDER=openrouter` |
| `AUTH_ENABLED` | `false` | Enable API key authentication |
| `AUTH_API_KEY` | (empty) | Required when `AUTH_ENABLED=true` |
| `DEBUG` | `false` | Enable debug logging |
| `PORT` | `8100` | Server port |
| `FRONTEND_URL` | `*` | CORS origin (use `*` when serving from same container) |

## Deploy to Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/github)

### Deploy from GitHub repo

Click the button above (or go to **railway.com/new → Deploy from GitHub repo**) and select your fork of `kestrel`. Railway reads the included `railway.json`, builds from the Dockerfile, binds to the injected `$PORT`, and gives you a public URL. The only post-deploy step is adding a volume for data persistence (see below).

> **Note:** `railway.com/new/template?template=<github-url>` does **not** work for a plain GitHub repo — that URL form expects a *published* Railway template and falls through to a generic database/service picker. Use the deploy-from-repo flow above instead.

### True one-click button (optional, owner-only)

To get a real one-click button that provisions the volume and variables automatically, publish a template once from the Railway dashboard:

1. Deploy the repo once (above), then open the project → **Settings → Publish as Template**.
2. Railway mints a stable URL: `https://railway.com/new/template/<code>`.
3. Replace the button target in `README.md` and this file with that URL.

This is a manual dashboard step tied to your Railway account, so it can't be committed from the repo alone.

### Manual deploy (Railway CLI)

```bash
# Install the CLI
npm i -g @railway/cli

# Login and initialize
railway login
railway init

# Link to your project (or create one)
railway link

# Deploy
railway up
```

### Environment variables

Set these in the Railway dashboard under your service's **Variables** tab:

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `mock` | AI backend (`mock`, `openrouter`, `anthropic`, `together`, `ollama`) |
| `OPENROUTER_API_KEY` | (empty) | Required when `AI_PROVIDER=openrouter` |
| `AUTH_ENABLED` | `false` | Enable API key authentication |
| `AUTH_API_KEY` | (empty) | Required when `AUTH_ENABLED=true` |
| `PORT` | `8100` | Server port (Railway sets this automatically via `$PORT`) |

`DATABASE_URL` and `FRONTEND_URL` are pre-configured in the Dockerfile and do not need to be set.

### Data persistence (required)

SQLite stores all data at `/app/data/career_os.db`. Without a volume, data is lost on every redeploy.

1. Open your service in the Railway dashboard
2. Go to **Settings > Volumes**
3. Click **Add Volume**
4. Set mount path to `/app/data`
5. Choose a size (1 GB is plenty)

### Free tier limitations

Railway's free Hobby plan includes:

- **500 hours/month** of execution (enough for always-on if you have one service)
- **512 MB RAM** (sufficient for Kestrel with moderate usage)
- **1 GB disk** per volume (enough for thousands of job applications)
- **Automatic sleep** after 10 minutes of inactivity on the free trial; Hobby plan stays awake
- No credit card required to start (trial), $5/month for the Hobby plan with included credits

## Deploy to Fly.io

```bash
# First time
fly launch --copy-config --no-deploy
fly volumes create kestrel_data --region fra --size 1
fly deploy

# Subsequent deploys
fly deploy
```

The included `fly.toml` is pre-configured for Frankfurt region with a 1 GB persistent volume.

**Set secrets:**
```bash
fly secrets set AUTH_ENABLED=true AUTH_API_KEY=your-secret
fly secrets set AI_PROVIDER=openrouter OPENROUTER_API_KEY=sk-...
```

## Deploy to Any VPS (self-hosted)

```bash
# Clone and build
git clone <repo-url> && cd kestrel
docker compose -f docker-compose.prod.yml up -d --build

# With reverse proxy (Caddy example)
# Caddyfile:
#   kestrel.example.com {
#       reverse_proxy localhost:8100
#   }
```

## Architecture

```
Browser --> :8100
              |
              +--> /api/*      --> FastAPI routers
              +--> /health     --> FastAPI health check
              +--> /docs       --> Swagger UI
              +--> /*          --> React SPA (frontend/dist)
```

The FastAPI app mounts the built frontend as static files and uses a catch-all fallback to serve `index.html` for client-side routing.

## Data Persistence

SQLite database lives at `/app/data/career_os.db` (internal database name). For any deployment, ensure this path is backed by persistent storage (Docker volume, Fly volume, Railway volume).

Alembic migrations run automatically on startup.
