"""Tool Router (MVP 3): the arms. Five tools, all safe by construction.

Doctrine enforced here:
  - no tool action without a node (the loop only calls run_tool on a node)
  - a tool RUN produces a receipt = evidence; it does NOT mark the node done
  - DONE_CHECKERS verify the node's done_condition against the evidence;
    only the reviewer, using these, can pass a node

Safety:
  calendar / message_drafter / n8n  -> draft/stub/dry-run, never touch the real
    world (no real reminders created, nothing sent). n8n POSTs only if
    DROPLIST_N8N_URL is set AND reachable, else returns a dry-run receipt.
  file_writer -> writes ONLY under data/results/ (sandboxed path).
  script_runner -> allowlist only (project test_*.py / echo), no shell, timeout.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid

from . import storage


def _receipt(node, status, output, tool_input=None):
    return {
        "tool_run_id": "TR-" + uuid.uuid4().hex[:8],
        "node_id": node["id"],
        "tool_type": node["tool_type"],
        "action": node.get("tool_action", ""),
        "input": tool_input or {},
        "status": status,                       # success | failed | blocked | dry_run
        "output": output,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---- tools -----------------------------------------------------------------

def _calendar(node, dag):
    """Stub: drafts a reminder receipt. Never creates a real reminder."""
    msg = f"Recheck: {dag.get('goal', node['title'])}"
    out = {"reminder_id": "REM-" + uuid.uuid4().hex[:6], "message": msg,
           "time": "in 3 hours", "note": "DRAFT only — not added to real calendar"}
    return _receipt(node, "success", out, {"message": msg, "time": "in 3 hours"})


def _file_writer(node, dag):
    """Writes a results file under data/results/ only. Links back to the DAG."""
    d = storage.results_dir()
    fname = f"{dag['dag_id']}_{node['id']}.md"
    path = os.path.join(d, fname)
    body = (f"# {node['title']}\n\n"
            f"source_dag: {dag['dag_id']}\n"
            f"source_drop: {dag['source_drop']}\n"
            f"goal: {dag['goal']}\n\n"
            f"drop: {dag['raw_input']}\n")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        return _receipt(node, "success", {"path": path, "bytes": len(body)},
                        {"summary_text": node["title"]})
    except OSError as e:
        return _receipt(node, "failed", {"error": str(e)})


def _message_drafter(node, dag):
    """Drafts a message. Never sends."""
    body = (f"Re: {dag['goal']}\n\n"
            f"Context: {dag['raw_input'][:200]}\n"
            f"(draft — review before sending)")
    return _receipt(node, "success",
                    {"draft": body, "channel": "draft", "sent": False},
                    {"body": body})


def _n8n_webhook(node, dag):
    """POSTs to DROPLIST_N8N_URL if set+reachable; otherwise a dry-run receipt."""
    payload = {"node_id": node["id"], "dag_id": dag["dag_id"],
               "workflow": node.get("tool_action", ""),
               "summary": dag["goal"], "drop_id": dag["source_drop"]}
    url = os.environ.get("DROPLIST_N8N_URL")
    if not url:
        return _receipt(node, "success",
                        {"external_ref": "dryrun-" + uuid.uuid4().hex[:6],
                         "message": "no DROPLIST_N8N_URL set — dry run",
                         "would_send": payload}, payload)
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"raw": raw[:200]}
        ext = data.get("external_ref") or data.get("id") or "n8n-" + uuid.uuid4().hex[:6]
        return _receipt(node, "success", {"external_ref": ext, "response": data}, payload)
    except (urllib.error.URLError, OSError) as e:
        return _receipt(node, "failed", {"error": str(e), "url": url}, payload)


# Adding a new prefix? Audit the corresponding dag_builder tool_action for
# Windows-shim portability: shutil.which() returning a .BAT path is NOT proof
# the bare name is invocable via subprocess.run([name, ...]). The
# `_resolve_python_literal` helper in dag_builder.py shows the invocation-probe
# pattern. See PKT-002 / PKT-003 / PKT-004 / OQ-15.
_SAFE_SCRIPT_PREFIXES = ("python3 test_", "python test_", "echo ")


def _script_runner(node, dag):
    """Runs ONLY allowlisted project commands, no shell, with a timeout."""
    cmd = node.get("tool_action", "").strip()
    if not any(cmd.startswith(p) for p in _SAFE_SCRIPT_PREFIXES):
        return _receipt(node, "blocked",
                        {"reason": "command not on allowlist", "command": cmd})
    try:
        proc = subprocess.run(cmd.split(), capture_output=True, text=True,
                              timeout=120, cwd=os.getcwd())
        tail = (proc.stdout or "")[-400:]
        return _receipt(node, "success" if proc.returncode == 0 else "failed",
                        {"returncode": proc.returncode, "stdout_tail": tail},
                        {"command": cmd})
    except subprocess.TimeoutExpired:
        return _receipt(node, "failed", {"error": "timeout", "command": cmd})


_DEFAULT_SEARCH_STACK_URL = "http://127.0.0.1:3070/search"


def _external_search(node, dag):
    """Queries services/search-stack and returns top results in the receipt.

    tool_action shape: free-text query (defaults to the dag goal if empty).
    Reads SEARCH_STACK_URL env var; falls back to localhost:3070. If the service
    is unreachable, returns a blocked receipt (not failed) so retries are cheap.
    """
    query = (node.get("tool_action") or "").strip() or dag.get("goal", "")
    if not query:
        return _receipt(node, "blocked", {"reason": "no query"}, {})
    url = os.environ.get("SEARCH_STACK_URL", _DEFAULT_SEARCH_STACK_URL)
    payload = {"q": query, "max_results": 5}
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        return _receipt(node, "blocked",
                        {"reason": "search-stack unreachable", "error": str(e)[:200]},
                        payload)
    results = data.get("results") or []
    summary = [
        {"title": r.get("title", ""), "url": r.get("url", ""),
         "snippet": (r.get("snippet") or "")[:200], "source": r.get("source", "")}
        for r in results
    ]
    return _receipt(node, "success",
                    {"n_results": len(summary), "results": summary,
                     "providers_used": data.get("providers_used", [])},
                    payload)


TOOL_REGISTRY = {
    "calendar": _calendar,
    "file_writer": _file_writer,
    "message_drafter": _message_drafter,
    "n8n_webhook": _n8n_webhook,
    "script_runner": _script_runner,
    "external_search": _external_search,
}


def run_tool(node, dag) -> dict:
    fn = TOOL_REGISTRY.get(node["tool_type"])
    if fn is None:
        receipt = _receipt(node, "failed", {"error": f"unknown tool {node['tool_type']}"})
    else:
        receipt = fn(node, dag)
    storage.append(storage.TOOL_RUNS, {"dag_id": dag["dag_id"], **receipt})
    return receipt


# ---- done-condition verifiers ---------------------------------------------
# These decide whether EVIDENCE satisfies the node's done_condition.

def _check_calendar(node, receipt, dag):
    o = receipt.get("output", {})
    return receipt["status"] == "success" and bool(o.get("message")) and bool(o.get("time"))


def _check_file_writer(node, receipt, dag):
    o = receipt.get("output", {})
    path = o.get("path")
    if receipt["status"] != "success" or not path or not os.path.exists(path):
        return False
    try:
        return dag["dag_id"] in open(path, encoding="utf-8").read()
    except OSError:
        return False


def _check_message_drafter(node, receipt, dag):
    o = receipt.get("output", {})
    return receipt["status"] == "success" and bool(o.get("draft"))


def _check_n8n(node, receipt, dag):
    o = receipt.get("output", {})
    return receipt["status"] == "success" and bool(o.get("external_ref"))


def _check_script_runner(node, receipt, dag):
    o = receipt.get("output", {})
    return receipt["status"] == "success" and o.get("returncode") == 0


def _check_external_search(node, receipt, dag):
    o = receipt.get("output", {})
    return receipt["status"] == "success" and int(o.get("n_results") or 0) > 0


DONE_CHECKERS = {
    "calendar": _check_calendar,
    "file_writer": _check_file_writer,
    "message_drafter": _check_message_drafter,
    "n8n_webhook": _check_n8n,
    "script_runner": _check_script_runner,
    "external_search": _check_external_search,
}


def done_condition_met(node, receipt, dag) -> bool:
    checker = DONE_CHECKERS.get(node["tool_type"])
    return bool(checker and checker(node, receipt, dag))
