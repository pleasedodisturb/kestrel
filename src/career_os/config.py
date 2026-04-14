"""Application configuration."""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Career OS application settings."""

    app_name: str = "Career OS"
    debug: bool = False
    database_url: str = "sqlite:///data/career_os.db"
    ai_provider: str = "mock"
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-4"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.3"
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
    # scoring prompts. Disabled by default until ≥10 explicit corrections exist.
    # Epic 11 (Bayesian Learning) will leverage this when enabled.
    feedback_calibration_enabled: bool = False

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
