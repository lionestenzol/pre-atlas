"""Persistent OS state: recurring nodes, the do-not-reopen lock, and the
cross-DAG/state index. All file-backed under data/state/.
"""

from __future__ import annotations

import json
import os
import uuid

from . import clock, storage


def _state_dir() -> str:
    storage.ensure_data_dir()
    d = os.path.join(storage.DATA_DIR, "state")
    os.makedirs(d, exist_ok=True)
    return d


def _load(name: str, default):
    p = os.path.join(_state_dir(), name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _save(name: str, data) -> None:
    with open(os.path.join(_state_dir(), name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---- recurring nodes -------------------------------------------------------

_REC = "recurring_nodes.json"


def add_recurring(title, domain, recurrence="daily", time_window="morning",
                  creates_node_type="field_check", done_condition="",
                  entity_refs=None, tool_type="", tool_action="") -> dict:
    items = _load(_REC, [])
    rn = {
        "id": "RN-" + uuid.uuid4().hex[:6],
        "title": title, "domain": domain, "recurrence": recurrence,
        "time_window": time_window, "creates_node_type": creates_node_type,
        "done_condition": done_condition or f"{title} logged",
        "entity_refs": entity_refs or [], "tool_type": tool_type,
        "tool_action": tool_action, "status": "scheduled",
        "last_materialized": "",
    }
    items.append(rn)
    _save(_REC, items)
    return rn


def list_recurring() -> list[dict]:
    return _load(_REC, [])


def _mark_materialized(rn_id: str, day: str) -> None:
    items = _load(_REC, [])
    for r in items:
        if r["id"] == rn_id:
            r["last_materialized"] = day
    _save(_REC, items)


def due_recurring() -> list[dict]:
    """Recurring nodes that haven't been materialized for the current day."""
    day = clock.today()
    return [r for r in _load(_REC, []) if r.get("last_materialized") != day]


# ---- do-not-reopen lock ----------------------------------------------------

_DNR = "do_not_reopen.json"


def lock_ref(ref: str, reason: str = "") -> None:
    locks = _load(_DNR, {})
    locks[ref] = {"reason": reason or "marked done; do not reopen",
                  "locked_at": clock.now_iso()}
    _save(_DNR, locks)


def locked_refs() -> dict:
    return _load(_DNR, {})


def is_locked(ref: str) -> bool:
    return ref in _load(_DNR, {})
