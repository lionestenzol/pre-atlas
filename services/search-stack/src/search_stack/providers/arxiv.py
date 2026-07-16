"""arXiv — preprint server for math, physics, CS, etc.

API: http://export.arxiv.org/api/query
No key required. Atom feed response; we parse minimally with stdlib.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import urlencode

import httpx

from ..settings import settings
from .base import SearchProvider, SearchResult

_NS = {"a": "http://www.w3.org/2005/Atom"}


class ArxivProvider(SearchProvider):
    name = "arxiv"
    kind_default = "research"
    endpoint = "http://export.arxiv.org/api/query"

    def _check_enabled(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": min(max_results, 25),
            "sortBy": "relevance",
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.get(f"{self.endpoint}?{urlencode(params)}")
            if resp.status_code != 200:
                return []
            body = resp.text

        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return []
        out: list[SearchResult] = []
        for i, entry in enumerate(root.findall("a:entry", _NS)):
            title_el = entry.find("a:title", _NS)
            summary_el = entry.find("a:summary", _NS)
            id_el = entry.find("a:id", _NS)
            published_el = entry.find("a:published", _NS)
            if title_el is None or id_el is None:
                continue
            out.append(
                SearchResult(
                    title=(title_el.text or "").strip(),
                    url=(id_el.text or "").strip(),
                    snippet=((summary_el.text if summary_el is not None else "") or "").strip()[:500],
                    score=1.0 - i * 0.04,
                    source="arxiv",
                    kind="research",
                    raw={"published": (published_el.text if published_el is not None else "")},
                )
            )
        return out
