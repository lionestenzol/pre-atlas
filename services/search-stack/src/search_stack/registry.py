"""Singleton registry of providers, keyed by intent kind."""

from __future__ import annotations

from .providers.arxiv import ArxivProvider
from .providers.base import ExtractProvider, SearchProvider
from .providers.brave import BraveProvider
from .providers.court_listener import CourtListenerProvider
from .providers.data_gov import DataGovProvider
from .providers.exa import ExaProvider
from .providers.federal_register import FederalRegisterProvider
from .providers.firecrawl import FirecrawlProvider
from .providers.fred import FredProvider
from .providers.gdelt import GdeltProvider
from .providers.github import GitHubProvider
from .providers.google_maps import GoogleMapsProvider
from .providers.govinfo import GovInfoProvider
from .providers.hackernews import HackerNewsProvider
from .providers.keepa import KeepaProvider
from .providers.local_file import LocalFileProvider
from .providers.memory import MemoryProvider
from .providers.newsapi import NewsApiProvider
from .providers.openalex import OpenAlexProvider
from .providers.openstreetmap import OpenStreetMapProvider
from .providers.perplexity import PerplexityProvider
from .providers.pubmed import PubMedProvider
from .providers.reddit import RedditProvider
from .providers.repo_search import RepoSearchProvider
from .providers.sec_edgar import SecEdgarProvider
from .providers.semantic_scholar import SemanticScholarProvider
from .providers.tavily import TavilyProvider
from .providers.world_bank import WorldBankProvider
from .providers.yelp import YelpProvider
from .providers.youtube import YouTubeProvider
from .settings import settings

_search_singletons: dict[str, SearchProvider] = {
    # External web (paid w/ free tier)
    "exa": ExaProvider(),
    "tavily": TavilyProvider(),
    "brave": BraveProvider(),
    "perplexity": PerplexityProvider(),
    # Local
    "repo_search": RepoSearchProvider(),
    "local_file": LocalFileProvider(),
    "github": GitHubProvider(),
    "memory": MemoryProvider(),
    # Research (free)
    "arxiv": ArxivProvider(),
    "semantic_scholar": SemanticScholarProvider(),
    "openalex": OpenAlexProvider(),
    "pubmed": PubMedProvider(),
    # Social (free)
    "hackernews": HackerNewsProvider(),
    "reddit": RedditProvider(),
    # News
    "gdelt": GdeltProvider(),
    "newsapi": NewsApiProvider(),
    # Legal (free)
    "sec_edgar": SecEdgarProvider(),
    "federal_register": FederalRegisterProvider(),
    "court_listener": CourtListenerProvider(),
    "govinfo": GovInfoProvider(),
    # Data (free + 1 paid)
    "world_bank": WorldBankProvider(),
    "data_gov": DataGovProvider(),
    "openstreetmap": OpenStreetMapProvider(),
    "fred": FredProvider(),
    # Multimedia
    "youtube": YouTubeProvider(),
    # Local biz
    "yelp": YelpProvider(),
    "google_maps": GoogleMapsProvider(),
    # Product
    "keepa": KeepaProvider(),
}

_extract_singletons: list[ExtractProvider] = [FirecrawlProvider()]


KIND_TO_PROVIDERS: dict[str, list[str]] = {
    "web": ["exa", "tavily", "brave", "perplexity"],
    "code": ["repo_search"],
    "file": ["local_file"],
    "github": ["github"],
    "memory": ["memory"],
    "extract": [],
    "research": ["arxiv", "semantic_scholar", "openalex", "pubmed"],
    "social": ["hackernews", "reddit"],
    "news": ["gdelt", "newsapi"],
    "legal": ["sec_edgar", "federal_register", "court_listener", "govinfo"],
    "data": ["world_bank", "data_gov", "fred"],
    "local": ["openstreetmap", "yelp", "google_maps"],
    "multimedia": ["youtube"],
    "product": ["keepa"],
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
