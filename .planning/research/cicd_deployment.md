# CI/CD & Deployment Research for Kestrel

**Researched:** 2026-04-16
**Overall confidence:** HIGH (multiple sources verified, post-April-2026 pricing confirmed)

---

## 1. Self-Hosted Deployment Platforms

### Recommendation: Kamal 2

For a solo developer shipping a Dockerized FastAPI + React app, **Kamal 2** is the best fit. It deploys Docker containers to any server via SSH with zero platform overhead — no dashboard daemon, no database for the platform itself, just your app and `kamal-proxy` (a lightweight reverse proxy).

| Platform | GitHub Stars | Setup Time | Maintenance | Dashboard | Multi-App | Zero-Downtime | Best For |
|----------|-------------|------------|-------------|-----------|-----------|---------------|----------|
| **Kamal 2** | ~15K | 30 min | Minimal | No (CLI) | Yes (v2) | Yes (built-in) | Docker-native deploys, solo devs |
| **Coolify** | ~52K | 15 min | Medium | Yes (web) | Yes | Yes | Teams wanting Vercel-like UX |
| **Dokku** | ~28K | 20 min | Low | No (CLI) | Yes | Plugin-based | git-push Heroku-style |
| **CapRover** | ~13K | 20 min | Medium | Yes (web) | Yes | Yes | Beginners wanting web UI |
| **Portainer** | ~31K | 10 min | Low | Yes (web) | Yes | No | Docker management (not deployment) |
| **Docker Compose (bare)** | N/A | 5 min | Manual | No | Yes | DIY | Simplest possible, full control |

### Why Kamal over Coolify

**Coolify had 11 critical security vulnerabilities disclosed January 2026**, three with CVSS 10.0 scores (maximum severity), exposing 52,000+ instances to authentication bypass, RCE, and root access. The vulnerabilities included:
- CVE-2025-66209: Command injection via database backup (container escape, full server compromise)
- CVE-2025-64420: Private key disclosure allowing SSH root access
- CVE-2025-64419: Command injection via docker-compose.yaml (root execution)

While patched, this demonstrates the attack surface of running a complex web dashboard on your deployment server. Kamal has zero server-side components to attack.

### Why Kamal over Dokku

Dokku is excellent but single-server-only with no upgrade path. Kamal 2 supports multi-server deployments when needed. Dokku's SQLite persistence requires careful volume mounting (each deploy creates a new filesystem). Kamal deploys pre-built Docker images, making the build-once-deploy-anywhere pattern natural.

### Kamal trade-offs

- Requires Ruby installed locally (not on server) -- minor friction for Python/Node developers
- Requires a Docker registry (GitHub Container Registry is free for public repos, $4/month for private)
- No web dashboard -- CLI-only, which is fine for solo dev but means no quick-glance status page

### Kamal 2 Config Example for Kestrel

```yaml
# config/deploy.yml
service: kestrel
image: ghcr.io/pleasedodisturb/kestrel

servers:
  web:
    hosts:
      - your-server-ip
    options:
      volume: /data/kestrel:/app/data

registry:
  server: ghcr.io
  username: pleasedodisturb
  password:
    - KAMAL_REGISTRY_PASSWORD

env:
  clear:
    DATABASE_URL: sqlite:///data/career_os.db
    AI_PROVIDER: openrouter
    AUTH_ENABLED: "true"
  secret:
    - AUTH_API_KEY
    - OPENROUTER_API_KEY

healthcheck:
  path: /health
  port: 8100

proxy:
  host: kestrel.yourdomain.com
  ssl: true
```

### Alternative: Docker Compose + Caddy (Simplest Path)

If Kamal feels like overkill, the simplest viable production deployment is:
1. Your existing `docker-compose.prod.yml` (already works)
2. Caddy as reverse proxy (automatic HTTPS, zero config)
3. A deploy script that does `docker compose pull && docker compose up -d`

This is what you have today. Kamal adds zero-downtime deploys, rollbacks, and secret management.

---

## 2. Hosting Provider Comparison

