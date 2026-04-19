"""Session store - SQLite-backed persistence of OptogonSessionState.

In-memory cache in front for hot sessions. Validates against
OptogonSessionState.v1.json on every write.
"""
from __future__ import annotations
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .config import DB_PATH, ensure_dirs
from .contract_validator import validate
from .context import empty_context
from .preferences_client import fetch_preferences, inject_preferences_into_context


_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    path_id    TEXT NOT NULL,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    closed_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_path_id ON sessions(path_id);
CREATE INDEX IF NOT EXISTS idx_sessions_closed_at ON sessions(closed_at);
"""


class SessionStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        ensure_dirs()
        self._db_path = str(db_path or DB_PATH)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_DDL)
        self._conn.commit()
        self._cache: dict[str, dict[str, Any]] = {}

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def create(self, path_id: str, initial_context: Optional[dict[str, Any]] = None, entry_node_id: str = "entry") -> dict[str, Any]:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        ctx = empty_context()
        # Load cross-session preferences FIRST (low tiers)
        try:
            prefs = fetch_preferences()
            inject_preferences_into_context(ctx, prefs)
        except Exception:
            # Never let preference loading fail session creation
            pass
        if initial_context:
            # Callers seed 'user' tier; overrides inferred prefs
            for key, val in initial_context.items():
                ctx["user"][key] = val
        state = {
            "schema_version": "1.0",
            "session_id": session_id,
            "path_id": path_id,
            "current_node": entry_node_id,
            "started_at": self._now(),
            "node_states": {entry_node_id: {"status": "unqualified", "entered_at": self._now(), "closed_at": None, "attempts": 0, "qualification_data": {}, "action_results": {}, "errors": []}},
            "context": ctx,
            "fork_stack": [],
            "action_log": [],
            "metrics": {
                "total_tokens": 0,
                "total_questions_asked": 0,
                "total_inferences_made": 0,
                "total_actions_fired": 0,
                "nodes_closed": 0,
                "nodes_total": 0,
            },
        }
        validate(state, "OptogonSessionState")
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions (session_id, path_id, state_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, path_id, json.dumps(state), self._now(), self._now()),
            )
            self._conn.commit()
            self._cache[session_id] = state
        return state

    def get(self, session_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            if session_id in self._cache:
                return self._cache[session_id]
            row = self._conn.execute(
                "SELECT state_json FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            state = json.loads(row["state_json"])
            self._cache[session_id] = state
            return state

    def update(self, state: dict[str, Any]) -> dict[str, Any]:
        validate(state, "OptogonSessionState")
        session_id = state["session_id"]
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET state_json = ?, updated_at = ? WHERE session_id = ?",
                (json.dumps(state), self._now(), session_id),
            )
            self._conn.commit()
            self._cache[session_id] = state
        return state

    def close(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET closed_at = ? WHERE session_id = ?",
                (self._now(), session_id),
            )
            self._conn.commit()
            # Keep in cache briefly; caller will stop touching it

    def list_active(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT state_json FROM sessions WHERE closed_at IS NULL ORDER BY updated_at DESC"
            ).fetchall()
        return [json.loads(r["state_json"]) for r in rows]


# Module-level singleton (main.py wires this)
_default_store: Optional[SessionStore] = None


def get_store() -> SessionStore:
    global _default_store
    if _default_store is None:
        _default_store = SessionStore()
    return _default_store
