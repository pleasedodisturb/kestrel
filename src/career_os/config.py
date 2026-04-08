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
    host: str = "0.0.0.0"
    port: int = 8100
    frontend_url: str = "http://localhost:8101"

    # Auth — disabled by default for local use
    auth_enabled: bool = False
    auth_api_key: str = ""

    # Data directory
    data_dir: Path = Path("data")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @model_validator(mode="after")
    def validate_api_keys(self) -> "Settings":
        """Fail fast if AI provider requires an API key that isn't set."""
        if self.ai_provider == "openrouter" and not self.openrouter_api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is required when AI_PROVIDER=openrouter. "
                "Set it in your .env file or environment."
            )
        if self.auth_enabled and not self.auth_api_key:
            raise ValueError(
                "AUTH_API_KEY is required when AUTH_ENABLED=true. "
                "Set it in your .env file or environment."
            )
        return self


settings = Settings()
