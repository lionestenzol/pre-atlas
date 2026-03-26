"""SQLite store for simulation persistence."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from mirofish.config import config


class SimulationStore:
    """SQLite-backed storage for simulation runs and tick data."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or config.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_tables(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS simulations (
                simulation_id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                agent_count INTEGER NOT NULL,
                tick_count INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                duration_seconds REAL,
                error_message TEXT,
                agents_json TEXT,
                report_json TEXT
            );

            CREATE TABLE IF NOT EXISTS ticks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                simulation_id TEXT NOT NULL,
                tick_number INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                messages_json TEXT NOT NULL,
                FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id)
            );

            CREATE INDEX IF NOT EXISTS idx_ticks_sim ON ticks(simulation_id, tick_number);
        """)
        conn.commit()

    def create_simulation(
        self, simulation_id: str, topic: str, agent_count: int, tick_count: int, agents: list[dict]
    ):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO simulations (simulation_id, topic, agent_count, tick_count, status, created_at, agents_json) "
            "VALUES (?, ?, ?, ?, 'pending', ?, ?)",
            (simulation_id, topic, agent_count, tick_count,
             datetime.now(timezone.utc).isoformat(), json.dumps(agents)),
        )
        conn.commit()

    def start_simulation(self, simulation_id: str):
        conn = self._get_conn()
        conn.execute(
            "UPDATE simulations SET status='running', started_at=? WHERE simulation_id=?",
            (datetime.now(timezone.utc).isoformat(), simulation_id),
        )
        conn.commit()

    def save_tick(self, simulation_id: str, tick_number: int, messages: list[dict]):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO ticks (simulation_id, tick_number, timestamp, messages_json) VALUES (?, ?, ?, ?)",
            (simulation_id, tick_number, datetime.now(timezone.utc).isoformat(), json.dumps(messages)),
        )
        conn.commit()

    def complete_simulation(self, simulation_id: str, duration_seconds: float):
        conn = self._get_conn()
        conn.execute(
            "UPDATE simulations SET status='completed', completed_at=?, duration_seconds=? WHERE simulation_id=?",
            (datetime.now(timezone.utc).isoformat(), duration_seconds, simulation_id),
        )
        conn.commit()

    def fail_simulation(self, simulation_id: str, error: str):
        conn = self._get_conn()
        conn.execute(
            "UPDATE simulations SET status='failed', completed_at=?, error_message=? WHERE simulation_id=?",
            (datetime.now(timezone.utc).isoformat(), error, simulation_id),
        )
        conn.commit()

    def save_report(self, simulation_id: str, report: dict):
        conn = self._get_conn()
        conn.execute(
            "UPDATE simulations SET report_json=? WHERE simulation_id=?",
            (json.dumps(report), simulation_id),
        )
        conn.commit()

    def get_simulation(self, simulation_id: str) -> dict | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM simulations WHERE simulation_id=?", (simulation_id,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["agents"] = json.loads(result.pop("agents_json") or "[]")
        report_json = result.pop("report_json")
        result["report"] = json.loads(report_json) if report_json else None
        return result

    def get_ticks(self, simulation_id: str, from_tick: int = 0) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT tick_number, timestamp, messages_json FROM ticks "
            "WHERE simulation_id=? AND tick_number >= ? ORDER BY tick_number",
            (simulation_id, from_tick),
        ).fetchall()
        results = []
        for row in rows:
            results.append({
                "tick_number": row["tick_number"],
                "timestamp": row["timestamp"],
                "messages": json.loads(row["messages_json"]),
            })
        return results

    def list_simulations(self) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT simulation_id, topic, agent_count, tick_count, status, created_at, duration_seconds "
            "FROM simulations ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def delete_simulation(self, simulation_id: str):
        conn = self._get_conn()
        conn.execute("DELETE FROM ticks WHERE simulation_id=?", (simulation_id,))
        conn.execute("DELETE FROM simulations WHERE simulation_id=?", (simulation_id,))
        conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
