# Dashboard

Job Search HQ dashboard -- a static site deployed on Cloudflare Pages.

## Local Development

```bash
# Set your Linear API key (or create a .env file in the repo root)
export LINEAR_API_KEY=lin_api_xxxxx

# Build data + serve locally
npm run dev
# Opens at http://localhost:3000
```

## Cloudflare Pages Deployment

1. Go to [Cloudflare Dashboard > Pages](https://dash.cloudflare.com/?to=/:account/pages)
2. Create a project > Connect to Git > Select `job-search-hq` repo
3. Build settings:
   - **Build command:** `cd dashboard && npm install && npm run build`
   - **Build output directory:** `dashboard`
   - **Root directory:** `/`
4. Environment variables:
   - `LINEAR_API_KEY` = your Linear personal API key
5. Deploy

## Cloudflare Access (Private)

After deploying, add access control:
1. Go to Cloudflare Dashboard > Zero Trust > Access > Applications
2. Add application > Self-hosted
3. Application domain: your `*.pages.dev` domain
4. Add policy: Allow > Email = your email
5. Authentication: One-time PIN (email OTP)
