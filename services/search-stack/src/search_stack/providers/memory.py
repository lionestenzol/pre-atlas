"""Memory provider — talks to services/memory-hub on :3071 first; in-process
fallback when memory-hub isn't running.

Wraps existing tools (no re-implementation):
  - memory-hub REST (preferred) — unified surface over droplist, atlas_query,
    idea_registry
  - droplist packets.jsonl direct (fallback) — token-overlap on normalized_input

The HTTP path is the primary route — it gives Phase 3 a clean seam where
adding new stores (embedding-based retrieval, etc.) requires no change to
search-stack. memory.py stays a 1-page wrapper.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from .base import SearchProvider, SearchResult

PRE_ATLAS_ROOT = Path(__file__).resolve().parents[5]
DROPLIST_PACKETS = PRE_ATLAS_ROOT / "services" / "droplist" / "data" / "packets.jsonl"
DEFAULT_MEMORY_HUB_URL = "http://127.0.0.1:3071/search"

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "is",
    "it", "this", "that", "with", "was", "were", "be", "are", "as", "at", "by",
    "i", "my", "we", "so", "if", "not", "no", "do", "did", "too", "than",
}


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 2}


def _memory_hub_url() -> str:
    return os.environ.get("MEMORY_HUB_URL", DEFAULT_MEMORY_HUB_URL)


class MemoryProvider(SearchProvider):
    name = "memory"
    kind_default = "memory"

    def _check_enabled(self) -> bool:
        return DROPLIST_PACKETS.exists() or self._memory_hub_reachable()

    @staticmethod
    def _memory_hub_reachable() -> bool:
        try:
            urllib.request.urlopen(
                _memory_hub_url().rsplit("/", 1)[0] + "/healthz", timeout=1.0
            )
            return True
        except OSError:
            return False

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        hub_hits = self._via_memory_hub(query, max_results)
        if hub_hits is not None:
            return hub_hits
        return self._via_droplist_fallback(query, max_results)

    def _via_memory_hub(self, query: str, max_results: int) -> list[SearchResult] | None:
        """Returns None if memory-hub is unreachable; results otherwise."""
        payload = {"q": query, "max_results": max_results}
        req = urllib.request.Request(
            _memory_hub_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                body = resp.read().decode("utf-8")
        except (urllib.error.URLError, OSError):
            return None
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return None
        out: list[SearchResult] = []
        for hit in data.get("results", []):
            cid = hit.get("canonical_id") or hit.get("snippet", "")[:60]
            url = self._url_for(hit.get("source", ""), cid)
            out.append(
                SearchResult(
                    title=hit.get("snippet", "")[:200],
                    url=url,
                    snippet=hit.get("snippet", ""),
                    score=float(hit.get("relevance") or 0.0),
                    source=hit.get("source", "memory-hub"),
                    kind="memory",
                    raw=hit.get("raw") or {},
                )
            )
        return out

    @staticmethod
    def _url_for(source: str, cid: str) -> str:
        if source == "droplist":
            return f"droplist://{cid}"
        if source == "idea_registry":
            return f"idea://{cid}"
        if source == "cognitive_sensor":
            return f"atlas://cluster/{cid}"
        return f"memory://{cid}"

    def _via_droplist_fallback(self, query: str, max_results: int) -> list[SearchResult]:
        if not DROPLIST_PACKETS.exists():
            return []
        q = _tokens(query)
        if not q:
            return []
        out: list[SearchResult] = []
        try:
            for line in DROPLIST_PACKETS.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    p = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = p.get("normalized_input", "")
                toks = _tokens(text)
                if not toks:
                    continue
                overlap = q & toks
                if not overlap:
                    continue
                relevance = len(overlap) / (len(q) ** 0.5 * len(toks) ** 0.5)
                out.append(
                    SearchResult(
                        title=p.get("drop_id", "drop"),
                        url=f"droplist://{p.get('drop_id', 'unknown')}",
                        snippet=text[:300],
                        score=round(relevance, 3),
                        source="droplist-fallback",
                        kind="memory",
                        raw={"type": p.get("type"), "domain": p.get("domain")},
                    )
                )
        except OSError:
            return []
        out.sort(key=lambda r: r.score, reverse=True)
        return out[:max_results]
