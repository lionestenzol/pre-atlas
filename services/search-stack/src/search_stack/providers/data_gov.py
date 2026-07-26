"""data.gov — CKAN catalog of US federal datasets.

API: https://catalog.data.gov/api/3/action/package_search
No key required. Note: ckan endpoint sometimes 404s during catalog rebuilds;
provider degrades to empty silently in that case.
"""

from __future__ import annotations

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class DataGovProvider(SearchProvider):
    name = "data_gov"
    kind_default = "data"
    endpoint = "https://catalog.data.gov/api/3/action/package_search"

    def _check_enabled(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        params = {"q": query, "rows": min(max_results, 25)}
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds, follow_redirects=True) as client:
            resp = await client.get(self.endpoint, params=params)
            if resp.status_code != 200:
                return []
            try:
                data = resp.json()
            except ValueError:
                return []

        out: list[SearchResult] = []
        results = (data.get("result") or {}).get("results", [])
        for i, pkg in enumerate(results):
            name = pkg.get("name", "")
            out.append(
                SearchResult(
                    title=pkg.get("title", "")[:200],
                    url=f"https://catalog.data.gov/dataset/{name}",
                    snippet=(pkg.get("notes") or "")[:500],
                    score=1.0 - i * 0.04,
                    source="data_gov",
                    kind="data",
                    raw={
                        "organization": (pkg.get("organization") or {}).get("title"),
                        "num_resources": pkg.get("num_resources"),
                    },
                )
            )
        return out
