#!/usr/bin/env bash
set -euo pipefail

echo ""
echo "  Kestrel Setup"
echo "  ============="
echo "  Your AI-powered job search system"
echo ""

# -- Check Docker --
if ! command -v docker &>/dev/null; then
    echo "Docker is not installed."
    echo ""
    echo "  Docker is a free app that runs Kestrel on your computer."
    echo "  Download it from: https://www.docker.com/products/docker-desktop/"
    echo ""
    echo "  Install it like any other app (drag to Applications on Mac)."
    echo "  You do NOT need to create a Docker account."
    echo ""
    echo "After installing, open Docker Desktop, then run this script again."
    exit 1
fi

if ! docker info &>/dev/null 2>&1; then
    echo "Docker is installed but not running."
    echo ""
    echo "  Open the Docker Desktop app from your Applications folder."
    echo "  Wait for the whale icon in your menu bar to stop animating."
    echo "  Then run this script again."
    echo ""
    # Try to start Docker on macOS
    if [[ "$(uname)" == "Darwin" ]]; then
        echo "  Trying to start Docker for you..."
        open -a Docker 2>/dev/null || true
        echo "  Docker is starting. Wait about 30 seconds, then run this script again."
    fi
    exit 1
fi

echo "[ok] Docker is ready"

# -- Check ports --
check_port() {
    local port=$1
    if command -v lsof &>/dev/null && lsof -i :"$port" >/dev/null 2>&1; then
        echo ""
        echo "Port $port is already in use by another program."
        echo ""
        echo "  Either close that program, or change the port:"
        echo "  1. Open the .env file in a text editor"
        echo "  2. Change PORT=8100 to PORT=8200 (or any free port)"
        echo "  3. Run this script again"
        echo ""
        exit 1
    fi
}

check_port 8100
check_port 8101
echo "[ok] Ports 8100 and 8101 are free"

# -- Check disk space --
if command -v df &>/dev/null; then
    available_mb=$(df -m . 2>/dev/null | awk 'NR==2 {print $4}')
    if [ -n "$available_mb" ] && [ "$available_mb" -lt 2048 ] 2>/dev/null; then
        echo ""
        echo "Low disk space: ${available_mb}MB available, Kestrel needs about 2GB."
        echo ""
        echo "  Free up some space and try again."
        echo "  Tip: Docker images from other projects can take a lot of space."
        echo "  Run 'docker system prune' to clean up unused Docker data."
        exit 1
    fi
fi
echo "[ok] Disk space looks fine"

# -- Check internet (quick) --
if ! curl -sf --max-time 5 https://registry-1.docker.io/v2/ >/dev/null 2>&1; then
    echo ""
    echo "Can't reach Docker's servers. Check your internet connection."
    echo "Kestrel needs internet for the first setup (to download components)."
    echo "After setup, it works fully offline."
    echo ""
    echo "  If you're behind a VPN or firewall, try disconnecting and running again."
    exit 1
fi
echo "[ok] Internet connection works"

# -- Config files --
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[ok] Created settings file (.env)"
    echo "     Kestrel works out of the box. Edit .env later to add AI keys."
else
    echo "[ok] Settings file (.env) already exists"
fi

if [ ! -f config/personal.yaml ]; then
    mkdir -p config
    cp config/personal.yaml.example config/personal.yaml
    echo "[ok] Created your profile (config/personal.yaml)"
    echo "     Edit it with your name, email, and job preferences"
else
    echo "[ok] Profile (config/personal.yaml) already exists"
fi

echo ""

# -- Handle --dry-run flag --
if [[ "${1:-}" == "--dry-run" ]]; then
    echo "Dry run complete. Everything looks good."
    echo "Run this script without --dry-run to start Kestrel."
    exit 0
fi

# -- Build and start --
echo "Building Kestrel (this takes 2-3 minutes the first time)..."
echo "Don't close this window. You'll see some technical output - that's normal."
echo ""

