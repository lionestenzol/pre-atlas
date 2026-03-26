"""Metering Module — SQLite-based AI usage tracking.

Tracks AI seconds consumed across all providers (Claude, Ollama).
Supports a free tier (default 3600s) and pause/resume.
"""
import sqlite3
import structlog
from datetime import datetime, timezone
from pathlib import Path

log = structlog.get_logger()


class MeteringStore:
    """SQLite-backed metering store for AI usage tracking."""

    def __init__(self, db_path: Path, free_tier_seconds: int = 3600):
        self.db_path = Path(db_path)
        self.free_tier_seconds = free_tier_seconds
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    ai_seconds REAL NOT NULL,
                    tokens_used INTEGER NOT NULL DEFAULT 0,
                    provider TEXT NOT NULL,
                    workflow_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metering_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            # Initialize paused state if not exists
            existing = conn.execute(
                "SELECT value FROM metering_config WHERE key = 'paused'"
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO metering_config (key, value) VALUES ('paused', 'false')"
                )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def record_usage(
        self,
        ai_seconds: float,
        tokens_used: int,
        provider: str,
        workflow_id: str = "",
    ):
        """Record an AI usage event."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO usage_log (timestamp, ai_seconds, tokens_used, provider, workflow_id) VALUES (?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), ai_seconds, tokens_used, provider, workflow_id),
            )
        log.info("metering.recorded", ai_seconds=ai_seconds, tokens=tokens_used, provider=provider)

    def get_usage(self) -> dict:
        """Get current usage summary."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(ai_seconds), 0), COALESCE(SUM(tokens_used), 0), COUNT(*) FROM usage_log"
            ).fetchone()
            total_seconds = row[0]
            total_tokens = row[1]
            total_events = row[2]

        return {
            "ai_seconds_used": round(total_seconds, 2),
            "free_tier_seconds": self.free_tier_seconds,
            "remaining_seconds": round(max(0, self.free_tier_seconds - total_seconds), 2),
            "total_tokens": total_tokens,
            "total_events": total_events,
            "paused": self.is_paused(),
            "over_limit": total_seconds >= self.free_tier_seconds,
        }

    def is_paused(self) -> bool:
        """Check if metering is paused."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM metering_config WHERE key = 'paused'"
            ).fetchone()
            return row is not None and row[0] == "true"

    def pause(self):
        """Pause AI processing."""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO metering_config (key, value) VALUES ('paused', 'true')"
            )
        log.info("metering.paused")

    def resume(self):
        """Resume AI processing."""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO metering_config (key, value) VALUES ('paused', 'false')"
            )
        log.info("metering.resumed")
