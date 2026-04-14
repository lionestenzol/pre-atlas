"""MiroFish configuration — prediction engine settings from env vars."""
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

    # Ollama (used ONLY for ingestion extraction + embeddings, NOT for prediction)
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    ollama_fallback_model: str = os.getenv("OLLAMA_FALLBACK_MODEL", "qwen2.5:7b")
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    # Cognitive-sensor paths (read-only data source)
    # When running inside cognitive-sensor/mirofish/, parents[1] = cognitive-sensor root
    cognitive_sensor_path: Path = Path(
        os.getenv("COGNITIVE_SENSOR_PATH", str(Path(__file__).resolve().parents[1]))
    )

    @property
    def memory_db_path(self) -> Path:
        return self.cognitive_sensor_path / "memory_db.json"

    @property
    def results_db_path(self) -> Path:
        return self.cognitive_sensor_path / "results.db"

    @property
    def classifications_path(self) -> Path:
        return self.cognitive_sensor_path / "conversation_classifications.json"

    @property
    def loops_path(self) -> Path:
        return self.cognitive_sensor_path / "loops_latest.json"

    @property
    def cognitive_state_path(self) -> Path:
        return self.cognitive_sensor_path / "cognitive_state.json"

    @property
    def ideas_path(self) -> Path:
        return self.cognitive_sensor_path / "excavated_ideas_raw.json"

    # Prediction settings
    similarity_threshold: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
    prediction_k: int = int(os.getenv("PREDICTION_K", "20"))
    temporal_decay_days: int = int(os.getenv("TEMPORAL_DECAY_DAYS", "90"))
    min_pattern_frequency: int = int(os.getenv("MIN_PATTERN_FREQUENCY", "5"))

    # Ingestion
    ingest_batch_size: int = int(os.getenv("INGEST_BATCH_SIZE", "50"))
    ingest_state_path: Path = Path(
        os.getenv("INGEST_STATE_PATH", str(Path.home() / ".mirofish" / "ingest_state.json"))
    )

    # Retry
    max_retries: int = 2
    retry_base_delay: float = 1.0


config = MirofishConfig()
