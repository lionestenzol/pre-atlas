"""Mosaic Orchestrator — main entry point.

Starts the FastAPI server and the background scheduler.
"""
import asyncio
import structlog
import uvicorn

from mosaic.api import app
from mosaic.config import config

log = structlog.get_logger()


def main():
    """Entry point for the mosaic CLI command."""
    log.info(
        "mosaic.starting",
        port=config.orchestrator_port,
        delta_kernel=config.delta_kernel_url,
        cognitive_sensor=str(config.cognitive_sensor_dir),
    )
    uvicorn.run(
        "mosaic.api:app",
        host="0.0.0.0",
        port=config.orchestrator_port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
