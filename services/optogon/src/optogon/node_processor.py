"""Node processor - dispatches a user turn to the correct node-type handler.

Per doctrine/03_OPTOGON_SPEC.md Section 14. Six node types:
qualify, execute, gate, fork, approval, close.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .context import empty_context, missing_keys, resolve, set_tier
from .inference import apply_node_rules
from .response_composer import compose
from . import signals


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def process_turn(
    session_state: dict[str, Any],
    path: dict[str, Any],
    user_message: Optional[str],
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    """Advance the session by one turn.

    Returns (new_state, response_text, emitted_signals).
    """
    current_id = session_state["current_node"]
    node = path["nodes"].get(current_id)
    if node is None:
        raise ValueError(f"Current node {current_id} not in path.nodes")

    # Merge node id into the node dict if not present (paths-as-examples store type/label only)
    node = dict(node)
    node.setdefault("id", current_id)
    node.setdefault("schema_version", "1.0")

    ntype = node.get("type")
    emitted: list[dict[str, Any]] = []

    if ntype == "qualify":
        return _handle_qualify(session_state, path, node, user_message, emitted)
    if ntype == "execute":
        return _handle_execute(session_state, path, node, emitted)
    if ntype == "gate":
        return _handle_gate(session_state, path, node, emitted)
    if ntype == "approval":
        return _handle_approval(session_state, path, node, user_message, emitted)
    if ntype == "close":
        return _handle_close(session_state, path, node, emitted)
    if ntype == "fork":
        raise NotImplementedError("fork nodes deferred per 04_BUILD_PLAN.md Section 4")

    raise ValueError(f"Unknown node type: {ntype}")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
def _ensure_node_state(state: dict[str, Any], node_id: str) -> dict[str, Any]:
    ns = state["node_states"].setdefault(node_id, {
        "status": "unqualified",
        "entered_at": _now(),
        "closed_at": None,
        "attempts": 0,
        "qualification_data": {},
        "action_results": {},
        "errors": [],
    })
    return ns


def _transition(state: dict[str, Any], path: dict[str, Any], from_id: str, condition: str) -> Optional[str]:
    """Pick the next node based on edges matching condition."""
    edges = [e for e in path.get("edges", []) if e.get("from") == from_id]
    # Exact match first, then 'default'
    matching = [e for e in edges if e.get("condition") == condition]
    if not matching:
        matching = [e for e in edges if e.get("condition") == "default"]
    if not matching:
        return None
    matching.sort(key=lambda e: e.get("priority", 0))
    return matching[0].get("to")


def _handle_qualify(state, path, node, user_message, emitted):
    ns = _ensure_node_state(state, node["id"])
    ns["attempts"] += 1

    # Seed user tier from the message if provided
    if user_message:
        # If there's exactly one missing key, attribute the message to it
        required_keys = [r.get("key") for r in (node.get("qualification") or {}).get("required") or []]
        missing = missing_keys(required_keys, state["context"])
        if len(missing) == 1:
            set_tier(state["context"], "user", missing[0], user_message.strip())

    # Run inference rules
    applied = apply_node_rules(node.get("inference_rules") or [], state["context"])
    state["metrics"]["total_inferences_made"] += len(applied)

    # Check if qualified now
    required_keys = [r.get("key") for r in (node.get("qualification") or {}).get("required") or []]
    missing = missing_keys(required_keys, state["context"])

    if not missing:
        ns["status"] = "qualified"
        ns["closed_at"] = _now()
        state["metrics"]["nodes_closed"] += 1
        next_id = _transition(state, path, node["id"], "qualified") or _transition(state, path, node["id"], "default")
        if next_id:
            state["current_node"] = next_id
            _ensure_node_state(state, next_id)
        return state, "", emitted

    # Still missing keys - compose a question
    text, tokens = compose(node, state)
    state["metrics"]["total_tokens"] += tokens
    state["metrics"]["total_questions_asked"] += 1 if "?" in text else 0
    return state, text, emitted


def _handle_execute(state, path, node, emitted):
    ns = _ensure_node_state(state, node["id"])
    ns["attempts"] += 1
    # Actions fire here. In Phase 2 we do NOT invoke real side effects - we
    # log the intent and mark the node closed. Phase 3 wires real action handlers.
    for action in node.get("actions") or []:
        action_id = action.get("id") or f"act_{uuid.uuid4().hex[:8]}"
        state["action_log"].append({
            "action_id": action_id,
            "node_id": node["id"],
            "type": action.get("type", "unknown"),
            "status": "success",
            "executed_at": _now(),
            "result": {"stub": True},
            "reversible": action.get("reversible", True),
            "reversed": False,
        })
        state["metrics"]["total_actions_fired"] += 1
        ns["action_results"][action_id] = {"stub": True}

    ns["status"] = "closed"
    ns["closed_at"] = _now()
    state["metrics"]["nodes_closed"] += 1

    next_id = _transition(state, path, node["id"], "success") or _transition(state, path, node["id"], "default")
    if next_id:
        state["current_node"] = next_id
        _ensure_node_state(state, next_id)
    return state, "", emitted


def _handle_gate(state, path, node, emitted):
    ns = _ensure_node_state(state, node["id"])
    ns["attempts"] += 1
    # Evaluate the first true-branch edge; gates route silently.
    # For now: pick the highest-priority non-default edge whose condition expression
    # references only context. Safe eval via inference._safe_eval is reused.
    from .inference import _safe_eval  # local import to avoid cycles
    chosen_condition = None
    for edge in sorted(path.get("edges", []), key=lambda e: e.get("priority", 0)):
        if edge.get("from") != node["id"]:
            continue
        cond = edge.get("condition", "")
        if cond in ("", "default"):
            continue
        try:
            result = _safe_eval(cond, state["context"])
        except Exception:
            continue
        if result:
            chosen_condition = cond
            break
    ns["status"] = "closed"
    ns["closed_at"] = _now()
    state["metrics"]["nodes_closed"] += 1

    next_id = _transition(state, path, node["id"], chosen_condition or "default")
    if next_id:
        state["current_node"] = next_id
        _ensure_node_state(state, next_id)
    return state, "", emitted


def _handle_approval(state, path, node, user_message, emitted):
    ns = _ensure_node_state(state, node["id"])

    # If user_message is an approval keyword, treat as resolved
    if user_message and user_message.strip().lower() in {"approve", "approved", "yes", "y", "confirm"}:
        ns["status"] = "closed"
        ns["closed_at"] = _now()
        state["metrics"]["nodes_closed"] += 1
        next_id = _transition(state, path, node["id"], "approved") or _transition(state, path, node["id"], "default")
        if next_id:
            state["current_node"] = next_id
            _ensure_node_state(state, next_id)
        return state, "", emitted

    if user_message and user_message.strip().lower() in {"deny", "denied", "no", "n", "abandon"}:
        ns["status"] = "closed"
        ns["closed_at"] = _now()
        state["metrics"]["nodes_closed"] += 1
        next_id = _transition(state, path, node["id"], "denied") or _transition(state, path, node["id"], "abandon")
        if next_id:
            state["current_node"] = next_id
            _ensure_node_state(state, next_id)
        return state, "", emitted

    # First visit - emit approval signal, wait
    ns["status"] = "awaiting_approval"
    ns["attempts"] += 1
    sig = signals.emit(
        source_layer="optogon",
        signal_type="approval_required",
        priority="urgent",
        label=node.get("label", "Approval required"),
        summary=node.get("label", "Approval required"),
        data={"node_id": node["id"], "session_id": state["session_id"]},
        action_required=True,
        action_options=[
            {"id": "approve", "label": "Approve", "consequence": "Proceed with committed action", "risk_tier": "medium"},
            {"id": "deny", "label": "Deny", "consequence": "Abandon path", "risk_tier": "low"},
        ],
    )
    emitted.append(sig)
    text, tokens = compose(node, state)
    state["metrics"]["total_tokens"] += tokens
    return state, text, emitted


def _handle_close(state, path, node, emitted):
    """Close the session: build a CloseSignal and mark the session closed."""
    ns = _ensure_node_state(state, node["id"])
    ns["status"] = "closed"
    ns["closed_at"] = _now()
    state["metrics"]["nodes_closed"] += 1
    state["metrics"]["nodes_total"] = len(path.get("nodes", {}))

    # Build CloseSignal
    total_q = state["metrics"]["total_questions_asked"]
    total_inf = state["metrics"]["total_inferences_made"]
    accuracy = 1.0  # Phase 2 placeholder; Phase 4 measures actual
    time_to_close = 0.0
    try:
        started = datetime.fromisoformat(state.get("started_at", _now()).replace("Z", "+00:00"))
        time_to_close = (datetime.now(timezone.utc) - started).total_seconds()
    except Exception:
        pass

    close_signal = {
        "schema_version": "1.0",
        "id": f"close_{uuid.uuid4().hex[:12]}",
        "session_id": state["session_id"],
        "path_id": state["path_id"],
        "closed_at": _now(),
        "status": "completed",
        "deliverables": [
            {"type": "confirmation", "label": "path closed", "value": True, "location": None},
        ],
        "session_summary": {
            "total_tokens": state["metrics"]["total_tokens"],
            "total_questions_asked": total_q,
            "total_inferences_made": total_inf,
            "inference_accuracy": accuracy,
            "nodes_closed": state["metrics"]["nodes_closed"],
            "nodes_total": state["metrics"]["nodes_total"],
            "time_to_close_seconds": time_to_close,
            "path_completion_rate": 1.0,
        },
        "decisions_made": [
            {"key": k, "value": v, "source": "user", "node_id": state["current_node"]}
            for k, v in state["context"]["confirmed"].items()
        ] + [
            {"key": k, "value": v, "source": "inferred", "node_id": state["current_node"]}
            for k, v in state["context"]["inferred"].items()
        ],
        "unblocked": [],
        "context_residue": {
            "confirmed": dict(state["context"]["confirmed"]),
            "learned_preferences": {},
        },
        "interrupt_log": [],
    }

    # Validate before emit
    from .contract_validator import validate
    validate(close_signal, "CloseSignal")

    sig = signals.emit(
        source_layer="optogon",
        signal_type="completion",
        priority="normal",
        label=f"Path {state['path_id']} closed",
        summary=f"Completed in {time_to_close:.1f}s, {total_q} questions asked",
        data={"close_signal_id": close_signal["id"]},
        task_id=state.get("task_id"),
    )
    emitted.append(sig)

    # Stash the close signal on the state for /session/{id} consumers
    state["_close_signal"] = close_signal
    state["current_node"] = node["id"]  # terminal
    return state, "", emitted
