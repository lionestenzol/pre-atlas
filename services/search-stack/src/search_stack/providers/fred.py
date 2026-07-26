"""FRED — Federal Reserve Economic Data series search.

API: https://api.stlouisfed.org/fred/series/search
Requires free FRED_API_KEY. Without it, provider is DISABLED.
"""

from __future__ import annotations

import os

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class FredProvider(SearchProvider):
    name = "fred"
    kind_default = "data"
    endpoint = "https://api.stlouisfed.org/fred/series/search"

    def _check_enabled(self) -> bool:
        return bool(os.environ.get("FRED_API_KEY"))

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        api_key = os.environ.get("FRED_API_KEY", "")
        if not api_key:
            return []
        params = {
            "search_text": query,
            "api_key": api_key,
            "file_type": "json",
            "limit": min(max_results, 25),
            "order_by": "popularity",
            "sort_order": "desc",
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()

        out: list[SearchResult] = []
        for series in data.get("seriess", []):
            popularity = int(series.get("popularity") or 0)
            sid = series.get("id", "")
            out.append(
                SearchResult(
                    title=series.get("title", ""),
                    url=f"https://fred.stlouisfed.org/series/{sid}",
                    snippet=(series.get("notes") or "")[:500],
                    score=min(1.0, popularity / 100),
                    source="fred",
                    kind="data",
                    raw={
                        "series_id": sid,
                        "frequency": series.get("frequency"),
                        "units": series.get("units"),
                        "last_updated": series.get("last_updated"),
                    },
                )
            )
        return out
