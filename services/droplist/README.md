# Mini Ship #1 — DropList Packet Engine (CLI)

Drop messy human input. Get back exactly one Work Packet that says what this is,
where it routes, who handles the next step, the one next action, when it stops,
and what Atlas should remember. Everything appends to JSONL.

**Answers like an operator, not a chatbot.** No UI. No dispatch. No automation.

```
Drop → Normalize → Classify → Retrieve Context → Route Workflow
     → Complete Packet → (optional Mini Ship) → Log → (memory)
```

## Run it (zero dependencies, zero API key)

```bash
cd mini-ship-1
python3 -m droplist "Spark burned tokens on 14k Drive files before metadata indexing."
```

Or install the `drop` command:

```bash
pip install -e .
drop "the goats need water and the chickens got out again"
```

### Commands

```bash
drop "raw messy input"            # process one drop, print the Work Packet
drop --ship "raw messy input"     # also emit a Mini Ship packet
drop --recent 10                  # last N packets, one line each
drop --show drop_ab12cd34ef56     # full packet by id
drop --memory-search "rabbit"     # keyword search prior packets
drop --json "..."                 # machine-readable output

drop --review                     # surface unresolved work (read-only, no LLM)
drop --review --domain build_product --needs-decision
drop --morning                    # daily command brief (rules-based, no LLM)
drop --inventory ~/some/folder    # metadata-only file_ops inventory
drop --inventory ~/f --hash       # sample-hash to confirm duplicate groups
drop --ship-from drop_ab12cd34    # convert a stored packet into a Mini Ship
```

After `pip install -e .` the last three also exist as their own commands:
`drop-review [filters]`, `morning`, `inventory <folder> [--hash]`, `ship-from <drop_id>`.

### Acceptance test (20 real drops)

```bash
python3 test_drops.py            # checks all 7 spec criteria; 100% classification
python3 test_drops.py --verbose  # also prints every packet
```

## Where things live

| File | Role |
|---|---|
| `schema.py` | Work Packet + Mini Ship dataclasses, closed enums, validation |
| `hashing.py` | normalize, input_hash, classification cache |
| `storage.py` | append-only JSONL + `log_run()` execution memory |
| `classifier.py` | type/domain/entities (heuristic + optional LLM) |
| `retrieval.py` | top-5 prior packets by token overlap |
| `router.py` | `WORKFLOW_MAP` + the 6 DAG node lists |
| `completion.py` | the operator doctrine, per DAG |
| `daily.py` | Daily Command DAG — the `morning` brief, rules-based |
| `review.py` | `drop-review` — read-only grouping/filtering of packets |
| `inventory.py` | File Ops DAG — metadata-only folder inventory |
| `engine.py` | the core loop + Mini Ship converter + `ship_from` |
| `cli.py` | the `drop` command |
| `llm.py` | backend abstraction + call logger |

Data is written to `./data/` (override with `DROPLIST_DATA=/path`):
`packets.jsonl`, `mini_ships.jsonl`, `llm_calls.jsonl`, `run_log.jsonl`
(every command run leaves a trace in run_log.jsonl).


## MVP 2 — Recursive DAG loop (`graph`)

MVP 1 turns a drop into a packet. MVP 2 turns a packet into an execution graph
and *moves the first nodes*:

```
drop -> packet -> DAG -> [dispatch -> agent -> review -> update]* -> state
```

```bash
drop --graph "the doe is limping and not eating, hiding in the corner"
graph "the drop command crashes if the data dir doesn't exist"   # after install
drop --graph "..." --json
```

The loop is the real engineering and it is fully real: the dispatcher only runs
a node when it's `ready` and all deps are `done`; the updater flips `waiting`
nodes to `ready` when their parents finish (the recursion); the reviewer caps
how many new nodes an agent can spawn. The agent *content* is a deterministic
template by default (so the loop runs with no key) and becomes a real model
prompt when `DROPLIST_LLM=anthropic` — the protocol
(`result/evidence/confidence/new_nodes`) is identical either way.

New modules: `dag_builder.py`, `dispatcher.py`, `agents.py`, `node_reviewer.py`,
`dag_update.py`, `graph_engine.py`. New data: `data/dags/<id>.json`,
`agent_runs.jsonl`, `reviews.jsonl`, `dag_events.jsonl`.

Gate: `python3 test_graph.py` — 5 real-category drops, each must produce a
usable packet, valid DAG, correct ready nodes, correct agents, >= 1 recursive
update, and a final state summary. Currently 5/5.


## MVP 3 — Tool-connected execution (`graph` grows arms)

MVP 2 moved the graph. MVP 3 lets nodes trigger outside actions and verifies
the result before marking anything done:

