"""Central configuration loaded from environment variables / .env."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

# Legacy constant kept for backwards compatibility.
CLAUDE_MODEL = "claude-sonnet-4-20250514"

WIQL_PAGE_SIZE = 200          # max IDs per WIQL response
DEFAULT_BATCH_SIZE = 50       # work items per workitemsbatch call
MAX_RETRIES = 3
AZURE_BASE_URL = "https://dev.azure.com"


class Settings(BaseSettings):
    """Environment-backed settings.

    All fields are optional here; the CLI enforces what is required so that
    flags can override environment variables.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── AI provider ────────────────────────────────────────────────────────
    # Accepted values: anthropic | openai | deepseek | gemini
    # If omitted, the provider is auto-detected from the API key prefix.
    ai_provider: str | None = None
    ai_model: