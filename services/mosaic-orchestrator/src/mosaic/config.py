"""Mosaic orchestrator configuration — all settings from env vars."""
import os
import uuid
from pathlib import Path
from pydantic import BaseModel


def _repo_root() -> Path:
    """Walk up from this file to find the repo root (contains services/)."""
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "services").is_dir():
            return parent
    return Path.cwd()


REPO_ROOT = _repo_root()


class MosaicConfig(BaseModel):
    """All orchestrator configuration, sourced from environment."""

    # Ports
    delta_kernel_url: str = os.getenv("DELTA_KERNEL_URL", "http://localhost:3001")
    aegis_url: str = os.getenv("AEGIS_URL", "http://localhost:3002")
    mirofish_url: str = os.getenv("MIROFISH_URL", "http://localhost:3003")
    openclaw_url: str = os.getenv("OPENCLAW_URL", "http://localhost:3004")
    orchestrator_port: int = int(os.getenv("ORCHESTRATOR_PORT", "3005"))

    # Paths
    repo_root: Path = REPO_ROOT
    cognitive_sensor_dir: Path = Path(
        os.getenv("COGNITIVE_SENSOR_DIR", str(REPO_ROOT / "services" / "cognitive-sensor"))
    )

    # Auth
    aegis_api_key: str = os.getenv("AEGIS_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Ollama (fallback for non-critical tasks)
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:32b")

    # Metering
    free_tier_seconds: int = int(os.getenv("FREE_TIER_SECONDS", "3600"))
    metering_db_path: Path = Path(
        os.getenv("METERING_DB_PATH", str(Path.home() / ".mosaic" / "metering.db"))
    )

    # Retry
    max_retries: int = 2
    retry_base_delay: float = 1.0  # seconds, exponential backoff

    # Execution Queue (Phase 2)
    use_queue: bool = os.getenv("USE_QUEUE", "false").lower() == "true"
    postgres_dsn: str = os.getenv(
        "POSTGRES_DSN",
        "postgresql://aegis:aegis_dev_pass@localhost:5432/aegis_admin",
    )
    nats_url: str = os.getenv("NATS_URL", "nats://localhost:4222")
    executor_instance_id: str = os.getenv(
        "EXECUTOR_INSTANCE_ID",
        f"mosaic-{uuid.uuid4().hex[:8]}",
    )


config = MosaicConfig()
