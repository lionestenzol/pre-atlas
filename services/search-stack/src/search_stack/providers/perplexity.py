"""Perplexity Sonar API — answer-style search with built-in citations.

API: https://api.perplexity.ai/chat/completions
PERPLEXITY_API_KEY env var. Returns a synthesized answer, not raw results.
We map the answer + citations into our SearchResult shape.
"""

from __future__ import annotations

import os

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class PerplexityProvider(SearchProvider):
    name = "perplexity"
    kind_default = "web"
    endpoint = "https://api.perplexity.ai/chat/completions"

    def _check_enabled(self) -> bool:
        return bool(os.environ.get("PERPLEXITY_API_KEY"))

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        api_key = os.environ.get("PERPLEXITY_API_KEY", "")
        if not api_key:
            return []
        payload = {
            "model": "sonar",
            "messages": [{"role": "user", "content": query}],
            "return_citations": True,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds * 2) as client:
            resp = await client.post(self.endpoint, json=payload, headers=headers)
            if resp.status_code != 200:
                return []
            data = resp.json()

        out: list[SearchResult] = []
        answer = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        citations = data.get("citations", []) or []
        for i, citation in enumerate(citations[:max_results]):
            url = citation if isinstance(citation, str) else (citation.get("url") if isinstance(citation, dict) else "")
            if not url:
                continue
            out.append(
                SearchResult(
                    title=f"perplexity[{i+1}]",
                    url=url,
                    snippet=answer[:500] if i == 0 else "",
                    score=1.0 - i * 0.05,
                    source="perplexity",
                    kind="web",
                    raw={"answer_preview": answer[:200], "citation_index": i + 1},
                )
            )
        return out
