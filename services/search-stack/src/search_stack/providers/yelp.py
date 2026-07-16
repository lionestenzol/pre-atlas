"""Yelp Fusion — local business search.

API: https://api.yelp.com/v3/businesses/search
Free with API key. YELP_API_KEY env var.
"""

from __future__ import annotations

import os

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class YelpProvider(SearchProvider):
    name = "yelp"
    kind_default = "local"
    endpoint = "https://api.yelp.com/v3/businesses/search"

    def _check_enabled(self) -> bool:
        return bool(os.environ.get("YELP_API_KEY"))

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        api_key = os.environ.get("YELP_API_KEY", "")
        if not api_key:
            return []
        location = os.environ.get("YELP_DEFAULT_LOCATION", "United States")
        params = {
            "term": query,
            "location": location,
            "limit": min(max_results, 20),
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params, headers=headers)
            if resp.status_code != 200:
                return []
            data = resp.json()

        out: list[SearchResult] = []
        for biz in data.get("businesses", []):
            rating = float(biz.get("rating") or 0)
            review_count = int(biz.get("review_count") or 0)
            out.append(
                SearchResult(
                    title=biz.get("name", ""),
                    url=biz.get("url", ""),
                    snippet=" · ".join(filter(None, [
                        ", ".join(c.get("title") for c in biz.get("categories", []) if c.get("title")),
                        f"{rating}★ ({review_count})",
                        (biz.get("location") or {}).get("city"),
                    ]))[:500],
                    score=min(1.0, rating / 5 * min(1.0, review_count / 200)),
                    source="yelp",
                    kind="local",
                    raw={
                        "rating": rating,
                        "review_count": review_count,
                        "address": (biz.get("location") or {}).get("display_address"),
                        "phone": biz.get("display_phone"),
                    },
                )
            )
        return out
