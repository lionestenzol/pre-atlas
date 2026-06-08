"""Graph engine (MVP 3): the tool-connected recursive loop.

  drop -> packet -> DAG -> [route -> (agent|tool|human) -> review(done_condition)
          -> update]* -> state

Tool nodes produce receipts (evidence); the reviewer marks them done only when
the done_condition is verified, with bounded retries. Human nodes are surfaced
as awaiting-you, never auto-completed.
"""

from __future__ import annotations

from . import (clock, dag_builder, dag_update, dispatcher, engine, entities,
               node_reviewer, node_router, state, storage)

_MAX_CYCLES = 16


def _priority_score(packet) -> int:
    s = 40
    if getattr(packet, "needs_human_decision", False):
        s += 25
    s += {"warning": 30, "problem": 20, "follow_up": 12, "decision": 8}.get(packet.type, 0)
    if packet.domain in ("money_admin", "animal_property"):
        s += 8
    return min(100, s)


def _enrich(dag: dict, packet) -> dict:
    """Stamp MVP4 fields, attach entities, and link related DAGs."""
    dag["created_at"] = clock.now_iso()
    dag["updated_at"] = clock.now_iso()
    project = "DropList" if "droplist" in packet.normalized_input.lower() else ""
    dag["project"] = project

    ent_refs = entities.resolve_from_packet(packet.to_dict())
    dag["entity_refs"] = ent_refs

    # cross-DAG links: any prior DAG sharing one of these entities
    links: list[str] = []
    for eid in ent_refs:
        ent = entities.get(eid)
        if ent:
            links.extend(d for d in ent.get("related_dags", []) if d != dag["dag_id"])
    dag["links"] = sorted(set(links))

    # do-not-reopen refs relevant to this domain
    dnr = list(state.locked_refs().keys())
    score = _priority_score(packet)

    # guard: refuse to reopen locked work unless a failed validation exists
    low = packet.normalized_input.lower()
    reopen_intent = any(w in low for w in
                        ("redo", "rebuild", "reopen", "redesign", "rewrite",
                         "from scratch", "start over", "scrap"))
    targeted = [ref for ref in dnr
                if any(tok in low for tok in ref.lower().replace("-", " ").split()
                       if len(tok) > 2)]
    if reopen_intent and targeted:
        dag["blocked_by_lock"] = targeted
        dag["nodes"].append({
            "id": "LOCK", "title": f"Do-not-reopen: {', '.join(targeted)}",
            "type": "guard", "status": "blocked", "depends_on": [],
            "agent": "reviewer", "tool_type": "", "tool_action": "",
            "inputs_required": [], "result": None, "result_refs": [], "evidence": [],
            "retry_count": 0, "max_retries": 0,
            "done_condition": "only reopen if a failing validation is on record",
            "domain": packet.domain, "project": project, "entity_refs": [],
            "parent_dag": dag["dag_id"], "priority_score": 0,
            "stale_after_hours": 9999, "created_from": "lock_guard", "recurs": False,
            "do_not_reopen_refs": targeted,
        })

    for n in dag["nodes"]:
        n["domain"] = packet.domain
        n["project"] = project
        n["entity_refs"] = ent_refs
        n["parent_dag"] = dag["dag_id"]
        n["priority_score"] = score
        n["stale_after_hours"] = 24
        n["created_from"] = "user_drop"
        n["recurs"] = False
        n["do_not_reopen_refs"] = dnr

    # attach this dag to each entity (+ first observation)
    obs = packet.normalized_input[:120]
    for eid in ent_refs:
        entities.attach_dag(eid, dag["dag_id"], observation=obs)

    storage.save_dag(dag)
    return dag


def run_graph(raw_input: str) -> dict:
    packet, _ = engine.process_drop(raw_input)

    dag = dag_builder.build_dag(packet)
    dag_errs = dag_builder.validate_dag(dag)
    dag = _enrich(dag, packet)
    storage.append(storage.DAG_EVENTS,
                   {"dag_id": dag["dag_id"], "event": "built", "nodes": len(dag["nodes"]),
                    "entity_refs": dag["entity_refs"], "links": dag["links"]})

    trace = {
        "packet": packet.to_dict(),
        "dag_id": dag["dag_id"],
        "goal": dag["goal"],
        "dag_valid": not dag_errs,
        "dag_errors": dag_errs,
        "initial_ready": [n["id"] for n in dispatcher.get_ready_nodes(dag)],
        "project": dag.get("project", ""),
        "entity_refs": dag.get("entity_refs", []),
        "links": dag.get("links", []),
        "cycles": [],
        "tool_runs": [],
    }

    cycle = 0
    recursive_updates = 0
    while cycle < _MAX_CYCLES:
        ready = dispatcher.get_ready_nodes(dag)
        if not ready:
            break
        cycle += 1
        rec = {"cycle": cycle, "dispatched": [], "reviews": [], "updates": []}
        progressed = False
        for node in ready:
            kind, result, receipt = node_router.execute(node, dag)
            review = node_reviewer.review(node, result, dag)

            if receipt is not None:
                trace["tool_runs"].append(receipt)
                node["evidence"].append(receipt["tool_run_id"])

            if review["review_status"] == "retry":
                node["retry_count"] = node.get("retry_count", 0) + 1
                rec["updates"].append(
                    f"{node['id']}: retry {node['retry_count']}/{node['max_retries']} "
                    f"(done_condition not met)")
                progressed = True  # state changed (retry_count); avoid stall break
            else:
                updates = dag_update.apply_review(dag, node, result, review)
                rec["updates"].extend(updates)
                recursive_updates += sum(1 for u in updates if "-> ready" in u)
                progressed = True

            rec["dispatched"].append({
                "node": node["id"], "kind": kind, "agent": node["agent"],
                "tool": node["tool_type"] or "-",
                "result": result.get("result", ""),
            })
            rec["reviews"].append({
                "node": node["id"], "status": review["review_status"],
                "mark": review["mark_node_as"], "reason": review["reason"],
            })
            storage.append(storage.REVIEWS, {"dag_id": dag["dag_id"], **review})

        trace["cycles"].append(rec)
        storage.save_dag(dag)
        if not progressed:
            break

    _finalize(dag)
    summary = state_summary(dag)
    summary["recursive_updates"] = recursive_updates
    summary["tool_actions"] = len(trace["tool_runs"])
    trace["state"] = summary
    storage.save_dag(dag)
    storage.append(storage.DAG_EVENTS,
                   {"dag_id": dag["dag_id"], "event": "settled", "status": dag["status"]})
    return trace


def _finalize(dag: dict) -> None:
    st = [n["status"] for n in dag["nodes"]]
    if all(s == "done" for s in st):
        dag["status"] = "complete"
    elif any(s == "failed" for s in st):
        dag["status"] = "failed"
    elif any(s == "blocked" for s in st):
        dag["status"] = "needs_human"
    elif any(s in ("ready", "waiting") for s in st):
        dag["status"] = "stalled"
    else:
        dag["status"] = "complete"


def state_summary(dag: dict) -> dict:
    by = {"done": [], "blocked": [], "failed": [], "ready": [], "waiting": []}
    for n in dag["nodes"]:
        by.setdefault(n["status"], []).append(n["id"])
    next_node = next((n["id"] for n in dag["nodes"] if n["status"] == "ready"), None)
    return {
        "dag_id": dag["dag_id"],
        "goal": dag["goal"],
        "dag_status": dag["status"],
        "done": by["done"],
        "blocked": by["blocked"],
        "failed": by["failed"],
        "waiting": by["waiting"],
        "next_ready": next_node,
        "total_nodes": len(dag["nodes"]),
    }
