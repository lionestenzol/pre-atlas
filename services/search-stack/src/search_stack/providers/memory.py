"""Memory provider — searches DropList packets + cognitive-sensor embeddings.

Wraps existing tools rather than re-implementing:
- droplist packets.jsonl via token-overlap (mirrors droplist/retrieval.py)
- cognitive-sensor atlas_query.py via subprocess (its --json mode)

If a store is unavailable (file missing, atlas_query not runnable), that source
returns 0 results — provider stays enabled as long as ANY source is reachable.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sys
from pathlib import Path

from .base import SearchProvider, SearchResult

PRE_ATLAS_ROOT = Path(__file__).resolve().parents[5]
DROPLIST_PACKETS = PRE_ATLAS_ROOT / "services" / "droplist" / "data" / "packets.jsonl"
ATLAS_QUERY = PRE_ATLAS_ROOT / "services" / "cognitive-sensor" / "atlas_query.py"
IDEA_REGISTRY = PRE_ATLAS_ROOT / "services" / "cognitive-sensor" / "cycleboard" / "brain" / "idea_registry.json"

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "is",
    "it", "this", "that", "with", "was", "were", "be", "are", "as", "at", "by",
    "i", "my", "we", "so", "if", "not", "no", "do", "did", "too", "than",
}


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 2}


class MemoryProvider(SearchProvider):
    name = "memory"
    kind_default = "memory"

    def _check_enabled(self) -> bool:
        return DROPLIST_PACKETS.exists() or ATLAS_QUERY.exists() or IDEA_REGISTRY.exists()

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        results: list[SearchResult] = []
        results.extend(self._search_droplist(query, max_results))
        results.extend(await self._search_atlas(query, max_results))
        results.extend(self._search_idea_registry(query, max_results))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:max_results]

    def _search_droplist(self, query: str, k: int) -> list[SearchResult]:
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
                        source="droplist",
                        kind="memory",
                        raw={"type": p.get("type"), "domain": p.get("domain")},
                    )
                )
        except OSError:
            return []
        out.sort(key=lambda r: r.score, reverse=True)
        return out[:k]

    async def _search_atlas(self, query: str, k: int) -> list[SearchResult]:
        if not ATLAS_QUERY.exists() or not shutil.which(sys.executable):
            return []
        cmd = [sys.executable, str(ATLAS_QUERY), "search", query, "--limit", str(k)]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(ATLAS_QUERY.parent),
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15.0)
        except (OSError, asyncio.TimeoutError):
            return []
        if proc.returncode != 0:
            return []
        try:
            data = json.loads(stdout.decode("utf-8") or "[]")
        except json.JSONDecodeError:
            return []
        out: list[SearchResult] = []
        entries = data if isinstance(data, list) else data.get("results", [])
        for entry in entries[:k]:
            cluster_id = entry.get("id") or entry.get("cluster_id", "")
            score = float(entry.get("score") or entry.get("similarity") or 0.0)
            label = entry.get("label") or entry.get("title") or cluster_id
            out.append(
                SearchResult(
                    title=f"cluster:{cluster_id} {label}",
                    url=f"atlas://cluster/{cluster_id}",
                    snippet=(entry.get("preview") or entry.get("summary") or "")[:300],
                    score=score,
                    source="cognitive-sensor",
                    kind="memory",
                    raw={"cluster_id": cluster_id},
                )
            )
        return out

    def _search_idea_registry(self, query: str, k: int) -> list[SearchResult]:
        if not IDEA_REGISTRY.exists():
            return []
        q = _tokens(query)
        if not q:
            return []
        try:
            data = json.loads(IDEA_REGISTRY.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        ideas = data if isinstance(data, list) else data.get("ideas", [])
        out: list[SearchResult] = []
        for idea in ideas:
            if not isinstance(idea, dict):
                continue
            text_fields = " ".join(
                str(idea.get(k_, "")) for k_ in ("title", "name", "description", "summary", "canon_id")
            )
            toks = _tokens(text_fields)
            if not toks:
                continue
            overlap = q & toks
            if not overlap:
                continue
            relevance = len(overlap) / (len(q) ** 0.5 * len(toks) ** 0.5)
            idea_id = idea.get("canon_id") or idea.get("id") or idea.get("name", "idea")
            title = idea.get("title") or idea.get("name") or idea_id
            out.append(
                SearchResult(
                    title=str(title),
                    url=f"idea://{idea_id}",
                    snippet=str(idea.get("description") or idea.get("summary") or "")[:300],
                    score=round(relevance, 3),
                    source="idea-registry",
                    kind="memory",
                    raw={"canon_id": str(idea_id)},
                )
            )
        out.sort(key=lambda r: r.score, reverse=True)
        return out[:k]
