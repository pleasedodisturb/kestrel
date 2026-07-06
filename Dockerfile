# =============================================================================
# Kestrel — Multi-stage Dockerfile
# Single container: serves both FastAPI API and React frontend on one port.
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build the React frontend
# ---------------------------------------------------------------------------
FROM node:22-alpine AS frontend-build

WORKDIR /build

# Copy package files first for layer caching
COPY frontend/package.json frontend/package-lock.json* ./

# Install dependencies (--legacy-peer-deps needed for @tailwindcss/vite 4.x + Vite 8.x)
RUN npm ci --legacy-peer-deps

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: Python runtime — FastAPI + static frontend
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (curl for health check).
# `apt-get upgrade` picks up security patches to base-image packages
# (e.g. libssh2) that Trivy flags as fixable CRITICAL/HIGH.
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Upgrade build tooling before installing the package — pip's bundled
# setuptools/wheel can lag behind fixed CVEs (wheel, vendored
# jaraco.context) that Trivy flags as fixable CRITICAL/HIGH.
# Runs before the COPY layers so source edits don't invalidate it.
RUN pip install --no-cache-dir -U pip setuptools wheel

# Copy dependency specification and source (needed for pip install)
COPY pyproject.toml ./
COPY src/ ./src/

# Install the package (non-editable production install)
RUN pip install --no-cache-dir .

# Copy Alembic configuration and migrations
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Copy built frontend from stage 1
COPY --from=frontend-build /build/dist ./frontend/dist

# Ensure data directory exists (will be mounted as a volume)
RUN mkdir -p /app/data

# Default environment variables
ENV AI_PROVIDER=mock \
    DATABASE_URL=sqlite:///data/career_os.db \
    HOST=0.0.0.0 \
    PORT=8100 \
    FRONTEND_URL="*"

EXPOSE 8100

# Health check (honors $PORT; defaults to 8100 for local runs)
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf "http://localhost:${PORT:-8100}/health" || exit 1

# Run Alembic migrations, then start uvicorn.
# Bind to $PORT so platforms that inject it (Railway, etc.) route correctly;
# falls back to 8100 for local docker/compose.
CMD ["sh", "-c", "alembic upgrade head && uvicorn career_os.main:app --host 0.0.0.0 --port ${PORT:-8100}"]
