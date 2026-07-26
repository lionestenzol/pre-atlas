# PKT-001 — Remove the router.py orphan

**Status:** ABORTED 2026-06-07 — premise was wrong, no code changed
**Owner:** claude_code
**Scope:** ~30 min (estimated) / 0 min (actual; aborted at pre-flight grep)
**Created:** 2026-06-07
**Aborted:** 2026-06-07
**Bible refs:** §5 Packet, §8 Modules, §10 Build Rules, §12 Acceptance Gates

---

## Why aborted

Pre-flight grep `selected_workflow|current_node|next_node|import router|router\.` surfaced:

- `completion.py:185` reads `packet.selected_workflow` to look up which completer in `_COMPLETERS` runs. The 6 completer keys (`"file_ops_dag"`, `"build_product_dag"`, etc.) are exactly `router.py`'s `WORKFLOW_MAP` values.
- `inventory.py:143-145` sets `selected_workflow="file_ops_dag"` to populate the same dispatch key.
- `review.py:51` counts packets by `selected_workflow` for the `drop-review` surface.
- `cli.py:89, 219` reference it in run-log summaries and review output.

**The premise of PKT-001 was wrong.** `router.py` is NOT orphaned. It is the workflow-name source that MVP 1's packet-completion pipeline dispatches on. Deleting it would:

- Break `test_drops.py` criterion 4 (every packet must have a valid workflow / next / stop / allow / block / memory / status — all populated by the completer function that `selected_workflow` keys).
- Lose the `drop-review --domain build_product` ability to group by workflow.
- Break the run-log summary format.

The real situation: **MVP 1 and MVP 2-4 are two parallel pipelines.** MVP 1 goes drop -> engine -> router (workflow name) -> completion (dispatch on workflow name) -> finished packet. MVP 2-4 goes drop -> packet -> dag_builder(domain, type) -> graph_engine. Both use `(domain, type)` as input, but they emit different shapes for different purposes. Neither is orphaned.

What I called an "orphan" was actually "MVP 1's routing layer that MVP 2-4 doesn't read (and doesn't need to)." That's not a bug — it's two layers of the same system serving different surfaces.

## Lesson learned (workflow improvement)

The packet's "Inputs" section should have required a pre-flight grep BEFORE proposing the change scope. PKT-001 listed the files I expected to change but didn't require a `grep -rn` sweep over the symbols I planned to remove. That sweep would have caught the completion.py dispatch in 5 seconds.

**Future packets:** add a `## Pre-flight evidence` section that lists the grep / read commands that must be run BEFORE writing the proposed change, with results pasted in. No change is scoped before the grep is run.

This is what packets are *for*. The doctrine ("no completed core is reopened unless validation fails") protected the code. The packet caught the wrong assumption before any code changed. Cost of being wrong: zero.

## Reframed problem (for a future packet)

There IS a real concern in this area, but it's not "router is orphaned." It's:

- The packet's `current_node` / `next_node` reference router-DAG node names (`"inventory_metadata"`, `"identify_project"`, etc).
- The graph engine's DAG has its own node IDs (`N1, N2, ...`) with different titles.
- These two "current node" concepts are different abstractions stored in different places.
- If a future consumer reads `packet.current_node` expecting it to match the graph state, they'd be confused.

Whether that's a problem worth solving depends on whether anything outside droplist will read `packet.current_node`. If no, leave it. If yes (e.g., Atlas substrate), the field needs to be renamed to clarify ("packet.workflow_phase" or similar) or removed in favor of querying the graph directly.

**That is a different packet.** Probably PKT-005 or later, after we know what Atlas reads.

---

---

## Doctrine (always quoted)

1. The graph has authority.
2. No completed core is reopened unless validation fails.
3. Do not redesign working modules unless tests prove failure.

(See `DOCTRINE.md`.)

---

## Context

`droplist/router.py` defines `WORKFLOW_MAP` and 6 DAG node lists (`build_product_dag`, `file_ops_dag`, etc.). The `WorkPacket` it populates carries `selected_workflow`, `current_node`, and `next_node` fields.

Since MVP 2, `graph_engine.run_graph()` ignores those fields entirely. `dag_builder.build_dag()` is the only consumer of `(packet.domain, packet.type)`, and it emits its own 3–5 node DAG that does not match `router.DAGS`.

Result: the packet *claims* a workflow that no executor reads. `router.py` is dead code, and `selected_workflow` is a field whose contract no module honors.

