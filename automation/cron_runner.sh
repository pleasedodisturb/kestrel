#!/usr/bin/env bash
# Daily job scan — cron/launchd runner
#
# Schedule with cron (edit via: crontab -e):
#   0 7 * * 1-5 /path/to/job-search-hq/automation/cron_runner.sh >> /path/to/job-search-hq/logs/cron.log 2>&1
#
# Schedule with launchd (macOS):
#   See automation/com.jobsearchhq.daily-scan.plist
#
# Required env vars (set in your shell profile or pass inline):
#   OPENAI_API_KEY — for AI scoring
#
# Optional env vars:
#   PIPELINE_MODE       — api-only (default) | api-plus | all
#   PIPELINE_MIN_SCORE  — minimum score threshold (default: 5)
#   PIPELINE_HOURS_OLD  — max posting age in hours (default: 24)
#   PIPELINE_LOCATION   — search location (default: Berlin)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Daily Job Scan: $(date) ==="
echo "Project dir: $PROJECT_DIR"

cd "$PROJECT_DIR"

# Ensure logs directory exists
mkdir -p logs

# Activate venv
if [ ! -f ".venv/bin/python" ]; then
    echo "ERROR: .venv not found. Run: python -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Load env vars from .env if it exists (for API keys)
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Run the pipeline
echo "Running pipeline..."
.venv/bin/python tools/daily_pipeline.py
EXIT_CODE=$?

echo "Pipeline finished with exit code: $EXIT_CODE"
echo "=== Done: $(date) ==="

exit $EXIT_CODE
