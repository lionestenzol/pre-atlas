# PKT-008 — Wire lattice-projection to consume DropList signals

**Status:** drafted (not executed)
**Owner:** next session
**Scope:** ~45 min
**Created:** 2026-06-15
**Resolves:** OQ-19
**Bible refs:** §3 Principle ("graph has authority"), §10 (settled core boundary), §13 OQ-19, §16 Atlas Seam

---

## Doctrine

1. The graph has authority. DropList DAGs must surface in the Atlas viewmodel as items with verifiable provenance.
2. No interface before state. The DropList -> Atlas emission was built FIRST (PKT-006); the consumer wire follows now that data is real on the wire.
3. No completed core is reopened. `droplist/atlas_signal.py`, `graph_engine._maybe_emit_atlas_signal`, and `delta-kernel /api/signals/ingest` all stay untouched. The change lands entirely inside `lattice-projection.ts`.

(See `DOCTRINE.md`.)

---

## Summary

Today the DropList -> Lattice chain is half-built:

```
DropList settle  --Signal.v1-->  delta-kernel /api/signals/ingest  --[X]-->  lattice-projection.ts  -->  apps/lattice
                                       (writes to ring buffer)        (does not read signals)
```

The `lattice-projection.ts` module reads `cognitive-sensor/idea_registry.json` exclusively. Signals land in delta-kernel but never reach the viewmodel. PKT-008 closes that half: extend `lattice-projection.ts` to project signals as `LatticeItem`s, with `provenance.source = 'droplist'` so the right-click menu can show what proposed the item.

## Pre-flight evidence

```
Read:    services/delta-kernel/src/atlas/lattice-projection.ts (505 lines)
Grep:    "animal_property|droplist|signals|source_layer" in lattice-projection.ts -> 0 matches
Grep:    "/api/signals/ingest" in delta-kernel -> services/delta-kernel/src/api/server.ts:1803 (route exists)
Grep:    "MAX_SIGNALS" in delta-kernel -> in-memory ring, default 500
Read:    services/droplist/data/dag_events.jsonl -> proves prior atlas_signal_emit events
         (one succeeded, one returned HTTP 500 when delta-kernel was offline — fail-safe worked)
Read:    apps/lattice/index.html lines 2368-2480 -> calls delta-kernel:3001 /api/lattice/viewmodel
         + Zod schema requires `provenance` field on items
```

Confirms: emission side proven on production data; consumer side has the slot, just needs to read from signals.

## Spec

### Files touched (one)

`services/delta-kernel/src/atlas/lattice-projection.ts`

### Changes

1. Extend the `LatticeProvenanceSource` union:

```ts
export type LatticeProvenanceSource =
  | 'cognitive-sensor.idea_registry'
  | 'optogon'
  | 'user'
  | 'ghost_executor'
  | 'droplist';   // <-- new
```

2. Add a signals-reader analogous to `readRegistry`:

```ts
interface SignalEntry {
  id: string;
  signal_type: 'completion' | 'error' | 'approval_required' | 'blocked' | 'inferred_event';
  priority: 'urgent' | 'normal' | 'low';
  payload: { task_id?: string; label?: string; status?: string };
  emitted_at: string;
  source_layer: string;
}

function readDroplistSignals(signalsRing: StorageLike): SignalEntry[] {
  // pull from delta-kernel's signals ring; filter source_layer where
  // (source_layer === 'optogon' && payload.source === 'droplist') OR
  // source_layer === 'droplist' once OQ-17 ships.
}
```

3. Map each signal -> `LatticeItem`:

```ts
function signalToItem(sig: SignalEntry): LatticeItem {
  return {
    id: sig.payload.task_id ?? sig.id,
    title: sig.payload.label ?? '(droplist DAG)',
    project: 'atlas',   // first cut; refine when OQ-17 + domain mapping is decided
    status: signalStatusToLatticeStatus(sig.signal_type),
    time: relativeTime(sig.emitted_at),
    links: [],
    provenance: { source: 'droplist' },
  };
}
```

