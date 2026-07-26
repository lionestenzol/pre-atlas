"""Hacker News — Algolia full-text search over all HN items.

API: https://hn.algolia.com/api/v1/search
No key required.
"""

from __future__ import annotations

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class HackerNewsProvider(SearchProvider):
    name = "hackernews"
    kind_default = "social"
    endpoint = "https://hn.algolia.com/api/v1/search"

    def _check_enabled(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        params = {
            "query": query,
            "hitsPerPage": min(max_results, 30),
            "tags": "story",
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params)
            resp.raise_for_status()
            data = resp.json()

        out: list[SearchResult] = []
        for hit in data.get("hits", []):
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            points = int(hit.get("points") or 0)
            comments = int(hit.get("num_comments") or 0)
            out.append(
                SearchResult(
                    title=hit.get("title") or hit.get("story_title", ""),
                    url=url,
                    snippet=(hit.get("story_text") or hit.get("comment_text") or "")[:500],
                    score=min(1.0, points / 500),
                    source="hackernews",
                    kind="social",
                    raw={
                        "points": points,
                        "comments": comments,
                        "author": hit.get("author"),
                        "created_at": hit.get("created_at"),
                    },
                )
            )
        return out
