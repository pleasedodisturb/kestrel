#!/usr/bin/env bash
set -euo pipefail

# Build script for pip-installable Kestrel package
# Creates a wheel that includes the pre-built React frontend

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Building Kestrel pip package..."
echo ""

# Step 1: Build frontend
echo "[1/4] Building React frontend..."
(cd "$ROOT/frontend" && npm ci --legacy-peer-deps && npm run build)
echo ""

# Step 2: Copy frontend dist into the Python package
echo "[2/4] Bundling frontend into Python package..."
FRONTEND_DEST="$ROOT/src/career_os/_frontend_dist"
rm -rf "$FRONTEND_DEST"
cp -r "$ROOT/frontend/dist" "$FRONTEND_DEST"

# Step 3: (no-op) migrations already live in src/career_os/_alembic and are
# committed + shipped via package-data, so there is nothing to bundle (G-1350).
echo "[3/4] Migrations are in-package (src/career_os/_alembic) — nothing to bundle."

# Step 4: Build the wheel
echo "[4/4] Building Python package..."
(cd "$ROOT" && python -m build)

echo ""
echo "Done! Package is in dist/"
ls -la "$ROOT/dist/"
echo ""
echo "To install locally:  pip install dist/kestrel_app-*.whl"
echo "To upload to PyPI:   twine upload dist/*"
