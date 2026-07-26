"""Incremental ingestion state tracker — persists to JSON so ingestion is restartable."""
import json
import structlog
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from mirofish.config import config

log = structlog.get_logger()


@dataclass
class IngestState:
    last_convo_index: int = -1
    total_ingested: int = 0
    last_run: str = ""
    topics_created: int = 0
    similarity_edges_built: bool = False
    temporal_edges_built: bool = False


def load_state() -> IngestState:
    """Load ingestion state from disk, or return fresh state."""
    path = config.ingest_state_path
    if path.exists():
        try:
            data = json.loads(path.read_text())
            return IngestState(**{k: v for k, v in data.items() if k in IngestState.__dataclass_fields__})
        except Exception as e:
            log.warning("ingest_state.load_failed", error=str(e))
    return IngestState()


def save_state(state: IngestState) -> None:
    """Persist ingestion state to disk."""
    path = config.ingest_state_path
    path.parent.mkdir(parents=True, exist_ok=True)
    state.last_run = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(asdict(state), indent=2))
    log.info("ingest_state.saved", total=state.total_ingested, last_index=state.last_convo_index)
