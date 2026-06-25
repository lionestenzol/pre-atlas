# PKT-011 — Mark-off + Checklist (Brick 1 of the project-lifecycle spine)

**Status:** drafted, not built · **Branch:** continue on `experiment/droplist-remediation-2026-06-15`
**Author:** spec written 2026-06-25 · **Depends on:** nothing (pure addition over the green engine)

---

## Why this exists

DropList already turns a drop into a DAG of tasks, each with a `done_condition`,
and the read API (`/api/brief`, `/api/dag/{id}`) shows them. But there is **no way
to mark a task done from outside the engine** — the only path to "done" is the
internal `graph_engine` loop reviewing a tool/agent node. So a *human-driven*
project can be planned and viewed but never **steered or checked off**.

This is the genesis brick of the lifecycle:

```
①CAPTURE → ②PLAN → ③SCHEDULE → ④ADVANCE → ⑤CHECK-IN → ⑥ACT → ⑦TRACK
   ✅drop    🟡→✅      ❌          🟡→✅       ❌          ~        ✅
            THIS                  THIS
```

Brick 1 closes the write side of ② (you can see the plan as a checklist) and ④
(you can advance it by hand). It is fest-style planning + Definition-of-Done +
virtual mark-off — in pure Windows Python, no WSL. Bricks 2 (headless tick),
3 (cron), 4 (daisy-chain) build ON this; they are out of scope here.

## Definition of Done (the brick is finished when ALL are true)

- [ ] `POST /api/dag/{dag_id}/node/{node_id}/complete` marks the node `done`,
      unblocks dependents, and flips the DAG to `complete` when the last node lands.
- [ ] `GET  /api/dag/{dag_id}/checklist` returns the DAG as a flat, ordered
      checklist: `[{id, title, status, done_condition, depends_on, blocked_by}]`.
- [ ] Invalid `dag_id` or `node_id` → `404`. Completing an already-`done` node is
      **idempotent** (returns 200 with `already_done: true`, no double-mutation).
- [ ] Completing a node whose deps aren't `done` yet → `409` with a clear message
      (you can't check off step 3 while step 1 is open).
- [ ] New `test_markoff.py` passes; **the existing 23 tests still pass** (no regression).
- [ ] Read endpoints unchanged. No new dependency added.

## Endpoints

### 1. Mark a task off — `POST /api/dag/{dag_id}/node/{node_id}/complete`

Body (all optional): `{ "result": <any>, "evidence": [<str>...], "note": <str> }`

Behavior — **reuse `dag_update.apply_review`, do not reimplement the graph logic:**
```python
# load the dag the same way GET /api/dag/{dag_id} does (server.py:75-80)
dag = storage.load_dag(dag_id)            # 404 if None
node = next((n for n in dag["nodes"] if n["id"] == node_id), None)   # 404 if None
if node["status"] == "done":              # idempotent
    return {"already_done": True, ...}
unmet = [d for d in node["depends_on"] if not _is_done(dag, d)]
if unmet:                                  # 409
    raise HTTPException(409, f"{node_id} blocked by {unmet}")
review = {"mark_node_as": "done", "approved_new_nodes": []}
result = {"by": "human", "note": body.note, "evidence": body.evidence or []}
updates = dag_update.apply_review(dag, node, result, review)   # unblocks deps + flips dag.status
storage.save_dag(dag)                      # same save graph_engine.py uses (~:235)
storage.append(storage.DAG_EVENTS, {       # audit trail, matches existing pattern
    "event": "node_completed", "dag_id": dag_id, "node_id": node_id,
    "by": "human", "at": clock.now_iso(), "updates": updates})
return {"dag_id": dag_id, "node": node_id, "dag_status": dag["status"],
        "updates": updates, "ready_now": [n["id"] for n in dispatcher.get_ready_nodes(dag)]}
```

`apply_review` (dag_update.py:20) already: sets status→done, attaches result,
wakes `waiting` nodes whose deps are satisfied, and sets `dag.status = complete`
when nothing runnable remains. **That is the entire advance step — reuse it.**

### 2. See the plan as a checklist — `GET /api/dag/{dag_id}/checklist`

```python
dag = storage.load_dag(dag_id)            # 404 if None
done = {n["id"] for n in dag["nodes"] if n["status"] == "done"}
return {"dag_id": dag_id, "goal": dag.get("goal"), "status": dag["status"],
        "tasks": [{"id": n["id"], "title": n["title"], "status": n["status"],
                   "done_condition": n["done_condition"],
                   "depends_on": n["depends_on"],
                   "blocked_by": [d for d in n["depends_on"] if d not in done]}
                  for n in dag["nodes"]]}
```

### 3. (stretch, only if cheap) Reopen — `POST .../node/{node_id}/reopen`

Set a `done` node back to `ready` **iff** it is not in the do-not-reopen lock
(`state.py` / `do_not_reopen.json`). Skip if it adds risk — not required for DoD.

## Auth

Writes must match whatever `POST /api/drop` does today (server.py:148). If `/api/drop`
is open, these are open; if it checks a token, mirror it. **Do not invent a new
auth scheme** — check intake/server first and copy the pattern.

## Test sketch (`test_markoff.py`)

1. Push a drop that yields a multi-node DAG (reuse a fixture from `test_graph.py`).
2. `GET /checklist` → assert N tasks, first is `ready`, later ones `waiting`,
   `blocked_by` populated.
3. `POST /complete` on a `waiting` node whose deps are open → `409`.
4. `POST /complete` each node in dependency order → each returns the freshly
   `ready_now` set; assert dependents wake up.
5. After the last → `dag_status == "complete"` and `/brief` shows 0 ready for it.
6. `POST /complete` again on a done node → `200 already_done`.
7. Re-run full suite: `python -m pytest -q` → **24 files of behavior, 0 regressions.**

## Files touched

| File | Change |
|------|--------|
| `droplist/server.py` | +2 (maybe +3) endpoints; reuse storage + dag_update + dispatcher |
| `droplist/markoff.py` *(optional)* | thin helpers if server.py gets crowded; keep logic in dag_update |
| `test_markoff.py` | new |
| `BIBLE.md` | note the two write endpoints under the API section; resolve/append to §12 gates |

## Explicitly OUT of scope (later bricks — do not pull in)

- Headless/always-on tick loop (Brick 2)
- Cron / temporal scheduling (Brick 3)
- Daisy-chain staged-prompt protocol (Brick 4)
- Any UI. The checklist endpoint returns JSON; rendering is a separate concern.
