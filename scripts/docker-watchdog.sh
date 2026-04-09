#!/usr/bin/env bash
set -euo pipefail

# docker-watchdog.sh — Check Kestrel containers and restart if unhealthy
#
# Usage:
#   bash scripts/docker-watchdog.sh              # one-shot check & fix
#   bash scripts/docker-watchdog.sh --watch      # continuous monitoring
#   bash scripts/docker-watchdog.sh -f docker-compose.prod.yml  # production
#
# Exit codes: 0 = healthy, 1 = recovery failed, 2 = Docker unavailable

COMPOSE_FILE=""
WATCH_MODE=false
CHECK_INTERVAL=30
DOCKER_WAIT_TIMEOUT=60
HEALTH_URL="http://localhost:8100/health"

usage() {
    echo "Usage: bash scripts/docker-watchdog.sh [OPTIONS]"
    echo ""
    echo "Check Kestrel Docker containers and restart them if unhealthy."
    echo ""
    echo "Options:"
    echo "  -f FILE        Docker Compose file (default: docker-compose.yml)"
    echo "  --watch        Run continuously instead of one-shot"
    echo "  --interval N   Seconds between checks in watch mode (default: 30)"
    echo "  -h, --help     Show this help message"
    exit 0
}

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f)           COMPOSE_FILE="$2"; shift 2 ;;
        --watch)      WATCH_MODE=true; shift ;;
        --interval)   CHECK_INTERVAL="$2"; shift 2 ;;
        -h|--help)    usage ;;
        *)            echo "Unknown option: $1"; usage ;;
    esac
done

# Default compose file
if [ -z "$COMPOSE_FILE" ]; then
    COMPOSE_FILE="docker-compose.yml"
fi

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Compose file not found: $COMPOSE_FILE"
    echo "Run this script from the Kestrel project folder."
    exit 1
fi

COMPOSE_CMD=(docker compose -f "$COMPOSE_FILE")

wait_for_docker() {
    local elapsed=0
    while ! docker info &>/dev/null 2>&1; do
        if [ "$elapsed" -ge "$DOCKER_WAIT_TIMEOUT" ]; then
            log "Docker did not respond within ${DOCKER_WAIT_TIMEOUT}s"
            return 1
        fi
        if [ "$elapsed" -eq 0 ]; then
            log "Waiting for Docker to start..."
            # Try to launch Docker Desktop on macOS
            if [[ "$(uname 2>/dev/null)" == "Darwin" ]]; then
                open -a Docker 2>/dev/null || true
            fi
        fi
        sleep 5
        elapsed=$((elapsed + 5))
    done
    return 0
}

check_health() {
    # Check if containers are running
    local running
    running=$("${COMPOSE_CMD[@]}" ps --status running -q 2>/dev/null | wc -l | tr -d ' ')
    local expected
    expected=$("${COMPOSE_CMD[@]}" config --services 2>/dev/null | wc -l | tr -d ' ')

    if [ "$running" -lt "$expected" ]; then
        log "Only $running of $expected containers running"
        return 1
    fi

    # Check the health endpoint directly
    if ! curl -sf --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
        log "Health endpoint not responding"
        return 1
    fi

    return 0
}

recover() {
    log "Restarting containers..."
    "${COMPOSE_CMD[@]}" up -d 2>&1 | tail -5

    # Wait for health (same pattern as setup.sh)
    log "Waiting for health check..."
    local i
    for i in $(seq 1 30); do
        if curl -sf --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
            log "Kestrel is healthy again"
            return 0
        fi
        sleep 2
    done

    log "Recovery failed — containers did not become healthy within 60s"
    log "Try: "${COMPOSE_CMD[@]}" logs backend"
    return 1
}

run_check() {
    if ! wait_for_docker; then
        return 2
    fi

    if check_health; then
        log "All containers healthy"
        return 0
    fi

    recover
}

# Main
if [ "$WATCH_MODE" = true ]; then
    log "Watching Kestrel containers (every ${CHECK_INTERVAL}s, Ctrl+C to stop)"
    while true; do
        run_check || true
        sleep "$CHECK_INTERVAL"
    done
else
    run_check
fi