### Recommendation: Hetzner CX22 (2 vCPU / 4 GB RAM)

| Provider | Smallest Plan | 2 vCPU / 4 GB | Bandwidth | SQLite-Friendly | Notes |
|----------|--------------|----------------|-----------|-----------------|-------|
| **Hetzner** | CX22 @ EUR 4.49/mo (~$5) | CX32 @ EUR 7.99/mo (~$9.50) | 20 TB/mo | Yes (persistent disk) | Best price/perf. April 2026 price increase (+30-37%) already applied |
| **DigitalOcean** | $4/mo (512 MB) | $24/mo | 4 TB/mo | Yes (persistent disk) | Better docs, managed services |
| **Fly.io** | ~$2-5/mo (usage) | ~$15/mo | Pay per GB ($0.02/GB) | Tricky (ephemeral VMs) | No free tier. SQLite needs Volumes |
| **Railway** | $5/mo (includes $5 credit) | ~$10-15/mo | Included | No (ephemeral) | Great DX, bad for SQLite |
| **Render** | $7/mo | ~$25/mo | Included | No (ephemeral) | Predictable pricing |

### Why Hetzner

- **Price**: After April 2026 increases, still 2-3x cheaper than DigitalOcean at equivalent specs
- **Bandwidth**: 20 TB/mo included vs. DigitalOcean's 4 TB
- **Persistent disk**: SQLite runs on local NVMe -- fast, persistent, no special setup
- **Location**: EU datacenters (Falkenstein, Nuremberg, Helsinki) -- good for GDPR compliance
- **Bare metal option**: If you ever need more, Hetzner's dedicated servers start at EUR 39/mo

### Recommended Setup

**Start with Hetzner CX22 (2 shared vCPU, 4 GB RAM, 40 GB NVMe): EUR 4.49/mo (~$5.50)**

This comfortably runs:
- Kestrel app (FastAPI + React, single container)
- Caddy reverse proxy
- Litestream for SQLite backup
- Uptime Kuma for monitoring

Upgrade to CX32 (2 dedicated vCPU, 8 GB RAM) at ~$9.50/mo if you add AI provider calls or background job processing that needs more resources.

### US-based alternative

If US hosting is preferred for latency, **DigitalOcean $12/mo droplet** (2 GB RAM) is the pragmatic choice. Better documentation, simpler firewall UI, one-click Docker setup.

---

## 3. Zero-Downtime Deployment

### Recommendation: Kamal's built-in rolling deploy (or docker-rollout for Compose)

For a single-server, single-container app like Kestrel:

| Strategy | Complexity | Downtime | Rollback Speed | Best For |
|----------|-----------|----------|----------------|----------|
| **Kamal rolling deploy** | Low (built-in) | Zero | Instant | If using Kamal |
| **docker-rollout** | Low (plugin) | Zero | Fast (manual) | If using bare Docker Compose |
| **Blue-green (manual)** | Medium | Zero | Instant | If you want full control |
| **Just restart** | None | 5-15 seconds | N/A | MVP, honestly fine at first |

### docker-rollout (if staying with Docker Compose)

