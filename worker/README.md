# Sync Worker

Cloudflare Worker that handles bidirectional sync between Linear and TickTick.

## What It Does

- **Linear -> TickTick:** Receives Linear webhooks on issue status change, creates/updates TickTick tasks
- **TickTick -> Linear:** Polls TickTick every 15 minutes, syncs completed tasks back to Linear
- **Dashboard rebuild:** Triggers Cloudflare Pages deploy hook after each sync

## Setup

### 1. Deploy the Worker

```bash
cd worker
npm install
npx wrangler login        # Authenticate with Cloudflare
npx wrangler deploy        # Deploy to Cloudflare
```

### 2. Set Secrets

```bash
npx wrangler secret put LINEAR_API_KEY
npx wrangler secret put LINEAR_WEBHOOK_SECRET
npx wrangler secret put TICKTICK_ACCESS_TOKEN
npx wrangler secret put TICKTICK_PROJECT_ID
npx wrangler secret put CF_PAGES_DEPLOY_HOOK
```

### 3. Configure Linear Webhook

1. Go to Linear > Settings > API > Webhooks
2. Create webhook:
   - **URL:** `https://job-search-sync.<your-account>.workers.dev/webhook/linear`
   - **Events:** Issue updates
   - **Secret:** Same value you set for `LINEAR_WEBHOOK_SECRET`

### 4. Get TickTick API Token

1. Go to [TickTick Developer Portal](https://developer.ticktick.com/manage)
2. Create an app, get OAuth access token
3. Set it as the `TICKTICK_ACCESS_TOKEN` secret

## Endpoints

- `GET /health` -- Health check
- `POST /webhook/linear` -- Linear webhook receiver
- `POST /sync` -- Manual trigger for TickTick -> Linear sync

## Cron

Runs every 15 minutes to poll TickTick for completed tasks.
