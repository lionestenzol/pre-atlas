"""Keepa — Amazon product price history.

API: https://api.keepa.com/search
Paid (~$20/mo). KEEPA_API_KEY env var. DISABLED stub by default.
"""

from __future__ import annotations

import os

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class KeepaProvider(SearchProvider):
    name = "keepa"
    kind_default = "product"
    endpoint = "https://api.keepa.com/search"

    def _check_enabled(self) -> bool:
        return bool(os.environ.get("KEEPA_API_KEY"))

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        api_key = os.environ.get("KEEPA_API_KEY", "")
        if not api_key:
            return []
        params = {
            "key": api_key,
            "domain": 1,
            "type": "product",
            "term": query,
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()

        out: list[SearchResult] = []
        for i, asin in enumerate((data.get("asinList") or [])[:max_results]):
            out.append(
                SearchResult(
                    title=f"Amazon ASIN {asin}",
                    url=f"https://www.amazon.com/dp/{asin}",
                    snippet=f"Price history at keepa.com/#!product/1-{asin}",
                    score=1.0 - i * 0.05,
                    source="keepa",
                    kind="product",
                    raw={"asin": asin},
                )
            )
        return out
