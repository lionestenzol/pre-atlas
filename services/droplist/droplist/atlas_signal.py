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
import os
import urllib.error
import urllib.request
import uuid
from typing import Any

from . import clock, storage

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


# ---------------------------------------------------------------------------
# Signal.v1 validation (production-side mirror of test_atlas_signal.structural_check)
# ---------------------------------------------------------------------------

# Closed sets — must match contracts/schemas/Signal.v1.json
_VALID_SOURCE_LAYERS = {"site_pull", "optogon", "atlas", "ghost_executor", "claude_code"}
_VALID_SIGNAL_TYPES = {"status", "completion", "blocked", "approval_required",
                       "error", "insight"}
_VALID_PRIORITIES = {"urgent", "normal", "low"}
_REQUIRED_TOP = ["schema_version", "id", "emitted_at", "source_layer",
                 "signal_type", "priority", "payload"]
_REQUIRED_PAYLOAD = ["task_id", "label", "summary"]
_REQUIRED_PAYLOAD_DATA = [
    "dag_id", "domain", "type", "dag_status",
    "nodes", "evidence_refs", "entity_refs", "links",
]
_VALID_RISK_TIERS = {"low", "medium", "high"}


def _find_signal_schema_path() -> str | None:
    """Locate contracts/schemas/Signal.v1.json relative to this file.

    The droplist service may be invoked from several working directories
    (project root, services/droplist/, or installed via pip). Try the known
    repo-relative candidates in order; return None if none exist.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        # services/droplist/droplist/atlas_signal.py -> ../../../contracts/schemas/
        os.path.join(here, "..", "..", "..", "contracts", "schemas", "Signal.v1.json"),
        os.path.join(here, "..", "..", "contracts", "schemas", "Signal.v1.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def validate_signal(signal: dict) -> list[str]:
    """Validate a Signal.v1-shaped dict. Returns [] on success, list of errors otherwise.

    Production-side mirror of test_atlas_signal.structural_check. Uses jsonschema
    for strict validation when the library and schema file are both available;
    otherwise falls back to structural checks (closed enums, required fields,
    action_required<->action_options invariant). Either path is sufficient to
    detect a malformed Signal before POST.
    """
    if not isinstance(signal, dict):
        return [f"signal must be a dict, got {type(signal).__name__}"]

    # Try strict jsonschema first (catches every constraint at once).
    try:
        import jsonschema  # type: ignore
    except ImportError:
        jsonschema = None  # type: ignore

    if jsonschema is not None:
        schema_path = _find_signal_schema_path()
        if schema_path:
            try:
                with open(schema_path, encoding="utf-8") as f:
                    schema = json.load(f)
                jsonschema.validate(instance=signal, schema=schema)
                return []
            except jsonschema.ValidationError as e:
                # Truncate to keep audit records bounded.
                return [f"jsonschema: {str(e)[:300]}"]
            except (OSError, json.JSONDecodeError) as e:
                # Fall through to structural checks if schema can't be loaded.
                # Do not fail validation just because the schema file is broken.
                pass

    # Structural fallback (and belt-and-suspenders even when jsonschema passes).
    errs: list[str] = []
    for k in _REQUIRED_TOP:
        if k not in signal:
            errs.append(f"missing required top key {k}")
    if signal.get("schema_version") != "1.0":
        errs.append(f"schema_version must be '1.0', got {signal.get('schema_version')!r}")
    if signal.get("source_layer") not in _VALID_SOURCE_LAYERS:
        errs.append(f"source_layer {signal.get('source_layer')!r} not in enum")
    if signal.get("signal_type") not in _VALID_SIGNAL_TYPES:
        errs.append(f"signal_type {signal.get('signal_type')!r} not in enum")
    if signal.get("priority") not in _VALID_PRIORITIES:
        errs.append(f"priority {signal.get('priority')!r} not in enum")

    payload = signal.get("payload") or {}
    if not isinstance(payload, dict):
        errs.append("payload must be a dict")
        return errs
    for k in _REQUIRED_PAYLOAD:
        if k not in payload:
            errs.append(f"payload missing required key {k}")

    if "task_id" in payload and payload["task_id"] is not None:
        if not isinstance(payload["task_id"], str):
            errs.append(
                f"payload.task_id must be str or null, got {type(payload['task_id']).__name__}"
            )

    data = payload.get("data")
    if data is not None:
        if not isinstance(data, dict):
            errs.append("payload.data must be a dict")
        else:
            for k in _REQUIRED_PAYLOAD_DATA:
                if k not in data:
                    errs.append(f"payload.data missing required key {k}")
            for list_key in ("nodes", "evidence_refs", "entity_refs", "links"):
                if list_key in data and not isinstance(data[list_key], list):
                    errs.append(f"payload.data.{list_key} must be a list")

    # action_required=true => action_options.minItems >= 1
    if payload.get("action_required") is True:
        opts = payload.get("action_options") or []
        if not isinstance(opts, list) or len(opts) < 1:
            errs.append("action_required=true requires action_options with >= 1 item")
        else:
            for i, opt in enumerate(opts):
                if not isinstance(opt, dict):
                    errs.append(f"action_options[{i}] not a dict")
                    continue
                for k in ("id", "label", "risk_tier"):
                    if k not in opt:
                        errs.append(f"action_options[{i}] missing {k}")
                if opt.get("risk_tier") not in _VALID_RISK_TIERS:
                    errs.append(f"action_options[{i}] risk_tier invalid")

    return errs


def emit_signal(signal: dict, url: str, timeout: float = 10.0) -> dict[str, Any]:
    """POST a Signal.v1 dict to a delta-kernel-shaped ingest endpoint.

    Returns the parsed JSON response on success, or a dict with `error` on failure.
    Zero-dependency (stdlib urllib only). Suitable for both n8n webhook URLs and
    a direct delta-kernel URL (e.g. http://127.0.0.1:3001/api/signals/ingest).

    Validates the signal against Signal.v1 before POST. Behavior on validation
    failure is controlled by the DROPLIST_STRICT_EMIT environment variable:

      - strict mode (DROPLIST_STRICT_EMIT in {"1","true","yes","on"}, case-insensitive)
        returns {"ok": False, "error": "validation_failed", "validation_errors": [...]}
        WITHOUT POSTing. Used in CI and tests where a malformed signal must hard-stop.

      - fail-soft mode (default, unset): logs a `signal_validation_warning` record
        to dag_events.jsonl with the errors, then POSTs anyway. Matches the broader
        emission posture in graph_engine._maybe_emit_atlas_signal which catches all
        exceptions so the DAG loop completes regardless of emission outcome.

    Design rationale (fail-soft default): emission is already fail-soft for HTTP
    errors (returns ok=False rather than raising); making validation fail-loud by
    default would silently change that contract. Strict mode is an opt-in for
    contexts where stricter posture is wanted (CI, contract-conformance gates).
    """
    errors = validate_signal(signal)
    if errors:
        strict_env = (os.environ.get("DROPLIST_STRICT_EMIT") or "").strip().lower()
        strict_mode = strict_env in {"1", "true", "yes", "on"}
        # Always leave an audit trail so malformed-signal incidents are discoverable.
        try:
            storage.append(
                storage.DAG_EVENTS,
                {
                    "event": "signal_validation_warning",
                    "signal_id": signal.get("id") if isinstance(signal, dict) else None,
                    "url": url,
                    "errors": errors,
                    "strict_mode": strict_mode,
                    "posted": not strict_mode,
                    "emitted_at": clock.now_iso(),
                },
            )
        except Exception:  # noqa: BLE001 — never let logging break emission
            pass
        if strict_mode:
            return {
                "ok": False,
                "error": "validation_failed",
                "validation_errors": errors,
            }
        # else: fall through and POST anyway

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
    except urllib.error.HTTPError as e:
        # 4xx is a client-side bug (won't fix itself on retry); 5xx is server-side
        # and transient. Only enqueue the latter. See PKT-006 retry buffer doctrine.
        result: dict[str, Any] = {"ok": False, "error": str(e)}
        if getattr(e, "code", 0) >= 500:
            try:
                from . import retry_queue
                retry_queue.enqueue(signal, url, str(e))
            except Exception:  # noqa: BLE001 — queueing must never break emission
                pass
        return result
    except (urllib.error.URLError, OSError) as e:
        # DNS, timeout, connection refused — always retryable.
        result = {"ok": False, "error": str(e)}
        try:
            from . import retry_queue
            retry_queue.enqueue(signal, url, str(e))
        except Exception:  # noqa: BLE001
            pass
        return result
