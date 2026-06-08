"""Shared provider contract: Pydantic schemas + abstract base."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    score: float = 0.0
    source: str
    kind: Literal["web", "extract", "code", "github", "file", "memory"] = "web"
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw: dict[str, Any] = Field(default_factory=dict)


class ExtractResult(BaseModel):
    url: str
    content: str
    mode: Literal["clean", "markdown", "raw"] = "markdown"
    source: str
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw: dict[str, Any] = Field(default_factory=dict)


class BudgetSnapshot(BaseModel):
    provider: str
    month: str
    used: int
    quota: int
    percent: float
    blocked: bool


class SearchProvider(ABC):
    """Each provider wraps one vendor. Missing key → DISABLED, never raises."""

    name: str
    kind_default: str = "web"

    def __init__(self) -> None:
        self.enabled: bool = self._check_enabled()
        self.last_error: str | None = None

    def _check_enabled(self) -> bool:
        return True

    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        ...


class ExtractProvider(ABC):
    name: str

    def __init__(self) -> None:
        self.enabled: bool = self._check_enabled()
        self.last_error: str | None = None

    def _check_enabled(self) -> bool:
        return True

    @abstractmethod
    async def extract(self, url: str, mode: str = "markdown") -> ExtractResult:
        ...
