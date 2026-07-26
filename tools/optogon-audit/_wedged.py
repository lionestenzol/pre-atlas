"""Helper for audit.ps1: query sessions.db for sessions stuck >N days.

Usage:
    python _wedged.py <path/to/sessions.db> <wedge_days>

Output: JSON array of {session_id, path_id, current_node, updated_at}
"""
from __future__ import annotations
import json
import sqlite3
import sys


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: _wedged.py <db_path> <wedge_days>", file=sys.stderr)
        return 2
    db_path, days_str = argv[1], argv[2]
    try:
        days = int(days_str)
    except ValueError:
        print(f"invalid wedge_days: {days_str!r}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT session_id, path_id, state_json, updated_at "
        "FROM sessions "
        "WHERE closed_at IS NULL "
        "  AND updated_at < datetime('now', ? || ' days') "
        "ORDER BY updated_at ASC",
        (f"-{days}",),
    ).fetchall()

    out: list[dict] = []
    for r in rows:
        try:
            st = json.loads(r["state_json"])
            cur = st.get("current_node")
        except Exception:
            cur = "<unparseable>"
        out.append({
            "session_id": r["session_id"],
            "path_id": r["path_id"],
            "updated_at": r["updated_at"],
            "current_node": cur,
        })
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
