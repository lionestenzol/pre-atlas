"""DAG Builder (MVP 3): WorkPacket -> execution graph with tool-aware nodes.

Each node now carries tool fields. A node's `done_condition` is what the
reviewer verifies -- a tool running is only *evidence*, never proof on its own.

Node kinds, by tool_type:
  "" / "reasoning"  -> LLM/heuristic agent
  "human"           -> needs the user; the loop marks it awaiting-human, not done
  tool name         -> routed to that tool (calendar/file_writer/script_runner/...)

Node statuses: ready | waiting | done | blocked | failed
"""

from __future__ import annotations

import subprocess
import uuid

from .schema import WorkPacket

NODE_STATUSES = {"ready", "waiting", "done", "blocked", "failed"}


def _resolve_python_literal() -> str:
    """Return the bare command word ('python3' or 'python') that actually runs
    via subprocess on this host. We need a literal word, not a resolved path,
    so the script_runner allowlist (prefix match) still applies.

    shutil.which() returns the full path, which on Windows is often a .BAT shim
    that subprocess.run() cannot exec directly (no shell). The only honest test
    is to try invoking the literal and see if it works.
    See PKT-002 / PKT-003 / OQ-13 / OQ-14.
    """
    for candidate in ("python3", "python"):
        try:
            r = subprocess.run([candidate, "--version"], capture_output=True,
                               timeout=5)
            if r.returncode == 0:
                return candidate
        except (FileNotFoundError, OSError):
            continue
    return "python"  # last-resort fallback; will surface as a script_runner failure


_PYTHON = _resolve_python_literal()


def _node(nid, title, ntype, agent, *, depends_on=None, status="ready",
          tool_type="", tool_action="", inputs_required=None,
          done_condition="", max_retries=2):
    return {
        "id": nid,
        "title": title,
        "type": ntype,
        "status": status,
        "depends_on": depends_on or [],
        "agent": agent,
        "tool_type": tool_type,
        "tool_action": tool_action,
        "inputs_required": inputs_required or [],
        "done_condition": done_condition,
        "result": None,
        "result_refs": [],
        "evidence": [],
        "retry_count": 0,
        "max_retries": max_retries,
    }


def _short(text: str, n: int = 70) -> str:
    return text if len(text) <= n else text[: n - 1] + "\u2026"


