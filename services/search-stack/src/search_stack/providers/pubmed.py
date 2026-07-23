"""PubMed — biomedical literature via NCBI E-utilities.

API: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
No key required (3 req/s limit without key; 10/s with free key).
Two-step: esearch returns PMIDs, esummary returns metadata.
"""

from __future__ import annotations

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class PubMedProvider(SearchProvider):
    name = "pubmed"
    kind_default = "research"
    esearch = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    esummary = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    def _check_enabled(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            r1 = await client.get(
                self.esearch,
                params={
                    "db": "pubmed",
                    "term": query,
                    "retmax": min(max_results, 20),
                    "retmode": "json",
                    "sort": "relevance",
                },
            )
            r1.raise_for_status()
            ids = (r1.json().get("esearchresult") or {}).get("idlist") or []
            if not ids:
                return []

            r2 = await client.get(
                self.esummary,
                params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
            )
            r2.raise_for_status()
            summaries = (r2.json().get("result") or {})

        out: list[SearchResult] = []
        for i, pmid in enumerate(ids):
            entry = summaries.get(pmid) or {}
            title = entry.get("title", "")
            if not title:
                continue
            authors = ", ".join(a.get("name", "") for a in (entry.get("authors") or [])[:3])
            pubdate = entry.get("pubdate", "")
            snippet = f"{authors} · {pubdate}" if authors or pubdate else ""
            out.append(
                SearchResult(
                    title=title,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    snippet=snippet[:500],
                    score=1.0 - i * 0.03,
                    source="pubmed",
                    kind="research",
                    raw={"pmid": pmid, "journal": entry.get("source")},
                )
            )
        return out
