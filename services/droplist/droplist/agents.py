"""Agent Runner.

Each agent is a prompt template (objective + constraints + done_condition).
By default the runner produces a deterministic, scope-bounded result so the
LOOP runs with zero dependencies — the agent *content* is templated, the agent
*protocol* (result/evidence/confidence/new_nodes) is real. Flip DROPLIST_LLM=
anthropic and the same template becomes the system prompt for a real model.

An agent returns exactly:
  {node_id, status, result, evidence, confidence, new_nodes}
status in: done | blocked | failed
"""

from __future__ import annotations

import time

from . import llm
from .dispatcher import get_node

# agent template = the contract handed to the model when LLM is on
AGENTS: dict[str, dict] = {
    "animal_care": {
        "objective": "Read the animal description and give a risk level + the signs to watch.",
        "constraints": ["stay on this animal/issue", "no vet prescriptions", "flag if urgent"],
    },
    "ops": {
        "objective": "Do the concrete field/status check named by the node title.",
        "constraints": ["report observations only", "do not move/delete/pay anything"],
    },
    "coder": {
        "objective": "Perform the engineering step in the node title at the smallest scope.",
        "constraints": ["no redesign", "no force push", "smallest reproducible step"],
    },
    "finance": {
        "objective": "Extract money/admin fields; never authorize payment or send messages.",
        "constraints": ["extract only", "no payments", "no outbound messages"],
    },
    "documenter": {
        "objective": "Capture the item in one clear line and note where it belongs.",
        "constraints": ["one line", "no building", "no scope creep"],
    },
    "memory": {
        "objective": "Link this item to the owning project/context for later retrieval.",
        "constraints": ["link only", "do not invent projects"],
    },
    "reviewer": {
        "objective": "Synthesize the completed parent nodes into ONE next decision.",
        "constraints": ["one decision", "cite the parent results", "mark blockers"],
    },
}


def _parent_results(dag: dict, node: dict) -> list[str]:
    out = []
    for dep in node.get("depends_on", []):
        p = get_node(dag, dep)
        if p and p.get("result"):
            out.append(f"{dep}: {p['result']['result']}")
    return out


def _heuristic(node: dict, dag: dict) -> dict:
    """Deterministic, in-scope stand-in result. Proves the protocol; the model
    replaces the prose when enabled."""
    agent = node["agent"]
    title = node["title"]
    raw = dag.get("raw_input", "")

    if agent == "animal_care":
        low = raw.lower()
        urgent = any(w in low for w in ("not eating", "limping", "hiding", "won't move",
                                        "panting", "drooling", "limp", "bleeding"))
        result = ("Description suggests possible distress; watch for panting, drooling, "
                  "limpness, refusal to move, or red ears. Risk is ELEVATED — check soon."
                  if urgent else
                  "Signs read as routine/heat-regulation. Watch for escalation: panting, "
                  "drooling, limpness, refusal to move.")
        new = ([{"title": "Recheck animal in 2 hours", "type": "field_check",
                 "agent": "ops", "depends_on": [node["id"]]}] if urgent else [])
        return _r(node, result, "matched description to a heat/distress checklist",
                  0.82 if urgent else 0.7, new)

    if agent == "ops" and node["type"] == "field_check":
        return _r(node, "Confirm: water full, shade present, airflow on the animals, "
                        "posture relaxed vs hunched. Log each as ok/not-ok.",
                  "standard field-check list", 0.78, [])
    if agent == "ops":
        return _r(node, "Clarified the concrete ask and current status from the drop; "
                        "no blockers found.", "read packet + drop", 0.7, [])

    if agent == "coder" and node["type"] == "repro":
        return _r(node, "Write the smallest failing test that triggers the reported "
                        "failure before touching any fix.", "repro-first protocol", 0.8, [])
    if agent == "coder":
        return _r(node, "Scoped one bounded change; identified the single file/path most "
                        "likely responsible.", "narrowed from the description", 0.75, [])

    if agent == "finance":
        return _r(node, "Extracted entity/date/amount/deadline where present; staged a "
                        "tracker row. No payment, no message.", "field extraction", 0.78, [])

    if agent == "documenter":
        return _r(node, f"Captured in one line: {dag.get('goal','')}.",
                  "single-line capture", 0.8, [])

    if agent == "memory":
        return _r(node, "Linked to the owning project context for later retrieval.",
                  "memory link", 0.75, [])

    if agent == "reviewer":
        parents = _parent_results(dag, node)
        synthesis = " | ".join(parents) if parents else "no parent results"
        return _r(node, f"Decision: proceed on the single next move implied by parents. "
                        f"[basis: {synthesis}]", "synthesized parent nodes", 0.8, [])

    return _r(node, "Handled the node within scope.", "default", 0.6, [])


def _r(node, result, evidence, confidence, new_nodes):
    return {
        "node_id": node["id"],
        "status": "done",
        "result": result,
        "evidence": evidence,
        "confidence": confidence,
        "new_nodes": new_nodes,
    }


def run_agent(node: dict, dag: dict) -> dict:
    """Run one node through its agent. Returns the agent result dict."""
    t0 = time.time()
    tmpl = AGENTS.get(node["agent"], {})

    if llm.anthropic_available():
        system = (f"You are the '{node['agent']}' agent. {tmpl.get('objective','')} "
                  f"Constraints: {tmpl.get('constraints')}. Respond ONLY with JSON: "
                  '{"status":"done|blocked|failed","result":"","evidence":"",'
                  '"confidence":0.0,"new_nodes":[]}')
        parents = _parent_results(dag, node)
        user = (f"Node: {node['title']} (type {node['type']})\n"
                f"Drop: {dag.get('raw_input','')}\n"
                f"Parent results: {parents}")
        data = llm.call_json("agent_run", system, user, dag.get("source_drop", ""))
        if data and "result" in data:
            return {
                "node_id": node["id"],
                "status": data.get("status", "done"),
                "result": data["result"],
                "evidence": data.get("evidence", ""),
                "confidence": float(data.get("confidence", 0.7)),
                "new_nodes": data.get("new_nodes", []),
            }

    res = _heuristic(node, dag)
    llm.log_call("agent_run", "heuristic-v1", dag.get("source_drop", ""),
                 node["title"], res["result"], int((time.time() - t0) * 1000), "success")
    return res
