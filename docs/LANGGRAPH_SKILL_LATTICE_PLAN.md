# LangGraph Skill Lattice — LOCKED PLAN

**Date:** 2026-07-14 · **Branch:** `feat/atlas-setup-ui` · **Status:** IN PROGRESS — Seq 1-6 DONE incl. live proof (2026-07-15/16)

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
| **1** | ✅ **Receipt store.** Persist what atlas-map already mints. Add `run_id` + a receipt table/JSONL. | `POST /call` twice → both receipts readable from the store by `run_id`; `sha256` stable across runs. **DONE 2026-07-15**: `receipt_store.py` (append-only JSONL, `services/atlas-map-api/var/receipts.jsonl`); `/seam/call` now accepts optional `run_id` (auto-generated + echoed if omitted) and persists every Receipt; new `GET /seam/receipts?run_id=...` reads a chain back. Verified live (two POSTs sharing one `run_id`, both readable back) + 8 unit tests (`tests/test_receipt_store.py`, incl. sha256-persisted-verbatim and corrupt-line resilience). |
| **2** | ✅ **Skill→Receipt adapters.** An `output_format` JSON schema per graph-participating skill. | Each skill invoked via `claude-agent-sdk` returns `structured_output` validating against its schema; emits a `seam.v1` Receipt with a real `sha256`. **SCOPE CORRECTED 2026-07-16**: of the ~8 named by ledger volume, only 3 are genuinely agentic (need an LLM to produce their answer) — `code-recon`, `groundwork`, `weapon`. The rest already have a zero-LLM Receipt path (delta-scp, repo-inventory via Seq 1's `/seam/call`) or are explicit non-goals (`bearings` states "Zero LLM. Zero agents." in its own SKILL.md; `fest`'s Go internals are a locked NON-GOAL; `seam` is the dispatcher, already Receipt-shaped). See `tools/lattice/schemas.py`'s docstring for the full reasoning. **BUILT, NOT LIVE-VERIFIED**: `tools/lattice/schemas.py` (3 schemas, sourced from each skill's own SKILL.md output contract) + `tools/lattice/skill_nodes.py` (`invoke_skill()` — calls `claude-agent-sdk`, wraps `structured_output` into a Receipt, `sha256` = content-address of the structured output itself). SDK mechanism verified against installed `claude-agent-sdk` 0.2.120 source (confirms `skills=[...]`, `output_format`, `ResultMessage.structured_output` all real — but corrects the plan's own "forces a named skill" claim: it's a context filter, not a guarantee of invocation). 15 hermetic tests pass (`tests/test_lattice_skill_nodes.py` — schema validity + Receipt-wrapping logic via a fake SDK module, no real API cost). **Live end-to-end BLOCKED — root cause confirmed, corrected from initial guess**: first attempt (from inside this session) failed; re-ran externally from a genuinely separate terminal (2026-07-16) with BOTH the real `code-recon` call AND a bare no-schema/no-skills query — same failure both times, ruling out the initial "nested Claude-in-Claude" theory. Real cause, printed directly on the bare-query run: `ResultMessage is_error=True result="Failed to authenticate: OAuth session expired and could not be refreshed"`. A separate workspace-trust warning also fires (`this workspace has not been trusted... Run Claude Code interactively here once and accept the trust dialog`). Neither is a defect in `tools/lattice/` — the `claude` CLI's OAuth session needs re-authentication for non-interactive/SDK-driven invocation, and this workspace needs its trust dialog accepted in that context. (Traced the SDK's misleading "returned an error result: success" wrapper to `claude_agent_sdk/_internal/query.py:303-308` — it substitutes `str(subtype)` when `errors` is empty, which is why the real OAuth text only showed up on the bare-query run, not the first structured-output run.) Fix was on the user's machine, not in this code. **LIVE PROOF LANDED 2026-07-16**: Bruke ran `claude auth login` externally; `claude auth status` confirmed `loggedIn: true`. Re-ran `code-recon` through `run_chain.py` (Seq 3's `build_chain_graph`, real budget) — a real question about `graph.py`'s own source, answered correctly, returned a `status: "ok"` `seam.v1` Receipt with a genuine 64-hex-char `sha256`. Verified at the storage layer too: the checkpoint sqlite shows 3 real rows for that thread, not just a zero exit code. |
| **3** | ✅ **LangGraph spine.** `State` with `operator.add` receipts reducer; `@task`-wrapped skill nodes; `SqliteSaver`; `durability="sync"`. | Kill the process mid-chain → `graph.invoke(None, config)` resumes at the interrupted node; **already-completed `@task`s do not re-run** (proven by receipt CIDs being identical, not regenerated). **DONE 2026-07-16 (hermetic)**: `tools/lattice/graph.py` — `build_chain_graph(steps, order, checkpointer)` compiles a linear `StateGraph` whose nodes each `await` one `@task`-wrapped `StepFn`. Installed `langgraph` 1.2.9 + `langgraph-checkpoint-sqlite` 3.1.0 into `services/atlas-map-api/.venv` (a new `lattice` pyproject extra) — deliberately **not** the global Python, which already has an incompatible `langchain` 0.3.x stack (`langchain-community`/`-chroma`/`-ollama`, pinned `langchain-core<1.0.0`) installed for unrelated tools; `langgraph` hard-pins `langchain-core>=1.4.7,<2`. Confirmed the reverse-dependency conflict via `importlib.metadata` before installing, not assumed. Corrected two more plan-shorthand details against installed source rather than the plan's own wording: `durability` is an `ainvoke()`-time kwarg (not `compile()`-time), and since every node here is async, the checkpointer must be `langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver` — the sync `SqliteSaver` raises `NotImplementedError` against an async graph. 5 hermetic tests (`services/atlas-map-api/tests/test_lattice_graph.py`, 228/228 full suite still green): normal linear run; crash-in-node-then-resume (node-level Pregel durability); **two `@task` calls inside one node** — the specific case Design Constraint 2 warns about — crash between them, resume, prove the first task's underlying function is called exactly once while the second genuinely retries; receipt `sha256` identical across the crash/resume boundary (not regenerated); resume survives a **genuinely fresh `AsyncSqliteSaver` connection** against the same on-disk file (not just the same in-process Python object), which is the actual shape of a killed-and-restarted process. **Real `StepFn` wired 2026-07-16**: `tools/lattice/run_chain.py` wires `skill_nodes.invoke_skill` as a `StepFn`, checkpointed to an on-disk `AsyncSqliteSaver` — this same run is Seq 2's live proof (above). Still open: the literal kill-the-OS-process version of the DoD against a *real* skill call (the hermetic AsyncSqliteSaver-reconnect test proves the mechanism; a real crash mid-real-skill-chain hasn't been run, and costs real budget each time it's tried — deliberately deferred, not blocked). |
| **4** | ✅ **Bandit node.** `combo.py` as a NODE (constraint 1); pure `route` edge. | `get_state_history()` shows the drawn arm recorded as a receipt; replaying the same `thread_id` produces the **same** arm. **DONE 2026-07-16**: `tools/lattice/bandit.py` — `make_bandit_node(seed, load_combos)` wraps `combo.pick_combo(combo.build_combos(combo.router.load_rows()))` (imported from `~/.claude/scripts/ledger/combo.py`, not forked) in a `@task`-wrapped draw, records the arm as a `seam.v1` Receipt, writes it to `state["next_combo"]`. `route(state)` is pure — reads `next_combo` back out, no randomness, safe under LangGraph's repeated edge evaluation. 6 hermetic tests (`services/atlas-map-api/tests/test_lattice_bandit.py`, 240/240 full suite green) prove the DoD's own wording: `aget_state_history()` shows the drawn arm as a receipt; a downstream crash + `ainvoke(None, config)` resume produces the identical arm, proven via a call-counting `load_combos` stub that stays at 1 invocation across the crash boundary (not just "the output looked right"); plus cold-start safety (empty ledger → `next_combo=None` → routes to `"done"`, no crash). **Live-checked against the real ledger** (pure local Thompson sampling, no API cost): 209 real rows → 176 derived combos → a real node run through a real `StateGraph` returned a genuine Receipt with the top-ranked arm (`code-recon>groundwork-cli`, score 0.9999, n=12) correctly written to `next_combo`. |
| **5** | ✅ **Close the learn loop.** Every node completion appends a ledger row (mechanism exists, `SEAM_LEDGER=1`). | Ledger grows on a real graph run; `combo.py --evaluate` still beats random with the new rows. **DONE 2026-07-16**: `tools/lattice/ledger_feed.py` — mirrors `tools/seam/run.py`'s `_append_ledger`/`_ledger_rows` exactly (same row schema, same objective ok+sha256 reward convention, same `SEAM_LEDGER=1`/`SEAM_LEDGER_PATH` gate, reused not reinvented). Wired into `run_chain.py`, called automatically after every `ainvoke`. **Decided the "OPEN QUESTION FOR SEQ 3"**: the JSONL ledger stays canonical, NOT replaced by `get_state_history()` — three checked reasons (coverage: the ledger spans all sessions, `get_state_history()` only one thread; reward semantics: a Receipt has no reward field, `get_state_history()` can't supply what sentiment-fusion or the objective convention already do; coupling: `combo.py` is deliberately stdlib-only, coupling it to LangGraph's checkpoint schema buys nothing). Lattice rows are `seq`-shaped (distinct `request` per row, unlike seam's shared-request cofire rows) since chain nodes fire in a determined order; the bandit's own receipt is excluded from the feed (routing metadata, not a learnable skill transition). 8 hermetic tests (`services/atlas-map-api/tests/test_lattice_ledger_feed.py`, 242/242 full suite green) prove the DoD literally via `combo.evaluate()` on a synthetic lattice-shaped ledger. One real flakiness bug found and fixed en route: `evaluate()`'s holdout split hashes session id, and Python's `hash()` is salted per-process (`PYTHONHASHSEED`) — a small fixture failed 2/5 explicit seeds because a 30% holdout draw sometimes contained zero losing-arm sessions (a genuine tie, not a combo.py defect — its own docstring calls this "honest reporting"). Fixed by scaling the fixture (200-vs-60 sessions) until a zero-draw is vanishingly improbable; confirmed 0/30 failures across seeds before trusting it — root-caused via a direct diagnostic print of the full `evaluate()` result dict, not guessed. **Live-verified end to end**: a real `code-recon` call with `SEAM_LEDGER=1` pointed at a scratch file (not the real ledger) produced a real Receipt and a correctly-shaped appended row, confirmed by reading the file directly. |
| **6** | ✅ **Lattice renders it live.** `draw_mermaid()` / `stream_mode="updates"` → Cytoscape. | Watch a chain execute in the browser. Node states change as it runs. **DONE 2026-07-16**: `tools/lattice/viewer_server.py` (FastAPI, `/run` `/structure/{id}` `/stream/{id}` SSE) + `tools/lattice/viewer.html` (Cytoscape + `cytoscape-dagre`, gray→blue→green/red node states). Reuses `apps/lattice/`'s vendored Cytoscape libs read-only via a `/vendor` static mount — deliberately does NOT touch `apps/lattice/index.html` itself, a large unrelated production surface (work-item viewmodel UI, its own locked 3-week plan, live Replicache write-paths) with nothing to do with this. **Live-verified in an actual browser** via `preview_start`: clicked "Run demo chain," confirmed via direct Cytoscape state inspection that 2 real-succeeding demo nodes ended `"ok"` and 1 deliberately-failing node ended `"error"` — exactly matching each step's real outcome, not just "the page loaded." Then ran a REAL `code-recon` call through the actual UI (skill dropdown + prompt field) and confirmed that node ended `"ok"` too. **Found and fixed a real bug along the way**: the first UI draft used a single `"skill:prompt, skill:prompt"` text field; a prompt containing a comma silently mis-parsed into a bogus second pair and failed. Root-caused via direct DOM inspection, fixed with a proper skill `<select>` + prompt field, re-verified with the exact same comma-containing prompt. 4 hermetic tests cover the pure logic (node-name disambiguation, the updates-stream node-vs-task filter, demo-step receipt shapes); the FastAPI/SSE routes themselves are proven by the live browser run rather than a mocked TestClient. 246/246 full suite green. |
| **7** | **Supervisor.** delta-kernel work queue resumes dead threads (`graph.invoke(None, config)` on timeout). | Kill a run; the queue's `checkTimeouts()` resurrects it without human action. |

