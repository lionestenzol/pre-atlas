"""PKT-005 acceptance: dag_to_signal produces Signal.v1-shaped dicts.

Structural validation against the schema's required-fields, enums, and the
action_required <-> action_options invariant. If `jsonschema` is installed,
also runs a strict JSON Schema check against contracts/schemas/Signal.v1.json.

Run from the project root (so contracts/schemas/ is reachable for strict mode):

    python test_atlas_signal.py
"""

from __future__ import annotations

import json
import os
import sys

# Stable clock for reproducible emitted_at
os.environ.setdefault("DROPLIST_NOW", "2026-06-08T12:00:00Z")

from droplist import atlas_signal  # noqa: E402

# ---------------------------------------------------------------------------
# Signal.v1 closed sets (must match contracts/schemas/Signal.v1.json)
# ---------------------------------------------------------------------------

VALID_SOURCE_LAYERS = {"site_pull", "optogon", "atlas", "ghost_executor", "claude_code"}
VALID_SIGNAL_TYPES = {"status", "completion", "blocked", "approval_required",
                      "error", "insight"}
VALID_PRIORITIES = {"urgent", "normal", "low"}
REQUIRED_TOP = ["schema_version", "id", "emitted_at", "source_layer",
                "signal_type", "priority", "payload"]
REQUIRED_PAYLOAD = ["task_id", "label", "summary"]
REQUIRED_PAYLOAD_DATA = [
    "dag_id",
    "domain",
    "type",
    "dag_status",
    "nodes",
    "evidence_refs",
    "entity_refs",
    "links",
]


# ---------------------------------------------------------------------------
# Fixture DAGs
# ---------------------------------------------------------------------------

def _node(nid: str, status: str, tool_type: str = "", agent: str = "ops",
          title: str = "node", done_condition: str = "") -> dict:
    return {
        "id": nid, "status": status, "agent": agent,
        "tool_type": tool_type, "title": title,
        "done_condition": done_condition,
        "depends_on": [], "result": None, "evidence": [],
        "retry_count": 0, "max_retries": 2,
    }


def fixture_animal_needs_human() -> dict:
    return {
        "dag_id": "DAG-ANIMAL01",
        "source_drop": "drop_animal01",
        "domain": "animal_property",
        "type": "warning",
        "goal": "Check rabbits — possible heat distress",
        "status": "needs_human",
        "nodes": [
            _node("N1", "done", agent="animal_care", title="Assess risk signs"),
            _node("N2", "blocked", tool_type="human", title="Field checklist: water/shade/posture",
                  done_condition="user reports each as ok/not-ok"),
            _node("N3", "done", tool_type="calendar", title="Draft a reminder",
                  done_condition="reminder has message+time"),
        ],
        "entity_refs": ["ANIMAL-RABBITS"],
        "links": [],
    }


def fixture_build_problem_complete() -> dict:
    return {
        "dag_id": "DAG-BUILD01",
        "source_drop": "drop_build01",
        "domain": "build_product",
        "type": "problem",
        "goal": "Reproduce, scope, and verify a fix for unicode crash",
        "status": "complete",
        "nodes": [_node(f"N{i}", "done", title=f"step {i}") for i in range(1, 6)],
        "entity_refs": [],
        "links": [],
    }


def fixture_money_task_failed() -> dict:
    return {
        "dag_id": "DAG-MONEY01",
        "source_drop": "drop_money01",
        "domain": "money_admin",
        "type": "task",
        "goal": "Track truck insurance renewal",
        "status": "failed",
        "nodes": [
            _node("N1", "done", agent="finance", title="Extract entity/date/amount"),
            _node("N2", "failed", tool_type="message_drafter", title="Draft message"),
        ],
        "entity_refs": [],
        "links": [],
    }


def fixture_general_idea_stalled() -> dict:
    return {
        "dag_id": "DAG-IDEA01",
        "source_drop": "drop_idea01",
        "domain": "general",
        "type": "idea",
        "goal": "What if Atlas exposed a vector endpoint",
        "status": "stalled",
        "nodes": [
            _node("N1", "done", title="Summarize the idea"),
            _node("N2", "waiting", title="Link to owning project"),
        ],
        "entity_refs": ["PROJECT-ATLAS"],
        "links": [],
    }


FIXTURES = [
    ("animal/needs_human", fixture_animal_needs_human(), "approval_required", "urgent"),
    ("build/complete", fixture_build_problem_complete(), "completion", "urgent"),
    ("money/failed", fixture_money_task_failed(), "error", "normal"),
    ("general/stalled", fixture_general_idea_stalled(), "blocked", "low"),
]


# ---------------------------------------------------------------------------
# Structural validator (no external deps)
# ---------------------------------------------------------------------------

