"""Retrieval: pull the 3-5 most relevant prior packets from local memory.

MVP uses token-overlap scoring (no embeddings, no deps). The interface returns
the snippet shape specified in the spec so a vector backend can be swapped in
later without changing callers.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9]+")
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
