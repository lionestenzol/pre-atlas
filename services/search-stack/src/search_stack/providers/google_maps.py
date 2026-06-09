"""Google Maps Places API — local place search.

API: https://maps.googleapis.com/maps/api/place/textsearch/json
Requires Google Cloud account + billing enabled. GOOGLE_MAPS_KEY env var.
"""

from __future__ import annotations

import os

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult


class GoogleMapsProvider(SearchProvider):
    name = "google_maps"
    kind_default = "local"
    endpoint = "https://maps.googleapis.com/maps/api/place/textsearch/json"

    def _check_enabled(self) -> bool:
        return bool(os.environ.get("GOOGLE_MAPS_KEY"))

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        api_key = os.environ.get("GOOGLE_MAPS_KEY", "")
        if not api_key:
            return []
        params = {"query": query, "key": api_key}
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(self.endpoint, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()

        out: list[SearchResult] = []
        for i, place in enumerate(data.get("results", [])[:max_results]):
            place_id = place.get("place_id", "")
            rating = float(place.get("rating") or 0)
            user_ratings = int(place.get("user_ratings_total") or 0)
            out.append(
                SearchResult(
                    title=place.get("name", ""),
                    url=f"https://www.google.com/maps/place/?q=place_id:{place_id}",
                    snippet=" · ".join(filter(None, [
                        place.get("formatted_address"),
                        f"{rating}★ ({user_ratings})" if rating else "",
                    ]))[:500],
                    score=min(1.0, rating / 5),
                    source="google_maps",
                    kind="local",
                    raw={
                        "place_id": place_id,
                        "rating": rating,
                        "user_ratings_total": user_ratings,
                        "types": place.get("types"),
                    },
                )
            )
        return out