def _build_nodes(packet: WorkPacket):
    dom, typ = packet.domain, packet.type
    ent = ", ".join(packet.entities[:3]) if packet.entities else "the subject"
    src = _short(packet.normalized_input)

    if dom == "animal_property":
        goal = f"Check {ent}, schedule a recheck, and log the observation"
        return goal, [
            _node("N1", "Assess risk signs from the description", "diagnosis", "animal_care"),
            _node("N2", "Field checklist: water, shade, airflow, posture", "field_check", "ops",
                  tool_type="human",
                  done_condition="user has reported each check as ok/not-ok"),
            _node("N3", "Draft a reminder to recheck later", "tool_action", "ops",
                  tool_type="calendar", tool_action="create_reminder",
                  inputs_required=["message", "time"],
                  done_condition="reminder receipt has a message and a time"),
            _node("N4", "Log the observation to a results file", "tool_action", "documenter",
                  depends_on=["N1"], status="waiting",
                  tool_type="file_writer", tool_action="write_log",
                  inputs_required=["summary_text"],
                  done_condition="log file exists and links back to the source DAG"),
            _node("N5", "Decide if intervention is needed", "decision", "reviewer",
                  depends_on=["N1", "N3", "N4"], status="waiting",
                  done_condition="one clear decision citing the assessment and log"),
        ]

    if dom == "build_product" and typ == "problem":
        goal = f"Reproduce, scope, and verify a fix for: {src}"
        return goal, [
            _node("N1", "Reproduce with the validation suite", "tool_action", "coder",
                  tool_type="script_runner", tool_action=f"{_PYTHON} test_drops.py",
                  done_condition="validation script exits 0"),
            _node("N2", "Identify the failing case", "investigation", "coder",
                  depends_on=["N1"], status="waiting",
                  done_condition="suspect path named"),
            _node("N3", "Scope the patch (no redesign)", "scope", "coder",
                  depends_on=["N2"], status="waiting",
                  done_condition="bounded change described"),
            _node("N4", "Re-run validation after scoping", "tool_action", "coder",
                  depends_on=["N3"], status="waiting",
                  tool_type="script_runner", tool_action=f"{_PYTHON} test_drops.py",
                  done_condition="validation script exits 0"),
            _node("N5", "Save the audit report", "tool_action", "documenter",
                  depends_on=["N4"], status="waiting",
                  tool_type="file_writer", tool_action="write_report",
                  inputs_required=["summary_text"],
                  done_condition="report file exists and links back to the source DAG"),
        ]

    if dom == "build_product":
        goal = "Capture, route, and place the item without building yet"
        return goal, [
            _node("N1", "Summarize the item in one line", "capture", "documenter"),
            _node("N2", "Draft a note to the project archive", "tool_action", "documenter",
                  depends_on=["N1"], status="waiting",
                  tool_type="message_drafter", tool_action="draft_note",
                  inputs_required=["body"],
                  done_condition="draft has a non-empty body"),
            _node("N3", "Record to the ops log via webhook", "tool_action", "memory",
                  depends_on=["N1"], status="waiting",
                  tool_type="n8n_webhook", tool_action="save_to_log",
                  done_condition="webhook returned success with an external_ref"),
            _node("N4", "Flag for later scoping; do not build", "decision", "reviewer",
                  depends_on=["N2", "N3"], status="waiting",
                  done_condition="one decision; nothing built"),
        ]

    if dom == "money_admin":
        goal = "Extract the item, draft the action, and record it"
        return goal, [
            _node("N1", "Extract entity, date, amount, deadline", "extraction", "finance"),
            _node("N2", "Draft the admin message (no send)", "tool_action", "finance",
                  depends_on=["N1"], status="waiting",
                  tool_type="message_drafter", tool_action="draft_admin",
                  inputs_required=["body"],
                  done_condition="draft has a non-empty body; nothing sent"),
            _node("N3", "Record tracker row via webhook", "tool_action", "ops",
                  depends_on=["N1"], status="waiting",
                  tool_type="n8n_webhook", tool_action="save_tracker_row",
                  done_condition="webhook returned success with an external_ref"),
            _node("N4", "Confirm the next admin action", "decision", "reviewer",
                  depends_on=["N2", "N3"], status="waiting",
                  done_condition="one next action with an owner"),
        ]

    goal = f"Clarify, draft, and record the next move on: {src}"
    return goal, [
        _node("N1", "Clarify the concrete ask", "clarify", "ops"),
        _node("N2", "Draft the message/summary", "tool_action", "documenter",
              depends_on=["N1"], status="waiting",
              tool_type="message_drafter", tool_action="draft_note",
              inputs_required=["body"],
              done_condition="draft has a non-empty body"),
        _node("N3", "Record to the ops log via webhook", "tool_action", "ops",
              depends_on=["N1"], status="waiting",
              tool_type="n8n_webhook", tool_action="save_to_log",
              done_condition="webhook returned success with an external_ref"),
        _node("N4", "Decide the single next move", "decision", "reviewer",
              depends_on=["N2", "N3"], status="waiting",
              done_condition="one next move chosen"),
    ]


def build_dag(packet: WorkPacket) -> dict:
    goal, nodes = _build_nodes(packet)
    return {
        "dag_id": "DAG-" + uuid.uuid4().hex[:8],
        "source_drop": packet.drop_id,
        "domain": packet.domain,
        "type": packet.type,
        "goal": goal,
        "raw_input": packet.normalized_input,
        "nodes": nodes,
        "status": "running",
    }


def validate_dag(dag: dict):
    errs = []
    ids = {n["id"] for n in dag["nodes"]}
    if not dag.get("nodes"):
        errs.append("dag has no nodes")
    for n in dag["nodes"]:
        if n["status"] not in NODE_STATUSES:
            errs.append(f"{n['id']} bad status {n['status']}")
        for dep in n["depends_on"]:
            if dep not in ids:
                errs.append(f"{n['id']} depends on missing node {dep}")
        if n["tool_type"] and n["tool_type"] != "human" and not n["done_condition"]:
            errs.append(f"{n['id']} is a tool node with no done_condition")
    if not any(n["status"] == "ready" for n in dag["nodes"]):
        errs.append("no initially-ready node (graph can never start)")
    return errs
