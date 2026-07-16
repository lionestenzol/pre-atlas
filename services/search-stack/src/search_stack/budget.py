"""Per-provider quota tracking in SQLite.

Schema:
    provider TEXT, month TEXT (YYYY-MM), count INTEGER, quota INTEGER, blocked_at REAL
    PRIMARY KEY (provider, month)
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .providers.base import BudgetSnapshot
from .settings import DATA_DIR, settings

DB_PATH = DATA_DIR / "budget.db"


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


@contextmanager
def _conn():
    con = sqlite3.connect(str(DB_PATH))
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS budget (
            provider TEXT NOT NULL,
            month TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            quota INTEGER NOT NULL,
            blocked_at REAL,
            PRIMARY KEY (provider, month)
        )
        """
    )
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _ensure_row(con: sqlite3.Connection, provider: str, quota: int) -> None:
    month = _current_month()
    con.execute(
        "INSERT OR IGNORE INTO budget (provider, month, count, quota) VALUES (?, ?, 0, ?)",
        (provider, month, quota),
    )


def consume(provider: str, quota: int, count: int = 1) -> bool:
    """Increment provider count. Returns False if at/over block threshold."""
    block_pct = settings.search_stack_budget_block
    month = _current_month()
    with _conn() as con:
        _ensure_row(con, provider, quota)
        cur = con.execute(
            "SELECT count, blocked_at FROM budget WHERE provider=? AND month=?",
            (provider, month),
        )
        row = cur.fetchone()
        used, blocked_at = row
        if blocked_at is not None:
            return False
        new_used = used + count
        block_at = int(quota * block_pct / 100)
        if new_used >= block_at:
            con.execute(
                "UPDATE budget SET count=?, blocked_at=? WHERE provider=? AND month=?",
                (new_used, time.time(), provider, month),
            )
            return False
        con.execute(
            "UPDATE budget SET count=? WHERE provider=? AND month=?",
            (new_used, provider, month),
        )
        return True


def snapshot(provider: str, quota: int) -> BudgetSnapshot:
    month = _current_month()
    with _conn() as con:
        _ensure_row(con, provider, quota)
        cur = con.execute(
            "SELECT count, blocked_at FROM budget WHERE provider=? AND month=?",
            (provider, month),
        )
        used, blocked_at = cur.fetchone()
    pct = (used / quota * 100) if quota else 0.0
    return BudgetSnapshot(
        provider=provider,
        month=month,
        used=used,
        quota=quota,
        percent=round(pct, 1),
        blocked=blocked_at is not None,
    )


def all_snapshots(provider_quotas: dict[str, int]) -> list[BudgetSnapshot]:
    return [snapshot(p, q) for p, q in provider_quotas.items()]
