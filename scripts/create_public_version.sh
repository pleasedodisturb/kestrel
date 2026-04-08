#!/bin/bash
# Job Search HQ - Public Version Sanitization Script
# Run from ~/Projects/Jobs

set -e

PUBLIC_DIR="$HOME/Projects/REDACTED-public"

echo "🚀 Creating public version of Job Search HQ..."

# 1. Create fresh directory
mkdir -p "$PUBLIC_DIR"
cd "$PUBLIC_DIR"

# 2. Copy core structure (excluding sensitive stuff)
echo "📦 Copying core files..."

# Core docs and config
cp -r "$HOME/Projects/Jobs/docs" .
cp -r "$HOME/Projects/Jobs/dashboard" .
cp -r "$HOME/Projects/Jobs/recipes" .
cp -r "$HOME/Projects/Jobs/scripts" .
cp -r "$HOME/Projects/Jobs/tools" .
cp -r "$HOME/Projects/Jobs/worker" .

# Profile (will sanitize separately)
cp -r "$HOME/Projects/Jobs/profile" .

# Root files
cp "$HOME/Projects/Jobs/README.md" .
cp "$HOME/Projects/Jobs/.gitignore" .
cp "$HOME/Projects/Jobs/requirements.txt" .
cp "$HOME/Projects/Jobs/AGENT.md" .
cp "$HOME/Projects/Jobs/.goosehints" . 2>/dev/null || true

# 3. Create tracking directory with examples only
mkdir -p tracking
echo "company,role,location,status,score,date_added,url,notes" > tracking/applications.csv.example
echo "Example Corp,Senior AI Engineer,Remote,interested,9,2024-01-15,https://example.com/job,Remote-first company" >> tracking/applications.csv.example
echo "Tech Startup,Product Engineer,Berlin,applied,8,2024-01-20,https://example.com/job2,Early stage" >> tracking/applications.csv.example

# 4. Clean up sensitive artifacts
echo "🧹 Removing sensitive files..."
rm -f germany_jobs_out.json germany_jobs_err.txt
rm -f compass_artifact_*.md
rm -f oxide-computer-*.md
rm -rf docs/Mx-CRM-shadow-context
rm -rf .cursor .venv __pycache__ node_modules

# 5. Update .gitignore
echo "
# Personal data
tracking/applications.csv
tracking/contacts.csv
germany_jobs_out.json
germany_jobs_err.txt
compass_artifact_*.md
oxide-computer-*.md
*-intake.md

# Environment
.env
.env.local
*.local

# MCP configs (may contain API keys)
.cursor/
mcp.json
" >> .gitignore

echo "✅ Public version created at: $PUBLIC_DIR"
echo ""
echo "⚠️  NEXT STEPS (manual):"
echo "1. Sanitize profile/*.md files (remove personal email/phone/LinkedIn)"
echo "2. Review all docs for sensitive info"
echo "3. Create SETUP.md, ARCHITECTURE.md, PHILOSOPHY.md"
echo "4. Initialize git: cd $PUBLIC_DIR && git init"
echo "5. Create GitHub repo and push"
