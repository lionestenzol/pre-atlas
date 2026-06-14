"""Pydantic schemas — what callers see."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class MemoryHit(BaseModel):
    source: str
    snippet: str
    relevance: float
    type: str = ""
    domain: str = ""
    canonical_id: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class MemorySearchRequest(BaseModel):
    q: str = Field(..., min_length=1)
    max_results: int = Field(10, ge=1, le=50)
    sources: list[str] | None = None  # None → all enabled


class MemorySearchResponse(BaseModel):
    query: str
    results: list[MemoryHit]
    sources_used: list[str]
    sources_failed: list[dict]
    n: int
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SavePacketRequest(BaseModel):
    type: str
    content: str = Field(..., min_length=1)
    source: str = "memory-hub"
    metadata: dict[str, Any] = Field(default_factory=dict)


class StoreStatus(BaseModel):
    name: str
    available: bool
    note: str = ""
