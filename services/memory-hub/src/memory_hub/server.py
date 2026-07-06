"""FastAPI surface for memory-hub — port 3071."""

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import stores
from .schemas import (
    MemoryHit,
    MemorySearchRequest,
    MemorySearchResponse,
    SavePacketRequest,
    StoreStatus,
)

app = FastAPI(title="memory-hub", version="0.1.0")

# Same allowlist pattern as droplist/server.py -- no callers used this from a
# browser before lattice's search box, so CORS was never configured.
# See ~/.claude/rules/common/code-as-furniture.md -- open gap fixed inline.
_DEFAULT_ORIGINS = ["http://localhost:3011", "http://127.0.0.1:3011"]
_ENV_ORIGINS = [
    o.strip() for o in os.environ.get("MEMORY_HUB_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEFAULT_ORIGINS + _ENV_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Map source-name → callable that returns list[MemoryHit].
# Wrapped at request time so we can pass query + k.
ALL_SOURCES = {"droplist", "idea_registry", "cognitive_sensor"}


@app.get("/healthz", response_model=list[StoreStatus])
async def healthz() -> list[StoreStatus]:
    return stores.store_status()


@app.post("/search", response_model=MemorySearchResponse)
async def search(req: MemorySearchRequest) -> MemorySearchResponse:
    requested = set(req.sources) if req.sources else ALL_SOURCES
    used: list[str] = []
    failed: list[dict] = []
    all_hits: list[MemoryHit] = []

    if "droplist" in requested:
        try:
            hits = stores.search_droplist(req.q, req.max_results)
            all_hits.extend(hits)
            used.append("droplist")
        except Exception as exc:
            failed.append({"source": "droplist", "error": str(exc)[:200]})

    if "idea_registry" in requested:
        try:
            hits = stores.search_idea_registry(req.q, req.max_results)
            all_hits.extend(hits)
            used.append("idea_registry")
        except Exception as exc:
            failed.append({"source": "idea_registry", "error": str(exc)[:200]})

    if "cognitive_sensor" in requested:
        try:
            hits = await stores.search_atlas_query(req.q, req.max_results)
            all_hits.extend(hits)
            used.append("cognitive_sensor")
        except Exception as exc:
            failed.append({"source": "cognitive_sensor", "error": str(exc)[:200]})

    # Dedup by canonical_id (favor higher relevance)
    seen: dict[str, MemoryHit] = {}
    for h in all_hits:
        key = h.canonical_id or h.snippet[:80]
        if key not in seen or seen[key].relevance < h.relevance:
            seen[key] = h
    merged = sorted(seen.values(), key=lambda h: h.relevance, reverse=True)
    top = merged[: req.max_results]

    return MemorySearchResponse(
        query=req.q,
        results=top,
        sources_used=used,
        sources_failed=failed,
        n=len(top),
    )


@app.get("/idea/{canonical_id}")
async def get_idea(canonical_id: str) -> dict:
    idea = stores.lookup_idea(canonical_id)
    if idea is None:
        raise HTTPException(status_code=404, detail=f"idea {canonical_id} not in registry")
    return idea


@app.get("/entity/{name}", response_model=list[MemoryHit])
async def graph_entity(name: str, max_results: int = 10) -> list[MemoryHit]:
    return await stores.graph_neighbors(name, k=max_results)


@app.post("/save")
async def save(req: SavePacketRequest) -> dict:
    try:
        record = stores.append_to_droplist(
            packet_type=req.type,
            content=req.content,
            source=req.source,
            metadata=req.metadata,
        )
        return {"status": "saved", "record": record}
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"failed to persist: {exc}")


def run() -> None:
    uvicorn.run(
        "memory_hub.server:app",
        host="127.0.0.1",
        port=3071,
        log_level="info",
    )


if __name__ == "__main__":
    run()
