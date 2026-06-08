"""Retrieval: pull the 3-5 most relevant prior packets from local memory.

MVP uses token-overlap scoring (no embeddings, no deps). The interface returns
the snippet shape specified in the spec so a vector backend can be swapped in
later without changing callers.

External wire (Phase 2 of the ultimate-search-stack plan): retrieve_with_external()
optionally HTTP-calls services/search-stack on localhost and merges its results
into the same {source, snippet, relevance, type, domain} shape. Gated by
DROPLIST_EXTERNAL_SEARCH=1 so opt-in only. Closes BIBLE §15 OQ-10 for the
external half (internal vector swap still deferred).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

_TOKEN = re.compile(r"[a-z0-9]+")
_DEFAULT_SEARCH_STACK_URL = "http://127.0.0.1:3070/search"
_STOP = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "is",
    "it", "this", "that", "with", "was", "were", "be", "are", "as", "at", "by",
    "i", "my", "we", "so", "if", "not", "no", "do", "did", "too", "than",
}


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 2}


def retrieve(normalized: str, prior_packets: list[dict], k: int = 5) -> list[dict]:
    """Return up to k {source, snippet, relevance} dicts, best first."""
    q = _tokens(normalized)
    if not q:
        return []

    scored: list[tuple[float, dict]] = []
    for p in prior_packets:
        text = p.get("normalized_input", "")
        toks = _tokens(text)
        if not toks:
            continue
        overlap = q & toks
        if not overlap:
            continue
        # relevance = overlap weighted toward query coverage
        relevance = len(overlap) / (len(q) ** 0.5 * len(toks) ** 0.5)
        # small boost for same domain/type if present
        scored.append((
            round(relevance, 3),
            {
                "source": p.get("drop_id", "unknown"),
                "snippet": text[:140],
                "relevance": round(relevance, 3),
                "type": p.get("type"),
                "domain": p.get("domain"),
            },
        ))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:k]]


def _external_search_enabled() -> bool:
    return os.environ.get("DROPLIST_EXTERNAL_SEARCH", "0") == "1"


def _search_stack_url() -> str:
    return os.environ.get("SEARCH_STACK_URL", _DEFAULT_SEARCH_STACK_URL)


def retrieve_external(query: str, kind: str = "web", k: int = 5, timeout: float = 10.0) -> list[dict]:
    """POST to search-stack /search and return up to k results in the snippet shape.

    Returns an empty list on any error (network, non-2xx, malformed JSON). Never
    raises — caller can always merge with the internal retrieve() output safely.
    """
    if not query.strip():
        return []
    payload = {"q": query, "kind": kind, "max_results": k}
    req = urllib.request.Request(
        _search_stack_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - localhost only
            body = resp.read().decode("utf-8")
        data = json.loads(body)
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return []

    out: list[dict] = []
    for item in (data.get("results") or [])[:k]:
        score = float(item.get("score") or 0.0)
        out.append(
            {
                "source": item.get("url") or item.get("source", "external"),
                "snippet": (item.get("title") or "") + " — " + (item.get("snippet") or "")[:140],
                "relevance": round(score, 3),
                "type": "external",
                "domain": item.get("source", "external"),
            }
        )
    return out


def retrieve_with_external(
    normalized: str,
    prior_packets: list[dict],
    k: int = 5,
    kind: str = "web",
) -> list[dict]:
    """Merge internal token-overlap hits with external search-stack hits.

    Honors DROPLIST_EXTERNAL_SEARCH env gate. When disabled, behaves exactly
    like retrieve(). External hits are appended after internal hits — internal
    memory always wins on ranking ties since it has lived context.
    """
    internal = retrieve(normalized, prior_packets, k=k)
    if not _external_search_enabled():
        return internal
    external = retrieve_external(normalized, kind=kind, k=k)
    seen_sources = {h["source"] for h in internal}
    merged = list(internal)
    for hit in external:
        if hit["source"] in seen_sources:
            continue
        merged.append(hit)
        seen_sources.add(hit["source"])
    return merged[:k * 2]
