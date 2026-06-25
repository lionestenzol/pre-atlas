"""Chain Runner (Brick 4) — the DAISY-CHAIN staged-prompt protocol.

A *chain* is a staged prompt sequence that is wired up IN ADVANCE and fires on a
schedule or a state condition. When it fires it:

  1. runs each step's prompt against a set of TARGET DAGs/nodes selected from
     current state (``select_targets``),
  2. assembles a REPORT record (one per firing) and appends it to
     ``chain_reports.jsonl`` (the storage.py:35 append-only audit pattern),
  3. then EXECUTES a single ``on_report`` action that CHANGES REAL STATE — drops
     a follow-up, completes a node, or emits a Signal.v1.

The headline capability this closes: "string together prompts that fire on a
schedule/condition, verify tasks, produce a report, then TAKE ACTIONS based on
the report." Steps 1-2 are the report; step 3 is the action. The proof in
test_chains.py is report -> action: a follow-up drop/node that did not exist
before now exists, or a target node flipped to done.

PROTOCOL (chains/*.json). Each chain::

    {
      "id": str,
      "trigger": {"on": "cron"|"condition", "expr": <cron-str>|<target-query>},
      "steps": [
         {"prompt": str, "target_query": <query>, "expect": "non_empty"|"any"}
      ],
      "on_report": {"action": "drop"|"complete_node"|"emit_signal", "params": {}}
    }

A ``target_query`` reuses the /api/dags filter logic (server.py:143-146,
``domain`` + ``status``) and adds two chain predicates: ``older_than_days`` (on
the DAG's ``created_at``, graph_engine.py:96) and ``has_ready_node`` (a node in
``ready`` status). Selection is a pure function of (query, now); it never reads
the wall clock — ``now`` is passed in, mirroring the determinism rule in
clock.py:14 / scheduler.py:9.

REUSE MAP (assemble-first; ~/.claude/rules/common/assemble-first.md):
  - trigger evaluation  -> scheduler.cron_due (scheduler.py:68) for cron;
                           select_targets non-empty for condition.
  - prompt execution    -> llm.call_json when an api key is live (llm.py:70),
                           else a deterministic heuristic draft (NO key needed),
                           so every step is testable offline (llm.py:1-8 design).
  - action 'drop'       -> intake.chain_intake (intake.py:33), the SAME bouncer
                           the HTTP/CLI drop paths use.
  - action 'complete_node' -> dag_update.apply_review (dag_update.py:20), the
                           SAME advance step the mark-off endpoint uses
                           (server.py:295-297).
  - action 'emit_signal'   -> atlas_signal.dag_to_signal + emit_signal
                           (atlas_signal.py:88 / atlas_signal.py:308).

Action kinds are a CLOSED enum (~/.claude/rules/common/coding-style.md). The
runner validates membership up front and dispatches by kind; an unknown kind is
a load-time error, not a silent skip.
"""

from __future__ import annotations

import datetime as _dt
import glob
import json
import os
import uuid
from typing import Any

from . import (
    atlas_signal,
    clock,
    dag_update,
    intake,
    llm,
    scheduler,
    storage,
)

#: Closed set of on_report action kinds. Each maps to an existing entrypoint.
ACTION_KINDS: frozenset[str] = frozenset({"drop", "complete_node", "emit_signal"})

#: Closed set of trigger kinds.
TRIGGER_KINDS: frozenset[str] = frozenset({"cron", "condition"})

#: Append-only audit log of chain firings (one record per run_chain firing).
CHAIN_REPORTS = "chain_reports.jsonl"

#: Directory holding chain definitions, resolved relative to the service root
#: (services/droplist/chains/), independent of the data dir so chains are code,
#: not state. Overridable for tests via DROPLIST_CHAINS_DIR.
_DEFAULT_CHAINS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chains"
)


# ---------------------------------------------------------------------------
# Loading + validation (fail-loud at the boundary; coding-style.md)
# ---------------------------------------------------------------------------


def chains_dir() -> str:
    return os.environ.get("DROPLIST_CHAINS_DIR", _DEFAULT_CHAINS_DIR)


