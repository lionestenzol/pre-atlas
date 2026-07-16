"""Firecrawl — managed URL → clean markdown extraction.

API docs: https://docs.firecrawl.dev/api-reference/endpoint/scrape
"""

from __future__ import annotations

import httpx

from .. import budget
from ..settings import settings
from .base import ExtractProvider, ExtractResult


class FirecrawlProvider(ExtractProvider):
    name = "firecrawl"
    endpoint = "https://api.firecrawl.dev/v1/scrape"

    def _check_enabled(self) -> bool:
        return bool(settings.firecrawl_api_key)

    async def extract(self, url: str, mode: str = "markdown") -> ExtractResult:
        if not budget.consume(self.name, settings.firecrawl_monthly_quota):
            self.last_error = "budget_blocked"
            raise RuntimeError("firecrawl budget exhausted for this month")

        format_map = {
            "markdown": ["markdown"],
            "clean": ["markdown"],
            "raw": ["html"],
        }
        formats = format_map.get(mode, ["markdown"])

        payload = {"url": url, "formats": formats}
        headers = {
            "Authorization": f"Bearer {settings.firecrawl_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds * 2) as client:
            resp = await client.post(self.endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        body = data.get("data") or {}
        content = body.get("markdown") if mode != "raw" else body.get("html", "")
        return ExtractResult(
            url=url,
            content=content or "",
            mode=mode,
            source="firecrawl",
            raw={"metadata": body.get("metadata", {})},
        )
