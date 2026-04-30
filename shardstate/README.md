# shardstate

A shared-state coordination layer for agent fleets. Agents reference a Merkle-addressed graph instead of re-sending context.

## The problem (when it applies)

Some multi-agent systems have agents pass context back and forth as natural language. Each handoff re-describes entities the other side already knows about. A short coordination decision arrives wrapped in a long preamble: who the client is, what the document says, what was decided last turn. With more agents or longer-running tasks the restatement compounds, and subtle drift creeps in when "the agreement" means slightly different things to the researcher and the verifier.

This problem doesn't exist in every multi-agent system. Many are built around typed JSON envelopes that already pin entities by ID — those don't need shardstate. shardstate is for the systems that aren't.

## What this does

A content-addressed graph store that all agents read and write through. Instead of sending facts, agents send references into the graph. The graph is Merkle-hashed end-to-end, so any reference also implicitly commits to the state it was made against.

```python
# Where the bloat lives — natural-language handoffs that re-state shared context:
researcher.send(verifier, full_context_dump + "evidence is ready for task 18")

# What shardstate replaces it with — a coordinate, not a copy:
verifier.receive(Ref(state="b3f2...", node="tasks/18", op="mark_evidence_ready"))
```

The verifier already has the state at `b3f2...` cached. The reference is roughly 80 bytes regardless of how large the underlying entity is. The shared graph is the medium; messages are coordinates into it.

## What's in the box

- A SQLite-backed content-addressed store (each node hashed, parents hashed over children, Merkle DAG).
- A small set of operations: `get`, `patch`, `append`, `diff`, `subscribe`.
- Stable IDs for entities you want to refer to repeatedly (assigned once, resolved through the current state).
- Vector-clock conflict resolution for concurrent writes (last-writer-wins per node, with a conflict log you can inspect).
- An MCP server so Claude Code sessions and other MCP clients can read/write the same graph.

## What's not in the box

- A wire protocol or spec. This is a library, not a standard.
- A new packet format. References are just `(state_hash, node_path, op)` tuples.
- LLM-aware "formulas" for summarize/generate/modify. Those are application code on top of `get` and `patch`, not primitives.
- Temporal markers as a separate concept. Timestamps are properties on nodes; "before the call" is a query against the timeline subgraph.
- Checksums on resolved meaning. The Merkle root already commits to state; deterministic ops over committed state don't need a second hash.

## Quick start

```python
from shardstate import Store, Ref

store = Store("./fleet.db")

# Seed an entity
client = store.put({"type": "client", "name": "Marcus", "email": "m@example.com"})
agreement = store.put({
    "type": "agreement",
    "version": 2,
    "payment_terms": {"due_date": "2026-05-15", "clause": "Net 30"},
    "client": client.id,
})

# Agent A makes a change
new_state = store.patch(agreement.id, {"payment_terms.due_date": "2026-06-01"})

# Agent A sends a reference (this is the whole message)
ref = Ref(state=new_state.hash, node=agreement.id, op="read")

# Agent B resolves it
view = store.resolve(ref)
# view = {"type": "agreement", "version": 2, "payment_terms": {...}, ...}
```

## What's been measured

Nothing yet, honestly. The library works (26 passing tests, the quickstart above runs verbatim), but the agent-pair benchmark this README originally claimed hasn't been run on a real workload. The first codebase considered for it (the `pre-atlas` Atlas → ghost-executor pair) turned out to use typed JSON envelopes between services, not the natural-language handoffs shardstate is designed to compress — so there was nothing to measure on that pair. An honest benchmark needs an actual multi-agent pipeline where one LLM's prose output gets bundled into another LLM's prompt, run on ten or more real inputs with token counts logged before and after. If you have such a pipeline and want to try it, the test plan is straightforward and I'd like to see the numbers.

## Status

Pre-1.0. The mechanism works; the value claim is unproven. API may change. No version commitments. If you want to use it, expect to read the code, and be the first person to measure whether it actually pays.

## Why not [X]

- **Why not just a shared database?** A database gives you shared state but not shared *commitments* to a state. Two agents querying Postgres at slightly different times see slightly different worlds and don't know it. Merkle hashing makes "we are looking at the same thing" verifiable in one comparison.
- **Why not RDF/SPARQL?** Considered. Too heavy for the use case, and the tooling assumes a query-heavy workload. This is a write-heavy, reference-heavy workload between a small number of trusted agents.
- **Why not Automerge/Yjs?** Honestly, if your use case is collaborative editing, use those instead. shardstate is optimized for "agents pass references" not "many writers converge on a document." There's overlap; pick the one whose primary use case matches yours.
- **Why not just bigger context windows?** Bigger windows make the problem cheaper, not smaller. The drift and ambiguity costs don't go away when you can afford to restate everything every turn.

## License

MIT.
