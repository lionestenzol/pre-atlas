"""Node Router: decide how a ready node is handled, and run it.

  human    -> cannot be auto-completed; surfaced as awaiting-human (blocked)
  tool      -> run via the tool router; receipt becomes evidence
  reasoning -> run via the agent runner (MVP 2)

Returns (kind, result, receipt). For tool nodes, `result` wraps the receipt so
the reviewer can verify the done_condition against it.
"""

from __future__ import annotations

from . import agents, toolrouter


def classify(node: dict) -> str:
    tt = node.get("tool_type", "")
    if tt == "human":
        return "human"
    if tt in toolrouter.TOOL_REGISTRY:
        return "tool"
    return "reasoning"


def execute(node: dict, dag: dict):
    kind = classify(node)

    if kind == "human":
        result = {
            "node_id": node["id"], "status": "awaiting_human",
            "result": f"Needs you: {node['title']}",
            "evidence": "", "confidence": 1.0, "new_nodes": [],
        }
        return kind, result, None

    if kind == "tool":
        receipt = toolrouter.run_tool(node, dag)
        result = {
            "node_id": node["id"], "status": receipt["status"],
            "result": f"{node['tool_type']}.{receipt['action']} -> {receipt['status']}",
            "evidence": receipt["tool_run_id"], "confidence": 1.0, "new_nodes": [],
            "receipt": receipt,
        }
        return kind, result, receipt

    # reasoning
    result = agents.run_agent(node, dag)
    return kind, result, None
