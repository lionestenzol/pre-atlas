"""FastMCP wrapper — exposes 3 narrow tools to Claude.

Mirrors the competitor-monitor MCP pattern.
"""

from __future__ import annotations

from typing import Optional

from fastmcp import FastMCP

from . import budget, registry, router

mcp = FastMCP("search-stack")


@mcp.tool()
async def search_stack_search(
    query: str,
    kind: Optional[str] = None,
    max_results: int = 10,
) -> dict:
    """Unified search across web (Exa+Tavily+Brave), code (rg/fd/sg), files (es), and GitHub.

    Args:
        query: The search text. Prefix shortcuts: `rg:`, `fd:`, `sg:`, `path:`, `repo:`, or a URL.
        kind: Force a routing kind. One of: web, code, file, github, memory, extract.
        max_results: Cap on returned results per provider (1-50).

    Returns:
        {kind, results: [{title, url, snippet, score, source, kind, ts}], providers_used, providers_failed, n}
    """
    return await router.search(query=query, kind=kind, max_results=max_results)


@mcp.tool()
async def search_stack_extract(url: str, mode: str = "markdown") -> dict:
    """Fetch a single URL and return cleaned content via Firecrawl.

    Args:
        url: The page to extract.
        mode: One of markdown (default), clean, raw.

    Returns:
        {url, content, mode, source, ts}
    """
    result = await router.extract(url, mode)
    return result.model_dump(mode="json")


@mcp.tool()
async def search_stack_budget() -> list[dict]:
    """Per-provider quota state for the current month.

    Returns:
        List of {provider, month, used, quota, percent, blocked}.
    """
    snaps = budget.all_snapshots(registry.PROVIDER_QUOTAS)
    return [s.model_dump(mode="json") for s in snaps]


def run() -> None:
    mcp.run()


if __name__ == "__main__":
    run()
