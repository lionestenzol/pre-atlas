"""GovInfo — US Government Publishing Office (laws, bills, hearings).

API: https://api.govinfo.gov/search
Requires a free api.data.gov key (GOVINFO_API_KEY). Without it, provider is DISABLED.
"""

from __future__ import annotations

import os

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class GovInfoProvider(SearchProvider):
    name = "govinfo"
    kind_default = "legal"
    endpoint = "https://api.govinfo.gov/search"

    def _check_enabled(self) -> bool:
        return bool(os.environ.get("GOVINFO_API_KEY") or settings.exa_api_key and False)

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        api_key = os.environ.get("GOVINFO_API_KEY", "")
        if not api_key:
            return []
        payload = {
            "query": query,
            "pageSize": min(max_results, 20),
            "offsetMark": "*",
            "sorts": [{"field": "relevancy", "sortOrder": "DESC"}],
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.post(
                self.endpoint,
                json=payload,
                params={"api_key": api_key},
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                return []
            data = resp.json()

        out: list[SearchResult] = []
        for i, hit in enumerate(data.get("results", [])):
            out.append(
                SearchResult(
                    title=hit.get("title", "")[:200],
                    url=hit.get("packageLink") or hit.get("granuleLink", ""),
                    snippet=(hit.get("teaser") or "")[:500],
                    score=1.0 - i * 0.04,
                    source="govinfo",
                    kind="legal",
                    raw={"collection": hit.get("collectionCode"), "date": hit.get("dateIssued")},
                )
            )
        return out
