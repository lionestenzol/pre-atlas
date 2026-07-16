# lattice — LangGraph Skill Lattice (Seq 2 + Seq 3 + Seq 4 + Seq 5)

Wraps a genuinely agentic Claude Code Skill invocation (`claude-agent-sdk`, `skills=[...]`,
forced `output_format`) into the same `seam.v1` Receipt shape every deterministic tool in
this stack already produces — so a downstream LangGraph node (Seq 3) can treat an LLM-driven
skill call and a plain CLI call identically.

## Why only 3 skills

The locked plan (`docs/LANGGRAPH_SKILL_LATTICE_PLAN.md`) named ~8 skills by ledger volume.
Checking each one's actual determinism narrowed that to the 3 that genuinely need an LLM
invocation to produce their answer — the rest already have a zero-LLM Receipt path (Seq 1's
`/seam/call`, or are explicit non-goals). See `schemas.py`'s module docstring for the
skill-by-skill reasoning.

| Skill | Needs this adapter? | Why |
|---|---|---|
| **code-recon** | ✅ | Genuine reasoning to search/cite/conclude. Explicit 7-section output contract. |
| **groundwork** | ✅ | Genuine reasoning to pick regions, interpret evidence, author a plan. |
| **weapon** | ✅ | Genuine reasoning to spec/plan/execute/close. Explicit closed.md contract. |
| delta-scp | ❌ | Already reachable via `/seam/call` — zero-LLM HTTP surface. |
| repo-inventory | ❌ | Already reachable via `/seam/call` — zero-LLM CLI surface. |
| bearings | ❌ | Skill's own SKILL.md: "Zero LLM. Zero agents." Wrapping it would waste a real session. |
| fest | ❌ | Plan's own NON-GOALS: LangGraph shouldn't reach fest's Go internals; status/list/progress are plain CLI. |
| seam | ❌ | It's the dispatcher — its own Receipts already ARE seam.v1 shaped. |

## Use

```bash
python skill_nodes.py code-recon "locate where run_id is threaded through /seam/call" --json
python skill_nodes.py weapon "close out the chatpull archive skill" --max-budget 1.00
```

