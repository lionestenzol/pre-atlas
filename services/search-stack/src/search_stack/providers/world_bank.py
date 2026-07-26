"""World Bank Open Data — indicators and country statistics.

API: https://api.worldbank.org/v2/
No key required. Query returns indicator metadata; this provider searches indicators by keyword.
"""

from __future__ import annotations

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class WorldBankProvider(SearchProvider):
    name = "world_bank"
    kind_default = "data"
    endpoint = "https://api.worldbank.org/v2/indicator"

    def _check_enabled(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        params = {"format": "json", "per_page": min(max_results, 50), "source": 2}
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params)
            resp.raise_for_status()
            try:
                payload = resp.json()
            except ValueError:
                return []

        if not isinstance(payload, list) or len(payload) < 2:
            return []
        indicators = payload[1] or []
        q_lower = query.lower()
        scored: list[tuple[float, dict]] = []
        for ind in indicators:
            name = (ind.get("name") or "").lower()
            note = (ind.get("sourceNote") or "").lower()
            if q_lower in name:
                scored.append((1.0, ind))
            elif q_lower in note:
                scored.append((0.6, ind))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[SearchResult] = []
        for score, ind in scored[:max_results]:
            ind_id = ind.get("id", "")
            out.append(
                SearchResult(
                    title=ind.get("name", ""),
                    url=f"https://data.worldbank.org/indicator/{ind_id}",
                    snippet=(ind.get("sourceNote") or "")[:500],
                    score=score,
                    source="world_bank",
                    kind="data",
                    raw={"indicator_id": ind_id, "source": (ind.get("source") or {}).get("value")},
                )
            )
        return out
