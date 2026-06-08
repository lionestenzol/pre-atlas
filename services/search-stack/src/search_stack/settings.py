"""Centralized config — reads .env once, exposes typed settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    exa_api_key: str = ""
    tavily_api_key: str = ""
    brave_api_key: str = ""
    firecrawl_api_key: str = ""

    search_stack_port: int = 3070
    search_stack_host: str = "127.0.0.1"
    search_stack_cache_ttl: int = 3600
    search_stack_budget_warn: int = 70
    search_stack_budget_block: int = 80

    exa_monthly_quota: int = 1000
    tavily_monthly_quota: int = 1000
    brave_monthly_quota: int = 2000
    firecrawl_monthly_quota: int = 500

    droplist_intake_url: str = ""
    search_stack_n8n_url: str = ""

    http_timeout_seconds: float = 15.0


settings = Settings()