Bounded by `--max-turns` (default 12) and `--max-budget` (default $0.50 USD) — every call
here is a full Claude agentic session, not one inference (Honest Cost #3 in the plan).

## Caveat: `skills=[...]` is a filter, not a guarantee

`claude-agent-sdk`'s own docs are more precise than the plan's shorthand ("forces a named
skill"): `skills=[...]` is a **context filter** — it hides/rejects every *other* skill from
the model's listing, but does not itself force the named one to fire. The prompt still has
to actually ask for the work that skill does. Verified directly against the installed SDK
(0.2.120) on 2026-07-16 — see `ClaudeAgentOptions.skills`'s docstring in
`claude_agent_sdk/types.py`.

## Receipt shape

Same `seam.v1` Receipt as everything else (`atlas_map_api.seam.Receipt`): `tool`, `sha256`,
`produced_at`, `status`, `data`, `error`. The one difference from a CLI-wrapped tool: there's
no tool-printed sha256 to lift, so `sha256` here is computed locally — the content-address of
the skill's own `structured_output` (sorted-key canonical JSON, sha256 hex), not of an input
file. Two runs that produce byte-identical structured output get the same sha256; that's the
idempotency key Seq 3's `@task` wrapping relies on.

## graph.py — the LangGraph spine (Seq 3)

`build_chain_graph(steps, order, checkpointer)` compiles a linear `START -> ... -> END`
`StateGraph` whose state is `receipts: Annotated[list[dict], operator.add]` — an append-only
Receipt ledger. Each `StepFn` (a name + a zero-arg sync/async callable returning a Receipt
dict) is wrapped in a `langgraph.func.task`, per Design Constraint 2 in the locked plan:
LangGraph replays a crashed run from the **start of the interrupted node**, not the crashed
line, so a node that calls a skill/CLI directly would redo that call on every resume. Only
`@task` results are checkpointed and skipped on replay.

### Install (isolated — do not install into the global Python)

```bash
cd services/atlas-map-api
python -m venv .venv          # if not already present
.venv/Scripts/pip install -e ".[dev,lattice]"
```

`langgraph` hard-pins `langchain-core>=1.4.7,<2`, which conflicts with the `langchain` 0.3.x
stack (`langchain-community`/`-chroma`/`-ollama`) already installed **globally** on this
machine for unrelated tools. Confirmed via a reverse-dependency check before installing
(2026-07-16) — this is why `lattice` is its own extra and belongs in a venv, never
`pip install`ed into user site-packages.

### Nodes are async — use `ainvoke`, and `AsyncSqliteSaver`

Every node in `graph.py` `await`s its `@task` call, so the graph must be driven with
`await graph.ainvoke(...)`, not the sync `.invoke()`. Correspondingly the checkpointer must
be `langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver`, not the sync `SqliteSaver` — the sync
saver raises `NotImplementedError` against an async graph (confirmed against the installed
`langgraph-checkpoint-sqlite` 3.1.0, not assumed).

```python
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from graph import build_chain_graph, StepFn

async def make_receipt():
    ...  # e.g. skill_nodes.invoke_skill("code-recon", prompt) or a Seq 1 /seam/call

steps = {"recon": StepFn(name="recon", fn=make_receipt)}
async with AsyncSqliteSaver.from_conn_string("lattice.sqlite") as saver:
    graph = build_chain_graph(steps, order=["recon"], checkpointer=saver)
    config = {"configurable": {"thread_id": "some-run-id"}}
    result = await graph.ainvoke({"receipts": []}, config, durability="sync")

    # after a real crash, a fresh process reconnects and resumes:
    # result = await graph.ainvoke(None, config, durability="sync")
```

### Durability, proven hermetically

`services/atlas-map-api/tests/test_lattice_graph.py` (5 tests, no real skill/network calls)
proves the actual DoD, not just that the code runs:
- a crash mid-chain, then `ainvoke(None, config)`, resumes without re-running the completed node;
- a node with **two** `@task` calls inside it (the case Design Constraint 2 specifically warns
  about) does not re-invoke the first task's underlying function when the node body re-runs
  from its top on resume — only the still-incomplete second task retries;
- resumed receipts carry the **same** `sha256` as before the crash (not regenerated);
- resume survives a genuinely fresh `AsyncSqliteSaver` connection against the same on-disk
  file — i.e. it isn't relying on any in-process Python state, which is what a real killed
  and restarted process would look like.

## bandit.py — the Thompson bandit as a NODE, not an edge (Seq 4)

`make_bandit_node(seed=None, load_combos=None)` draws once from `combo.py`'s Thompson-sampled
ranking over tool-combination arms (`~/.claude/scripts/ledger/combo.py` -- same ledger, same
`pick_combo`/`build_combos`, imported not forked), records the draw as a `seam.v1` Receipt, and
writes the chosen combo to `state["next_combo"]`. `route(state)` is a **pure** function used as
the graph's conditional edge: it only reads `next_combo` back out of state, no randomness.

**Why this split matters (Design Constraint 1):** LangGraph edges are plain functions
re-evaluated against state, not checkpointed the way nodes are. A Thompson draw placed
*inside an edge function* would re-draw on every replay/resume, silently changing the route a
crashed-and-resumed run takes. Placing the draw inside a node means it executes exactly once;
its result becomes durable checkpointed state; the edge downstream can never re-randomize it.

```python
from bandit import make_bandit_node, route, BanditState
from langgraph.graph import StateGraph, START, END

g = StateGraph(BanditState)
g.add_node("bandit", make_bandit_node(seed=0))
g.add_node("code-recon+groundwork", ...)   # a real node, e.g. wired to skill_nodes.invoke_skill
g.add_edge(START, "bandit")
g.add_conditional_edges("bandit", route, {"code-recon+groundwork": "code-recon+groundwork", "done": END})
```

Cold-start safe: an empty ledger/combos list makes `next_combo` `None`, and `route` maps that to
`"done"` -- no crash, no fake arm.

`services/atlas-map-api/tests/test_lattice_bandit.py` (6 tests, hermetic -- `load_combos` is
always injected with a fixed fixture, never the real ledger file) proves the plan's own DoD
wording directly: `aget_state_history()` shows the drawn arm recorded as a receipt, and
replaying the same `thread_id` after a downstream crash produces the *same* arm (the draw's
underlying call count stays at 1 across the crash/resume boundary -- proven by a counting
`load_combos` stub, not just by the output looking right).

Sanity-checked live against the real ledger too (pure local Thompson sampling, no API cost):
209 real ledger rows -> 176 derived combos -> a real node run through a real `StateGraph`
returned a genuine `seam.v1` Receipt (`status: "ok"`, real `sha256`) with the top-ranked arm
(`code-recon>groundwork-cli`, score 0.9999, n=12) correctly written to `next_combo`.

## ledger_feed.py — closing the learn loop (Seq 5)

Feeds a completed graph run's receipts back into the SAME `tool-outcomes.jsonl` ledger
`combo.py` scores -- mirrors `tools/seam/run.py`'s `_append_ledger`/`_ledger_rows` exactly
(same row schema, same objective-reward convention, same `SEAM_LEDGER=1` /
`SEAM_LEDGER_PATH` gating). `run_chain.py` calls it automatically after every `ainvoke`.

```bash
SEAM_LEDGER=1 python run_chain.py --thread-id t1 code-recon "..."   # also feeds the ledger
python run_chain.py --thread-id t1 code-recon "..."                 # ledger feed is a no-op (default)
```

**The plan's own open question, decided:** should the JSONL ledger just *be*
`graph.get_state_history()` across threads instead of a separate file? **No.** Checked before
deciding, not assumed:
1. **Coverage** -- the ledger aggregates every skill invocation across every session
   (interactive + seam + lattice); `get_state_history()` is scoped to one thread. Swapping would
   blind `combo.py` to the much larger volume of non-lattice usage.
2. **Reward semantics** -- a checkpointed Receipt has no reward field, only status/error. The
   ledger's reward is sentiment+shipped/retried fusion (interactive) or the objective ok+sha256
   convention seam already established -- neither is derivable from a bare checkpoint.
3. **Coupling** -- `combo.py` is deliberately stdlib-only and ledger-format-agnostic; coupling it
   to LangGraph's internal checkpoint schema buys nothing and adds fragility.

Unification means what Seq 5's own DoD implies: lattice runs *feed* the same ledger seam
already feeds, not replace the substrate.

Rows are `seq`-shaped (`a>b`), not `cofire`: each row gets a **distinct** `request` key (unlike
seam's one-shared-request-per-manifest), so `combo.py`'s turn-chunking treats each node
completion as its own turn and derives the chain as ordered transitions -- matching what a
linear graph chain actually does. The bandit node's own receipt (`tool="bandit"`) is excluded --
it always immediately precedes whatever it routed to by construction, so it isn't a learnable
transition.

`services/atlas-map-api/tests/test_lattice_ledger_feed.py` (8 tests) proves the DoD literally:
builds a synthetic lattice-shaped ledger and confirms `combo.py --evaluate` (via
`combo.evaluate()`) reads the new rows and beats random. One flakiness bug found and fixed along
the way: `evaluate()`'s holdout split hashes session id, and Python's `hash()` is salted per
process (`PYTHONHASHSEED`) -- a small fixture (12-vs-3 sessions) failed 2/5 explicit seeds
because the 30% holdout draw sometimes contained zero losing-arm sessions, making
`random_expected_reward` accidentally tie `combo_expected_reward` (a genuine tie, which
`evaluate()`'s own docstring calls honest reporting, not a bug). Fixed by scaling the fixture up
(200-vs-60 sessions) until a zero-draw becomes vanishingly improbable -- confirmed 0/30 failures
across seeds 0-29 before trusting it.

Live-verified end to end (real `code-recon` call, `SEAM_LEDGER=1` pointed at a scratch file, not
the real ledger): the run produced a real Receipt and `run_chain.py` printed `lattice: fed 1
row(s) to the tool-outcomes ledger`; the appended row matched `_ledger_rows`' schema exactly.