---

## NON-GOALS (do not touch)

- **`delta-kernel` governance spine** — `routing.ts` header says *"LOCKED — the gravitational spine. Deterministic only. No AI."* Correct. Leave it.
- **`uasc-executor`** — capability/token set closed by source per `TRUST_BOUNDARY.md`. Verified: 10 tokens seeded in `schema.sql:55-65`, zero `INSERT INTO commands` in any Python. Leave it.
- **`fest`** — Go. LangGraph cannot reach it, and it doesn't need it: fest is already **the only genuinely event-sourced, step-resumable thing in the stack** (`localstore/store.go:347,369,483`). It's the proof the pattern works.
- **`langchain`** (the abstraction layer) — never import it.

---

## OPEN QUESTION FOR SEQ 3 — DECIDED 2026-07-16 (see Seq 5's row above)

~~Should the JSONL ledger `combo.py` reads simply *be* `graph.get_state_history()` across threads, rather than a separate file? Would unify the reward store and the execution trace into one substrate. Decide before building Seq 5.~~

**No.** The JSONL ledger stays canonical; lattice runs feed it (via `tools/lattice/ledger_feed.py`, mirroring `tools/seam/run.py`'s existing appender), they don't replace it with LangGraph's own checkpoint state. Full reasoning in the Seq 5 row and `ledger_feed.py`'s module docstring.
