"""Paid-tier providers stay DISABLED until their key arrives.

This test pins the contract: every paid provider follows the same shape —
no key → enabled=False → search() returns [] (no exception).
"""

from __future__ import annotations

import pytest

from search_stack.providers.fred import FredProvider
from search_stack.providers.google_maps import GoogleMapsProvider
from search_stack.providers.govinfo import GovInfoProvider
from search_stack.providers.keepa import KeepaProvider
from search_stack.providers.newsapi import NewsApiProvider
from search_stack.providers.perplexity import PerplexityProvider
from search_stack.providers.yelp import YelpProvider
from search_stack.providers.youtube import YouTubeProvider

PAID = [
    ("NEWSAPI_KEY", NewsApiProvider),
    ("YOUTUBE_API_KEY", YouTubeProvider),
    ("YELP_API_KEY", YelpProvider),
    ("GOOGLE_MAPS_KEY", GoogleMapsProvider),
    ("PERPLEXITY_API_KEY", PerplexityProvider),
    ("KEEPA_API_KEY", KeepaProvider),
    ("FRED_API_KEY", FredProvider),
    ("GOVINFO_API_KEY", GovInfoProvider),
]


@pytest.mark.parametrize("env_var,cls", PAID)
def test_paid_provider_disabled_without_key(monkeypatch, env_var, cls):
    monkeypatch.delenv(env_var, raising=False)
    p = cls()
    assert p.enabled is False, f"{cls.__name__} should be DISABLED without {env_var}"


@pytest.mark.asyncio
@pytest.mark.parametrize("env_var,cls", PAID)
async def test_paid_provider_search_returns_empty_without_key(monkeypatch, env_var, cls):
    monkeypatch.delenv(env_var, raising=False)
    p = cls()
    results = await p.search("anything", max_results=3)
    assert results == []
