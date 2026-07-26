"""Daily Command Brief: the user-facing MVP 4 surface.

Reads ALL persistent DAGs + entities + recurring + locks and answers:
ready now / blocked / waiting / recurring / overdue / next best / do-not-reopen.
"""

from __future__ import annotations

import os

from . import clock, state, storage

_UNRESOLVED = {"ready", "waiting"}


def _all_dags() -> list[dict]:
    d = os.path.join(storage.DATA_DIR, "dags")
    out = []
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".json"):
                dg = storage.load_dag(fn[:-5])
                if dg:
                    out.append(dg)
    return out


def _row(dag, n):
    return {"dag": dag["dag_id"], "node": n["id"], "title": n["title"],
            "domain": n.get("domain", dag.get("domain", "?")),
            "project": n.get("project", dag.get("project", "")),
            "priority": n.get("priority_score", 50),
            "tool": n.get("tool_type", ""),
            "age_hours": round(clock.hours_since(dag.get("updated_at",
                               dag.get("created_at", ""))), 1)}


def build_brief() -> dict:
    dags = _all_dags()
    ready, blocked, waiting, overdue = [], [], [], []
    for dag in dags:
        for n in dag["nodes"]:
            r = _row(dag, n)
            if n["status"] == "ready":
                ready.append(r)
                if r["age_hours"] > n.get("stale_after_hours", 24):
                    overdue.append(r)
            elif n["status"] == "blocked":
                blocked.append(r)
            elif n["status"] == "waiting":
                waiting.append(r)
                if r["age_hours"] > n.get("stale_after_hours", 24):
                    overdue.append(r)

    ready.sort(key=lambda x: -x["priority"])
    next_best = ready[0] if ready else None

    return {
        "day": clock.today(),
        "ready": ready,
        "blocked": blocked,
        "waiting": waiting,
        "overdue": overdue,
        "recurring": state.list_recurring(),
        "do_not_reopen": state.locked_refs(),
        "next_best": next_best,
        "totals": {"dags": len(dags), "ready": len(ready),
                   "blocked": len(blocked), "waiting": len(waiting)},
    }
