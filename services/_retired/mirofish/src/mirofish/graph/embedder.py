"""Ollama embedder — generates text embeddings via Ollama API."""
import asyncio
import structlog
import httpx

from mirofish.config import config

log = structlog.get_logger()


class OllamaEmbedder:
    """Generate text embeddings using Ollama's embedding endpoint."""

    def __init__(
        self,
        ollama_url: str | None = None,
        model: str | None = None,
    ):
        self.ollama_url = (ollama_url or config.ollama_url).rstrip("/")
        self.model = model or config.ollama_embed_model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text string.

        Returns vector of floats from Ollama /api/embeddings endpoint.
        Retries up to max_retries times with exponential backoff.
        """
        for attempt in range(config.max_retries + 1):
            try:
                client = await self._get_client()
                resp = await client.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                resp.raise_for_status()
                data = resp.json()
                return data["embedding"]
            except (httpx.HTTPError, KeyError) as e:
                if attempt < config.max_retries:
                    delay = config.retry_base_delay * (2 ** attempt)
                    log.warning("embedder.retry", attempt=attempt, error=str(e), delay=delay)
                    await asyncio.sleep(delay)
                else:
                    log.error("embedder.failed", error=str(e))
                    raise

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Processes sequentially to avoid overloading Ollama.
        """
        results: list[list[float]] = []
        for text in texts:
            embedding = await self.embed(text)
            results.append(embedding)
        return results

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
