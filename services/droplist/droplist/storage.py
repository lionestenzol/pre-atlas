"""Append-only JSONL storage. The raw log is the source of truth.

No updates, no deletes. State changes are expressed as new appended records.
Everything here is crash-safe enough for a single-writer CLI: open, write one
line, flush, close.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Iterator

DATA_DIR = os.environ.get("DROPLIST_DATA", "data")

# Real dag_ids are "DAG-" + 8 hex chars (dag_builder.py:180). GET /api/dag/{dag_id}
# is unauthenticated and Starlette's path-param regex ([^/]+) excludes "/" but not
# "\" — on Windows, os.path.join treats "\" as a separator too, so an unvalidated
# dag_id could traverse outside data/dags/ and read an arbitrary .json file.
# Single choke point: both /api/dag/{id} and /api/dag/{id}/checklist call load_dag.
# See ~/.claude/rules/common/code-as-furniture.md.
_DAG_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")

PACKETS = "packets.jsonl"
MINI_SHIPS = "mini_ships.jsonl"
LLM_CALLS = "llm_calls.jsonl"
RUN_LOG = "run_log.jsonl"
AGENT_RUNS = "agent_runs.jsonl"
REVIEWS = "reviews.jsonl"
DAG_EVENTS = "dag_events.jsonl"
TOOL_RUNS = "tool_runs.jsonl"
SCHEDULE_RUNS = "schedule_runs.jsonl"


def _path(filename: str) -> str:
    return os.path.join(DATA_DIR, filename)


def ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "memory_index"), exist_ok=True)


def append(filename: str, record: dict[str, Any]) -> None:
    """Append one JSON record as a single line."""
    ensure_data_dir()
    with open(_path(filename), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()


def read_all(filename: str) -> list[dict[str, Any]]:
    """Read every record. Skips malformed lines rather than crashing."""
    p = _path(filename)
    if not os.path.exists(p):
        return []
    out: list[dict[str, Any]] = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def iter_records(filename: str) -> Iterator[dict[str, Any]]:
    p = _path(filename)
    if not os.path.exists(p):
        return
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def read_with_errors(filename: str) -> tuple[list[dict[str, Any]], list[int]]:
    """Like read_all, but also returns the 1-indexed line numbers that failed
    to parse, so callers can report malformed lines instead of hiding them."""
    p = _path(filename)
    if not os.path.exists(p):
        return [], []
    records: list[dict[str, Any]] = []
    bad: list[int] = []
    with open(p, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                bad.append(i)
    return records, bad


def log_run(
    tool: str,
    command: str,
    goal: str = "",
    input_scope: str = "",
    result_summary: str = "",
    important_files: list[str] | None = None,
    decision: str = "",
    next_action: str = "",
    memory_update: str = "",
    status: str = "success",
) -> str:
    """Append one execution-memory record to run_log.jsonl. So no work
    evaporates: every command run leaves a reconstructable trace."""
    import time
    import uuid

    run_id = "run_" + uuid.uuid4().hex[:12]
    append(
        RUN_LOG,
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_id": run_id,
            "goal": goal,
            "tool": tool,
            "command": command,
            "input_scope": input_scope,
            "result_summary": result_summary,
            "important_files": important_files or [],
            "decision": decision,
            "next_action": next_action,
            "memory_update": memory_update,
            "status": status,
        },
    )
    return run_id


def save_dag(dag: dict) -> str:
    """Persist a DAG as JSON under data/dags/. Last write wins."""
    ensure_data_dir()
    d = os.path.join(DATA_DIR, "dags")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{dag['dag_id']}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(dag, f, ensure_ascii=False, indent=2)
    return p


def load_dag(dag_id: str) -> dict | None:
    if not _DAG_ID_RE.match(dag_id):
        return None
    p = os.path.join(DATA_DIR, "dags", f"{dag_id}.json")
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def results_dir() -> str:
    ensure_data_dir()
    d = os.path.join(DATA_DIR, "results")
    os.makedirs(d, exist_ok=True)
    return d
