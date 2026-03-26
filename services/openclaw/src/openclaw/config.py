"""OpenClaw configuration — all settings from env vars."""
import os
from pydantic import BaseModel


class OpenClawConfig(BaseModel):
    """All OpenClaw configuration, sourced from environment."""

    # Server
    port: int = int(os.getenv("OPENCLAW_PORT", "3004"))

    # Channel tokens
    telegram_token: str = os.getenv("TELEGRAM_TOKEN", "")
    slack_token: str = os.getenv("SLACK_TOKEN", "")
    slack_signing_secret: str = os.getenv("SLACK_SIGNING_SECRET", "")
    discord_token: str = os.getenv("DISCORD_TOKEN", "")

    # Channel defaults
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    slack_channel: str = os.getenv("SLACK_CHANNEL", "#atlas-briefs")
    discord_channel_id: str = os.getenv("DISCORD_CHANNEL_ID", "")

    # Internal service URLs
    orchestrator_url: str = os.getenv("ORCHESTRATOR_URL", "http://localhost:3005")
    cognitive_url: str = os.getenv("COGNITIVE_URL", "http://localhost:8000")
    mirofish_url: str = os.getenv("MIROFISH_URL", "http://localhost:3003")

    # Scheduler
    brief_cron_hour: int = int(os.getenv("BRIEF_CRON_HOUR", "9"))
    brief_cron_minute: int = int(os.getenv("BRIEF_CRON_MINUTE", "30"))
    stall_threshold_hours: int = int(os.getenv("STALL_THRESHOLD_HOURS", "48"))


config = OpenClawConfig()
