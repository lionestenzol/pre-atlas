"""OpenAlex — open citation graph (250M+ scholarly works).

API: https://api.openalex.org/works
No key required. Polite pool: pass mailto in user-agent for higher rate limits.
"""

from __future__ import annotations

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class OpenAlexProvider(SearchProvider):
    name = "openalex"
    kind_default = "research"
    endpoint = "https://api.openalex.org/works"

    def _check_enabled(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        params = {
            "search": query,
            "per-page": min(max_results, 25),
            "select": "id,title,doi,abstract_inverted_index,publication_year,cited_by_count,open_access",
        }
        headers = {"User-Agent": "search-stack/0.1 (mailto:brukev@gmail.com)"}
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        out: list[SearchResult] = []
        for work in data.get("results", []):
            citations = int(work.get("cited_by_count") or 0)
            score = min(1.0, citations / 500) if citations else 0.3
            url = work.get("doi") or work.get("id") or ""
            if url and url.startswith("10."):
                url = f"https://doi.org/{url}"
            elif url and url.startswith("https://openalex.org/"):
                pass
            elif url:
                url = f"https://doi.org/{url}" if not url.startswith("http") else url
            out.append(
                SearchResult(
                    title=work.get("title", ""),
                    url=url,
                    snippet=self._invert_abstract(work.get("abstract_inverted_index") or {})[:500],
                    score=score,
                    source="openalex",
                    kind="research",
                    raw={
                        "year": work.get("publication_year"),
                        "citations": citations,
                        "open_access": (work.get("open_access") or {}).get("is_oa"),
                    },
                )
            )
        return out

    @staticmethod
    def _invert_abstract(inverted: dict) -> str:
        """OpenAlex stores abstracts as {word: [positions]}. Reconstruct."""
        if not inverted:
            return ""
        positions: list[tuple[int, str]] = []
        for word, idxs in inverted.items():
            for i in idxs:
                positions.append((i, word))
        positions.sort(key=lambda x: x[0])
        return " ".join(w for _, w in positions)
