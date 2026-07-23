"""Watcher: the thing that makes the OS feel alive without fake autonomy.

On each tick it:
  - materializes any recurring node that's due today (one per day)
  - flags `waiting`/`ready` nodes that have gone stale (> stale_after_hours)
  - flags nodes that failed (escalation)
Returns a report; performs only the safe action of materializing recurring work.
"""

from __future__ import annotations

import uuid

from . import clock, dag_builder, entities, state, storage


def _materialize_recurring() -> list[dict]:
    made = []
    for rn in state.due_recurring():
        node = dag_builder._node(  # reuse the node constructor
            "N1", rn["title"], rn["creates_node_type"], "ops",
            tool_type=rn.get("tool_type", ""), tool_action=rn.get("tool_action", ""),
            done_condition=rn["done_condition"])
        node["domain"] = rn["domain"]
        node["recurs"] = True
        node["created_from"] = f"recurring:{rn['id']}"
        node["entity_refs"] = rn.get("entity_refs", [])
        node["priority_score"] = 60
        node["stale_after_hours"] = 18
        dag = {
            "dag_id": "DAG-REC-" + uuid.uuid4().hex[:6],
            "source_drop": rn["id"], "domain": rn["domain"], "type": "recurring",
            "goal": rn["title"], "raw_input": f"[recurring {rn['recurrence']}] {rn['title']}",
            "nodes": [node], "status": "running",
            "created_at": clock.now_iso(), "updated_at": clock.now_iso(),
            "project": "", "entity_refs": rn.get("entity_refs", []), "links": [],
        }
        storage.save_dag(dag)
        for eid in rn.get("entity_refs", []):
            entities.attach_dag(eid, dag["dag_id"])
        state._mark_materialized(rn["id"], clock.today())
        storage.append(storage.DAG_EVENTS,
                       {"dag_id": dag["dag_id"], "event": "recurring_materialized",
                        "rn": rn["id"], "day": clock.today()})
        made.append({"dag_id": dag["dag_id"], "rn": rn["id"], "title": rn["title"]})
    return made


def _all_dags() -> list[dict]:
    import os
    d = os.path.join(storage.DATA_DIR, "dags")
    out = []
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".json"):
                dg = storage.load_dag(fn[:-5])
                if dg:
                    out.append(dg)
    return out


def tick() -> dict:
    materialized = _materialize_recurring()

    stale, escalate, resurfaced = [], [], []
    for dag in _all_dags():
        for n in dag["nodes"]:
            ref = {"dag": dag["dag_id"], "node": n["id"], "title": n["title"],
                   "domain": n.get("domain", dag.get("domain")), "status": n["status"]}
            if n["status"] in ("waiting", "ready"):
                age = clock.hours_since(dag.get("updated_at", dag.get("created_at", "")))
                if age > n.get("stale_after_hours", 24):
                    stale.append({**ref, "age_hours": round(age, 1)})
            if n["status"] == "blocked":
                resurfaced.append(ref)
            if n["status"] == "failed":
                escalate.append(ref)

    report = {
        "at": clock.now_iso(),
        "recurring_materialized": materialized,
        "stale": stale,
        "blocked_resurfaced": resurfaced,
        "escalations": escalate,
    }
    storage.append(storage.DAG_EVENTS, {"event": "watch_tick", **{
        "at": report["at"], "materialized": len(materialized),
        "stale": len(stale), "blocked": len(resurfaced), "escalations": len(escalate)}})
    return report
