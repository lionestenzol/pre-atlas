"""Entity and relationship extractor — uses Ollama to extract structured data from text."""
import asyncio
import json
import structlog
import httpx

from dataclasses import dataclass, field
from mirofish.config import config

log = structlog.get_logger()

VALID_NODE_TYPES = {"Concept", "Person", "Argument", "Evidence", "Claim"}
VALID_EDGE_TYPES = {"SUPPORTS", "CONTRADICTS", "RELATED_TO", "AUTHORED_BY"}

EXTRACTION_PROMPT = """Extract entities and relationships from the following text.
Return ONLY valid JSON with this exact structure:
{
  "entities": [
    {"name": "entity name", "type": "Concept|Person|Argument|Evidence|Claim", "description": "brief description"}
  ],
  "relationships": [
    {"source": "entity name", "target": "entity name", "type": "SUPPORTS|CONTRADICTS|RELATED_TO|AUTHORED_BY", "evidence": "brief quote"}
  ]
}

Valid entity types: Concept, Person, Argument, Evidence, Claim
Valid relationship types: SUPPORTS, CONTRADICTS, RELATED_TO, AUTHORED_BY

Text:
"""


@dataclass
class Entity:
    name: str
    type: str
    description: str


@dataclass
class Relationship:
    source: str
    target: str
    type: str
    evidence: str


@dataclass
class ExtractionResult:
    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)


class EntityExtractor:
    """Extract entities and relationships from text chunks using Ollama."""

    def __init__(
        self,
        ollama_url: str | None = None,
        model: str | None = None,
        fallback_model: str | None = None,
    ):
        self.ollama_url = (ollama_url or config.ollama_url).rstrip("/")
        self.model = model or config.ollama_model
        self.fallback_model = fallback_model or config.ollama_fallback_model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def _call_ollama(self, prompt: str, model: str) -> str:
        """Call Ollama /api/generate and return the response text."""
        client = await self._get_client()
        resp = await client.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    def _parse_response(self, raw: str) -> ExtractionResult:
        """Parse JSON response into ExtractionResult, handling malformed data."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    data = json.loads(raw[start:end])
                except json.JSONDecodeError:
                    log.warning("extractor.parse_failed", raw_len=len(raw))
                    return ExtractionResult()
            else:
                return ExtractionResult()

        entities = []
        for e in data.get("entities", []):
            if isinstance(e, dict) and "name" in e:
                etype = e.get("type", "Concept")
                if etype not in VALID_NODE_TYPES:
                    etype = "Concept"
                entities.append(Entity(
                    name=e["name"],
                    type=etype,
                    description=e.get("description", ""),
                ))

        relationships = []
        for r in data.get("relationships", []):
            if isinstance(r, dict) and "source" in r and "target" in r:
                rtype = r.get("type", "RELATED_TO")
                if rtype not in VALID_EDGE_TYPES:
                    rtype = "RELATED_TO"
                relationships.append(Relationship(
                    source=r["source"],
                    target=r["target"],
                    type=rtype,
                    evidence=r.get("evidence", ""),
                ))

        return ExtractionResult(entities=entities, relationships=relationships)

    async def extract(self, text: str) -> ExtractionResult:
        """Extract entities and relationships from a text chunk.

        Tries primary model first, falls back to smaller model if unavailable.
        """
        prompt = EXTRACTION_PROMPT + text

        for attempt in range(config.max_retries + 1):
            model = self.model if attempt == 0 else self.fallback_model
            try:
                raw = await self._call_ollama(prompt, model)
                result = self._parse_response(raw)
                if result.entities:
                    return result
                # Empty result — retry with fallback
                if model == self.model and self.fallback_model != self.model:
                    log.info("extractor.fallback", from_model=model, to_model=self.fallback_model)
                    model = self.fallback_model
                    raw = await self._call_ollama(prompt, model)
                    return self._parse_response(raw)
                return result
            except (httpx.HTTPError, Exception) as e:
                if attempt < config.max_retries:
                    delay = config.retry_base_delay * (2 ** attempt)
                    log.warning("extractor.retry", attempt=attempt, model=model, error=str(e))
                    await asyncio.sleep(delay)
                else:
                    log.error("extractor.failed", error=str(e))
                    return ExtractionResult()

        return ExtractionResult()

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
