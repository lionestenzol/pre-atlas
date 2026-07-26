"""Tests for mirofish.config."""
from pathlib import Path

from mirofish.config import MirofishConfig


class TestMirofishConfig:
    def test_default_values(self):
        cfg = MirofishConfig()
        assert cfg.port == 3003
        assert cfg.neo4j_uri == "bolt://localhost:7687"
        assert cfg.ollama_url == "http://localhost:11434"
        assert cfg.max_agents == 500
        assert cfg.max_ticks == 50
        assert cfg.parallel_factor == 4
        assert cfg.max_retries == 2
        assert cfg.retry_base_delay == 1.0
        assert isinstance(cfg.db_path, Path)

    def test_is_pydantic_model(self):
        cfg = MirofishConfig()
        # Should be serializable
        d = cfg.model_dump()
        assert "port" in d
        assert "neo4j_uri" in d
