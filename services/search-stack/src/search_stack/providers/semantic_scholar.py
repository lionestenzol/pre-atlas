"""Semantic Scholar — Allen AI's academic graph.

API: https://api.semanticscholar.org/graph/v1/paper/search
No key required (rate-limited without; free api-key recommended for production).
"""

from __future__ import annotations

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class SemanticScholarProvider(SearchProvider):
    name = "semantic_scholar"
    kind_default = "research"
    endpoint = "https://api.semanticscholar.org/graph/v1/paper/search"

    def _check_enabled(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        params = {
            "query": query,
            "limit": min(max_results, 20),
            "fields": "title,abstract,url,year,authors,citationCount,openAccessPdf",
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params)
            if resp.status_code == 429:
                return []
            resp.raise_for_status()
            data = resp.json()

        out: list[SearchResult] = []
        for paper in data.get("data", []):
            url = paper.get("url") or (paper.get("openAccessPdf") or {}).get("url") or ""
            if not url:
                continue
            citations = int(paper.get("citationCount") or 0)
            score = min(1.0, citations / 1000) if citations else 0.3
            out.append(
                SearchResult(
                    title=paper.get("title", ""),
                    url=url,
                    snippet=(paper.get("abstract") or "")[:500],
                    score=score,
                    source="semantic_scholar",
                    kind="research",
                    raw={"year": paper.get("year"), "citations": citations},
                )
            )
        return out
