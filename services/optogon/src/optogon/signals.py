"""Signal emitter - builds Signal.v1 payloads to send to InPACT.

This module just builds payloads and logs them. Transport to delta-kernel's
/api/signals/ingest happens in Phase 3. Until then, signals are appended to
an in-memory list that /session endpoints can return for debugging.
"""
from __future__ import annotations
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .contract_validator import validate


_signals: list[dict[str, Any]] = []
_lock = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def emit(
    source_layer: str,
    signal_type: str,
    priority: str,
    label: str,
    summary: str,
    data: Optional[dict[str, Any]] = None,
    action_required: bool = False,
    action_options: Optional[list[dict[str, Any]]] = None,
    task_id: Optional[str] = None,
) -> dict[str, Any]:
    signal = {
        "schema_version": "1.0",
        "id": f"sig_{uuid.uuid4().hex[:12]}",
        "emitted_at": _now(),
        "source_layer": source_layer,
        "signal_type": signal_type,
        "priority": priority,
        "payload": {
            "task_id": task_id,
            "label": label,
            "summary": summary,
            "data": data or {},
            "action_required": action_required,
            "action_options": action_options or [],
        },
    }
    # Signal.v1 conditional: action_required=true requires non-empty action_options
    if not action_required:
        # Remove the empty array so it passes validation cleanly
        signal["payload"].pop("action_options", None)
    validate(signal, "Signal")
    with _lock:
        _signals.append(signal)
    return signal


def all_signals(since: Optional[str] = None) -> list[dict[str, Any]]:
    with _lock:
        if since is None:
            return list(_signals)
        return [s for s in _signals if s["emitted_at"] > since]


def clear() -> None:
    """Test helper."""
    with _lock:
        _signals.clear()