def structural_check(sig: dict) -> list[str]:
    errs: list[str] = []
    for k in REQUIRED_TOP:
        if k not in sig:
            errs.append(f"missing required top key {k}")
    if sig.get("schema_version") != "1.0":
        errs.append(f"schema_version must be '1.0', got {sig.get('schema_version')!r}")
    if sig.get("source_layer") not in VALID_SOURCE_LAYERS:
        errs.append(f"source_layer {sig.get('source_layer')!r} not in enum")
    if sig.get("signal_type") not in VALID_SIGNAL_TYPES:
        errs.append(f"signal_type {sig.get('signal_type')!r} not in enum")
    if sig.get("priority") not in VALID_PRIORITIES:
        errs.append(f"priority {sig.get('priority')!r} not in enum")

    payload = sig.get("payload") or {}
    for k in REQUIRED_PAYLOAD:
        if k not in payload:
            errs.append(f"payload missing required key {k}")

    # task_id must be a str or None (never absent)
    if "task_id" in payload and payload["task_id"] is not None:
        if not isinstance(payload["task_id"], str):
            errs.append(f"payload.task_id must be str, got {type(payload['task_id']).__name__}")

    # payload.data sub-field presence and basic type checks
    data = payload.get("data")
    if not isinstance(data, dict):
        errs.append("payload.data must be a dict")
    else:
        for k in REQUIRED_PAYLOAD_DATA:
            if k not in data:
                errs.append(f"payload.data missing required key {k}")
        # Type assertions for structured sub-fields
        if "nodes" in data and not isinstance(data["nodes"], list):
            errs.append("payload.data.nodes must be a list")
        if "evidence_refs" in data and not isinstance(data["evidence_refs"], list):
            errs.append("payload.data.evidence_refs must be a list")
        if "entity_refs" in data and not isinstance(data["entity_refs"], list):
            errs.append("payload.data.entity_refs must be a list")
        if "links" in data and not isinstance(data["links"], list):
            errs.append("payload.data.links must be a list")

    # Schema invariant: action_required=true => action_options.minItems >= 1
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
                if opt.get("risk_tier") not in {"low", "medium", "high"}:
                    errs.append(f"action_options[{i}] risk_tier invalid")
    return errs


# ---------------------------------------------------------------------------
# Optional strict jsonschema validation
# ---------------------------------------------------------------------------

def strict_check(sig: dict) -> str | None:
    """Returns None on success, error message on failure, "SKIPPED" if no lib."""
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        return "SKIPPED"
    # Find the schema relative to this file: ../../contracts/schemas/Signal.v1.json
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "..", "contracts", "schemas", "Signal.v1.json"),
        os.path.join(here, "..", "..", "..", "contracts", "schemas", "Signal.v1.json"),
    ]
    schema_path = next((p for p in candidates if os.path.exists(p)), None)
    if not schema_path:
        return "SKIPPED (schema file not found)"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    try:
        jsonschema.validate(instance=sig, schema=schema)
        return None
    except Exception as e:  # jsonschema.ValidationError
        return str(e)[:200]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(verbose: bool = False) -> int:
    print("PKT-005 ATLAS SEAM ACCEPTANCE\n" + "-" * 64)
    print(f"{'fixture':22} {'sig_type':18} {'priority':8} struct strict")
    print("-" * 64)
    all_pass = True
    for label, dag, exp_type, exp_priority in FIXTURES:
        sig = atlas_signal.dag_to_signal(dag)
        errs = structural_check(sig)
        type_ok = sig.get("signal_type") == exp_type
        priority_ok = sig.get("priority") == exp_priority
        struct_ok = not errs and type_ok and priority_ok
        strict = strict_check(sig)
        strict_marker = "OK" if strict is None else ("SKIP" if strict and strict.startswith("SKIPPED") else "FAIL")

        if not struct_ok:
            all_pass = False
        if strict and not strict.startswith("SKIPPED") and strict is not None:
            all_pass = False

        print(f"{label:22} {sig['signal_type']:18} {sig['priority']:8} "
              f"{'OK' if struct_ok else 'FAIL':6} {strict_marker}")
        if verbose or not struct_ok:
            if errs:
                for e in errs:
                    print(f"    struct err: {e}")
            if not type_ok:
                print(f"    expected signal_type={exp_type}, got {sig.get('signal_type')}")
            if not priority_ok:
                print(f"    expected priority={exp_priority}, got {sig.get('priority')}")
            if strict and strict != "SKIPPED" and strict is not None and not strict.startswith("SKIPPED"):
                print(f"    strict err: {strict}")

    print("-" * 64)
    print(("PKT-005 GATE: PASS" if all_pass else "PKT-005 GATE: FAIL"))
    return 0 if all_pass else 1


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv
    raise SystemExit(run(verbose))
