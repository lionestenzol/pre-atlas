"""MVP 4 acceptance: 7-day persistence simulation across 3 domains.

Uses the controllable clock (DROPLIST_NOW) to advance one day per tick without
waiting. One persistent data dir for all 7 days. Verifies every pass condition.

Run from the project root (script_runner shells out to test_drops.py).
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="mvp4_")
os.environ["DROPLIST_DATA"] = _TMP

from droplist import command_brief, entities, graph_engine, state, storage, watcher  # noqa: E402


def _set_day(d: dt.date, hour=8):
    os.environ["DROPLIST_NOW"] = f"{d.isoformat()}T{hour:02d}:00:00Z"


def run() -> int:
    base = dt.date(2026, 6, 1)
    briefs = []

    # --- Day 0: set up the world ---
    _set_day(base)
    state.lock_ref("SCHEMA-V1", "packet schema frozen at MVP 1")
    state.lock_ref("MVP1-CORE", "core parser done; do not reopen")
    state.add_recurring("Check rabbit water", "animal_property", "daily", "morning",
                        entity_refs=["ANIMAL-RABBITS"],
                        done_condition="water logged for each cage")
    watcher.tick()
    graph_engine.run_graph("The JSONL writer crashes on weird unicode in DropList, the bug breaks the packet file.")
    graph_engine.run_graph("The doe is limping and not eating, hiding in the corner.")
    briefs.append(command_brief.build_brief())

    droplist_dags_day0 = len(entities.get("PROJECT-DROPLIST")["related_dags"]) \
        if entities.get("PROJECT-DROPLIST") else 0

    # --- Days 1..6 ---
    cross_link_seen = False
    reopen_blocked = False
    for i in range(1, 7):
        _set_day(base + dt.timedelta(days=i))
        watcher.tick()  # materialize the day's recurring node
        if i == 3:
            tr = graph_engine.run_graph(
                "Package DropList but do not reopen the heart — choose the interface shell.")
            cross_link_seen = len(tr["links"]) >= 1
            tr2 = graph_engine.run_graph("Let's redo the packet schema from scratch.")
            reopen_blocked = bool(tr2.get("links") is not None) and any(
                n["id"] == "LOCK" for n in storage.load_dag(tr2["dag_id"])["nodes"])
        briefs.append(command_brief.build_brief())

    # ---- checks ----
    rec_dags = [d for d in os.listdir(os.path.join(_TMP, "dags")) if d.startswith("DAG-REC-")]
    droplist_ent = entities.get("PROJECT-DROPLIST")
    rabbit_ent = entities.get("ANIMAL-RABBITS") or entities.get("ANIMAL-DOE-3")

    # evidence on a completed tool node
    evidence_ok = False
    for fn in os.listdir(os.path.join(_TMP, "dags")):
        dag = storage.load_dag(fn[:-5])
        for n in dag["nodes"]:
            if n["status"] == "done" and n.get("tool_type") and n.get("evidence"):
                evidence_ok = True

    c1_attach = droplist_ent and len(droplist_ent["related_dags"]) > droplist_dags_day0
    c2_recurring = len(rec_dags) == 7
    c3_brief = all(set(("ready", "blocked", "waiting")).issubset(b) for b in briefs)
    c4_evidence = evidence_ok
    c5_blocked_resurfaces = all(len(b["blocked"]) >= 1 for b in briefs[1:])
    c6_no_reopen = reopen_blocked and len(state.locked_refs()) >= 2
    c7_cross_link = cross_link_seen

    checks = [
        ("new drops attach to existing entity/project", c1_attach),
        ("recurring nodes generate one per day (7)", c2_recurring),
        ("daily brief shows ready/blocked/waiting", c3_brief),
        ("completed tool nodes save evidence", c4_evidence),
        ("blocked nodes resurface every day", c5_blocked_resurfaces),
        ("done work not reopened by default (lock guard)", c6_no_reopen),
        (">=1 cross-DAG relationship created", c7_cross_link),
    ]
    print("7-DAY PERSISTENCE SIMULATION\n" + "-" * 50)
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'XX'}] {name}")
    print("-" * 50)
    print(f"recurring DAGs materialized: {len(rec_dags)} (expect 7)")
    print(f"PROJECT-DROPLIST related_dags: "
          f"{len(droplist_ent['related_dags']) if droplist_ent else 0}")
    print(f"brief day0 -> day6 ready counts: {[b['totals']['ready'] for b in briefs]}")
    print(f"locked refs: {list(state.locked_refs().keys())}")

    passed = all(ok for _, ok in checks)
    print("\n" + ("MVP 4 GATE: PASS" if passed else "MVP 4 GATE: FAIL"))
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        code = run()
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
        os.environ.pop("DROPLIST_NOW", None)
    raise SystemExit(code)
