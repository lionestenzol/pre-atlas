"""OpenStreetMap Nominatim — geocoding + place search.

API: https://nominatim.openstreetmap.org/search
No key required. User-agent mandatory; respect 1 req/s policy.
"""

from __future__ import annotations

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class OpenStreetMapProvider(SearchProvider):
    name = "openstreetmap"
    kind_default = "local"
    endpoint = "https://nominatim.openstreetmap.org/search"

    def _check_enabled(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        params = {
            "q": query,
            "format": "json",
            "limit": min(max_results, 20),
            "addressdetails": 1,
        }
        headers = {"User-Agent": "search-stack/0.1 brukev@gmail.com"}
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params, headers=headers)
            if resp.status_code != 200:
                return []
            try:
                data = resp.json()
            except ValueError:
                return []

        out: list[SearchResult] = []
        for i, place in enumerate(data):
            lat = place.get("lat", "")
            lon = place.get("lon", "")
            osm_type = place.get("osm_type", "")
            osm_id = place.get("osm_id", "")
            url = (
                f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
                if osm_type and osm_id
                else f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}"
            )
            out.append(
                SearchResult(
                    title=place.get("display_name", "")[:200],
                    url=url,
                    snippet=f"lat={lat} lon={lon} · class={place.get('class')} type={place.get('type')}",
                    score=float(place.get("importance") or (1.0 - i * 0.05)),
                    source="openstreetmap",
                    kind="local",
                    raw={
                        "lat": lat,
                        "lon": lon,
                        "address": place.get("address", {}),
                        "boundingbox": place.get("boundingbox"),
                    },
                )
            )
        return out
