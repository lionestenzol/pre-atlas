"""Atlas seam: map a settled DropList DAG to a Signal.v1 dict.

The Atlas substrate (delta-kernel `POST /api/signals/ingest`) accepts events
conforming to `contracts/schemas/Signal.v1.json`. This module is the canonical
mapping from a DropList DAG's terminal state to that shape.

Pure functions in this module are I/O-free and side-effect-free; the live POST
helper `emit_signal()` uses stdlib urllib (zero-dependency).

See PKT-005 and BIBLE.md §16 for the contract.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from typing import Any

from . import clock

# ---------------------------------------------------------------------------
# Mapping tables (closed sets, matching Signal.v1 enums)
# ---------------------------------------------------------------------------

# DAG terminal status -> Signal.v1 signal_type
_STATUS_TO_SIGNAL_TYPE: dict[str, str] = {
    "complete": "completion",
    "failed": "error",
    "needs_human": "approval_required",
    "stalled": "blocked",
    # active states (defensive; should not normally be emitted)
    "running": "status",
    "blocked": "blocked",
}

# DropList domain+type -> Signal.v1 priority
_URGENT_TYPES = {"warning", "problem"}
_LOW_DOMAINS = {"general"}


def _derive_priority(dag: dict) -> str:
    """Compute Signal.v1 priority from DAG fields. Closed-enum output."""
    dag_type = dag.get("type", "")
    dag_domain = dag.get("domain", "")
    # Any urgent_type or any node with priority_score >= 80 -> urgent
    if dag_type in _URGENT_TYPES:
        return "urgent"
    if any(n.get("priority_score", 0) >= 80 for n in dag.get("nodes", [])):
        return "urgent"
    if dag_domain in _LOW_DOMAINS:
        return "low"
    return "normal"


def _node_summary(node: dict) -> dict[str, Any]:
    """Compact per-node introspection for payload.data.nodes."""
    return {
        "id": node.get("id"),
        "status": node.get("status"),
        "agent": node.get("agent"),
        "tool_type": node.get("tool_type", ""),
        "done_condition": node.get("done_condition", ""),
    }


def _collect_action_options(dag: dict) -> list[dict[str, Any]]:
    """Surface blocked-human nodes as action_options. Required by Signal.v1
    schema when action_required=true."""
    options: list[dict[str, Any]] = []
    for n in dag.get("nodes", []):
        if n.get("status") == "blocked" and n.get("tool_type") == "human":
            options.append({
                "id": n.get("id", "?"),
                "label": (n.get("title") or "Awaiting human")[:140],
                "risk_tier": "low",
            })
    return options


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def dag_to_signal(dag: dict, source_layer: str = "optogon") -> dict[str, Any]:
    """Map a settled DropList DAG to a Signal.v1-shaped dict.

    Pure function. No I/O. Uses controllable clock so tests can pin timestamps.

    `source_layer` defaults to "optogon" because the Signal.v1 enum does not
    yet include "droplist". See OQ-17 in BIBLE §13.
    """
    nodes = dag.get("nodes", []) or []
    done = [n for n in nodes if n.get("status") == "done"]
    total = len(nodes)
    dag_status = dag.get("status", "running")

    signal_type = _STATUS_TO_SIGNAL_TYPE.get(dag_status, "status")
    priority = _derive_priority(dag)

    label = (dag.get("goal") or "").strip()[:140] or "DropList DAG"
    domain = dag.get("domain", "?")
    dag_type = dag.get("type", "?")
    summary = f"{domain}/{dag_type}: {len(done)}/{total} done; status={dag_status}"

    payload: dict[str, Any] = {
        "task_id": dag.get("source_drop"),
        "label": label,
        "summary": summary,
        "data": {
            "dag_id": dag.get("dag_id"),
            "domain": domain,
            "type": dag_type,
            "dag_status": dag_status,
            "nodes": [_node_summary(n) for n in nodes],
            "evidence_refs": [
                ev
                for n in nodes
                for ev in (n.get("evidence") or [])
            ],
            "entity_refs": list(dag.get("entity_refs") or []),
            "links": list(dag.get("links") or []),
        },
    }

    action_required = signal_type == "approval_required"
    if action_required:
        options = _collect_action_options(dag)
        # Schema requires action_options with minItems >= 1 when action_required=true.
        # If no human-blocked nodes were found, synthesize a fallback option so the
        # invariant holds; this should never happen in practice but is defensive.
        if not options:
            options = [{
                "id": "DAG",
                "label": f"Review settled DAG {dag.get('dag_id')}",
                "risk_tier": "low",
            }]
        payload["action_required"] = True
        payload["action_options"] = options

    return {
        "schema_version": "1.0",
        "id": "sig_" + uuid.uuid4().hex[:12],
        "emitted_at": clock.now_iso(),
        "source_layer": source_layer,
        "signal_type": signal_type,
        "priority": priority,
        "payload": payload,
    }


def emit_signal(signal: dict, url: str, timeout: float = 10.0) -> dict[str, Any]:
    """POST a Signal.v1 dict to a delta-kernel-shaped ingest endpoint.

    Returns the parsed JSON response on success, or a dict with `error` on failure.
    Zero-dependency (stdlib urllib only). Suitable for both n8n webhook URLs and
    a direct delta-kernel URL (e.g. http://127.0.0.1:3001/api/signals/ingest).
    """
    try:
        body = json.dumps(signal).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8") if resp.length != 0 else ""
        try:
            return json.loads(raw) if raw else {"ok": True}
        except json.JSONDecodeError:
            return {"ok": True, "raw": raw[:200]}
    except (urllib.error.URLError, OSError) as e:
        return {"ok": False, "error": str(e)}
