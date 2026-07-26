"""FastAPI REST surface on port 3070."""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import budget, registry, router
from .providers.base import BudgetSnapshot, ExtractResult
from .settings import settings

app = FastAPI(title="search-stack", version="0.1.0")

# /memory/save's `drop_to` override must stay inside the local Atlas service mesh.
# This route has no auth, so an unvalidated `drop_to` is a full SSRF + response-
# reflection primitive (POST any body to any URL, read the response back) — found
# in this session's injection sweep. Restrict to loopback + the configured
# intake host, matching the same allowlist pattern applied to cortex's api_call
# handler in the same sweep. See ~/.claude/rules/common/code-as-furniture.md.
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1"}


def _is_allowed_drop_target(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    if parsed.hostname in _LOOPBACK_HOSTS:
        return True
    configured = urlparse(settings.droplist_intake_url) if settings.droplist_intake_url else None
    return bool(configured and configured.hostname and parsed.hostname == configured.hostname)


class SearchRequest(BaseModel):
    q: str = Field(..., min_length=1)
    kind: Optional[str] = None
    max_results: int = Field(10, ge=1, le=50)
    providers: Optional[list[str]] = None
    force_fresh: bool = False


class ExtractRequest(BaseModel):
    url: str
    mode: str = "markdown"


class MemorySaveRequest(BaseModel):
    result: dict
    drop_to: Optional[str] = None


@app.get("/healthz")
async def healthz() -> dict:
    provs = registry.all_search_providers()
    extracts = registry.extract_providers()
    return {
        "status": "ok",
        "search_providers": [
            {"name": p.name, "enabled": p.enabled, "last_error": p.last_error}
            for p in provs.values()
        ],
        "extract_providers": [
            {"name": p.name, "enabled": p.enabled, "last_error": p.last_error}
            for p in extracts
        ],
    }


@app.post("/search")
async def search(req: SearchRequest) -> dict:
    return await router.search(
        query=req.q,
        kind=req.kind,
        max_results=req.max_results,
        providers=req.providers,
        force_fresh=req.force_fresh,
    )


@app.post("/extract", response_model=ExtractResult)
async def extract(req: ExtractRequest) -> ExtractResult:
    try:
        return await router.extract(req.url, req.mode)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/budget", response_model=list[BudgetSnapshot])
async def get_budget() -> list[BudgetSnapshot]:
    return budget.all_snapshots(registry.PROVIDER_QUOTAS)


@app.post("/memory/save")
async def memory_save(req: MemorySaveRequest) -> dict:
    target = req.drop_to or settings.droplist_intake_url
    if not target:
        raise HTTPException(
            status_code=400,
            detail="no drop_to URL provided and DROPLIST_INTAKE_URL not configured",
        )
    if not _is_allowed_drop_target(target):
        raise HTTPException(status_code=400, detail=f"drop_to target not in allowlist: {target}")
    payload = {
        "type": "intel_drop",
        "source": "search-stack",
        "result": req.result,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(target, json=payload)
        resp.raise_for_status()
        return {"status": "saved", "target": target, "response": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text}


def run() -> None:
    uvicorn.run(
        "search_stack.server:app",
        host=settings.search_stack_host,
        port=settings.search_stack_port,
        log_level="info",
    )


if __name__ == "__main__":
    run()
