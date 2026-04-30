# shardstate

A shared-state coordination layer for agent fleets. Agents reference a Merkle-addressed graph instead of re-sending context.

## The problem

Two agents working on the same task pass context back and forth as natural language. Each handoff re-describes entities the other side already knows about. A 200-token coordination decision arrives wrapped in 4,000 tokens of preamble: who the client is, what the document says, what was decided last turn.

This gets worse with more agents and longer-running tasks. Context windows fill with restated facts. Costs scale with the square of the team size. Subtle drift creeps in when "the agreement" means slightly different things to the researcher and the verifier.

## What this does

A content-addressed graph store that all agents read and write through. Instead of sending facts, agents send references into the graph. The graph is Merkle-hashed end-to-end, so any reference also implicitly commits to the state it was made against.

```python
# Before: 3,200 tokens of context + 80 tokens of decision
researcher.send(verifier, full_context_dump + "evidence is ready for task 18")

# After: a reference
verifier.receive(Ref(state="b3f2...", node="tasks/18", op="mark_evidence_ready"))
```

The verifier already has the state at `b3f2...` cached. The reference is ~60 bytes. The shared graph is the medium; messages are coordinates into it.

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

## Benchmark

Two-agent handoff on a real Atlas synthesis → ghost-executor task. Same task, same outcome.

|                          | Tokens | Latency | Re-explanation errors (10 runs) |
|--------------------------|--------|---------|---------------------------------|
| Natural-language handoff | 3,847  | 4.2s    | 2                               |
| shardstate references    | 312    | 1.1s    | 0                               |

The errors in the baseline were both cases where the second agent inferred a slightly different version of an entity than the first agent meant. With references, this is structurally impossible — the hash either matches or the resolve fails loudly.

## Status

Working library, used in one production agent pair (Atlas → ghost executor). API may change. No version commitments. If you want to use it for something else, expect to read the code.

## Why not [X]

- **Why not just a shared database?** A database gives you shared state but not shared *commitments* to a state. Two agents querying Postgres at slightly different times see slightly different worlds and don't know it. Merkle hashing makes "we are looking at the same thing" verifiable in one comparison.
- **Why not RDF/SPARQL?** Considered. Too heavy for the use case, and the tooling assumes a query-heavy workload. This is a write-heavy, reference-heavy workload between a small number of trusted agents.
- **Why not Automerge/Yjs?** Honestly, if your use case is collaborative editing, use those instead. shardstate is optimized for "agents pass references" not "many writers converge on a document." There's overlap; pick the one whose primary use case matches yours.
- **Why not just bigger context windows?** Bigger windows make the problem cheaper, not smaller. The drift and ambiguity costs don't go away when you can afford to restate everything every turn.

## License

MIT.
