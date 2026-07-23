"""SQLite TTL cache for search results.

Key = SHA256 of (provider, kind, query, max_results). Value = JSON list of SearchResult.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager

from .settings import DATA_DIR, settings

DB_PATH = DATA_DIR / "cache.db"


@contextmanager
def _conn():
    con = sqlite3.connect(str(DB_PATH))
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            stored_at REAL NOT NULL,
            ttl INTEGER NOT NULL
        )
        """
    )
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _hash_key(provider: str, kind: str, query: str, max_results: int) -> str:
    raw = f"{provider}|{kind}|{query}|{max_results}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def get(provider: str, kind: str, query: str, max_results: int) -> list[dict] | None:
    key = _hash_key(provider, kind, query, max_results)
    with _conn() as con:
        cur = con.execute(
            "SELECT value, stored_at, ttl FROM cache WHERE key=?", (key,)
        )
        row = cur.fetchone()
        if not row:
            return None
        value, stored_at, ttl = row
        if time.time() - stored_at > ttl:
            con.execute("DELETE FROM cache WHERE key=?", (key,))
            return None
        return json.loads(value)


def put(
    provider: str,
    kind: str,
    query: str,
    max_results: int,
    value: list[dict],
    ttl: int | None = None,
) -> None:
    key = _hash_key(provider, kind, query, max_results)
    effective_ttl = ttl if ttl is not None else settings.search_stack_cache_ttl
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO cache (key, value, stored_at, ttl) VALUES (?, ?, ?, ?)",
            (key, json.dumps(value), time.time(), effective_ttl),
        )


def clear() -> int:
    with _conn() as con:
        cur = con.execute("DELETE FROM cache")
        return cur.rowcount
