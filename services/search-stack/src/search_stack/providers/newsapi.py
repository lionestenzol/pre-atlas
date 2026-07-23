"""NewsAPI.org — global news headlines + search.

API: https://newsapi.org/v2/everything
Free tier: 100 req/day (dev only). NEWSAPI_KEY env var.
"""

from __future__ import annotations

import os

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class NewsApiProvider(SearchProvider):
    name = "newsapi"
    kind_default = "news"
    endpoint = "https://newsapi.org/v2/everything"

    def _check_enabled(self) -> bool:
        return bool(os.environ.get("NEWSAPI_KEY"))

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        api_key = os.environ.get("NEWSAPI_KEY", "")
        if not api_key:
            return []
        params = {
            "q": query,
            "pageSize": min(max_results, 25),
            "sortBy": "relevancy",
            "language": "en",
        }
        headers = {"X-Api-Key": api_key}
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params, headers=headers)
            if resp.status_code != 200:
                return []
            data = resp.json()

        out: list[SearchResult] = []
        for i, article in enumerate(data.get("articles", [])):
            out.append(
                SearchResult(
                    title=article.get("title", ""),
                    url=article.get("url", ""),
                    snippet=(article.get("description") or "")[:500],
                    score=1.0 - i * 0.03,
                    source="newsapi",
                    kind="news",
                    raw={
                        "source": (article.get("source") or {}).get("name"),
                        "published_at": article.get("publishedAt"),
                        "author": article.get("author"),
                    },
                )
            )
        return out
