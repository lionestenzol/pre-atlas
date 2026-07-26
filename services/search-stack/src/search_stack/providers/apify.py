"""Apify — managed cloud scraping via pre-built actors.

API: https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items
Auth: APIFY_TOKEN env var.

Apify has 4,000+ actors. This provider wraps the most useful ones for
search-stack kinds and lets you turn each on/off independently via env vars:

    APIFY_TOKEN=<your apify api token>             # required for ANY actor
    APIFY_ENABLE_GOOGLE_MAPS=1   → kind=local
    APIFY_ENABLE_AMAZON=1        → kind=product
    APIFY_ENABLE_INSTAGRAM=1     → kind=social
    APIFY_ENABLE_TIKTOK=1        → kind=social

Each Apify actor call COSTS COMPUTE UNITS — typically $0.001-0.01 per
result depending on the actor. Free tier: $5 credit/mo. Set
APIFY_MAX_RESULTS env var to cap per-call results (default 10).

Adding a new actor: register it in ACTOR_ADAPTERS below — supply actor ID,
input builder, and result mapper. No router changes needed.
"""

from __future__ import annotations

import os
from typing import Any, Callable

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult

APIFY_ENDPOINT = "https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"


def _maps_input(q: str, n: int) -> dict:
    return {
        "searchStringsArray": [q],
        "maxCrawledPlacesPerSearch": n,
        "language": "en",
    }


def _maps_map(item: dict) -> SearchResult | None:
    if not item.get("title"):
        return None
    return SearchResult(
        title=item.get("title", ""),
        url=item.get("url") or item.get("website") or "",
        snippet=" · ".join(filter(None, [
            item.get("address"),
            f"{item.get('totalScore')}★ ({item.get('reviewsCount')})" if item.get("totalScore") else "",
            item.get("phone"),
        ]))[:500],
        score=float(item.get("totalScore") or 0) / 5,
        source="apify-google-maps",
        kind="local",
        raw={
            "place_id": item.get("placeId"),
            "lat": (item.get("location") or {}).get("lat"),
            "lng": (item.get("location") or {}).get("lng"),
            "categories": item.get("categories"),
        },
    )


def _amazon_input(q: str, n: int) -> dict:
    return {
        "searchKeywords": [q],
        "maxItemsPerKeyword": n,
        "country": "US",
    }


def _amazon_map(item: dict) -> SearchResult | None:
    title = item.get("title") or item.get("name")
    url = item.get("url") or item.get("link")
    if not title or not url:
        return None
    price = item.get("price") or item.get("priceText")
    rating = item.get("rating") or item.get("stars")
    reviews = item.get("reviewsCount") or item.get("reviews")
    return SearchResult(
        title=str(title)[:200],
        url=str(url),
        snippet=" · ".join(filter(None, [
            f"${price}" if price else "",
            f"{rating}★ ({reviews})" if rating else "",
            item.get("brand"),
        ]))[:500],
        score=float(rating or 0) / 5 if rating else 0.5,
        source="apify-amazon",
        kind="product",
        raw={"asin": item.get("asin"), "price": price, "rating": rating, "brand": item.get("brand")},
    )


def _instagram_input(q: str, n: int) -> dict:
    return {
        "search": q,
        "searchType": "hashtag" if q.startswith("#") else "user",
        "resultsLimit": n,
    }


def _instagram_map(item: dict) -> SearchResult | None:
    username = item.get("username") or item.get("ownerUsername")
    if not username:
        return None
    url = item.get("url") or f"https://instagram.com/{username}"
    return SearchResult(
        title=f"@{username}",
        url=url,
        snippet=(item.get("biography") or item.get("caption") or "")[:500],
        score=min(1.0, int(item.get("followersCount") or 0) / 100_000),
        source="apify-instagram",
        kind="social",
        raw={
            "followers": item.get("followersCount"),
            "verified": item.get("verified"),
            "posts": item.get("postsCount"),
        },
    )


def _tiktok_input(q: str, n: int) -> dict:
    return {
        "searchQueries": [q],
        "resultsPerPage": n,
    }


def _tiktok_map(item: dict) -> SearchResult | None:
    url = item.get("webVideoUrl") or item.get("url")
    if not url:
        return None
    return SearchResult(
        title=(item.get("text") or item.get("desc") or "tiktok")[:200],
        url=url,
        snippet=(item.get("text") or "")[:500],
        score=min(1.0, int(item.get("playCount") or 0) / 1_000_000),
        source="apify-tiktok",
        kind="social",
        raw={
            "author": (item.get("authorMeta") or {}).get("name"),
            "plays": item.get("playCount"),
            "likes": item.get("diggCount"),
        },
    )


ACTOR_ADAPTERS: dict[str, dict[str, Any]] = {
    "google_maps": {
        "actor": "compass/crawler-google-places",
        "kind": "local",
        "env_flag": "APIFY_ENABLE_GOOGLE_MAPS",
        "build_input": _maps_input,
        "map_result": _maps_map,
    },
    "amazon": {
        "actor": "junglee/amazon-crawler",
        "kind": "product",
        "env_flag": "APIFY_ENABLE_AMAZON",
        "build_input": _amazon_input,
        "map_result": _amazon_map,
    },
    "instagram": {
        "actor": "apify/instagram-scraper",
        "kind": "social",
        "env_flag": "APIFY_ENABLE_INSTAGRAM",
        "build_input": _instagram_input,
        "map_result": _instagram_map,
    },
    "tiktok": {
        "actor": "clockworks/free-tiktok-scraper",
        "kind": "social",
        "env_flag": "APIFY_ENABLE_TIKTOK",
        "build_input": _tiktok_input,
        "map_result": _tiktok_map,
    },
}


class ApifyProvider(SearchProvider):
    """One instance per (kind, actor-adapter) pairing."""

    def __init__(self, adapter_key: str) -> None:
        self.adapter_key = adapter_key
        self.adapter = ACTOR_ADAPTERS[adapter_key]
        self.name = f"apify_{adapter_key}"
        self.kind_default = self.adapter["kind"]
        super().__init__()

    def _check_enabled(self) -> bool:
        if not os.environ.get("APIFY_TOKEN"):
            return False
        flag = self.adapter["env_flag"]
        return os.environ.get(flag, "0") == "1"

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        token = os.environ.get("APIFY_TOKEN", "")
        if not token:
            return []
        actor_id = self.adapter["actor"].replace("/", "~")
        url = APIFY_ENDPOINT.format(actor_id=actor_id)
        body = self.adapter["build_input"](query, min(max_results, 25))
        params = {"token": token, "timeout": 60}
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds * 6) as client:
            resp = await client.post(url, json=body, params=params)
            if resp.status_code not in (200, 201):
                return []
            try:
                items = resp.json()
            except ValueError:
                return []
        if not isinstance(items, list):
            return []
        mapper: Callable[[dict], SearchResult | None] = self.adapter["map_result"]
        out: list[SearchResult] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                r = mapper(item)
            except Exception:
                r = None
            if r is not None:
                out.append(r)
            if len(out) >= max_results:
                break
        return out