[docker-rollout](https://github.com/wowu/docker-rollout) is a Docker CLI plugin that replaces `docker compose up -d <service>` with zero-downtime rolling updates:

1. Scales service to 2x instances
2. Waits for new containers to pass health checks
3. Removes old containers

**Requirements:**
- Cannot use `container_name` in compose file (Kestrel's prod compose uses `careeros` -- needs removal)
- Cannot use `ports` directly (need a reverse proxy like Caddy/Traefik)
- Health checks must be defined (Kestrel already has `/health`)

### Database Migration Strategy

SQLite migrations (Alembic) must be backwards-compatible during rolling deploys:

1. **Expand**: Add new columns/tables (nullable or with defaults)
2. **Migrate**: Deploy app that writes to both old and new schema
3. **Contract**: Remove old columns in a subsequent deploy

Kestrel's `alembic upgrade head` runs before the app starts -- this is correct. Just ensure migrations never drop columns that the currently-running version needs.

---

## 4. SQLite in Production

### Recommendation: Litestream to S3-compatible storage

SQLite with WAL mode (which Kestrel already uses) is production-ready for single-server, moderate-traffic apps. The main risks are:
- Server failure = data loss (if no backups)
- No read replicas (fine for single-server)
- Write throughput limited to ~1000 TPS (fine for job search app)

### Backup Strategy: Litestream

Litestream continuously streams SQLite WAL changes to S3-compatible storage, providing:
- **Near-zero RPO**: Changes replicated within seconds
- **Point-in-time recovery**: Snapshots + WAL replay
- **Minimal overhead**: Runs as a sidecar, reads WAL files from disk

**Setup with Docker Compose:**
```yaml
services:
  litestream:
    image: litestream/litestream:latest
    volumes:
      - career-data:/data
      - ./litestream.yml:/etc/litestream.yml
    command: replicate
    restart: unless-stopped

  kestrel:
    # ... existing service
    volumes:
      - career-data:/app/data
```

**litestream.yml:**
```yaml
dbs:
  - path: /data/career_os.db
    replicas:
      - type: s3
        bucket: kestrel-backups
        path: db
        endpoint: https://s3.eu-central-1.amazonaws.com  # or Backblaze B2, Cloudflare R2
        retention: 720h  # 30 days
        snapshot-interval: 24h
```

**Cost**: Backblaze B2 is $0.005/GB/month, Cloudflare R2 has 10 GB free. A job search app's SQLite DB will be <100 MB. Monthly cost: effectively $0.

### LiteFS: Skip It

LiteFS (Fly.io's distributed SQLite) is pre-1.0, deprioritized by Fly.io, and LiteFS Cloud was sunset October 2024. Write throughput limited to ~100 TPS due to FUSE. Not recommended for new projects.

### When to Migrate to Postgres

Migrate when ANY of these occur:
- Multiple application servers need to write simultaneously
- Database exceeds 10 GB (SQLite performance degrades with large datasets)
- You need full-text search beyond SQLite's FTS5
- You want managed database hosting (RDS, Supabase, etc.)

For Kestrel's self-hosted single-user model, this is unlikely to happen. SQLite is the right choice.

---

## 5. Docker Deployment Pipeline

### Recommendation: GitHub Actions -> GHCR -> Kamal deploy

```
Push to main -> CI (lint, test) -> Build Docker image -> Push to GHCR -> Deploy via Kamal
```

### Multi-stage Build (Already Done Well)

Kestrel's Dockerfile is already well-structured:
- Stage 1: `node:22-alpine` builds React frontend
- Stage 2: `python:3.11-slim` runs FastAPI + serves static frontend

**Improvements to make:**

1. **Pin exact versions in FROM** (not just `22-alpine` but `22.14.0-alpine3.21`)
2. **Add `--mount=type=cache` for pip/npm** to speed up builds:
   ```dockerfile
   RUN --mount=type=cache,target=/root/.cache/pip pip install --no-cache-dir .
   ```
3. **Non-root user** (security hardening):
   ```dockerfile
   RUN useradd -r -s /bin/false kestrel
   USER kestrel
   ```
4. **Graceful shutdown** -- uvicorn already handles SIGTERM, but add `stop_grace_period: 30s` to compose

### GitHub Actions Deploy Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    needs: [ci]  # Reuse existing CI job
    steps:
      - uses: actions/checkout@v6
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          push: true
          tags: ghcr.io/pleasedodisturb/kestrel:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - uses: ruby/setup-ruby@v1
        with:
          ruby-version: '3.3'
      - run: gem install kamal
      - run: kamal deploy
        env:
          KAMAL_REGISTRY_PASSWORD: ${{ secrets.GITHUB_TOKEN }}
```

---

## 6. Environment Management

### Staging: Don't Bother (Yet)

For a solo developer, a separate staging environment is overhead that provides minimal value. Instead:

1. **Local Docker testing** with `docker-compose.prod.yml` (you already have this)
2. **CI pipeline** catches regressions before deploy
3. **Feature flags** for gradual rollouts (see below)

### Preview Environments: Coolify or Kamal PR apps (future)

Both Coolify and Kamal support PR-based preview deployments. This is a nice-to-have for later, not MVP.

### Feature Flags: Simple JSON or Environment Variables

For a solo dev, skip Unleash/Flagsmith/GrowthBook (all require PostgreSQL + their own infrastructure). Instead:

**Option A: Environment variables** (simplest)
```python
FEATURES = {
    "discovery_v2": os.getenv("FF_DISCOVERY_V2", "false") == "true",
    "ai_scoring": os.getenv("FF_AI_SCORING", "true") == "true",
}
```

**Option B: JSON file in config** (slightly more flexible)
```json
{
  "discovery_v2": { "enabled": false, "rollout_percent": 0 },
  "ai_scoring": { "enabled": true }
}
```

Graduate to a real feature flag service only when you have multiple users or need percentage rollouts.

---

## 7. Monitoring & Observability

### Recommendation: Uptime Kuma + Sentry Free Tier + Structured Logging

| Tool | Purpose | Cost | Setup Effort |
|------|---------|------|-------------|
| **Uptime Kuma** | Uptime monitoring, status page | Free (self-hosted) | 10 min |
| **Sentry Free** | Error tracking (Python + React) | Free (5K errors/mo) | 20 min |
| **Structured logging** | Application observability | Free | 1 hour |
| **Grafana Cloud Free** | Metrics dashboards | Free (10K series) | 30 min |
| **Ntfy** | Push notifications for alerts | Free (self-hosted) | 10 min |

### Uptime Kuma

Self-hosted, single Docker container, beautiful UI, 95+ notification channels. Run alongside your app:

```yaml
uptime-kuma:
  image: louislam/uptime-kuma:latest
  volumes:
    - uptime-kuma-data:/app/data
  ports:
    - "3001:3001"
  restart: unless-stopped
```

Monitor `/health`, set up Telegram/Discord notifications, get a public status page for free.

### Sentry Free Tier

5,000 errors and 10,000 performance events per month -- plenty for a self-hosted app. SDKs exist for both Python (FastAPI) and React. Setup is just `pip install sentry-sdk` + `npm install @sentry/react`.

**Alternative**: GlitchTip (self-hosted, Sentry SDK compatible, 4 containers vs Sentry's 40+, runs on 2 GB VPS). Only worth it if you exceed Sentry's free tier.

### Structured Logging

FastAPI with Python's `structlog`:
```python
import structlog
logger = structlog.get_logger()
logger.info("job_scored", job_id=123, score=85, provider="openrouter")
```

Output as JSON, ship to Grafana Cloud's free Loki tier (50 GB/month) via Promtail if you want centralized logs later.

---

## 8. CDN & Static Assets

### Recommendation: Cloudflare Free Plan

Kestrel's production Dockerfile serves the React frontend from FastAPI (single container). Cloudflare in front adds:

- **Free SSL** (though Caddy handles this too)
- **DDoS protection** (the real value)
- **CDN caching** for static assets (`/assets/*`)
- **Global edge network** for faster static delivery

**Setup**: Point DNS to Cloudflare, proxy enabled (orange cloud), cache static assets. Total time: 15 minutes. Cost: $0.

### Static Frontend Hosting (Alternative Architecture)

If you later separate frontend from backend:
- **Cloudflare Pages**: Free, unlimited bandwidth, deploy from GitHub
- **Vercel**: Free tier, great DX, but vendor lock-in
- **Netlify**: Free tier, similar to Vercel

Current single-container approach is simpler and correct for self-hosted. Only split if you need edge-deployed frontend.

---

## 9. Backup & Disaster Recovery

### Recommendation: Litestream + Hetzner Snapshots + Infrastructure as Code

| What | Tool | Frequency | Recovery Time |
|------|------|-----------|---------------|
| SQLite database | Litestream to S3/R2 | Continuous (seconds) | 5 minutes |
| Server state | Hetzner snapshots | Weekly | 10 minutes |
| Configuration | Git repo (deploy config) | Every commit | 5 minutes |
| Docker images | GHCR (tagged by SHA) | Every deploy | 2 minutes |
| Secrets | Bitwarden (already used) | As changed | Manual |

### Disaster Recovery Runbook

Server dies? Recovery in under 30 minutes:

1. **Provision new Hetzner CX22** (2 min via API or dashboard)
2. **Run Kamal setup** which installs Docker and configures the server (5 min)
3. **Deploy latest image** with `kamal deploy` (3 min)
4. **Restore SQLite from Litestream**: `litestream restore -o /data/career_os.db s3://kestrel-backups/db` (2 min)
5. **Verify** health check passes (1 min)

### Infrastructure as Code (Simple Version)

Don't use Terraform/Pulumi for a single server. Instead:
- **Kamal's `deploy.yml`**: Defines server, environment, health checks -- committed to git
- **`docker-compose.prod.yml`**: Already in git
- **Hetzner Cloud API**: Can provision a server with one `curl` command if needed

Keep a `RUNBOOK.md` in the repo with the exact recovery steps. This IS your IaC for a solo project.

---

## 10. Mobile Deployment (Expo EAS)

### Recommendation: EAS Build + EAS Submit + OTA Updates

| Service | Free Tier | Paid (Starter) | What You Get |
|---------|-----------|-----------------|-------------|
| **EAS Build** | Low-priority builds (slow) | $19/mo ($45 credit) | Priority builds, ~5 min iOS / ~8 min Android |
| **EAS Submit** | Included | Included | Auto-submit to TestFlight/Play Store |
| **EAS Update (OTA)** | 1,000 MAU | 3,000 MAU ($19/mo) | Push JS updates without app store review |

### Workflow

```
Code push -> EAS Build (cloud) -> EAS Submit -> TestFlight/Play Store
                                     |
                              OTA update (for JS-only changes)
```

### EAS Configuration (`eas.json`)

```json
{
  "cli": { "version": ">= 14.0.0" },
  "build": {
    "development": {
      "distribution": "internal",
      "ios": { "simulator": true }
    },
    "preview": {
      "distribution": "internal",
      "autoIncrement": true
    },
    "production": {
      "autoIncrement": true,
      "autoSubmit": true,
      "submitProfile": "production"
    }
  },
  "submit": {
    "production": {
      "ios": {
        "appleId": "your@email.com",
        "ascAppId": "your-app-id",
        "appleTeamId": "YOUR_TEAM_ID"
      },
      "android": {
        "serviceAccountKeyPath": "./google-play-key.json",
        "track": "internal"
      }
    }
  }
}
```

### OTA Update Strategy

- **Critical bug fixes**: Push OTA immediately (`eas update --branch production`)
- **Feature updates**: Full build + app store submission
- **Why OTA matters**: App store review takes 24-48 hours. OTA updates land in seconds.
- **Limitation**: OTA can only update JS/assets, not native modules

### Cost Optimization

Start with **free tier** (low-priority builds). Build times are slower (15-30 min vs 5-8 min) but free. Graduate to $19/mo Starter when:
- You need faster iteration (daily builds)
- You have >1000 monthly active users receiving OTA updates
- You need more than 1 concurrent build

### TestFlight/Play Store Notes

- **iOS**: First submission requires manual Apple Developer enrollment ($99/year). EAS Submit handles subsequent uploads automatically.
- **Android**: First APK/AAB must be uploaded manually to Google Play Console. After that, EAS Submit automates via service account.
- **Internal testing**: Both platforms allow immediate internal distribution without review.

---

## Decision Matrix: Deployment Architecture for Kestrel

### Phase 1: MVP Launch (Now)

| Decision | Choice | Monthly Cost |
|----------|--------|-------------|
| Hosting | Hetzner CX22 | $5.50 |
| Deploy tool | Docker Compose + manual `docker compose pull && up -d` | $0 |
| Reverse proxy | Caddy (automatic HTTPS) | $0 |
| SQLite backup | Litestream -> Cloudflare R2 (10 GB free) | $0 |
| Monitoring | Uptime Kuma (same server) | $0 |
| Error tracking | Sentry free tier | $0 |
| CDN | Cloudflare free plan | $0 |
| Mobile builds | EAS Build free tier | $0 |
| **Total** | | **~$5.50/mo** |

### Phase 2: Production Hardening

| Decision | Choice | Monthly Cost |
|----------|--------|-------------|
| Hosting | Hetzner CX32 (upgrade) | $9.50 |
| Deploy tool | Kamal 2 (zero-downtime) | $0 |
| Registry | GHCR (free with GitHub) | $0 |
| Mobile builds | EAS Starter | $19 |
| Domain | Already owned (assumed) | $0 |
| **Total** | | **~$28.50/mo** |

### Phase 3: Growth (Multiple Users)

| Decision | Choice | Monthly Cost |
|----------|--------|-------------|
| Hosting | Hetzner CX42 or dedicated | $15-39 |
| Database | Consider Postgres migration | (same server) |
| Feature flags | Unleash self-hosted | $0 |
| Log aggregation | Grafana Cloud free | $0 |
| **Total** | | **~$15-39/mo** |

---

## Sources

### Self-Hosted Platforms
- [Self-Hosted Deployment Tools Compared 2026](https://haloy.dev/blog/self-hosted-deployment-tools-compared)
- [Coolify Review 2026](https://temps.sh/blog/coolify-review-2026)
- [Coolify Security Vulnerabilities Disclosure](https://thehackernews.com/2026/01/coolify-discloses-11-critical-flaws.html)
- [Dokku Review 2026](https://www.srvrlss.io/provider/dokku/)
- [Kamal Deploy](https://kamal-deploy.org/)
- [Deploying FastAPI with Kamal on Hetzner](https://www.ianwootten.co.uk/2024/10/13/deploying-a-fastapi-app-to-hetzner-with-kamal/)
- [Deploying Multiple Apps with Kamal 2](https://www.honeybadger.io/blog/new-in-kamal-2/)

### Hosting
- [Hetzner Price Adjustment April 2026](https://www.hetzner.com/pressroom/statement-price-adjustment/)
- [DigitalOcean vs Hetzner 2026](https://betterstack.com/community/guides/web-servers/digitalocean-vs-hetzner/)
- [Fly.io Pricing](https://fly.io/docs/about/pricing/)
- [Railway Pricing 2026](https://railway.com/pricing)

### SQLite in Production
- [Litestream](https://litestream.io/)
- [SQLite Renaissance 2026](https://dev.to/pockit_tools/the-sqlite-renaissance-why-the-worlds-most-deployed-database-is-taking-over-production-in-2026-3jcc)
- [LiteFS Docs (deprioritized)](https://fly.io/docs/litefs/)

### Zero-Downtime
- [docker-rollout](https://github.com/wowu/docker-rollout)
- [Zero Downtime Deployment 2026](https://rajeshrnair.com/blog/zero-downtime-deployment)

### Monitoring
- [Uptime Kuma](https://uptimekuma.org/)
- [Sentry Alternatives 2026](https://dev.to/david-ssojet/best-sentry-alternatives-for-error-tracking-and-monitoring-2026-44op)
- [GlitchTip vs Sentry](https://osalfinder.com/sentry-vs-glitchtip/)

### CDN
- [Cloudflare Free Plan](https://www.cloudflare.com/plans/free/)
- [Caddy Reverse Proxy Guide](https://1vps.com/caddy-reverse-proxy-guide)

### Mobile
- [EAS Submit Docs](https://docs.expo.dev/submit/introduction/)
- [EAS Pricing](https://expo.dev/pricing)
- [EAS Automated Submissions](https://docs.expo.dev/build/automate-submissions/)

### Feature Flags
- [Open Source Feature Flag Tools Compared 2026](https://flagshark.com/blog/open-source-feature-flag-tools-compared-2026/)
