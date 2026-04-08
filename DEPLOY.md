# CareerOS Deployment Guide

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

1. Connect your GitHub repo in Railway
2. Railway auto-detects the Dockerfile
3. Set environment variables in the Railway dashboard
4. Add a volume mounted at `/app/data` for persistent SQLite storage
5. Railway assigns a public URL automatically

**Settings:**
- Root directory: `/` (default)
- Dockerfile path: `Dockerfile`
- Port: `8100`

## Deploy to Fly.io

```bash
# First time
fly launch --copy-config --no-deploy
fly volumes create careeros_data --region fra --size 1
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
git clone <repo-url> && cd career-os
docker compose -f docker-compose.prod.yml up -d --build

# With reverse proxy (Caddy example)
# Caddyfile:
#   careeros.example.com {
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

SQLite database lives at `/app/data/career_os.db`. For any deployment, ensure this path is backed by persistent storage (Docker volume, Fly volume, Railway volume).

Alembic migrations run automatically on startup.
