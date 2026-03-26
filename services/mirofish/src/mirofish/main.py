"""MiroFish — main entry point.

Starts the FastAPI server on port 3003.
"""
import structlog
import uvicorn

from mirofish.api import app
from mirofish.config import config

log = structlog.get_logger()


def main():
    """Entry point for the mirofish CLI command."""
    log.info(
        "mirofish.starting",
        port=config.port,
        neo4j=config.neo4j_uri,
        ollama=config.ollama_url,
    )
    uvicorn.run(
        "mirofish.api:app",
        host="0.0.0.0",
        port=config.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