```
drop -> packet -> DAG -> route -> (agent | tool | human)
       -> capture receipt -> review against done_condition -> update -> next
```

Five tools, all safe by construction:

| tool | what it does | safety |
|---|---|---|
| `calendar` | drafts a reminder receipt | stub — never touches a real calendar |
| `file_writer` | writes a results file | sandboxed to `data/results/` only |
| `message_drafter` | drafts a message | never sends |
| `n8n_webhook` | POSTs a node payload | dry-run unless `DROPLIST_N8N_URL` set + reachable |
| `script_runner` | runs a command | allowlist only (`test_*.py`/`echo`), no shell, timeout |

The four rules, enforced in code:

- **No tool action without a node** — only the loop calls a tool, on a node.
- **No node done without evidence** — every tool run writes a receipt to `tool_runs.jsonl`.
- **No evidence accepted without review** — the reviewer gates every result.
- **No review passed without a done_condition** — a tool can succeed and still
  leave the node *not done* if its `done_condition` isn't verified; it then
  retries (bounded by `max_retries`) and finally `failed`.

Human nodes are surfaced as *awaiting you* (`needs_human`), never auto-completed.

New modules: `toolrouter.py` (tools + done-checkers), `node_router.py`
(human/tool/reasoning), and tool-aware `dag_builder` / `node_reviewer` /
`graph_engine`. New data: `tool_runs.jsonl`, `data/results/`.

Gate: `python3 test_tools.py` — 3 drops (farm / code / personal), each must
produce a valid DAG, >= 1 tool action, a saved receipt, a reviewed result, an
updated node, and a final state summary. Currently 3/3.


## MVP 4 — Persistent operating layer (`brief`, `watch`, entities, recurrence)

MVP 3 executes one graph. MVP 4 maintains an operating world: graphs persist,
recur, attach to long-lived entities, resurface when blocked, and roll up into
a daily command brief across every domain.

```bash
drop --recurring-add "Check rabbit water | animal_property | daily"
drop --watch        # materialize due recurring nodes; flag stale / escalations
drop --brief        # cross-domain command board: ready/blocked/waiting/recurring/do-not-reopen
drop --entities     # the long-lived things drops attach to (animals/projects/...)
```

What persists:

- **Entities** (`data/entities/`) — animals, projects, people, assets with a
  history of observations and the DAGs that touched them. Drops resolve to the
  same entity across days, so continuity holds.
- **Recurring nodes** (`data/state/recurring_nodes.json`) — the watcher
  materializes one fresh ready node per day per recurrence.
- **Do-not-reopen lock** (`data/state/do_not_reopen.json`) — frozen work
  (e.g. `SCHEMA-V1`). A drop that tries to reopen a locked ref produces a
  `blocked` LOCK node instead of a redesign — done work isn't reopened by default.
- **Cross-DAG links** — a new graph links to prior graphs that share an entity,
  so tasks aren't isolated islands.

New node fields: `domain, project, entity_refs, parent_dag, priority_score,
stale_after_hours, created_from, recurs, do_not_reopen_refs`.

New modules: `clock.py` (controllable time), `entities.py`, `state.py`
(recurrence + locks), `watcher.py`, `command_brief.py`.

Gate: `python3 test_persist.py` — a 7-day simulation (via the clock) that
checks attachment, one-recurrence-per-day, brief completeness, evidence on done
tool nodes, blocked-node resurfacing, the lock guard, and cross-DAG linking.
Currently 7/7.

## Turning on a real model

The default classifier and completer are deterministic heuristics — that's why it
runs with no key and the acceptance test is reproducible. To route classification
through Claude instead, set:

```bash
export DROPLIST_LLM=anthropic
export ANTHROPIC_API_KEY=sk-...
pip install -e ".[llm]"
```

The heuristic stays as the fallback on any API error, and every call (heuristic,
cache hit, or real) is logged to `llm_calls.jsonl` with latency and estimated cost.

## What was deliberately left for later (per the build packet)

- **Mini Ship** schema + converter exist and are wired (`--ship`, `--ship-from`), but it's MVP 3.
- **Vector retrieval** (Chroma/Qdrant): the retrieval interface already returns the
  `{source, snippet, relevance}` shape, so it swaps in without touching callers.
- **`inventory` deep-read stage**: inventory runs the metadata + cluster nodes; the
  `deep_read_selected` -> `cleanup_plan` -> `ask_before_move_delete` nodes are next,
  and stay gated behind explicit approval.
- **LangGraph**: not used. Plain dispatcher, as specified. Add it when sub-DAGs need
  parallelism / retries / streaming.