def validate_chain(chain: dict[str, Any]) -> dict[str, Any]:
    """Validate one chain definition, returning it unchanged on success.

    Every chain needs a string ``id``, a ``trigger`` whose ``on`` is in
    TRIGGER_KINDS (with a croniter-valid ``expr`` when ``on == 'cron'``), a list
    of ``steps``, and an ``on_report`` whose ``action`` is in ACTION_KINDS.
    """
    cid = chain.get("id")
    if not isinstance(cid, str) or not cid:
        raise ValueError(f"chain missing string id: {chain!r}")

    trigger = chain.get("trigger") or {}
    on = trigger.get("on")
    if on not in TRIGGER_KINDS:
        raise ValueError(
            f"chain {cid!r} trigger.on {on!r} not in {sorted(TRIGGER_KINDS)}"
        )
    if on == "cron" and not scheduler.is_valid_cron(trigger.get("expr", "")):
        raise ValueError(
            f"chain {cid!r} has invalid cron expr: {trigger.get('expr')!r}"
        )
    if on == "condition" and not isinstance(trigger.get("expr"), dict):
        raise ValueError(
            f"chain {cid!r} condition trigger.expr must be a target-query dict"
        )

    if not isinstance(chain.get("steps"), list):
        raise ValueError(f"chain {cid!r} steps must be a list")
    for i, step in enumerate(chain["steps"]):
        if not isinstance(step, dict) or "prompt" not in step:
            raise ValueError(f"chain {cid!r} step[{i}] missing 'prompt'")

    on_report = chain.get("on_report") or {}
    action = on_report.get("action")
    if action not in ACTION_KINDS:
        raise ValueError(
            f"chain {cid!r} on_report.action {action!r} not in {sorted(ACTION_KINDS)}"
        )
    return chain


def load_chains(path: str | None = None) -> list[dict[str, Any]]:
    """Load and validate every chains/*.json definition.

    Returns ``[]`` when the directory is absent (an un-provisioned deployment
    has no chains — a valid empty state, mirroring scheduler.load_schedules,
    scheduler.py:153). A malformed file raises via ``validate_chain`` so a typo
    cannot silently disable a chain.
    """
    d = path or chains_dir()
    if not os.path.isdir(d):
        return []
    out: list[dict[str, Any]] = []
    for fp in sorted(glob.glob(os.path.join(d, "*.json"))):
        with open(fp, encoding="utf-8") as f:
            chain = json.load(f)
        out.append(validate_chain(chain))
    return out


# ---------------------------------------------------------------------------
# Target selection — reuses the /api/dags filter logic (server.py:143-146)
# ---------------------------------------------------------------------------


def _dag_dir() -> str:
    return os.path.join(storage.DATA_DIR, "dags")


def _has_ready_node(dag: dict[str, Any]) -> bool:
    return any(n.get("status") == "ready" for n in dag.get("nodes", []))


def _older_than_days(dag: dict[str, Any], days: float, now: _dt.datetime) -> bool:
    """True iff the DAG's ``created_at`` is more than ``days`` before ``now``.

    ``now`` is passed in (never read from the wall clock) so the predicate is
    deterministic under DROPLIST_NOW. ``created_at`` is the ISO stamp graph
    engine writes (graph_engine.py:96); a DAG with no/unparseable stamp is
    treated as NOT old (conservative — a chain won't act on an undated DAG).
    """
    created = clock.parse(dag.get("created_at", ""))
    if created is None:
        return False
    return (now - created) > _dt.timedelta(days=days)


def select_targets(
    target_query: dict[str, Any], now: _dt.datetime
) -> list[dict[str, Any]]:
    """Return the DAGs matching ``target_query`` from current stored state.

    Reuses the /api/dags filter contract (server.py:143-146): ``domain`` and
    ``status`` are equality filters on the loaded DAG. Two chain-specific
    predicates extend it:
      - ``older_than_days``: DAG ``created_at`` older than N days (vs ``now``).
      - ``has_ready_node``:  at least one node in ``ready`` status.

    Pure function of (query, current dags-dir, now). DAGs are returned in sorted
    filename order (stable, no churn), matching list_dags (server.py:139).
    """
    domain = target_query.get("domain")
    status = target_query.get("status")
    older = target_query.get("older_than_days")
    want_ready = target_query.get("has_ready_node")

    out: list[dict[str, Any]] = []
    d = _dag_dir()
    if not os.path.isdir(d):
        return out
    for fp in sorted(glob.glob(os.path.join(d, "*.json"))):
        dag = storage.load_dag(os.path.basename(fp)[:-5])
        if not dag:
            continue
        if domain is not None and dag.get("domain") != domain:
            continue
        if status is not None and dag.get("status") != status:
            continue
        if older is not None and not _older_than_days(dag, float(older), now):
            continue
        if want_ready and not _has_ready_node(dag):
            continue
        out.append(dag)
    return out


