"""YouTube Data API v3 — video search.

API: https://www.googleapis.com/youtube/v3/search
Free tier: 10,000 units/day (a search costs 100 units). YOUTUBE_API_KEY env var.
"""

from __future__ import annotations

import os

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class YouTubeProvider(SearchProvider):
    name = "youtube"
    kind_default = "multimedia"
    endpoint = "https://www.googleapis.com/youtube/v3/search"

    def _check_enabled(self) -> bool:
        return bool(os.environ.get("YOUTUBE_API_KEY"))

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        api_key = os.environ.get("YOUTUBE_API_KEY", "")
        if not api_key:
            return []
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": min(max_results, 25),
            "key": api_key,
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()

        out: list[SearchResult] = []
        for i, item in enumerate(data.get("items", [])):
            video_id = (item.get("id") or {}).get("videoId", "")
            snippet = item.get("snippet") or {}
            out.append(
                SearchResult(
                    title=snippet.get("title", ""),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    snippet=(snippet.get("description") or "")[:500],
                    score=1.0 - i * 0.03,
                    source="youtube",
                    kind="multimedia",
                    raw={
                        "channel": snippet.get("channelTitle"),
                        "published_at": snippet.get("publishedAt"),
                        "video_id": video_id,
                    },
                )
            )
        return out
