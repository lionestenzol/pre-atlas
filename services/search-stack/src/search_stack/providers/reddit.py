"""Reddit — public JSON search endpoint.

API: https://www.reddit.com/search.json
No auth required for read; user-agent is mandatory.
"""

from __future__ import annotations

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class RedditProvider(SearchProvider):
    name = "reddit"
    kind_default = "social"
    endpoint = "https://www.reddit.com/search.json"

    def _check_enabled(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        params = {
            "q": query,
            "limit": min(max_results, 25),
            "sort": "relevance",
        }
        headers = {"User-Agent": "search-stack/0.1 (by /u/lionestenzol)"}
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params, headers=headers)
            if resp.status_code != 200:
                # 403 (OAuth now required for some queries), 429 (rate-limited), etc.
                return []
            try:
                data = resp.json()
            except ValueError:
                return []

        out: list[SearchResult] = []
        for child in (data.get("data") or {}).get("children", []):
            post = child.get("data") or {}
            score_n = int(post.get("score") or 0)
            comments = int(post.get("num_comments") or 0)
            subreddit = post.get("subreddit_name_prefixed", "r/?")
            out.append(
                SearchResult(
                    title=post.get("title", ""),
                    url=f"https://reddit.com{post.get('permalink', '')}",
                    snippet=(post.get("selftext") or "")[:500],
                    score=min(1.0, score_n / 1000),
                    source="reddit",
                    kind="social",
                    raw={
                        "subreddit": subreddit,
                        "score": score_n,
                        "comments": comments,
                        "author": post.get("author"),
                    },
                )
            )
        return out
