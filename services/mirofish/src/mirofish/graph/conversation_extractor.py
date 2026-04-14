"""Conversation-tuned entity extractor — extracts topics, intentions, and outcomes via Ollama."""
import json
import structlog
import httpx

from mirofish.config import config

log = structlog.get_logger()

EXTRACTION_PROMPT = """Extract structured information from this conversation excerpt.
The speaker is discussing projects, ideas, problems, and personal topics with an AI assistant.

Return ONLY valid JSON with this exact structure:
{{
    "topics": [{{"name": "short topic name", "salience": 0.0}}],
    "intentions": [{{"action": "what the user wants to do", "target": "what it applies to", "strength": 0.0}}],
    "outcomes": [{{"description": "what was resolved or produced", "type": "produced|resolved|deferred|abandoned"}}],
    "references": [{{"to_topic": "topic name", "type": "callback|continuation|contradiction"}}]
}}

Rules:
- Topics should be 1-4 word phrases (e.g., "authentication system", "personal finance", "career anxiety")
- Salience is 0.0 to 1.0 (how central this topic is to the conversation)
- Only include intentions if the user expresses clear intent to DO something
- Only include outcomes if something was actually completed or decided
- References are cross-topic links (user mentioning a previous project, revisiting an old idea)

Conversation:
{text}

JSON:"""


class ConversationExtractor:
    """Extract topics, intentions, and outcomes from conversation chunks."""

    def __init__(self, ollama_url: str | None = None, model: str | None = None):
        self.ollama_url = (ollama_url or config.ollama_url).rstrip("/")
        self.model = model or config.ollama_model
        self.fallback_model = config.ollama_fallback_model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def extract(self, text: str) -> dict:
        """Extract structured data from a conversation chunk.

        Returns dict with topics, intentions, outcomes, references.
        Falls back to empty extraction on failure.
        """
        prompt = EXTRACTION_PROMPT.format(text=text[:3000])  # Cap input length

        for model in [self.model, self.fallback_model]:
            try:
                client = await self._get_client()
                resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
                )
                resp.raise_for_status()
                raw = resp.json().get("response", "")
                return _parse_extraction(raw)
            except Exception as e:
                log.warning("extractor.model_failed", model=model, error=str(e))

        return _empty_extraction()

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def _parse_extraction(raw: str) -> dict:
    """Parse JSON from LLM output, handling malformed responses."""
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {
                "topics": _validate_topics(data.get("topics", [])),
                "intentions": data.get("intentions", []),
                "outcomes": data.get("outcomes", []),
                "references": data.get("references", []),
            }
    except json.JSONDecodeError:
        # Try to find JSON in the response
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start:end])
                return {
                    "topics": _validate_topics(data.get("topics", [])),
                    "intentions": data.get("intentions", []),
                    "outcomes": data.get("outcomes", []),
                    "references": data.get("references", []),
                }
            except json.JSONDecodeError:
                pass
    return _empty_extraction()


def _validate_topics(topics: list) -> list[dict]:
    """Ensure topics have valid structure."""
    valid = []
    for t in topics:
        if isinstance(t, dict) and "name" in t:
            name = str(t["name"]).strip().lower()
            if 1 < len(name) < 100:
                valid.append({
                    "name": name,
                    "salience": min(1.0, max(0.0, float(t.get("salience", 0.5)))),
                })
    return valid


def _empty_extraction() -> dict:
    return {"topics": [], "intentions": [], "outcomes": [], "references": []}
