"""GDELT — Global Database of Events, Language, and Tone.

API: https://api.gdeltproject.org/api/v2/doc/doc?format=json
No key required. Worldwide news in many languages, with sentiment + entities.
"""

from __future__ import annotations

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class GdeltProvider(SearchProvider):
    name = "gdelt"
    kind_default = "news"
    endpoint = "https://api.gdeltproject.org/api/v2/doc/doc"

    def _check_enabled(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": min(max_results, 50),
            "sort": "DateDesc",
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params)
            if resp.status_code != 200:
                return []
            try:
                data = resp.json()
            except ValueError:
                return []

        out: list[SearchResult] = []
        for i, article in enumerate(data.get("articles", [])):
            out.append(
                SearchResult(
                    title=article.get("title", "")[:200],
                    url=article.get("url", ""),
                    snippet=(article.get("seendate", "") + " · " + article.get("sourcecountry", ""))[:500],
                    score=1.0 - i * 0.03,
                    source="gdelt",
                    kind="news",
                    raw={
                        "domain": article.get("domain"),
                        "language": article.get("language"),
                        "seendate": article.get("seendate"),
                        "tone": article.get("tone"),
                    },
                )
            )
        return out
