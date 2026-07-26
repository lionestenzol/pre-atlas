"""Brave Search — broad independent index.

API docs: https://api.search.brave.com/app/documentation/web-search/get-started
"""

from __future__ import annotations

import httpx

from .. import budget
from ..settings import settings
from .base import SearchProvider, SearchResult


class BraveProvider(SearchProvider):
    name = "brave"
    kind_default = "web"
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def _check_enabled(self) -> bool:
        return bool(settings.brave_api_key)

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        if not budget.consume(self.name, settings.brave_monthly_quota):
            self.last_error = "budget_blocked"
            return []

        params = {
            "q": query,
            "count": min(max_results, 20),
        }
        headers = {
            "X-Subscription-Token": settings.brave_api_key,
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        out: list[SearchResult] = []
        web_results = (data.get("web") or {}).get("results", [])
        for i, item in enumerate(web_results):
            out.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    score=1.0 - i * 0.04,
                    source="brave",
                    kind="web",
                    raw={
                        "age": item.get("age"),
                        "language": item.get("language"),
                        "family_friendly": item.get("family_friendly"),
                    },
                )
            )
        return out
