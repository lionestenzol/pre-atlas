"""OpenClaw entry point — starts the FastAPI server."""
import structlog
import uvicorn

from openclaw.config import config

log = structlog.get_logger()


def main():
    log.info("openclaw.starting", port=config.port)
    uvicorn.run("openclaw.api:app", host="0.0.0.0", port=config.port)


if __name__ == "__main__":
    main()
