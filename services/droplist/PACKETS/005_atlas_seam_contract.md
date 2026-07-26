# PKT-005 — Atlas seam contract (DropList -> Signal.v1)

**Status:** done
**Owner:** claude_code
**Scope:** ~45 min (research + mapping + helper + test + BIBLE §16)
**Created:** 2026-06-08
**Closed:** 2026-06-08
**Resolves:** OQ-10
**Opens:** OQ-17 (source_layer enum extension), PKT-006 (live POST wire)
**Bible refs:** §3 Principle, §5 Key Objects, §13 Open Questions, NEW §16 Atlas Seam

---

## Doctrine

1. The graph has authority.
2. No tool action runs without a node.
3. **No completed core is reopened unless validation fails** — the Atlas-side `Signal.v1` schema is settled core; DropList must conform to it, not the other way around.

(See `DOCTRINE.md`.)

---

## Context

OQ-10 had been open since MVP 3: `n8n_webhook` with `DROPLIST_N8N_URL` set is the seam, but the *endpoint contract* was undefined. Without a contract, the wire is "POSTs JSON somewhere"; with a contract, it's "DropList emits Signal.v1 events that Atlas can act on."

This packet defines that contract.

## Pre-flight evidence

```
Found at: services/delta-kernel/src/api/server.ts:1803
  POST /api/signals/ingest  ->  202 { ok, signal_id }

Schema at: contracts/schemas/Signal.v1.json
  AJV-validated; schema_version "1.0"
  required: id, emitted_at, source_layer, signal_type, priority, payload, schema_version
  source_layer enum: site_pull | optogon | atlas | ghost_executor | claude_code
  signal_type enum: status | completion | blocked | approval_required | error | insight
  priority enum: urgent | normal | low
  payload.action_required=true REQUIRES action_options with minItems 1

Store impl at: services/delta-kernel/src/atlas/signals-store.ts
  In-memory ring buffer, MAX_SIGNALS=500
  Signals are ephemeral (act-on-or-log), not persisted
```

**Important finding:** `source_layer` enum did not include `"droplist"` at PKT-005 ship; closest semantic fit was `"optogon"` (DropList is part of the path-runtime / brain-stem layer that feeds Atlas). Opened OQ-17 to formally add `droplist`. **OQ-17 has since shipped (Stop 5, 2026-06-17)** — the enum now includes `"droplist"` and the default has been flipped; the historical mapping below is retained for context.

## The contract

**DropList -> Atlas direction only for v1.** Atlas-initiated read of DropList state is OQ-3-shaped (cross-DAG deps); defer.

When a DAG settles into a terminal state (`complete`, `failed`, `needs_human`, `stalled`), DropList emits exactly one `Signal.v1` shaped event. Mapping:

| Signal field | Source in DAG | Notes |
|---|---|---|
| `schema_version` | literal `"1.0"` | |
| `id` | `f"sig_{uuid4().hex[:12]}"` | DropList-side id |
| `emitted_at` | `clock.now_iso()` | controllable for tests |
| `source_layer` | literal `"droplist"` (post-Stop-5; originally `"optogon"` placeholder until OQ-17) | enum extended 2026-06-17 |
| `signal_type` | map from `dag.status`: complete -> `completion`, failed -> `error`, needs_human -> `approval_required`, stalled -> `blocked` | |
| `priority` | derived from max node priority + DAG type (warning/problem -> urgent) | |
| `payload.task_id` | `dag.source_drop` (the drop_id) | |
| `payload.label` | `dag.goal` (trimmed to 140 chars) | |
| `payload.summary` | `f"{domain}/{type}: {done}/{total} done; status={dag.status}"` | |
| `payload.data` | `{ dag_id, domain, type, dag_status, nodes: [...], evidence_refs, entity_refs, links }` | structured introspection |
| `payload.action_required` | `True` iff `signal_type == "approval_required"` | enforces schema's allOf |
| `payload.action_options` | list of `{ id: node_id, label: node.title, risk_tier: "low" }` for blocked-human nodes | required when action_required=true |

