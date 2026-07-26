"""Exa — neural/semantic web search.

API docs: https://docs.exa.ai/reference/search
"""

from __future__ import annotations

import httpx

from .. import budget
from ..settings import settings
from .base import SearchProvider, SearchResult


class ExaProvider(SearchProvider):
    name = "exa"
    kind_default = "web"
    endpoint = "https://api.exa.ai/search"

    def _check_enabled(self) -> bool:
        return bool(settings.exa_api_key)

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        if not budget.consume(self.name, settings.exa_monthly_quota):
            self.last_error = "budget_blocked"
            return []

        payload = {
            "query": query,
            "numResults": min(max_results, 25),
            "type": "neural",
            "contents": {"text": {"maxCharacters": 500}},
        }
        headers = {
            "x-api-key": settings.exa_api_key,
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.post(self.endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        out: list[SearchResult] = []
        for i, item in enumerate(data.get("results", [])):
            text = item.get("text") or ""
            snippet = text[:500] if text else item.get("summary", "")
            score = float(item.get("score") or (1.0 - i * 0.05))
            out.append(
                SearchResult(
                    title=item.get("title") or item.get("url", ""),
                    url=item.get("url", ""),
                    snippet=snippet,
                    score=score,
                    source="exa",
                    kind="web",
                    raw={
                        "id": item.get("id"),
                        "publishedDate": item.get("publishedDate"),
                        "author": item.get("author"),
                    },
                )
            )
        return out
