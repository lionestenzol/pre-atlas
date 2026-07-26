"""Execution pipeline tracker.

Models the iteration + workflow_status structure seen in the thread's
final_output.md. Persists to disk so restarts don't wipe progress.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class ExecutionPipeline:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {
            "conversation_id": "AI_EXEC_001",
            "session_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "in_progress",
            "conversation_flow": [],
        }

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def state(self) -> dict[str, Any]:
        return self._state

    def record(self, step: str, status: str, note: str | None = None) -> None:
        iteration = len(self._state["conversation_flow"]) + 1
        self._state["conversation_flow"].append(
            {
                "iteration": iteration,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "step": step,
                "workflow_status": status,
                "note": note,
            }
        )
        if status not in {"completed", "in_progress"}:
            self._state["status"] = status
        self._save()
