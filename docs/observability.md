# Observability with Langfuse

Kestrel includes optional LLM observability via [Langfuse](https://langfuse.com) (v3, MIT licensed, self-hosted). When enabled, every AI provider call is traced with model, token usage, latency, cache hit/miss, and PII detection counts.

## Quick Start

### 1. Start the Langfuse stack

```bash
# Copy and configure the env file
cp langfuse.env.example langfuse.env
# Edit langfuse.env — generate secrets as instructed in the file

# Start Kestrel + Langfuse together
docker compose -f docker-compose.yml -f docker-compose.langfuse.yml up
```

Langfuse UI will be available at **http://localhost:3100**.

On first boot, Langfuse auto-creates an org, project, and API keys via the `LANGFUSE_INIT_*` env vars in `langfuse.env`.

### 2. Connect Kestrel to Langfuse

Add these to your Kestrel `.env` file:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-kestrel-dev
LANGFUSE_SECRET_KEY=sk-lf-kestrel-dev
LANGFUSE_HOST=http://localhost:3100
```

### 3. Install the Python SDK

```bash
pip install kestrel-app[observability]
```

Restart Kestrel. You should see `Langfuse observability enabled` in the logs.

## What Gets Traced

| Layer | What's captured | Langfuse type |
|-------|----------------|---------------|
| **AI Providers** (OpenRouter, Anthropic, Together, Ollama) | Model, input/output (truncated to 500 chars), token usage (input/output/cache tokens) | Generation |
| **Cache** (CachedProvider) | Cache hit/miss, feature type | Span metadata |
| **PII Masking** (MaskedProvider) | Detection count (NOT the PII values) | Span metadata |
| **Route context** | user_id (profile_id), session_id, tags, metadata (job_family, rubric_version) | Trace attributes |

### Token Usage Details

Each generation includes `usage_details` with provider-specific fields:

- **OpenRouter**: `input`, `output`
- **Anthropic**: `input`, `output`, `cache_read_input_tokens`, `cache_creation_input_tokens`
- **Together**: `input`, `output`
- **Ollama**: `input`, `output`

## Configuration

All configuration is via environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LANGFUSE_PUBLIC_KEY` | Yes (to enable) | — | Project public key from Langfuse |
| `LANGFUSE_SECRET_KEY` | Yes (to enable) | — | Project secret key from Langfuse |
| `LANGFUSE_HOST` | Recommended | `https://cloud.langfuse.com` | Self-hosted Langfuse URL |

When `LANGFUSE_PUBLIC_KEY` is not set, all observability code is a no-op with zero overhead. The `langfuse` package itself is an optional dependency — Kestrel runs fine without it installed.

## Architecture

```
FastAPI Route
  └── propagate_attributes(user_id, session_id, tags, metadata)
        └── MaskedProvider  [@observe → pii_detections count]
              └── CachedProvider  [@observe → cache hit/miss]
                    └── Provider.complete()  [@observe(as_type="generation")]
                          └── update_current_generation(model, input, output, usage_details)
```

The instrumentation wraps the existing provider decorator chain. Each layer adds its own span or generation to the trace. The `propagate_attributes` context manager at the route level injects user and session context that flows to all child observations.

## Graceful Degradation

The observability module (`src/career_os/ai/observability.py`) handles three states:

1. **`langfuse` not installed**: All functions are no-ops. Zero import overhead.
2. **`langfuse` installed but `LANGFUSE_PUBLIC_KEY` not set**: Same no-op behavior.
3. **`langfuse` installed and configured**: Full tracing active.

On application shutdown, `flush()` is called in the FastAPI lifespan to drain any pending events.

## Self-Hosted Langfuse Stack

The `docker-compose.langfuse.yml` file provides a complete Langfuse v3 stack:

| Service | Image | Port (host) | Purpose |
|---------|-------|-------------|---------|
| langfuse-web | `langfuse/langfuse:3` | 3100 | Web UI + API |
| langfuse-worker | `langfuse/langfuse-worker:3` | — | Async event processing |
| langfuse-postgres | `postgres:16-alpine` | 5433 | Metadata storage |
| langfuse-clickhouse | `clickhouse/clickhouse-server:24` | 8124, 9001 | Analytics/trace storage |
| langfuse-redis | `redis:7-alpine` | 6380 | Job queues |
| langfuse-minio | `minio/minio:latest` | 9090, 9091 | S3-compatible blob storage |

**Resource requirements**: 4 vCPU / 8 GB RAM minimum.

All credentials are in `langfuse.env` (not in the compose file). Copy `langfuse.env.example` and generate secrets before first run.

## Dashboard Tips

Once traces are flowing, use the Langfuse UI to:

- **Filter by tags**: Use tags like `scoring`, `coaching`, `gap-analysis` to isolate feature types
- **Track costs**: Langfuse auto-calculates costs for known models (Anthropic, OpenAI). Set custom pricing for OpenRouter/Together models in Settings > Models
- **Monitor cache efficiency**: Filter spans by `cache=hit` vs `cache=miss` metadata to measure cache hit rate
- **Detect PII leaks**: Sort by `pii_detections > 0` to verify masking is working
- **Compare providers**: Group generations by model to compare latency and token usage across providers
