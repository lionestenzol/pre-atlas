"""DAG Updater: apply a review to the graph.

1. set the reviewed node's status (done/blocked/failed) and attach its result
2. insert any approved new nodes
3. recompute: any `waiting` node whose deps are all `done` becomes `ready`

Step 3 is the recursive magic — it's what makes a finished N1+N2 wake up N3.
Returns human-readable update strings for the trace.
"""

from __future__ import annotations

import uuid


def _done_ids(dag: dict) -> set[str]:
    return {n["id"] for n in dag["nodes"] if n["status"] == "done"}


def apply_review(dag: dict, node: dict, result: dict, review: dict) -> list[str]:
    updates: list[str] = []

    # 1. set status + attach result
    old = node["status"]
    node["status"] = review["mark_node_as"]
    node["result"] = result
    updates.append(f"{node['id']}: {old} -> {node['status']}")

    # 2. insert approved new nodes (as ready, bounded)
    for spec in review.get("approved_new_nodes", []):
        nid = "N" + uuid.uuid4().hex[:4]
        dag["nodes"].append({
            "id": nid,
            "title": spec.get("title", "follow-up"),
            "type": spec.get("type", "field_check"),
            "status": "ready",
            "depends_on": spec.get("depends_on", []),
            "agent": spec.get("agent", "ops"),
            "tool_type": spec.get("tool_type", ""),
            "tool_action": spec.get("tool_action", ""),
            "inputs_required": spec.get("inputs_required", []),
            "done_condition": spec.get("done_condition", ""),
            "result": None,
            "result_refs": [],
            "evidence": [],
            "retry_count": 0,
            "max_retries": spec.get("max_retries", 2),
        })
        updates.append(f"+{nid}: new node '{spec.get('title','follow-up')}' (ready)")

    # 3. wake up waiting nodes whose deps are satisfied
    done = _done_ids(dag)
    for n in dag["nodes"]:
        if n["status"] == "waiting" and all(d in done for d in n["depends_on"]):
            n["status"] = "ready"
            updates.append(f"{n['id']}: waiting -> ready (deps satisfied)")

    # mark dag complete if nothing remains runnable or pending
    pending = [n for n in dag["nodes"] if n["status"] in ("ready", "waiting")]
    blocked = [n for n in dag["nodes"] if n["status"] in ("blocked", "failed")]
    if not pending:
        dag["status"] = "blocked" if blocked else "complete"

    return updates
