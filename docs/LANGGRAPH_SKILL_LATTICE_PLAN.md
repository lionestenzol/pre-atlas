# LangGraph Skill Lattice — LOCKED PLAN

**Date:** 2026-07-14 · **Branch:** `feat/atlas-setup-ui` · **Status:** PLAN LOCKED, NOT BUILT

---

## WHAT

A LangGraph graph whose **nodes are Claude Code skill invocations**, whose **state is an append-only list of `seam.v1` Receipts**, whose **router is `combo.py`'s Thompson bandit**, checkpointed to SQLite so a skill chain can resume from step N after a crash. Lattice renders it live.

## WHY (the gap, from a 6-agent forensic recon on 2026-07-14)

You have a **learned policy over skills with no durable executor.**

| Piece | Reality (file:line verified) |
|---|---|
| `~/.claude/scripts/ledger/combo.py` | Thompson bandit over skill *tuples*. **Beats random** (+0.19..+0.57). Learns from `tool-outcomes.jsonl` (**203 rows**, live, growing). |
| ...but it can only `suggest` | No executor. A human reads the suggestion and fires skills by hand, in order. |
| `tools/seam/run.py:478` | Runs the tool chain — but **every stage binds the same input arg. No stage consumes the previous stage's output.** It fans out; it does not chain. |
| `tools/seam/run.py:387` | Receipts are `print()`ed. **Zero persistence.** A `seam full` that dies on the last stage loses all prior receipts. |
| `atlas-map-api/seam.py:57-107` + `server.py:678` | **Mints proper `seam.v1` Receipts and throws them away.** The only durable trace of any gateway call is a per-capability integer counter (`call_counter.py:56`). |
| Everything else | **Zero orchestration libraries anywhere in the stack.** ~30 hand-rolled coordination points. Almost none crash-resume. |

LangGraph is the missing executor. Every other piece already exists.

---

## THE TWO DESIGN CONSTRAINTS THAT WOULD HAVE BEEN BUGS

Both from primary docs (`docs.langchain.com/oss/python/langgraph/durable-execution`). Non-obvious. **Get these wrong and the system silently corrupts on every resume.**

### 1. The bandit is a NODE, not an edge.

LangGraph **replays** on resume: *"it identifies an appropriate starting point and replays all steps from there."* A Thompson draw is a random number generation. In an edge function it **re-draws differently on every replay** — the routing decision would not be a recorded fact.

```python
def bandit(state: State) -> dict:                 # random happens ONCE, inside a node
    arm = thompson_draw(read_ledger())
    return {"next_tool": arm,
            "receipts": [receipt("bandit", arm)]}  # the choice is now durable + auditable

def route(state: State) -> str:                   # pure, deterministic, replay-safe
    return state["next_tool"]

b.add_conditional_edges("bandit", route, {"code-recon": "code-recon", ..., "done": END})
```

### 2. Every skill/CLI invocation goes in a `@task` — and the Receipt CID is the idempotency key.

**Resume restarts the interrupted node from its beginning, not from the crashed line.** A node that shells out and dies afterward **re-runs the shell command**. Only `@task` results are checkpointed and not re-executed.

```python
from langgraph.func import task

@task
def invoke_skill(name: str, args: dict) -> dict:   # checkpointed; NOT re-run on replay
    ...
```

**Your content-addressing already solves LangGraph's worst footgun.** The receipt `sha256` is a natural idempotency key: *check whether a receipt with this CID exists before executing.* This is why the seam Receipt design is load-bearing, not decorative.

---

## THE ARCHITECTURE

| Layer | Mechanism | Status |
|---|---|---|
| **Node** | `claude-agent-sdk` → `query(prompt, ClaudeAgentOptions(skills=["code-recon"], output_format={"type":"json_schema","schema":...}, max_budget_usd=..., max_turns=...))` → `message.structured_output` | SDK confirmed; **`skills=[...]` forces a named skill**; `setting_sources=["user","project"]` loads from disk |
| **State** | `receipts: Annotated[list[dict], operator.add]` — the reducer IS the append-only ledger | Receipt shape exists (`seam.v1`) |
| **Edge** | `combo.py` Thompson pick — **as a node** (see constraint 1) | Exists, beats random |
| **Checkpointer** | `SqliteSaver` (`langgraph-checkpoint-sqlite` 3.1.0), **`durability="sync"`** (default `"async"` has a loss window) | New |
| **Reward feed** | one ledger row per node completion | Exists — `_append_ledger`, `tools/seam/run.py:334` |
| **Observability** | `stream_mode="updates"` + `graph.get_graph().draw_mermaid()` — free, offline, no account | New |
| **Lattice** | Cytoscape renders the live graph (it already renders Cytoscape DAGs — just dead ones today) | Exists, needs wiring |