## Mechanism (3 layers, decoupled)

```
                   minimal payload                    Signal.v1
DropList graph  -----------------------> n8n flow -----------------------> delta-kernel
graph_engine     (existing _n8n_webhook)  (transform              POST /api/signals/ingest
                                          per BIBLE §16)
```

OR, bypass n8n for testing/dev:

```
                  Signal.v1
DropList helper ------------------------> delta-kernel
atlas_signal.py  (direct POST when         POST /api/signals/ingest
                  DROPLIST_ATLAS_SIGNALS_URL set)
```

This packet ships layer 1 (the pure-function mapping) + the direct-POST helper. Layer 2 (n8n flow) is a separate config artifact, deferred. Layer 3 (delta-kernel endpoint) already exists.

## Inputs

- `services/droplist/droplist/clock.py` (for `now_iso`)
- The Signal.v1 schema understanding (above)
- The current `graph_engine` settled-DAG hook point (for PKT-006)

## Output

1. **New module** `droplist/atlas_signal.py`:
   - `dag_to_signal(dag, source_layer="droplist") -> dict` — pure function, no I/O (default flipped from `"optogon"` by Stop 5)
   - `emit_signal(signal, url, timeout=10) -> dict` — POSTs via stdlib urllib (zero-dep)
   - Internal mapping tables for status / priority

2. **New test** `test_atlas_signal.py`:
   - 4 DAG fixtures (animal_warning, build_problem, money_task, generic_idea)
   - Each is mapped, then structurally validated against Signal.v1 requirements (required keys present, enums respected, action_required <-> action_options invariant)
   - Optional jsonschema strict-validation if the library is available

3. **New BIBLE §16 "Atlas Seam"** documenting:
   - The mapping table above
   - The 3-layer architecture
   - The contract guarantees (idempotency, replay safety)
   - The OQs this opens (OQ-17, PKT-006)

## Do not touch

- `graph_engine.py` (live emission is PKT-006, not this packet)
- `toolrouter._n8n_webhook` (the existing minimal-payload n8n call is unchanged)
- `delta-kernel/src/api/server.ts` (Atlas-side, settled core)
- `contracts/schemas/Signal.v1.json` (settled core; OQ-17 if we ever extend)

## Done condition

1. `droplist/atlas_signal.py` exists, exports `dag_to_signal` and `emit_signal`.
2. `test_atlas_signal.py` passes: 4 fixture DAGs produce Signal.v1-shaped dicts that meet all required-field and enum constraints.
3. BIBLE §16 added; OQ-10 marked resolved; OQ-17 opened.
4. All four pre-existing gates still PASS (no regression):
   - test_drops -> ALL PASS
   - test_graph -> 5/5
   - test_tools -> 3/3
   - test_persist -> 7/7

## Verification result

(Filled at end of session — see commit message + Bible §13 status.)

## When done

- Mark this packet `done`.
- Commit: `feat(droplist): define Atlas seam contract; map DAG -> Signal.v1 (PKT-005, resolves OQ-10)`.

---

## What this does NOT do

- **Does not wire live emission.** When a DAG settles in graph_engine, NO signal is emitted today. PKT-006 will hook this in (single line: `atlas_signal.emit_settled(dag)` at the end of `run_graph()`).
- ~~**Does not change source_layer in the schema.** Uses `"optogon"` as placeholder. OQ-17 tracks the schema amendment.~~ **PKT-005 itself did not change the schema; OQ-17 was resolved later by Stop 5 (2026-06-17), which extended the enum to include `"droplist"` and flipped the default.**
- **Does not define the n8n flow.** The n8n config is an external artifact (`n8n_flows/droplist_to_atlas_signal.json`), not committed in this packet. Pattern documented in BIBLE §16.
