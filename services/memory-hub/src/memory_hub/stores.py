"""Each function = one store. Each returns list[MemoryHit] or [] on any failure."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

from .schemas import MemoryHit, StoreStatus

PRE_ATLAS_ROOT = Path(__file__).resolve().parents[4]
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


def _overlap_score(q: set[str], target: set[str]) -> float:
    if not q or not target:
        return 0.0
    overlap = q & target
    if not overlap:
        return 0.0
    return round(len(overlap) / (len(q) ** 0.5 * len(target) ** 0.5), 3)


# ----- droplist -----

def search_droplist(query: str, k: int) -> list[MemoryHit]:
    if not DROPLIST_PACKETS.exists():
        return []
    q = _tokens(query)
    if not q:
        return []
    out: list[MemoryHit] = []
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
            relevance = _overlap_score(q, toks)
            if relevance == 0.0:
                continue
            out.append(
                MemoryHit(
                    source="droplist",
                    snippet=text[:300],
                    relevance=relevance,
                    type=p.get("type", ""),
                    domain=p.get("domain", ""),
                    canonical_id=p.get("drop_id", ""),
                    raw={"drop_id": p.get("drop_id")},
                )
            )
    except OSError:
        return []
    out.sort(key=lambda h: h.relevance, reverse=True)
    return out[:k]


# ----- idea registry -----
# Real shape: {metadata, execute_now: [...], next_up: [...]}. Both arrays contain
# canonical idea dicts. The OLD in-process search-stack provider was looking for
# data["ideas"] and missing everything — fixed here.

def search_idea_registry(query: str, k: int) -> list[MemoryHit]:
    if not IDEA_REGISTRY.exists():
        return []
    q = _tokens(query)
    if not q:
        return []
    try:
        data = json.loads(IDEA_REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    all_ideas: list[tuple[dict, str]] = []
    for bucket in ("execute_now", "next_up"):
        for idea in data.get(bucket, []) or []:
            if isinstance(idea, dict):
                all_ideas.append((idea, bucket))

    out: list[MemoryHit] = []
    for idea, bucket in all_ideas:
        text_blob = " ".join(
            str(idea.get(field, ""))
            for field in ("canonical_title", "canonical_id", "category")
        )
        toks = _tokens(text_blob)
        relevance = _overlap_score(q, toks)
        if relevance == 0.0:
            continue
        cid = idea.get("canonical_id", "")
        out.append(
            MemoryHit(
                source="idea_registry",
                snippet=str(idea.get("canonical_title") or cid)[:300],
                relevance=relevance,
                type=str(idea.get("category", "")),
                domain=bucket,  # 'execute_now' vs 'next_up'
                canonical_id=str(cid),
                raw={
                    "priority_score": idea.get("priority_score"),
                    "status": idea.get("status"),
                    "mention_count": idea.get("mention_count"),
                    "alignment_score": idea.get("alignment_score"),
                    "bucket": bucket,
                },
            )
        )
    out.sort(key=lambda h: h.relevance, reverse=True)
    return out[:k]


def lookup_idea(canonical_id: str) -> dict | None:
    if not IDEA_REGISTRY.exists():
        return None
    try:
        data = json.loads(IDEA_REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for bucket in ("execute_now", "next_up"):
        for idea in data.get(bucket, []) or []:
            if isinstance(idea, dict) and idea.get("canonical_id") == canonical_id:
                return {**idea, "_bucket": bucket}
    return None


# ----- cognitive-sensor atlas_query -----

async def search_atlas_query(query: str, k: int) -> list[MemoryHit]:
    if not ATLAS_QUERY.exists():
        return []
    # `--` end-of-options guard: not exploitable today (a leading "--root"/etc
    # takeover would leave the required `query` positional unfilled and argparse
    # errors -> empty result), but that safety is incidental to atlas_query.py's
    # current flag set, not deliberate. `query` is unauthenticated POST /search
    # input; guard it structurally rather than rely on argparse arity by accident.
    # See ~/.claude/rules/common/code-as-furniture.md.
    cmd = [sys.executable, str(ATLAS_QUERY), "search", "--limit", str(k), "--", query]
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
    entries = data if isinstance(data, list) else data.get("results", [])
    out: list[MemoryHit] = []
    for entry in entries[:k]:
        cluster_id = entry.get("id") or entry.get("cluster_id", "")
        score = float(entry.get("score") or entry.get("similarity") or 0.0)
        label = entry.get("label") or entry.get("title") or cluster_id
        out.append(
            MemoryHit(
                source="cognitive_sensor",
                snippet=f"{label} — {(entry.get('preview') or entry.get('summary') or '')[:240]}",
                relevance=score,
                type="cluster",
                domain="atlas",
                canonical_id=str(cluster_id),
                raw={"cluster_id": cluster_id},
            )
        )
    return out


# ----- graph neighbors (no backend) -----
# The graph store (mirofish / Neo4j) was retired 2026-07-06 (festival FA0001);
# its successor is cognitive-sensor, which is already a first-class source above.
# The /entity route is kept as a stable surface and returns [] until a graph
# backend is wired again.

async def graph_neighbors(entity: str, k: int = 10) -> list[MemoryHit]:
    """1-hop graph neighbors for a topic/entity name. No graph backend since the
    mirofish/Neo4j store was retired — returns [] until one is re-wired."""
    return []


# ----- status -----

def store_status() -> list[StoreStatus]:
    statuses = [
        StoreStatus(
            name="droplist",
            available=DROPLIST_PACKETS.exists(),
            note=f"packets at {DROPLIST_PACKETS}" if DROPLIST_PACKETS.exists() else "no packets.jsonl",
        ),
        StoreStatus(
            name="idea_registry",
            available=IDEA_REGISTRY.exists(),
            note=f"file at {IDEA_REGISTRY}" if IDEA_REGISTRY.exists() else "missing",
        ),
        StoreStatus(
            name="cognitive_sensor",
            available=ATLAS_QUERY.exists(),
            note=f"atlas_query.py at {ATLAS_QUERY}" if ATLAS_QUERY.exists() else "missing",
        ),
    ]
    return statuses


# ----- save (back to DropList) -----

def append_to_droplist(packet_type: str, content: str, source: str, metadata: dict | None = None) -> dict:
    """Append a new packet line to droplist/data/packets.jsonl. Returns the
    persisted record (with timestamp + drop_id) for the caller's reference."""
    import time
    import uuid

    DROPLIST_PACKETS.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "drop_id": f"drop_{uuid.uuid4().hex[:12]}",
        "type": packet_type,
        "source": source,
        "normalized_input": content,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metadata": metadata or {},
        "status": "intel_drop",
    }
    with DROPLIST_PACKETS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return record
