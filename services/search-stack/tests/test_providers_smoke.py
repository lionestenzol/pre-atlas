"""Smoke tests — gated on real API keys via env. Skip when missing."""

import os

import pytest

from search_stack.providers.brave import BraveProvider
from search_stack.providers.exa import ExaProvider
from search_stack.providers.firecrawl import FirecrawlProvider
from search_stack.providers.tavily import TavilyProvider


@pytest.mark.asyncio
async def test_exa_smoke():
    if not os.getenv("EXA_API_KEY"):
        pytest.skip("EXA_API_KEY not set")
    p = ExaProvider()
    results = await p.search("react server components", max_results=3)
    assert isinstance(results, list)
    assert len(results) > 0
    assert all(r.url.startswith("http") for r in results)


@pytest.mark.asyncio
async def test_tavily_smoke():
    if not os.getenv("TAVILY_API_KEY"):
        pytest.skip("TAVILY_API_KEY not set")
    p = TavilyProvider()
    results = await p.search("openai dev day 2026", max_results=3)
    assert isinstance(results, list)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_brave_smoke():
    if not os.getenv("BRAVE_API_KEY"):
        pytest.skip("BRAVE_API_KEY not set")
    p = BraveProvider()
    results = await p.search("anthropic claude api docs", max_results=3)
    assert isinstance(results, list)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_firecrawl_smoke():
    if not os.getenv("FIRECRAWL_API_KEY"):
        pytest.skip("FIRECRAWL_API_KEY not set")
    p = FirecrawlProvider()
    result = await p.extract("https://example.com")
    assert result.content
    assert "example" in result.content.lower()


def test_providers_disabled_without_keys(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    from search_stack.settings import Settings

    s = Settings(_env_file=None)
    assert not (s.exa_api_key or s.tavily_api_key or s.brave_api_key or s.firecrawl_api_key)
