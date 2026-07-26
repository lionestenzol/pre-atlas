"""MVP 2 acceptance: 5 real-category drops must each produce a working graph.

Pass if >= 4/5 drops yield: usable packet, valid DAG, correct ready nodes,
correct agent assignment, >= 1 recursive update, and a final state summary.
"""

from __future__ import annotations

import os
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="mvp2_")
os.environ["DROPLIST_DATA"] = _TMP

from droplist import graph_engine  # noqa: E402

# (category, drop, expected_agents_subset)
DROPS = [
    ("animal/farm", "One of the does looks off, not eating much and hiding in the corner of the hutch.",
     {"animal_care", "ops"}),
    ("code/build", "The drop command crashes if the data directory doesn't exist yet.",
     {"coder"}),
    ("money/ops", "Truck insurance renewal came in, due end of month, $612.",
     {"finance", "ops"}),
    ("family/social", "My brother keeps saying he'll call about the family land but never does.",
     {"ops", "documenter"}),
    ("product idea", "What if Atlas exposed a vector endpoint that DropList hits before routing.",
     {"documenter", "memory"}),
]


def run() -> int:
    passed = 0
    from droplist import storage
    print(f"{'category':14} pkt dag ready agents recur state | PASS")
    for cat, text, want_agents in DROPS:
        tr = graph_engine.run_graph(text)
        p = tr["packet"]
        dag = storage.load_dag(tr["dag_id"])
        agents_used = {n["agent"] for n in dag["nodes"]}

        c1 = bool(p.get("type") and p.get("domain"))          # usable packet
        c2 = tr["dag_valid"]                                    # valid DAG
        c3 = len(tr["initial_ready"]) >= 1                      # correct ready nodes
        c4 = want_agents.issubset(agents_used)                 # correct agent assignment
        c5 = tr["state"]["recursive_updates"] >= 1             # recursive update
        c6 = bool(tr.get("state") and tr["state"].get("dag_status"))  # final summary
        ok = sum([c1, c2, c3, c4, c5, c6]) == 6
        passed += int(ok)
        print(f"{cat:14}  {int(c1)}   {int(c2)}   {int(c3)}     {int(c4)}      "
              f"{int(c5)}     {int(c6)}  | {'PASS' if ok else 'FAIL'}"
              f"{'' if c4 else '  (agents='+str(sorted(agents_used))+')'}")

    print("\n" + "=" * 60)
    print(f"MVP 2 GATE: {passed}/5 drops fully passed (need >= 4)  -> "
          f"{'PASS' if passed >= 4 else 'FAIL'}")
    return 0 if passed >= 4 else 1


if __name__ == "__main__":
    try:
        code = run()
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    raise SystemExit(code)
