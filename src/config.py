"""Central configuration loaded from environment variables / .env."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

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

    anthropic_api_key: str | None = None
    azure_org: str | None = None
    azure_pat: str | None = None
    azure_project: str | None = None
    azure_team: str | None = None

    swarm_sprints: int = 5
    swarm_output_dir: str = "."
    swarm_verbose: bool = False
    swarm_batch_size: int = DEFAULT_BATCH_SIZE


def load_settings() -> Settings:
    """Load settings from environment and .env file."""
    return Settings()
