"""SEC EDGAR — full-text search of public company filings.

API: https://efts.sec.gov/LATEST/search-index
No key required. User-agent is mandatory per SEC policy.
"""

from __future__ import annotations

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class SecEdgarProvider(SearchProvider):
    name = "sec_edgar"
    kind_default = "legal"
    endpoint = "https://efts.sec.gov/LATEST/search-index"

    def _check_enabled(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        params = {"q": f'"{query}"', "dateRange": "custom", "forms": ""}
        headers = {
            "User-Agent": "Bruke Vasi search-stack brukev@gmail.com",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        out: list[SearchResult] = []
        hits = (data.get("hits") or {}).get("hits", [])
        for i, hit in enumerate(hits[:max_results]):
            src = hit.get("_source") or {}
            accession = (hit.get("_id") or "").split(":")[0].replace("-", "")
            cik = src.get("ciks", ["0"])[0] if src.get("ciks") else "0"
            form = src.get("form", "")
            file_name = src.get("file_name") or src.get("file_type") or ""
            if accession and cik:
                url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{file_name}"
            else:
                url = f"https://efts.sec.gov/LATEST/search-index?q={query}"
            out.append(
                SearchResult(
                    title=f"{form} · {(src.get('display_names') or [''])[0]}",
                    url=url,
                    snippet=(src.get("description") or src.get("file_description") or "")[:500],
                    score=1.0 - i * 0.05,
                    source="sec_edgar",
                    kind="legal",
                    raw={"form": form, "cik": cik, "filed": src.get("file_date")},
                )
            )
        return out
