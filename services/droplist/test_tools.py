"""MVP 3 acceptance: tool-connected execution across 3 domains.

Pass if 3/3 drops produce: valid DAG, >=1 tool action, a saved tool receipt,
a reviewed result, an updated node status, and a final state summary.

Run from the project root (the script_runner tool shells out to test_drops.py).
"""

from __future__ import annotations

import os
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="mvp3_")
os.environ["DROPLIST_DATA"] = _TMP

from droplist import graph_engine, storage  # noqa: E402

DROPS = [
    ("farm/animal", "Rabbits outside are hot. Need to check them again later and log who looked stressed."),
    ("code/build", "The JSONL writer crashes on weird unicode characters, the bug breaks the packet file."),
    ("personal/task", "Draft and log the agenda for the family land meeting this weekend."),
]


def run() -> int:
    passed = 0
    print(f"{'domain':14} dag tool receipt review status summary | PASS")
    for label, text in DROPS:
        tr = graph_engine.run_graph(text)
        dag_id = tr["dag_id"]

        receipts = [r for r in storage.read_all(storage.TOOL_RUNS) if r.get("dag_id") == dag_id]
        reviews = [r for r in storage.read_all(storage.REVIEWS) if r.get("dag_id") == dag_id]
        dag = storage.load_dag(dag_id)
        done_nodes = [n for n in dag["nodes"] if n["status"] == "done"]

        c1 = tr["dag_valid"]                                   # valid DAG
        c2 = tr["state"]["tool_actions"] >= 1                  # >=1 tool action
        c3 = len(receipts) >= 1                                # saved tool receipt
        c4 = len(reviews) >= 1                                 # reviewed result
        c5 = len(done_nodes) >= 1                              # updated node status
        c6 = bool(tr["state"].get("dag_status"))               # final state summary
        ok = all([c1, c2, c3, c4, c5, c6])
        passed += int(ok)
        print(f"{label:14}  {int(c1)}   {int(c2)}    {int(c3)}      {int(c4)}     "
              f"{int(c5)}      {int(c6)}   | {'PASS' if ok else 'FAIL'}  "
              f"[{tr['state']['dag_status']}, {tr['state']['tool_actions']} tools]")

    print("\n" + "=" * 64)
    print(f"MVP 3 GATE: {passed}/3 drops fully passed (need 3)  -> "
          f"{'PASS' if passed >= 3 else 'FAIL'}")
    return 0 if passed >= 3 else 1


if __name__ == "__main__":
    try:
        code = run()
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    raise SystemExit(code)
