"""Daemon: DropList as a living entity.

A persistent, clock-driven runner that turns DropList from request-driven into
self-advancing. On each pass it:

  1. watcher.tick() — materializes due recurring nodes + flags stale/blocked/
     failed (watcher.py:62).
  2. advances every stored DAG that has a runnable ready node through the EXACT
     existing engine path (graph_engine.advance_dag, which reuses
     node_router.execute / node_reviewer.review / dag_update.apply_review).

This closes the real gap Brick 2 targets: today a recurring DAG materializes
with one `ready` node (dag_builder._node default status='ready') but NOTHING
dispatches it. The daemon's tick does.

Two surfaces, ONE loop body (`_run_once`), so there is no second code path to
rot (~/.claude/rules/common/code-as-furniture.md):
  - PRIMARY:  `python -m droplist.daemon [--once] [--interval N]` — the
    testable, cron-drivable, HTTP-free entity. Brick 3's cron calls `--once`.
  - SECONDARY: a FastAPI startup hook in server.py, gated by DROPLIST_DAEMON=1,
    spawns run_loop on a daemon thread so an always-on `droplist-ui` process is
    self-advancing without a separate cron entry.

LIBRARY DECISION (~/.claude/rules/common/assemble-first.md): the loop cadence is
a hand-rolled `while True: _run_once(); time.sleep(interval)`. APScheduler 3.11.2
IS installed, but its scheduler thread uses wall-clock and does NOT consult
clock.now() — it would bypass the DROPLIST_NOW determinism that test_persist.py
and test_daemon.py depend on. Here a scheduler library makes it WORSE, not just
later, so the 6-line sleep loop is the real answer. Richer recurrence than the
existing per-day semantics (weekly/monthly/cron) is out of scope for this brick;
croniter (on PyPI, not yet installed) is the named candidate when it lands.
"""

from __future__ import annotations

import argparse
import time

from . import chain_runner, clock, dispatcher, graph_engine, storage, watcher

#: DAG statuses worth re-driving on a tick. A 'complete'/'failed'/'needs_human'
#: DAG has nothing runnable; 'running' (fresh) and 'stalled' (settled with a
#: pending ready/waiting node) are the live ones. get_ready_nodes is still the
#: real gate — this set just skips the obviously-terminal DAGs cheaply.
_ADVANCEABLE_STATUSES = frozenset({"running", "stalled"})

_DEFAULT_INTERVAL = 300.0


def _advance_stored_dags() -> list[dict]:
    """Advance every stored DAG that has a runnable ready node.

    Returns a per-DAG delta list ({dag_id, advanced, settled}) for DAGs that
    actually moved this pass. DAGs with no runnable node are skipped (no churn).
    """
    advanced: list[dict] = []
    for dag in watcher._all_dags():  # reuse the dags-dir walk (watcher.py:49)
        if dag.get("status") not in _ADVANCEABLE_STATUSES:
            continue
        if not dispatcher.get_ready_nodes(dag):
            continue
        delta = graph_engine.advance_dag(dag)
        graph_engine._finalize(dag)  # re-derive dag.status off the new node states
        storage.save_dag(dag)
        if delta["advanced"]:
            advanced.append({
                "dag_id": dag["dag_id"],
                "advanced": delta["advanced"],
                "settled": delta["settled"],
                "status": dag["status"],
            })
    return advanced


def _run_once() -> dict:
    """One full tick: materialize + flag (watcher.tick) THEN advance runnable
    DAGs, so a freshly-materialized recurring DAG is advanced in the SAME pass
    rather than waiting a full cycle.

    Returns a report folding the watcher.tick() report (watcher.py:79) with the
    daemon's advancement delta. Writes a 'daemon_tick' audit record and a
    run-memory summary so no tick evaporates (storage.py:35 / storage.py:96).
    """
    tick = watcher.tick()
    advanced = _advance_stored_dags()
    # Brick 4: run every due daisy-chain this pass (trigger -> steps -> report ->
    # action). Fail-soft so a chain fault never sinks the whole tick
    # (~/.claude/rules/common/code-as-furniture.md). chain_runner.tick reads the
    # clock once and reconstructs per-chain last_run from chain_reports.jsonl.
    try:
        chains = chain_runner.tick()
    except Exception:  # noqa: BLE001 — a chain fault must not break the DAG tick
        chains = {"at": clock.now_iso(), "fired": []}

    report: dict = {
        "at": clock.now_iso(),
        "recurring_materialized": tick["recurring_materialized"],
        "advanced": advanced,
        "chains_fired": chains["fired"],
        "stale": tick["stale"],
        "blocked_resurfaced": tick["blocked_resurfaced"],
        "escalations": tick["escalations"],
    }

    storage.append(storage.DAG_EVENTS, {
        "event": "daemon_tick",
        "at": report["at"],
        "materialized": len(report["recurring_materialized"]),
        "advanced": len(advanced),
        "chains_fired": len(report["chains_fired"]),
        "stale": len(report["stale"]),
        "escalations": len(report["escalations"]),
    })
    storage.log_run(
        tool="daemon", command="daemon._run_once", goal="self-advance tick",
        result_summary=(
            f"materialized={len(report['recurring_materialized'])} "
            f"advanced={len(advanced)} chains={len(report['chains_fired'])} "
            f"stale={len(report['stale'])} "
            f"escalations={len(report['escalations'])}"),
    )
    return report


def run_loop(interval: float = _DEFAULT_INTERVAL) -> None:
    """Hand-rolled clock-driven loop: _run_once() then sleep(interval), forever.

    KeyboardInterrupt-clean (no traceback). Each pass calls _run_once() which
    reads the clock fresh, so DROPLIST_NOW (clock.py:14) still governs every
    tick — a wall-clock scheduler library would not. See module docstring for
    the assemble-first rationale.
    """
    try:
        while True:
            _run_once()
            time.sleep(interval)
    except KeyboardInterrupt:
        return


def _summary_line(report: dict) -> str:
    return (
        f"daemon tick {report['at']}  "
        f"materialized={len(report['recurring_materialized'])} "
        f"advanced={len(report['advanced'])} "
        f"chains={len(report['chains_fired'])} "
        f"stale={len(report['stale'])} "
        f"escalations={len(report['escalations'])}")


def build_parser() -> argparse.ArgumentParser:
    """Mirror cli.py:467 build_parser style."""
    p = argparse.ArgumentParser(
        prog="droplist-daemon",
        description="DropList self-advancing daemon (watcher tick + DAG advance)")
    p.add_argument("--once", action="store_true",
                   help="run exactly one tick then exit (Brick 3 cron entrypoint)")
    p.add_argument("--interval", type=float, default=_DEFAULT_INTERVAL,
                   help=f"loop sleep seconds (default {int(_DEFAULT_INTERVAL)})")
    p.add_argument("--no-color", action="store_true",
                   help="disable ANSI color (parity with cli.py; daemon output is plain)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.once:
        report = _run_once()
        print(_summary_line(report))
        return 0
    print(f"droplist-daemon: loop every {int(args.interval)}s — Ctrl-C to stop")
    run_loop(interval=args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
