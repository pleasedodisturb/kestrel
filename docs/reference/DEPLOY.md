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

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/template?template=https://github.com/pleasedodisturb/kestrel)

### One-click deploy

Click the button above. Railway reads the included `railway.json`, builds from the Dockerfile, and gives you a public URL. The `railway.json` declares `requiredMountPath: /app/data`, and the published template provisions a persistent volume at that path — so data persistence is set up automatically, with no manual post-deploy step.

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

### Data persistence

SQLite stores all data at `/app/data/career_os.db`. Without a volume mounted there, data is lost on every redeploy.

**One-click template deploys:** persistence is automatic. `railway.json` sets `deploy.requiredMountPath` to `/app/data`, and the published Railway template attaches a volume at that path — nothing to do.

**Manual / CLI deploys (`railway up`):** `requiredMountPath` declares the requirement, but you attach the volume yourself:

1. Open your service in the Railway dashboard
2. Go to **Settings > Volumes**
3. Click **Add Volume**
4. Set mount path to `/app/data`
5. Choose a size (1 GB is plenty)

> Note: a volume can't be defined in `railway.json` itself (Railway's config schema has no `volumes` key) — `requiredMountPath` only declares where the mount must be. The volume resource is provisioned by the template or added in the dashboard.

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
