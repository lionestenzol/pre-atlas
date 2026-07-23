"""Intent classifier → provider dispatch.

Rule-based classifier first. Upgrade to LLM-classified later if rule-based misroutes >5%.
"""

from __future__ import annotations

import re
from typing import Iterable

from . import audit, cache
from .providers.base import ExtractResult, SearchResult
from .settings import settings

KIND_WEB = "web"
KIND_EXTRACT = "extract"
KIND_GITHUB = "github"
KIND_FILE = "file"
KIND_CODE = "code"
KIND_MEMORY = "memory"
KIND_RESEARCH = "research"
KIND_SOCIAL = "social"
KIND_NEWS = "news"
KIND_LEGAL = "legal"
KIND_DATA = "data"
KIND_LOCAL = "local"
KIND_MULTIMEDIA = "multimedia"
KIND_PRODUCT = "product"

VALID_KINDS = {
    KIND_WEB, KIND_EXTRACT, KIND_GITHUB, KIND_FILE, KIND_CODE, KIND_MEMORY,
    KIND_RESEARCH, KIND_SOCIAL, KIND_NEWS, KIND_LEGAL, KIND_DATA, KIND_LOCAL,
    KIND_MULTIMEDIA, KIND_PRODUCT,
}

URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def classify(query: str, explicit_kind: str | None = None) -> str:
    """Map a query to a kind. Explicit kind always wins."""
    if explicit_kind and explicit_kind in VALID_KINDS:
        return explicit_kind
    q = query.strip()
    if URL_RE.match(q):
        return KIND_EXTRACT
    if "site:github.com" in q.lower() or q.lower().startswith("repo:"):
        return KIND_GITHUB
    if q.startswith(("path:", "file:")):
        return KIND_FILE
    if q.startswith(("rg:", "fd:", "sg:")):
        return KIND_CODE
    if q.startswith(("arxiv:", "paper:", "doi:")):
        return KIND_RESEARCH
    if q.startswith(("reddit:", "hn:", "social:")):
        return KIND_SOCIAL
    if q.startswith("news:"):
        return KIND_NEWS
    if q.startswith(("sec:", "edgar:", "law:", "court:")):
        return KIND_LEGAL
    if q.startswith(("dataset:", "data:", "fred:")):
        return KIND_DATA
    if q.startswith(("place:", "near:", "yelp:", "maps:")):
        return KIND_LOCAL
    if q.startswith(("video:", "youtube:", "yt:")):
        return KIND_MULTIMEDIA
    if q.startswith(("amazon:", "asin:", "product:")):
        return KIND_PRODUCT
    return KIND_WEB


def _dedup_by_url(results: Iterable[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    out: list[SearchResult] = []
    for r in results:
        if r.url in seen:
            continue
        seen.add(r.url)
        out.append(r)
    return out


async def search(
    query: str,
    kind: str | None = None,
    max_results: int = 10,
    providers: list[str] | None = None,
    force_fresh: bool = False,
) -> dict:
    """Main dispatch. Returns {kind, results, providers_used, providers_failed, errors}."""
    from . import registry

    resolved_kind = classify(query, kind)
    audit.log("search.start", query=query, kind=resolved_kind, max_results=max_results)

    provider_list = registry.providers_for(resolved_kind)
    if providers:
        provider_list = [p for p in provider_list if p.name in providers]

    all_results: list[SearchResult] = []
    used: list[str] = []
    failed: list[dict] = []

    for prov in provider_list:
        if not prov.enabled:
            failed.append({"provider": prov.name, "reason": "disabled"})
            continue

        if not force_fresh:
            cached = cache.get(prov.name, resolved_kind, query, max_results)
            if cached is not None:
                all_results.extend(SearchResult(**r) for r in cached)
                used.append(prov.name + ":cache")
                continue

        try:
            results = await prov.search(query, max_results)
            all_results.extend(results)
            used.append(prov.name)
            cache.put(
                prov.name,
                resolved_kind,
                query,
                max_results,
                [r.model_dump(mode="json") for r in results],
            )
        except Exception as exc:
            failed.append({"provider": prov.name, "reason": str(exc)[:200]})
            audit.log("search.error", provider=prov.name, error=str(exc)[:500])

    deduped = _dedup_by_url(all_results)
    deduped.sort(key=lambda r: r.score, reverse=True)
    top = deduped[:max_results]

    audit.log(
        "search.done",
        query=query,
        kind=resolved_kind,
        used=used,
        failed=[f["provider"] for f in failed],
        n_results=len(top),
    )

    return {
        "kind": resolved_kind,
        "results": [r.model_dump(mode="json") for r in top],
        "providers_used": used,
        "providers_failed": failed,
        "n": len(top),
    }


async def extract(url: str, mode: str = "markdown") -> ExtractResult:
    from . import registry

    provs = registry.extract_providers()
    last_err = None
    for prov in provs:
        if not prov.enabled:
            continue
        try:
            return await prov.extract(url, mode)
        except Exception as exc:
            last_err = str(exc)
            audit.log("extract.error", provider=prov.name, url=url, error=last_err[:500])
            continue
    raise RuntimeError(f"all extract providers failed: {last_err}")
