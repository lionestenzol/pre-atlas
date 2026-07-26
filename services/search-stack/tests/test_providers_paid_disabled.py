"""Paid-tier providers stay DISABLED until their key arrives.

This test pins the contract: every paid provider follows the same shape —
no key → enabled=False → search() returns [] (no exception).
"""

from __future__ import annotations

import pytest

from search_stack.providers.apify import ACTOR_ADAPTERS, ApifyProvider
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


@pytest.mark.parametrize("adapter_key", list(ACTOR_ADAPTERS.keys()))
def test_apify_disabled_without_token(monkeypatch, adapter_key):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    monkeypatch.setenv(ACTOR_ADAPTERS[adapter_key]["env_flag"], "1")
    p = ApifyProvider(adapter_key)
    assert p.enabled is False, "Apify adapters need APIFY_TOKEN even with their enable flag set"


@pytest.mark.parametrize("adapter_key", list(ACTOR_ADAPTERS.keys()))
def test_apify_disabled_without_enable_flag(monkeypatch, adapter_key):
    monkeypatch.setenv("APIFY_TOKEN", "fake")
    monkeypatch.delenv(ACTOR_ADAPTERS[adapter_key]["env_flag"], raising=False)
    p = ApifyProvider(adapter_key)
    assert p.enabled is False, "Apify adapters need both APIFY_TOKEN AND their per-actor enable flag"


@pytest.mark.parametrize("adapter_key", list(ACTOR_ADAPTERS.keys()))
def test_apify_enabled_with_both(monkeypatch, adapter_key):
    monkeypatch.setenv("APIFY_TOKEN", "fake")
    monkeypatch.setenv(ACTOR_ADAPTERS[adapter_key]["env_flag"], "1")
    p = ApifyProvider(adapter_key)
    assert p.enabled is True


def test_apify_each_adapter_in_a_known_kind():
    valid_kinds = {"local", "product", "social", "multimedia", "news"}
    for key, ad in ACTOR_ADAPTERS.items():
        assert ad["kind"] in valid_kinds, f"adapter {key} has unknown kind {ad['kind']}"