---

## HONEST COSTS — accept these or don't start

1. **`langchain-core` is unavoidable.** `langgraph` 1.2.9 hard-pins `langchain-core>=1.4.7,<2`. The *abstraction layer* (`langchain` — chains, agent executors, model wrappers) is **NOT** a dependency and never gets imported. But you cannot have zero `langchain*` packages on disk.
2. **LangGraph is NOT Temporal.** In-process, single-language, and there is **no auto-resume** — nothing detects a crash and restarts the run. Something external must call `graph.invoke(None, {"configurable": {"thread_id": ...}})`. **delta-kernel's work queue is that supervisor** (it already does claim/heartbeat/timeout/retry). This is the correct division of labor, not a workaround.
3. **Every node is a full Claude agentic session** — the sum of all its tool turns, not one inference. Bound with `max_budget_usd` + `max_turns`. **Do not graph all ~50 skills.** Start with the ~8 that already have real `n` in the ledger.
4. **Zero-LLM LangGraph works but is off the beaten path.** Nodes are plain Python functions — no model required by the runtime. But every doc, example, and issue assumes you have an LLM. Expect to be a minority user.
5. **Studio requires a LangSmith account** even for the local flow. Skip it. `stream_mode="updates"` + `draw_mermaid()` gives full observability with no signup and no cloud.
6. **Security:** set `LANGGRAPH_STRICT_MSGPACK=true` from day one — otherwise a compromised checkpoint DB is a code-execution vector (flagged by the Postgres saver package itself).

---

## SEQUENCE (to the end)

| # | Seq | DoD (tool-provable) |
|---|---|---|
| **1** | **Receipt store.** Persist what atlas-map already mints. Add `run_id` + a receipt table/JSONL. | `POST /call` twice → both receipts readable from the store by `run_id`; `sha256` stable across runs. |
| **2** | **Skill→Receipt adapters.** An `output_format` JSON schema per graph-participating skill, for the ~8 with real ledger `n` (code-recon, delta-scp, repo-inventory, groundwork-cli, fest, bearings, seam surfaces). | Each skill invoked via `claude-agent-sdk` returns `structured_output` validating against its schema; emits a `seam.v1` Receipt with a real `sha256`. |
| **3** | **LangGraph spine.** `State` with `operator.add` receipts reducer; `@task`-wrapped skill nodes; `SqliteSaver`; `durability="sync"`. | Kill the process mid-chain → `graph.invoke(None, config)` resumes at the interrupted node; **already-completed `@task`s do not re-run** (proven by receipt CIDs being identical, not regenerated). |
| **4** | **Bandit node.** `combo.py` as a NODE (constraint 1); pure `route` edge. | `get_state_history()` shows the drawn arm recorded as a receipt; replaying the same `thread_id` produces the **same** arm. |
| **5** | **Close the learn loop.** Every node completion appends a ledger row (mechanism exists, `SEAM_LEDGER=1`). | Ledger grows on a real graph run; `combo.py --evaluate` still beats random with the new rows. |
| **6** | **Lattice renders it live.** `draw_mermaid()` / `stream_mode="updates"` → Cytoscape. | Watch a chain execute in the browser. Node states change as it runs. |
| **7** | **Supervisor.** delta-kernel work queue resumes dead threads (`graph.invoke(None, config)` on timeout). | Kill a run; the queue's `checkTimeouts()` resurrects it without human action. |

---

## NON-GOALS (do not touch)

- **`delta-kernel` governance spine** — `routing.ts` header says *"LOCKED — the gravitational spine. Deterministic only. No AI."* Correct. Leave it.
- **`uasc-executor`** — capability/token set closed by source per `TRUST_BOUNDARY.md`. Verified: 10 tokens seeded in `schema.sql:55-65`, zero `INSERT INTO commands` in any Python. Leave it.
- **`fest`** — Go. LangGraph cannot reach it, and it doesn't need it: fest is already **the only genuinely event-sourced, step-resumable thing in the stack** (`localstore/store.go:347,369,483`). It's the proof the pattern works.
- **`langchain`** (the abstraction layer) — never import it.

---

## OPEN QUESTION FOR SEQ 3

Should the JSONL ledger `combo.py` reads simply *be* `graph.get_state_history()` across threads, rather than a separate file? Would unify the reward store and the execution trace into one substrate. Decide before building Seq 5.
