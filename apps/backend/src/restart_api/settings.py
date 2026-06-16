"""Application settings: environment-driven, secure by default.

Conventions:

* Every variable is prefixed ``RESTART_`` to avoid collisions on shared hosts.
* No credentials or connection strings have in-code defaults. Infrastructure
  URLs are ``None`` until the phase that introduces the dependency wires them
  (Phase 0 has no database or queue code, so configuring them would be a lie).
* Secrets use :class:`pydantic.SecretStr` so they never appear in reprs/logs.
* A local ``.env`` file is honored for development; production injects real
  environment variables (see .env.example at the repository root).
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RESTART_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["dev", "test", "prod"] = "dev"
    debug: bool = False

    api_title: str = "Restart Lab API"

    # CORS origins as a JSON list, e.g. RESTART_CORS_ORIGINS=["http://localhost:3000"]
    cors_origins: list[str] = ["http://localhost:3000"]

    # Infrastructure (unused in Phase 0; reserved, no defaults with credentials).
    database_url: SecretStr | None = None
    redis_url: SecretStr | None = None

    # API key for mutating endpoints (introduced with the first write endpoint).
    api_key: SecretStr | None = None

    # Per-IP rate limits (slowapi format "<n>/<period>"). Reads get a generous
    # global bucket; compute-triggering POSTs get a stricter one. Disable for
    # benchmarks/load tests via RESTART_RATE_LIMIT_ENABLED=false.
    rate_limit_enabled: bool = True
    rate_limit_read: str = "120/minute"
    rate_limit_write: str = "20/minute"

    # Global cap on concurrently-running simulation jobs (cost-bomb protection,
    # enforced by the in-process JobQueue; doc 02 9).
    max_concurrent_jobs: int = 2


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings, cached. FastAPI dependencies call this; tests
    bypass the cache by constructing :class:`Settings` directly or via
    ``create_app(settings=...)``."""
    return Settings()
