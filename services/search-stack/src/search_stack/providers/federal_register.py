"""Federal Register — US federal rules, proposed rules, notices.

API: https://www.federalregister.gov/api/v1/documents
No key required.
"""

from __future__ import annotations

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class FederalRegisterProvider(SearchProvider):
    name = "federal_register"
    kind_default = "legal"
    endpoint = "https://www.federalregister.gov/api/v1/documents"

    def _check_enabled(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        params = {
            "conditions[term]": query,
            "per_page": min(max_results, 20),
            "order": "relevance",
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params)
            resp.raise_for_status()
            data = resp.json()

        out: list[SearchResult] = []
        for i, doc in enumerate(data.get("results", [])):
            out.append(
                SearchResult(
                    title=doc.get("title", "")[:200],
                    url=doc.get("html_url") or doc.get("pdf_url", ""),
                    snippet=(doc.get("abstract") or "")[:500],
                    score=1.0 - i * 0.04,
                    source="federal_register",
                    kind="legal",
                    raw={
                        "type": doc.get("type"),
                        "agency": (doc.get("agencies") or [{}])[0].get("name"),
                        "publication_date": doc.get("publication_date"),
                    },
                )
            )
        return out
