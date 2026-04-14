"""Delta-Kernel client — wraps REST API on port 3001.

Integrates with:
  - GET  /api/state/unified   (merged delta + cognitive state)
  - POST /api/ingest/cognitive (push cognitive-sensor payload)
  - POST /api/work/request    (admit work to queue)
  - POST /api/work/complete   (mark work done)
  - GET  /api/daemon/status   (governance daemon health)
  - GET  /api/health          (basic health check)
"""
import asyncio
import structlog
import httpx
from typing import Any

log = structlog.get_logger()

MAX_RETRIES = 2
RETRY_BASE_DELAY = 1.0  # seconds


class DeltaClient:
    """Async HTTP client for delta-kernel service."""

    def __init__(self, base_url: str = "http://localhost:3001", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0, headers=headers)
        return self._client

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """HTTP request with retry logic (2 attempts, exponential backoff)."""
        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self.client.request(method, path, **kwargs)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, httpx.ConnectError) as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    log.warning("delta_client.retry", path=path, attempt=attempt + 1, delay=delay)
                    await asyncio.sleep(delay)
        log.error("delta_client.failed", path=path, error=str(last_err))
        raise last_err

    # --- State ---

    async def get_unified_state(self) -> dict[str, Any]:
        """GET /api/state/unified — merged view of delta + cognitive state."""
        return await self._request("GET", "/api/state/unified")

    async def get_state(self) -> dict[str, Any]:
        """GET /api/state — raw system state."""
        return await self._request("GET", "/api/state")

    # --- Cognitive Ingestion ---

    async def ingest_cognitive(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /api/ingest/cognitive — push cognitive-sensor state to delta-kernel.

        Payload must include schema_version and mode_source per ModeContract.v1.json.
        """
        return await self._request("POST", "/api/ingest/cognitive", json=payload)

    # --- Work Queue ---

    async def request_work(self, job: dict[str, Any]) -> dict[str, Any]:
        """POST /api/work/request — admit a job to the work queue.

        Job shape: { type: "human"|"ai"|"system", title, description, priority, timeout_ms }
        """
        return await self._request("POST", "/api/work/request", json=job)

    async def complete_work(self, job_id: str, outcome: dict[str, Any]) -> dict[str, Any]:
        """POST /api/work/complete — mark a job as completed.

        Outcome shape: { job_id, status: "completed"|"failed", result, metrics }
        """
        return await self._request("POST", "/api/work/complete", json={"job_id": job_id, **outcome})

    async def get_work_status(self) -> dict[str, Any]:
        """GET /api/work/status — active and queued jobs."""
        return await self._request("GET", "/api/work/status")

    # --- Daemon ---

    async def get_daemon_status(self) -> dict[str, Any]:
        """GET /api/daemon/status — governance daemon state."""
        return await self._request("GET", "/api/daemon/status")

    # --- Health ---

    async def health(self) -> dict[str, Any]:
        """GET /api/health — basic health check."""
        return await self._request("GET", "/api/health")

    # --- Governance Config ---

    async def get_governance_config(self) -> dict[str, Any]:
        """GET /api/governance/config — atlas_config exported as JSON."""
        return await self._request("GET", "/api/governance/config")

    # --- Cleanup ---

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
