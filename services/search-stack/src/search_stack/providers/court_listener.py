"""CourtListener — Free Law Project case-law search.

API: https://www.courtlistener.com/api/rest/v3/search/
No key required for basic search; free token raises rate limits.
"""

from __future__ import annotations

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class CourtListenerProvider(SearchProvider):
    name = "court_listener"
    kind_default = "legal"
    endpoint = "https://www.courtlistener.com/api/rest/v3/search/"

    def _check_enabled(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        params = {"q": query, "type": "o", "order_by": "score desc"}
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params)
            if resp.status_code != 200:
                # Now usually requires COURTLISTENER_TOKEN env for v3 search
                return []
            try:
                data = resp.json()
            except ValueError:
                return []

        out: list[SearchResult] = []
        for result in data.get("results", [])[:max_results]:
            url = f"https://www.courtlistener.com{result.get('absolute_url', '')}"
            out.append(
                SearchResult(
                    title=result.get("caseName") or result.get("case_name", ""),
                    url=url,
                    snippet=(result.get("snippet") or "")[:500],
                    score=float(result.get("score") or 0.5),
                    source="court_listener",
                    kind="legal",
                    raw={
                        "court": result.get("court"),
                        "date_filed": result.get("dateFiled"),
                        "citation": result.get("citation"),
                    },
                )
            )
        return out
