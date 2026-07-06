"""NATS publisher — emits events matching delta-kernel's envelope format.

Gracefully degrades: if NATS is unavailable, events are silently dropped
(matches the pattern in services/delta-kernel/src/core/event-emitter.ts).
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import structlog

log = structlog.get_logger()

# Import is optional — publisher degrades if nats-py not installed
try:
    import nats
    from nats.aio.client import Client as NatsClient

    HAS_NATS = True
except ImportError:
    HAS_NATS = False


class NatsPublisher:
    """Publish events to NATS, matching the delta-kernel envelope format."""

    def __init__(self, source: str = "mosaic-orchestrator") -> None:
        self._nc: Any = None
        self._source = source
        self._connected = False

    async def connect(self, nats_url: str) -> None:
        """Connect to NATS. Silently degrades if unavailable."""
        if not HAS_NATS:
            log.warning("nats_publisher.no_nats_lib", msg="nats-py not installed, events disabled")
            return

        try:
            self._nc = await nats.connect(
                nats_url,
                max_reconnect_attempts=5,
                reconnect_time_wait=2,
            )
            self._connected = True
            log.info("nats_publisher.connected", url=nats_url)
        except Exception as e:
            log.warning("nats_publisher.connect_failed", error=str(e))
            self._connected = False

    async def publish(self, topic: str, data: dict[str, Any]) -> None:
        """Publish an event. No-op if not connected."""
        if not self._connected or self._nc is None:
            return

        envelope = {
            "id": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "source": self._source,
            "topic": topic,
            "data": data,
        }

        try:
            payload = json.dumps(envelope).encode("utf-8")
            await self._nc.publish(topic, payload)
            log.debug("nats_publisher.published", topic=topic, id=envelope["id"])
        except Exception as e:
            log.warning("nats_publisher.publish_failed", topic=topic, error=str(e))

    async def close(self) -> None:
        if self._nc and self._connected:
            try:
                await self._nc.close()
            except Exception:
                pass
            self._connected = False
