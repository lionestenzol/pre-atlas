"""MiroFish configuration — all settings from env vars."""
import os
from pathlib import Path
from pydantic import BaseModel


class MirofishConfig(BaseModel):
    """All MiroFish configuration, sourced from environment."""

    # Server
    port: int = int(os.getenv("MIROFISH_PORT", "3003"))

    # Neo4j
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "mirofish123")

    # Ollama
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:32b")
    ollama_fallback_model: str = os.getenv("OLLAMA_FALLBACK_MODEL", "qwen2.5:7b")
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    # Simulation limits
    max_agents: int = int(os.getenv("MAX_AGENTS", "500"))
    max_ticks: int = int(os.getenv("MAX_TICKS", "50"))
    parallel_factor: int = int(os.getenv("PARALLEL_FACTOR", "4"))

    # Storage
    db_path: Path = Path(
        os.getenv("MIROFISH_DB_PATH", str(Path.home() / ".mirofish" / "simulations.db"))
    )

    # Retry
    max_retries: int = 2
    retry_base_delay: float = 1.0


config = MirofishConfig()
