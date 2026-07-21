"""Application configuration."""

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

# Ensure .env vars land in os.environ before anything reads them (ported from
# Eyas). pydantic-settings can silently fail to load some variables from .env,
# and the tools/ pipeline reads several config vars via os.getenv rather than as
# Settings fields — an explicit load_dotenv backfills both. override=False so
# real environment vars (tests/CI/containers) always take precedence over .env.
load_dotenv(override=False)


class Settings(BaseSettings):
    """Career OS application settings."""

    app_name: str = "Career OS"
    debug: bool = False
    database_url: str = "sqlite:///data/career_os.db"
    ai_provider: str = "mock"
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-5"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.3"
    together_api_key: str = ""
    together_model: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    host: str = "0.0.0.0"
    port: int = 8100
    frontend_url: str = "http://localhost:8101"

    # Auth — disabled by default for local use
    auth_enabled: bool = False
    auth_api_key: str = ""

    # Data directory
    data_dir: Path = Path("data")

    # Browser extension (Phase 0 / G-1390) — the extension authenticates with a
    # DEDICATED token minted via POST /api/extension/pair, entirely separate from
    # AUTH_API_KEY (locked decision D-1) and required even when AUTH_ENABLED=false
    # (D-2). extension_token_secret seeds the stateless HMAC token/pairing-code
    # scheme; when empty it is auto-generated and persisted to
    # {data_dir}/.extension_secret so tokens survive a backend restart (see
    # services.extension_pairing). extension_pairing_window_seconds is the pairing
    # code's validity window (a code stays valid across one boundary). The CORS
    # regex ADDS concrete chrome-extension:// origins (Chrome extension IDs are 32
    # chars in a–p) without widening the existing credentialed frontend CORS list.
    extension_token_secret: str = ""
    extension_pairing_window_seconds: int = 300
    extension_cors_regex: str = r"^chrome-extension://[a-p]{32}$"

    # Cache settings
    cache_enabled: bool = True
    cache_encryption_key: str = ""  # User-provided Fernet key; auto-generated if empty

    # Feedback calibration (Epic 6 / G-274) — inject top feedback examples into
    # scoring prompts. Self-gating: get_feedback_calibration() returns [] when
    # fewer than 10 explicit corrections exist, so no data leaks into prompts
    # until the user has provided enough feedback. Can be disabled via env var.
    feedback_calibration_enabled: bool = True

    # Active query selection (Epic 11 / G-279) — when enabled, borderline
    # scores may include a prompt asking the user for feedback to reduce
    # preference model uncertainty.  Disabled by default to avoid annoying
    # users with too many prompts.
    active_query_enabled: bool = False

    # Cost preset (G-442) — one setting selects provider, model, pre-filter
    # strategy, and batch size. Valid values: free, budget, quality, private, custom.
    cost_preset: str = "budget"

    # Regex pre-filter (G-439) — lightweight keyword/title/industry filter
    # that runs BEFORE AI scoring to eliminate ~60% of irrelevant jobs.
    # Strategy: "strict" (title OR skills, NOT blacklisted industry),
    # "moderate" (title OR skills), "off" (disabled).
    prefilter_strategy: str = "strict"

    # Embedding pre-filter (Epic 4 / G-272) — compute embedding cosine
    # similarity before sending jobs through the full LLM scoring pipeline.
    # Shadow mode (default): similarities are computed and logged but jobs are
    # NOT filtered.  Set to True to actually skip low-similarity jobs.
    embedding_prefilter_enabled: bool = False
    embedding_prefilter_threshold: float = 0.65
    embedding_model: str = "nomic-embed-text"

    # Borderline 2-pass scoring (Epic 5 / G-273) — when a job's fit_score falls
    # in the borderline zone [BORDERLINE_LOW, BORDERLINE_HIGH], a second scoring
    # pass is run and the two results are averaged.  This reduces variance by ~50%
    # in the borderline zone (LLM-as-Judge on a Budget, 2026) at ~1.3x cost.
    # Set BORDERLINE_SCORING_ENABLED=false to disable entirely.
    borderline_scoring_enabled: bool = True
    borderline_low_threshold: float = 4.0
    borderline_high_threshold: float = 6.5

    # Scoring shadow-mode (Scoring Engine v2 / G-1336, finding I) — when set,
    # production scoring ALSO scores the job with a DISTINCT candidate provider
    # and logs it to the ``shadow_scores`` table (never surfaced), so a candidate
    # can be measured against the live scorer on real jobs before promotion.
    # Format: "<provider>" or "<provider>:<model>" (e.g. "mistral",
    # "anthropic:claude-opus-4"); it must resolve to a provider DIFFERENT from the
    # live one (a self-comparison no-ops). The shadow runs fire-and-forget on its
    # own task/session, so it adds NO latency to the live score — but it DOES cost
    # an extra background LLM call per sampled job (see the COST guardrail). Empty
    # (off) by default; bound the spend with SCORING_SHADOW_SAMPLE.
    scoring_shadow_variant: str = ""

    # Fraction (0.0–1.0) of scored jobs to shadow when scoring_shadow_variant is
    # set. 1.0 = every job (default), 0.1 = ~10% — the lever that bounds shadow
    # cost on high-volume runs.
    scoring_shadow_sample: float = 1.0

    # Per-provider score calibration (Scoring Engine v2 / G-1337, finding G) —
    # when enabled, the production fit_score is passed through a per-provider
    # isotonic raw→calibrated map so cheap-model scores are comparable across
    # runs/providers. Off by default and a strict no-op unless a calibrator has
    # been fit + registered for the live provider (see services.scoring_calibration).
    # The map is fit from STORED labels (user corrections / golden set) — no paid ops.
    scoring_calibration_enabled: bool = False

    # Distillation logging (Scoring Engine v2 / G-1338, finding M) — when set,
    # every production scoring call opportunistically records the training tuple
    # ``(structured signals, LLM score, user correction)`` to the
    # ``distillation_samples`` table so a future small local feature model has a
    # dataset to distill from ("every unlogged day is training data lost"). It
    # makes NO LLM calls — it only records what already happened. Fully defensive
    # (a logging failure never breaks scoring). Off by default; opt-in to start
    # accumulating data.
    distillation_logging_enabled: bool = False

    # Relative/percentile batch scoring (Scoring Engine v2 / G-1338, finding N) —
    # when set, a discovery batch's raw fit scores are additionally normalized to
    # within-batch percentiles/tiers (relative ranking is more stable than
    # absolute calibration). Opt-in and non-destructive: raw fit_scores are never
    # mutated; the relative view is exposed alongside them. Off by default (strict
    # identity: default behavior is unchanged).
    relative_batch_scoring_enabled: bool = False

    # Confidence-routed cascade (Scoring Engine v2 / G-1338, finding K — Phase 4b) —
    # a conservative, SHADOW-FIRST routing layer that decides which jobs even need
    # the expensive LLM call. A job is auto-rejected (LLM skipped) ONLY when ALL
    # THREE cheap signals have data and all three independently agree it is clearly
    # not a fit: (1) low embedding similarity, (2) no lexical must-have overlap,
    # (3) low ESCO skills-overlap. One or two signals is never enough (the G-272
    # lesson). It NEVER auto-accepts — everything that is not a unanimous reject
    # goes to the LLM as today.
    #
    # Two SEPARATE flags, both OFF by default:
    #   * CASCADE_SHADOW_ENABLED — log what the router WOULD skip (plus the eventual
    #     LLM score) but still score everything, so the false-skip rate can be
    #     measured BEFORE trusting the router. This is the primary deliverable.
    #   * CASCADE_ROUTING_ENABLED — LIVE skipping: a unanimous-reject job actually
    #     bypasses the LLM and is persisted as a scored-but-rejected job (never
    #     dropped). Keep OFF until the shadow false-skip rate is acceptably low.
    cascade_shadow_enabled: bool = False
    cascade_routing_enabled: bool = False

    # Per-signal conservative reject thresholds. Each signal only votes to reject
    # on POSITIVE evidence of non-fit; an unavailable signal abstains and blocks a
    # skip. Deliberately strict so a good job is never skipped on a weak signal:
    #   * embedding: reject only when cosine similarity is BELOW this (far below the
    #     0.65 pre-filter bar — a confident reject, not a filter).
    #   * lexical / esco: reject only when overlap is AT OR BELOW this (0.0 = the
    #     candidate shares genuinely zero must-have terms / ESCO skills with the JD).
    # Bounded [0, 1] so a misconfigured operator with the live flag on cannot set a
    # threshold high enough to mass-skip good jobs (a high reject bar would reject
    # almost everything). All three are similarity/overlap fractions in [0, 1].
    cascade_embedding_reject_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    cascade_lexical_reject_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    cascade_esco_reject_threshold: float = Field(default=0.0, ge=0.0, le=1.0)

    # Deterministic low fit score persisted for a LIVE skip_reject (so the job is
    # visibly scored-but-rejected, never silently dropped). Lands in the "reject"
    # tier (< 3.5) and below the quadrant threshold (5.0). Bounded to the fit-score
    # range [0, 10]; keep it low so a skipped job never masquerades as a fit.
    cascade_reject_fit_score: float = Field(default=1.0, ge=0.0, le=10.0)

    # Drift canary (Scoring Engine v2 / G-1336, finding J) — nightly-style check
    # that computes PSI of the score distribution vs a rolling baseline and
    # re-scores the frozen golden set, alerting via Pushover ONLY on the joint
    # condition (PSI drift AND a κ/NDCG agreement drop). Opt-in because re-scoring
    # the golden set with the live provider is a (small) paid op — off by default.
    drift_canary_enabled: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # Per-provider API key requirements: provider → (settings_attr, expected_prefix).
    # New providers add one entry here instead of a new if-block.
    _PROVIDER_KEY_REQUIREMENTS: dict[str, tuple[str, str]] = {
        "openrouter": ("openrouter_api_key", "sk-or-"),
        "anthropic": ("anthropic_api_key", "sk-ant-"),
    }

    @model_validator(mode="after")
    def validate_api_keys(self) -> "Settings":
        """Fail fast if AI provider requires an API key that isn't set."""
        req = self._PROVIDER_KEY_REQUIREMENTS.get(self.ai_provider)
        if req:
            attr, prefix = req
            val = getattr(self, attr, "")
            if not val:
                raise ValueError(
                    f"{attr.upper()} is required when AI_PROVIDER={self.ai_provider}. "
                    f"Set it in your .env file or environment."
                )
            if prefix and val and not val.startswith(prefix):
                import logging

                logging.getLogger(__name__).warning(
                    f"{attr.upper()} doesn't start with '{prefix}'. "
                    "It may be pasted incorrectly. Check for extra spaces or missing characters."
                )
        if self.auth_enabled and not self.auth_api_key:
            raise ValueError(
                "AUTH_API_KEY is required when AUTH_ENABLED=true. "
                "Set it in your .env file or environment."
            )
        return self


settings = Settings()