4. Inside `buildViewmodel`, append signal-derived items AFTER the idea_registry items but BEFORE the correction-override pass, so user corrections can override droplist provenance too.

### What about graph nodes?

Existing pattern: every item also becomes a `LatticeNode` with a `belongs_to` edge to its project. Droplist items follow that pattern. No new node types.

### Storage shim

`StorageLike` already has `loadEntitiesByType<T>`. The signals ring is NOT in entity storage today — it's an in-process Map. Choose:

- **Option A (recommended):** add `loadSignals(): SignalEntry[]` to `StorageLike` and have the delta-kernel host implementation read from the signals ring. Keeps `lattice-projection.ts` decoupled from the in-memory implementation.
- **Option B:** persist signals to disk as a JSONL log and read the file. Cleaner audit trail, more I/O. Defer unless durability becomes a separate requirement.

Pick A.

## Contract

After PKT-008 lands, the viewmodel returned by `GET /api/lattice/viewmodel` includes:

```jsonc
{
  "items": [
    /* ...existing 12 execute_now ideas... */
    {
      "id": "drop_2681d50fd332",
      "title": "Check the subject, schedule a recheck, and log the observation",
      "project": "atlas",
      "status": "blocked",      // signal_type=approval_required -> blocked
      "time": "recently",
      "links": [],
      "provenance": { "source": "droplist" }
    }
  ],
  /* events, projects, nodes, edges all extended in lockstep */
}
```

Right-click an item -> "what proposed this?" -> "droplist (PKT-006 signal sig_abc123)".

## Verification

New test: `services/delta-kernel/test/lattice-projection-droplist.test.ts` (or equivalent in the existing test layout). Fixtures:

1. Empty signals ring + populated idea_registry -> viewmodel matches today's behavior (regression guard for OQ-19's pre-state).
2. One droplist signal + empty idea_registry -> exactly one item, provenance=droplist, status mapped per signal_type.
3. User correction over droplist item -> provenance flips to user, correctedFrom = "droplist", correctedAt set.
4. Multiple signal_types -> status mapping matrix.

Existing `apps/lattice/index.html:2369-2377` Zod schema must accept the new provenance value without modification (the union widened, not narrowed). Smoke-test by loading the page against a delta-kernel populated by `test_atlas_emit.py`.

Existing droplist gates must still pass — PKT-008 does not touch droplist files:

```
test_drops          PASS
test_graph          5/5
test_tools          3/3
test_persist        7/7
test_atlas_signal   4/4
test_atlas_emit     2/2
test_server         7/7
```

## What this does NOT do

- **Does not modify droplist.** Settled core stays settled.
- **Does not change the Signal.v1 schema.** OQ-17 (`source_layer = 'droplist'` enum extension) remains independent. PKT-008 reads existing signals where source_layer is the placeholder `'optogon'`.
- **Does not persist signals to disk.** PKT-008 keeps signals in-memory. Durability across delta-kernel restarts is a separate question (defer until a real consumer cares).
- **Does not solve project routing.** Droplist signals all land in `project: 'atlas'` in the first cut. A domain -> project mapping is a follow-up OQ if/when Bruke wants doe DAGs to land under `property` instead.
- **Does not delete idea_registry items.** Lattice continues to show 12 execute_now Atlas ideas alongside any droplist items.

## Open before execution

1. Does delta-kernel's signals-ring implementation actually expose a read API today, or is it write-only via `/api/signals/ingest`? Read first; the StorageLike extension may need to be wider than Option A assumes.
2. Should items emitted from `signal_type: 'completion'` (DAG settled) get `status: done` automatically, or stay as `open` until reviewed? PKT-007 doctrine says graph has authority — completion in droplist IS the verification. Default: `done`.
3. Should the time field reflect the signal's `emitted_at` (richer than today's `'recently'` literal)? Likely yes — the existing `relativeTime` helper in droplist's deleted lattice_viewmodel.py was a good shape; port it as a TypeScript equivalent.
