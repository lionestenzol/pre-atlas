"""Cortex configuration."""

from __future__ import annotations

import os


class CortexConfig:
    # Service URLs
    DELTA_URL: str = os.getenv("DELTA_URL", "http://localhost:3001")
    AEGIS_URL: str = os.getenv("AEGIS_URL", "http://localhost:3002")
    UASC_URL: str = os.getenv("UASC_URL", "http://localhost:3008")
    MOSAIC_URL: str = os.getenv("MOSAIC_URL", "http://localhost:3005")
    NATS_URL: str = os.getenv("NATS_URL", "nats://localhost:4222")

    # Cortex identity
    INSTANCE_ID: str = os.getenv("CORTEX_INSTANCE_ID", "cortex-primary")
    PORT: int = int(os.getenv("CORTEX_PORT", "3009"))

    # Delta auth (reads from .aegis-tenant-key if env not set)
    DELTA_API_KEY: str = os.getenv("DELTA_API_KEY", "")

    # Aegis auth
    AEGIS_API_KEY: str = os.getenv("AEGIS_API_KEY", "")
    AEGIS_AGENT_ID: str = os.getenv("AEGIS_AGENT_ID", "")
    AEGIS_TENANT_ID: str = os.getenv("AEGIS_TENANT_ID", "")

    # Claude API (for planner decomposition)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CORTEX_CLAUDE_MODEL", "claude-sonnet-4-6")

    # Loop timing
    POLL_INTERVAL_SECONDS: float = float(os.getenv("CORTEX_POLL_INTERVAL", "10"))
    APPROVAL_POLL_SECONDS: float = float(os.getenv("CORTEX_APPROVAL_POLL", "30"))

    # Execution limits
    MAX_CONCURRENT_TASKS: int = int(os.getenv("CORTEX_MAX_CONCURRENT", "1"))
    DEFAULT_TIMEOUT_SECONDS: int = 300
    DEFAULT_MAX_COST_USD: float = 0.50
    MAX_RETRIES: int = 3

    # Circuit breaker
    CB_FAILURE_THRESHOLD: int = 5
    CB_COOLDOWN_SECONDS: float = 60.0

    # Stale lock threshold multiplier (locked_at + timeout * this = stale)
    STALE_LOCK_MULTIPLIER: float = 2.0


config = CortexConfig()

# Auto-load delta API key from .aegis-tenant-key if not set via env
if not config.DELTA_API_KEY:
    from pathlib import Path
    _key_path = Path(__file__).resolve().parents[4] / ".aegis-tenant-key"
    if _key_path.exists():
        config.DELTA_API_KEY = _key_path.read_text(encoding="utf-8").strip()
