#!/usr/bin/env bash
# External cron trigger for daily scan - bypasses GitHub's scheduler deprioritization
#
# Deploy: crontab on any server or Mac Mini:
#   17 7 * * * /path/to/kestrel/automation/trigger-daily-scan.sh
#
# GitHub Actions deprioritizes cron jobs on inactive repos, especially weekends.
# This script acts as a reliable external trigger that calls the workflow via API.
#
# Prerequisites:
#   - gh CLI installed and authenticated
#   - Network access to GitHub API
#
# Optional environment variables:
#   KESTREL_REPO          - Override target repo (default: auto-detect from git remote)
#   PUSHOVER_APP_TOKEN    - Pushover app token for failure alerts
#   PUSHOVER_USER_KEY     - Pushover user key for failure alerts

set -euo pipefail

# Auto-detect repo from git remote, or use override
if [ -n "${KESTREL_REPO:-}" ]; then
  REPO="$KESTREL_REPO"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
  REPO=$(git -C "$PROJECT_DIR" remote get-url origin 2>/dev/null \
    | sed -E 's|.*github\.com[:/]||; s|\.git$||')

  if [ -z "$REPO" ]; then
    echo "[ERROR] Could not detect repo. Set KESTREL_REPO env var."
    exit 1
  fi
fi

WORKFLOW="daily-scan.yml"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Triggering ${WORKFLOW} on ${REPO}"

if gh workflow run "${WORKFLOW}" --repo "${REPO}"; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Trigger sent successfully"
else
  EXIT_CODE=$?
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Trigger FAILED (exit ${EXIT_CODE})"

  # Send Pushover alert if secrets are available
  if [ -n "${PUSHOVER_APP_TOKEN:-}" ] && [ -n "${PUSHOVER_USER_KEY:-}" ]; then
    curl -s \
      --form-string "token=$PUSHOVER_APP_TOKEN" \
      --form-string "user=$PUSHOVER_USER_KEY" \
      --form-string "title=Kestrel Trigger Failed" \
      --form-string "message=External trigger for ${WORKFLOW} failed on ${REPO} with exit code ${EXIT_CODE}." \
      --form-string "priority=1" \
      https://api.pushover.net/1/messages.json
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Pushover alert sent"
  fi

  exit "$EXIT_CODE"
fi
