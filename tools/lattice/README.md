# lattice — LangGraph Skill Lattice (Seq 2 + Seq 3)

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