# ---------------------------------------------------------------------------
# Trigger evaluation
# ---------------------------------------------------------------------------


def is_due(
    chain: dict[str, Any], now: _dt.datetime, last_run: _dt.datetime | None
) -> bool:
    """Evaluate a chain's trigger at ``now``.

    - ``cron``: delegate to scheduler.cron_due (scheduler.py:68) over the
      (last_run, now] window — the same temporal-selection core the scheduler
      uses, so cron semantics are identical to Brick 3.
    - ``condition``: fire iff ``select_targets(trigger.expr, now)`` is non-empty,
      i.e. there is currently work matching the predicate.

    ``now`` is always supplied by the caller; nothing here reads the real clock.
    """
    trigger = chain.get("trigger") or {}
    on = trigger.get("on")
    if on == "cron":
        return scheduler.cron_due(trigger["expr"], now, last_run)
    if on == "condition":
        return len(select_targets(trigger.get("expr") or {}, now)) > 0
    raise ValueError(f"unknown trigger kind: {on!r}")


# ---------------------------------------------------------------------------
# Prompt execution (heuristic fallback — NO api key needed)
# ---------------------------------------------------------------------------


def _run_prompt(prompt: str, targets: list[dict[str, Any]]) -> str:
    """Run one step's prompt against its selected targets, returning draft text.

    When a live Anthropic backend is available (llm.anthropic_available(),
    llm.py:58) the real model drafts the text; otherwise a DETERMINISTIC
    heuristic produces it. The heuristic path is what makes a chain provable
    with NO api key — the whole zero-key design intent of llm.py:1-8.

    The heuristic is intentionally simple and transparent: it names each target
    DAG, its goal, and its ready nodes. That is enough to (a) be non-empty so the
    ``expect: non_empty`` gate passes, and (b) carry real, inspectable content
    into the report and the follow-up drop.
    """
    if llm.anthropic_available():
        ctx = json.dumps(
            [
                {
                    "dag_id": t.get("dag_id"),
                    "goal": t.get("goal", ""),
                    "ready_nodes": [
                        n.get("title", n.get("id"))
                        for n in t.get("nodes", [])
                        if n.get("status") == "ready"
                    ],
                }
                for t in targets
            ]
        )
        data = llm.call_json(
            purpose="chain_step",
            system="You draft a short, direct nudge. Reply as JSON {\"text\": str}.",
            user=f"{prompt}\n\nTargets:\n{ctx}",
            input_hash=str(uuid.uuid4()),
        )
        if data and isinstance(data.get("text"), str) and data["text"].strip():
            return data["text"].strip()
        # fall through to heuristic on any model failure (llm.call_json -> None)

    lines = [f"{prompt}"]
    for t in targets:
        ready = [
            n.get("title", n.get("id"))
            for n in t.get("nodes", [])
            if n.get("status") == "ready"
        ]
        ready_txt = "; ".join(ready) or "(no ready node)"
        lines.append(
            f"- {t.get('dag_id')}: {t.get('goal', '')} "
            f"[ready: {ready_txt}]"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# on_report actions — each CHANGES REAL STATE (the load-bearing half)
# ---------------------------------------------------------------------------


def _action_drop(
    report: dict[str, Any], params: dict[str, Any]
) -> dict[str, Any]:
    """Create a follow-up drop from the report via intake.chain_intake.

    Reuses the SAME bouncer the HTTP/CLI drop paths use (intake.py:33), so the
    follow-up is deduped/secured identically. The drop text is the report's
    assembled draft, prefixed for provenance.
    """
    prefix = params.get("title_prefix", "Chain follow-up")
    body = report.get("draft") or report.get("chain_id", "chain")
    raw = f"{prefix}: {body}"
    res = intake.chain_intake(raw)
    return {"action": "drop", **res}


def _action_complete_node(
    report: dict[str, Any], params: dict[str, Any]
) -> dict[str, Any]:
    """Mark a target node done via dag_update.apply_review (dag_update.py:20).

    Applies to the first target DAG in the report. Reuses the SAME advance step
    the mark-off endpoint uses (server.py:295-297): set the node done, attach a
    result, wake dependents whose deps are satisfied, flip dag.status. Idempotent
    on an already-done node (apply_review just re-affirms).
    """
    targets = report.get("target_dags") or []
    if not targets:
        return {"action": "complete_node", "status": "no_target"}
    node_id = params.get("node_id")
    dag_id = targets[0]
    dag = storage.load_dag(dag_id)
    if not dag:
        return {"action": "complete_node", "status": "dag_missing", "dag_id": dag_id}
    node = next(
        (n for n in dag["nodes"]
         if (node_id is None and n["status"] == "ready") or n["id"] == node_id),
        None,
    )
    if node is None:
        return {"action": "complete_node", "status": "node_missing", "dag_id": dag_id}

    result = {
        "by": "chain",
        "note": f"auto-completed by chain {report.get('chain_id')}",
        "evidence": [f"chain_report:{report.get('report_id')}"],
        "result": report.get("draft", ""),
        "at": clock.now_iso(),
    }
    review = {"mark_node_as": "done", "approved_new_nodes": []}
    updates = dag_update.apply_review(dag, node, result, review)
    storage.save_dag(dag)
    storage.append(storage.DAG_EVENTS, {
        "event": "node_completed", "dag_id": dag_id, "node_id": node["id"],
        "by": "chain", "at": clock.now_iso(), "updates": updates,
    })
    return {
        "action": "complete_node", "status": "done",
        "dag_id": dag_id, "node_id": node["id"], "updates": updates,
    }


def _action_emit_signal(
    report: dict[str, Any], params: dict[str, Any]
) -> dict[str, Any]:
    """Emit a Signal.v1 for the first target DAG (atlas_signal.py:88 / :308).

    Maps the DAG to a Signal.v1 dict and POSTs it to DROPLIST_ATLAS_SIGNALS_URL
    when set, the SAME path graph_engine emits on (intake.py:78-83 gate). If the
    URL is unset the signal is still built and recorded in the action result
    (built, not sent) so the chain is observable in test/offline runs.
    """
    targets = report.get("target_dags") or []
    if not targets:
        return {"action": "emit_signal", "status": "no_target"}
    dag = storage.load_dag(targets[0])
    if not dag:
        return {"action": "emit_signal", "status": "dag_missing"}
    signal = atlas_signal.dag_to_signal(dag)
    url = os.environ.get("DROPLIST_ATLAS_SIGNALS_URL", "")
    if not url:
        return {"action": "emit_signal", "status": "built", "signal_id": signal["id"]}
    resp = atlas_signal.emit_signal(signal, url)
    return {
        "action": "emit_signal",
        "status": "sent" if resp.get("ok") else "error",
        "signal_id": signal["id"],
        "response": resp,
    }


_ACTION_DISPATCH = {
    "drop": _action_drop,
    "complete_node": _action_complete_node,
    "emit_signal": _action_emit_signal,
}


# ---------------------------------------------------------------------------
# run_chain — the whole loop: trigger -> steps -> report -> action
# ---------------------------------------------------------------------------


def run_chain(
    chain: dict[str, Any],
    now: _dt.datetime,
    last_run: _dt.datetime | None = None,
) -> dict[str, Any]:
    """Evaluate ``chain`` at ``now``; if firing, run steps, write a report, and
    execute the on_report action.

    Returns a dict ``{chain_id, fired, report_id?, actions_taken}``. When the
    trigger does not fire, returns ``{fired: False}`` and writes NOTHING — a
    chain that does not fire changes no state (proved by
    test_run_chain_not_due_is_noop).

    ``now`` is supplied by the caller (clock-free; clock.py:14 / scheduler.py:9).
    """
    validate_chain(chain)
    if not is_due(chain, now, last_run):
        return {"chain_id": chain["id"], "fired": False, "actions_taken": []}

    # 1. run each step's prompt against its selected targets.
    step_records: list[dict[str, Any]] = []
    all_target_ids: list[str] = []
    draft_parts: list[str] = []
    for step in chain["steps"]:
        targets = select_targets(step.get("target_query") or {}, now)
        draft = _run_prompt(step.get("prompt", ""), targets)
        expect = step.get("expect", "any")
        ok = bool(draft.strip()) if expect == "non_empty" else True
        tids = [t.get("dag_id") for t in targets]
        for tid in tids:
            if tid not in all_target_ids:
                all_target_ids.append(tid)
        if draft:
            draft_parts.append(draft)
        step_records.append({
            "prompt": step.get("prompt", ""),
            "targets": tids,
            "draft": draft,
            "expect": expect,
            "ok": ok,
        })

    # 1b. A chain only ACTS when its steps actually found work AND met their
    # expectations. A cron window firing with zero matching targets must NOT
    # emit a spurious action (e.g. a generic "clarify intent" drop) — that is
    # noise, and DropList's whole posture is one-fact-per-row, no noise. The
    # per-step `ok` gate and `all_target_ids` were computed but never consulted,
    # so the action fired unconditionally once the trigger was due. We leave the
    # cron window UNCONSUMED (write nothing) so the chain re-checks on the next
    # tick and fires the instant real work appears in the window.
    # Bug found by the SMOKE_AND_DOD.md §C break run; fixed inline 2026-06-25.
    # See ~/.claude/rules/common/code-as-furniture.md — no broken code left in place.
    gates_passed = all(r["ok"] for r in step_records)
    if not all_target_ids or not gates_passed:
        return {
            "chain_id": chain["id"],
            "fired": False,
            "reason": "no_targets" if not all_target_ids else "step_expectation_unmet",
            "actions_taken": [],
        }

    # 2. assemble + persist the report (storage.py:35 append-only audit).
    report_id = "chrep_" + uuid.uuid4().hex[:12]
    report = {
        "report_id": report_id,
        "chain_id": chain["id"],
        "fired": True,
        "at": clock.now_iso(),
        "target_dags": all_target_ids,
        "draft": "\n\n".join(draft_parts),
        "steps": step_records,
    }

    # 3. execute the on_report action — the half that CHANGES STATE.
    on_report = chain["on_report"]
    action_kind = on_report["action"]
    action_fn = _ACTION_DISPATCH[action_kind]
    action_result = action_fn(report, on_report.get("params") or {})
    report["action_result"] = action_result

    storage.append(CHAIN_REPORTS, report)
    storage.log_run(
        tool="chain_runner",
        command=f"run_chain:{chain['id']}",
        goal="daisy-chain staged-prompt firing",
        result_summary=(
            f"targets={len(all_target_ids)} action={action_kind} "
            f"status={action_result.get('status')}"
        ),
    )
    return {
        "chain_id": chain["id"],
        "fired": True,
        "report_id": report_id,
        "actions_taken": [action_result],
    }


# ---------------------------------------------------------------------------
# Daemon tick hook — run every due chain on a --once cycle (daemon.py:75)
# ---------------------------------------------------------------------------


def tick(now: _dt.datetime | None = None) -> dict[str, Any]:
    """Run every loaded chain that is due at ``now``.

    Called from daemon._run_once (daemon.py:75) so an always-on daemon advances
    chains alongside DAGs. ``last_run`` for cron chains is reconstructed from the
    last firing recorded in chain_reports.jsonl (the append-only log IS the
    bookkeeping — no separate state file), so a fire is not repeated within one
    cron window. Reads the clock once (clock.py:13) when ``now`` is not supplied.
    """
    when = now or clock.now()
    last_run_by_chain = _last_run_map()
    fired: list[dict[str, Any]] = []
    for chain in load_chains():
        res = run_chain(chain, when, last_run=last_run_by_chain.get(chain["id"]))
        if res.get("fired"):
            fired.append(res)
    return {"at": clock.now_iso(), "fired": fired}


def _last_run_map() -> dict[str, _dt.datetime]:
    """Most-recent firing time per chain id, from chain_reports.jsonl.

    The append-only report log doubles as last_run bookkeeping (no second state
    file to drift). A report's ``at`` is the firing instant; the latest per chain
    closes that cron window so the daemon does not re-fire within it.
    """
    out: dict[str, _dt.datetime] = {}
    for rec in storage.read_all(CHAIN_REPORTS):
        cid = rec.get("chain_id")
        ts = clock.parse(rec.get("at", ""))
        if cid is None or ts is None:
            continue
        if cid not in out or ts > out[cid]:
            out[cid] = ts
    return out
