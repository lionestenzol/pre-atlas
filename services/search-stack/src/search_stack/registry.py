"""Singleton registry of providers, keyed by intent kind."""

from __future__ import annotations

from .providers.base import ExtractProvider, SearchProvider
from .providers.brave import BraveProvider
from .providers.exa import ExaProvider
from .providers.firecrawl import FirecrawlProvider
from .providers.github import GitHubProvider
from .providers.local_file import LocalFileProvider
from .providers.repo_search import RepoSearchProvider
from .providers.tavily import TavilyProvider
from .settings import settings

_search_singletons: dict[str, SearchProvider] = {
    "exa": ExaProvider(),
    "tavily": TavilyProvider(),
    "brave": BraveProvider(),
    "repo_search": RepoSearchProvider(),
    "local_file": LocalFileProvider(),
    "github": GitHubProvider(),
}

_extract_singletons: list[ExtractProvider] = [FirecrawlProvider()]


KIND_TO_PROVIDERS: dict[str, list[str]] = {
    "web": ["exa", "tavily", "brave"],
    "code": ["repo_search"],
    "file": ["local_file"],
    "github": ["github"],
    "memory": [],  # Phase 3 — wire memory-hub provider here
    "extract": [],
}


def providers_for(kind: str) -> list[SearchProvider]:
    names = KIND_TO_PROVIDERS.get(kind, [])
    return [_search_singletons[n] for n in names if n in _search_singletons]


def all_search_providers() -> dict[str, SearchProvider]:
    return dict(_search_singletons)


def extract_providers() -> list[ExtractProvider]:
    return list(_extract_singletons)


PROVIDER_QUOTAS = {
    "exa": settings.exa_monthly_quota,
    "tavily": settings.tavily_monthly_quota,
    "brave": settings.brave_monthly_quota,
    "firecrawl": settings.firecrawl_monthly_quota,
}
