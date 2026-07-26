"""Tavily — real-time web + news search.

API docs: https://docs.tavily.com/docs/rest-api/api-reference
"""

from __future__ import annotations

import httpx

from .. import budget
from ..settings import settings
from .base import SearchProvider, SearchResult


class TavilyProvider(SearchProvider):
    name = "tavily"
    kind_default = "web"
    endpoint = "https://api.tavily.com/search"

    def _check_enabled(self) -> bool:
        return bool(settings.tavily_api_key)

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        if not budget.consume(self.name, settings.tavily_monthly_quota):
            self.last_error = "budget_blocked"
            return []

        payload = {
            "api_key": settings.tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": min(max_results, 20),
            "include_answer": False,
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.post(self.endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()

        out: list[SearchResult] = []
        for item in data.get("results", []):
            out.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    score=float(item.get("score") or 0.0),
                    source="tavily",
                    kind="web",
                    raw={
                        "published_date": item.get("published_date"),
                    },
                )
            )
        return out
