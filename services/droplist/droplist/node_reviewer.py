"""Reviewer (MVP 3): the gate. Strict, not smart.

Rules:
  - human node          -> mark blocked (awaiting the user), never done
  - tool node           -> PASS only if the done_condition is verified against
                           the receipt; else retry (if budget) or fail. A tool
                           that ran successfully but didn't satisfy its
                           done_condition is NOT done.
  - reasoning node      -> pass on adequate confidence; cap new-node creation
"""

from __future__ import annotations

from . import toolrouter

_MIN_CONFIDENCE = 0.4
_MAX_NEW_NODES = 1


def review(node, result, dag):
    kind = node.get("tool_type", "")

    # human
    if kind == "human":
        return {
            "node_id": node["id"], "review_status": "blocked",
            "mark_node_as": "blocked",
            "reason": "needs human input — cannot be auto-completed",
            "approved_new_nodes": [],
        }

    # tool
    if kind in toolrouter.TOOL_REGISTRY:
        receipt = result.get("receipt", {})
        met = toolrouter.done_condition_met(node, receipt, dag)
        if met:
            return {
                "node_id": node["id"], "review_status": "pass",
                "mark_node_as": "done",
                "reason": f"done_condition verified ({receipt.get('status')})",
                "approved_new_nodes": [],
            }
        # not met: retry if budget remains
        if node.get("retry_count", 0) < node.get("max_retries", 0):
            return {
                "node_id": node["id"], "review_status": "retry",
                "mark_node_as": "ready",
                "reason": f"done_condition NOT met (tool={receipt.get('status')}); retrying",
                "approved_new_nodes": [],
            }
        return {
            "node_id": node["id"], "review_status": "fail",
            "mark_node_as": "failed",
            "reason": f"done_condition NOT met after {node.get('max_retries')} retries",
            "approved_new_nodes": [],
        }

    # reasoning
    new = result.get("new_nodes", []) or []
    conf = float(result.get("confidence", 0))
    if result.get("status") == "blocked":
        return {"node_id": node["id"], "review_status": "blocked",
                "mark_node_as": "blocked", "reason": "agent reported a blocker",
                "approved_new_nodes": []}
    if conf < _MIN_CONFIDENCE or not result.get("result"):
        return {"node_id": node["id"], "review_status": "fail",
                "mark_node_as": "failed",
                "reason": f"low confidence ({conf}) or empty result",
                "approved_new_nodes": []}
    approved = new[:_MAX_NEW_NODES]
    reason = "node objective answered in scope"
    if len(new) > len(approved):
        reason += f"; rationed {len(new) - len(approved)} extra node(s)"
    return {"node_id": node["id"], "review_status": "pass",
            "mark_node_as": "done", "reason": reason,
            "approved_new_nodes": approved}