if ! docker compose up -d --build 2>&1 | tail -10; then
    echo ""
    echo "Something went wrong during the build."
    echo ""
    echo "  Common causes:"
    echo "  - No internet connection (Docker needs to download components)"
    echo "  - Not enough disk space (Kestrel needs about 2 GB)"
    echo ""
    echo "  Try again: bash setup.sh"
    echo "  Still failing? Copy the error above and ask ChatGPT or Claude:"
    echo "  'I'm setting up Kestrel (a Docker-based app) and got this error: [paste error]'"
    exit 1
fi

# -- Wait for health --
echo ""
echo "Starting up (checking every few seconds)..."
healthy=false
for i in $(seq 1 45); do
    if curl -sf http://localhost:8100/health >/dev/null 2>&1; then
        healthy=true
        break
    fi
    # Show progress dots so user knows it's not frozen
    printf "."
    sleep 2
done
echo ""

if [ "$healthy" = true ]; then
    echo "[ok] Kestrel is healthy and ready"

    # -- Check AI provider status --
    ai_provider=$(grep "^AI_PROVIDER=" .env 2>/dev/null | cut -d= -f2 | tr -d ' "')
    if [ "$ai_provider" = "openrouter" ]; then
        api_key=$(grep "^OPENROUTER_API_KEY=" .env 2>/dev/null | cut -d= -f2 | tr -d ' "')
        if [ -z "$api_key" ]; then
            echo ""
            echo "[!] AI_PROVIDER is set to openrouter but OPENROUTER_API_KEY is empty."
            echo "    Kestrel will fall back to Demo Mode until you add a key."
        elif [[ ! "$api_key" == sk-or-* ]]; then
            echo ""
            echo "[!] Your OPENROUTER_API_KEY doesn't start with 'sk-or-'."
            echo "    It might be pasted incorrectly. Check for extra spaces."
            echo "    Get your key at: https://openrouter.ai/keys"
        fi
    fi
else
    echo ""
    echo "Kestrel didn't start in 90 seconds."
    echo ""
    # Try to diagnose the actual problem
    backend_log=$(docker compose logs backend --tail 5 2>/dev/null)
    if echo "$backend_log" | grep -qi "address already in use"; then
        echo "  Problem: Port 8100 is being used by something else."
        echo "  Fix: Close that program, or edit .env and change PORT=8200"
    elif echo "$backend_log" | grep -qi "no space left"; then
        echo "  Problem: Not enough disk space."
        echo "  Fix: Free up space and run 'bash setup.sh' again."
    elif echo "$backend_log" | grep -qi "connection refused\|network"; then
        echo "  Problem: Network issue during startup."
        echo "  Fix: Check your internet and run 'bash setup.sh' again."
    else
        echo "  This sometimes happens on the first run. Try these:"
        echo "  1. Wait another minute, then open http://localhost:8101"
        echo "  2. Start fresh: docker compose down -v && bash setup.sh"
    fi
    echo ""
    echo "  Still stuck? Here's what to do:"
    echo "  - Open an issue: https://github.com/pleasedodisturb/kestrel/issues"
    echo "  - Or paste this into ChatGPT/Claude:"
    echo "    'I'm setting up Kestrel (a Docker job search tool) and it didn't"
    echo "     start after 90 seconds. Here's the last few log lines:"
    echo "     $(docker compose logs backend --tail 3 2>/dev/null | head -3)'"
    exit 1
fi

echo ""
echo "================================================"
echo ""
echo "  Kestrel is running!"
echo ""
echo "  Open in your browser:  http://localhost:8101"
echo ""
echo "  What to do now:"
echo "  1. Open http://localhost:8101 in Chrome/Safari/Firefox"
echo "  2. Go to Settings > Profiles and add your details"
echo "  3. Try the Discovery page to find jobs automatically"
echo ""
echo "  Kestrel is running in Demo Mode (free, offline)."
echo "  To get real AI-powered scoring:"
echo "  1. Sign up at https://openrouter.ai (takes 2 minutes)"
echo "  2. Open .env in a text editor and set:"
echo "     AI_PROVIDER=openrouter"
echo "     OPENROUTER_API_KEY=your-key-here"
echo "  3. Restart: docker compose restart backend"
echo ""
echo "  To stop Kestrel:  docker compose down"
echo "  To start again:   docker compose up -d"
echo "  Your data is saved between restarts."
echo ""
echo "================================================"
