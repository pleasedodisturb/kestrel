"""Application configuration."""

from pathlib import Path

from dotenv import load_dotenv
from pydantic import model_validator
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