This violates Bible §10 ("do not redesign working modules") in the opposite direction: the *retired* module is still being imported and quoted. Code-as-furniture rule: don't leave broken furniture in the house.

---

## Inputs

- `droplist/router.py` (the orphan)
- `droplist/engine.py` (imports `router`, calls `select_workflow` + `first_and_next`)
- `droplist/schema.py` (defines `selected_workflow / current_node / next_node` on `WorkPacket`)
- `droplist/cli.py::print_packet` (prints those fields)
- All four acceptance gates: `test_drops.py`, `test_graph.py`, `test_tools.py`, `test_persist.py`

---

## Output (choose one path)

### Path A — Canonical: delete the orphan (RECOMMENDED)

1. Delete `droplist/router.py`.
2. Remove the `from . import router` line in `engine.py`. Remove the `workflow = router.select_workflow(...)`, `current, nxt = router.first_and_next(workflow)` calls. Remove `selected_workflow / current_node / next_node` from the `WorkPacket(...)` construction.
3. Remove `selected_workflow: str = ""`, `current_node: str = ""`, `next_node: str = ""` from `WorkPacket` dataclass in `schema.py`.
4. Remove the validator check `if not self.selected_workflow: errors.append("selected_workflow is empty")` from `WorkPacket.validate()`.
5. Remove the workflow / current_node / next_node print line in `cli.py::print_packet`.
6. Re-run all four gates. Confirm 100% still pass.

### Path B — Revival: re-wire router as the canonical workflow source

NOT recommended. Estimated 4h+. Requires `dag_builder` to consult `router.DAGS` and emit nodes from those lists instead of its own hand-written shapes. **Do not pick Path B without writing a follow-up packet** (PKT-002-bigger). The current `dag_builder` is more capable than `router.DAGS` (tool nodes, done_conditions, retries); reverting to router-shape regresses MVP 3.

---

## Do not touch

- `dag_builder.py` (canonical for DAG shape)
- `graph_engine.py` (the loop)
- `node_router.py`, `node_reviewer.py`, `toolrouter.py` (MVP 3 governance)
- `state.py`, `entities.py`, `watcher.py`, `clock.py`, `command_brief.py` (MVP 4 persistence)
- Any field in `WorkPacket` other than the three being removed
- Any `.jsonl` log file (existing data must remain readable)

---

## Done condition

ALL must hold:

1. `grep -r "import router\|from .router\|from .* import router" droplist/` returns no results.
2. `grep -rn "selected_workflow\|current_node\|next_node" droplist/` returns no results.
3. All four acceptance gates pass at parity with current baseline:
   - `python3 test_drops.py` -> "ALL ACCEPTANCE CRITERIA PASS"
   - `python3 test_graph.py` -> ">= 4/5 drops fully passed"
   - `python3 test_tools.py` -> "MVP 3 GATE: 3/3"
   - `python3 test_persist.py` -> "MVP 4 GATE: PASS"
4. `drop "the goats need water"` prints a packet with no `KeyError` and no reference to removed fields.
5. Reading any existing packet from `data/packets.jsonl` via `--show <drop_id>` does not crash on the missing keys (the dataclass tolerates extra keys, but be sure).

---

## Verification plan

```bash
# 1. Baseline (capture current state)
cd mini-ship-1
python3 test_drops.py && python3 test_graph.py && python3 test_tools.py && python3 test_persist.py
# expected: all four green

# 2. Do the work (Path A)
# ... edits ...

# 3. Re-run gates
python3 test_drops.py && python3 test_graph.py && python3 test_tools.py && python3 test_persist.py
# expected: all four still green

# 4. Spot-check
python3 -m droplist "Spark burned tokens on 14k Drive files."
python3 -m droplist --recent 3
```

If any gate degrades, revert and re-scope.

---

## Open questions surfaced

- **OQ-A:** Does Atlas substrate (`services/cognitive-sensor/`) or any external consumer read `selected_workflow` from `data/packets.jsonl`? If yes, write a migration packet before deleting. Check with `es selected_workflow -p` across the machine.
- **OQ-B:** Should the deletion be a single commit, or two (one per file)? Recommendation: single commit so the gates pass atomically.

---

## When done

1. Update `BIBLE.md §5 Packet` field list to remove the three deleted fields.
2. Add a row to `BIBLE.md §13 Open Questions` if OQ-A or OQ-B surfaced anything non-trivial.
3. Mark this packet `done` (change Status at top).
4. Commit: `chore(droplist): remove router.py orphan; close PKT-001`.
