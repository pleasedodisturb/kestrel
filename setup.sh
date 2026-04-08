#!/usr/bin/env bash
set -euo pipefail

echo ""
echo "  Kestrel Setup"
echo "  ============="
echo "  Your AI-powered job search system"
echo ""

# -- Check Docker --
if ! command -v docker &>/dev/null; then
    echo "Docker not found."
    echo ""
    echo "  Install Docker Desktop: https://docker.com"
    echo "  Or OrbStack (Mac):     https://orbstack.dev"
    echo ""
    echo "After installing, run this script again."
    exit 1
fi

if ! docker info &>/dev/null 2>&1; then
    echo "Docker is installed but not running."
    echo ""
    echo "  Start Docker Desktop or OrbStack, then run this script again."
    exit 1
fi

echo "[ok] Docker is ready"

# -- Config files --
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[ok] Created .env from .env.example"
    echo "     Edit .env to add API keys (optional - works without them)"
else
    echo "[ok] .env already exists"
fi

if [ ! -f config/personal.yaml ]; then
    mkdir -p config
    cp config/personal.yaml.example config/personal.yaml
    echo "[ok] Created config/personal.yaml"
    echo "     Edit it with your name, email, and job preferences"
else
    echo "[ok] config/personal.yaml already exists"
fi

echo ""

# -- Handle --dry-run flag --
if [[ "${1:-}" == "--dry-run" ]]; then
    echo "Dry run complete. Everything looks good."
    echo "Run ./setup.sh without --dry-run to start Kestrel."
    exit 0
fi

# -- Build and start --
echo "Building and starting Kestrel (this takes 2-3 minutes the first time)..."
echo ""
docker compose up -d --build 2>&1 | tail -5

# -- Wait for health --
echo ""
echo "Waiting for backend to be ready..."
healthy=false
for i in $(seq 1 30); do
    if curl -sf http://localhost:8100/health >/dev/null 2>&1; then
        healthy=true
        break
    fi
    sleep 2
done

if [ "$healthy" = true ]; then
    echo "[ok] Backend is healthy"
else
    echo ""
    echo "Backend didn't respond in 60 seconds. This might be normal on first run."
    echo ""
    echo "  Check logs:    docker compose logs backend"
    echo "  Retry:         docker compose restart backend"
    echo "  Start fresh:   docker compose down -v && docker compose up -d --build"
    exit 1
fi

echo ""
echo "================================================"
echo ""
echo "  Kestrel is running!"
echo ""
echo "  Dashboard:  http://localhost:8101"
echo "  API docs:   http://localhost:8100/docs"
echo ""
echo "  Next steps:"
echo "  1. Open http://localhost:8101"
echo "  2. Go to Settings > Profiles and add your details"
echo "  3. Add your first job application to the pipeline"
echo ""
echo "  To use real AI scoring (optional):"
echo "  1. Get an API key from https://openrouter.ai"
echo "  2. Edit .env: AI_PROVIDER=openrouter"
echo "  3. Edit .env: OPENROUTER_API_KEY=your-key"
echo "  4. Restart: docker compose restart backend"
echo ""
echo "  To stop:  docker compose down"
echo "  To start: docker compose up -d"
echo ""
echo "================================================"
