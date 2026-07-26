# PKT-009 — Lattice UI consumer-side fixes for droplist items

**Status:** drafted (not executed)
**Owner:** next session
**Scope:** ~30 min
**Created:** 2026-06-15
**Follows:** PKT-008 (which shipped the backend wire)
**Bible refs:** §3 Principle ("graph has authority"), §16 Atlas Seam

---

## Doctrine

1. PKT-008 shipped the backend half (delta-kernel emits droplist items in `/api/lattice/viewmodel`). PKT-009 closes the consumer half so the user-facing affordances actually work.
2. No completed core is reopened. `lattice-projection.ts`, `signals-store.ts`, and droplist itself stay untouched.
3. Code = furniture. Three real defects survived PKT-008's gate suite because no fixture exercised them at the UI layer; they need fixes, not labels.

(See `DOCTRINE.md`.)

---

## Summary

PKT-008 shipped a backend that correctly emits droplist items into the lattice viewmodel. The PKT-008 ship-readiness audit (workflow `wf_545bca5e-82b`, 2026-06-15) verified three real defects on the consumer side that PKT-008's scope (one file: `lattice-projection.ts`) excluded:

1. Right-click corrections on droplist items silently no-op (gate regex excludes `drop_*` ids)
2. Context menu has no `'droplist'` branch, mislabels items as `'local'`
3. The packet-promised E2E smoke (kernel boot + populated signals + page load) was not run

PKT-009 closes all three. One file: `apps/lattice/index.html`.

## Pre-flight evidence (from PKT-008 audit)

```
Grep:  /^canon_/.test  in apps/lattice/index.html -> 2 hits (lines 1980, 2205)
       Both gate setItemStatus / setItemProject calls behind canon_ prefix
       check, so drop_* and sig_* IDs fall through to local-only mutation.
Read:  apps/lattice/index.html:2094-2098 -> provLabel switch handles
       'cognitive-sensor.idea_registry' | 'optogon' | 'user' | 'ghost_executor'
       with `else 'local'` fallback. No 'droplist' branch.
Grep:  source_drop in droplist/atlas_signal.py -> line 109; IDs are 'drop_*'
       (via dag.get("source_drop")), confirming the prefix collision.
Read:  apps/lattice/index.html:2415-2416 -> next pull replays viewmodel,
       which would wipe any local-only correction made via the silent no-op.
Read:  delta-kernel/src/api/server.ts:2030 -> POST /api/lattice/correct has
       NO canon_ guard; the UI is the only block.
```

## Spec

### Files touched (one)

`apps/lattice/index.html`

### Changes

1. Widen the correction-gate regex at two sites (lines 1980, 2205). Current:

```js
if (/^canon_/.test(it.id) && window.latticeSync) {
  window.latticeSync.queueCorrection(...)
}
```

Widen to a typed-prefix allowlist:

```js
const SUBSTRATE_PREFIXES = /^(canon_|drop_|sig_)/;
if (SUBSTRATE_PREFIXES.test(it.id) && window.latticeSync) {
  window.latticeSync.queueCorrection(...)
}
```

Hoist the constant near the top of the section (DRY: shared by both call sites).

2. Add the `'droplist'` branch to the ctx-menu provLabel switch at lines 2094-2098:

```js
} else if (prov.source === 'droplist') {
  provLabel = 'from droplist DAG';
}
```

Position before the `else { provLabel = 'local'; }` fallback. Optional richer label: include `prov.dag_id` or the signal id if exposed in the viewmodel response — but the first cut is the literal string above, matching PKT-008 §6 Contract.

3. (Optional within scope) Surface `prov.correctedFrom = 'droplist'` literal when the user accepts a droplist-projected item without changes. The PKT-008 audit flagged `correctedFrom` as never containing the literal `'droplist'`; this is a backend concern though, not UI. Defer until PKT-010 unless trivial.

### What about the backend?

Untouched. `lattice-projection.ts` emits exactly what's needed (`provenance.source = 'droplist'`); the UI just has to render it.

## Verification

### E2E smoke (the test PKT-008 deferred — packet L150)

1. Boot delta-kernel: `cd services/delta-kernel && npx tsx src/api/server.ts`
2. Emit a droplist signal: `cd services/droplist && python test_atlas_emit.py` (or `python -m droplist.engine` if available)
3. Load `apps/lattice/index.html` against `http://127.0.0.1:3001`
4. Confirm:
   - At least one item rendered with prefix `drop_*` (verified by reading the rendered DOM, not just localStorage)
   - Right-clicking the item shows "from droplist DAG" in the ctx menu provLabel field
   - Changing project or status persists across page reload (substrate write succeeded — confirms gate widening works)
   - Browser console has zero Zod parse errors against the viewmodel response

### Manual UI test plan

- Two corrections on different droplist items, full reload, both survive
- One correction on an idea_registry (`canon_*`) item — must still work (regression guard for gate widening)
- Hover-context menu on a `canon_*` item shows `cognitive-sensor.idea_registry`, NOT `droplist` (regression guard for the switch addition)

### Existing PKT-008 unit tests must still pass

```
npm run test:lattice-droplist   # delta-kernel side, 14/14
python test_atlas_signal.py     # droplist side, 4/4
python test_atlas_emit.py       # droplist side, 2/2
... (other 5 droplist gates)
```

PKT-009 touches no `.ts` or `.py` files, so all of the above are vacuously green.

## Contract

After PKT-009 lands:

- Right-clicking a droplist item shows "from droplist DAG" in the ctx menu (Packet PKT-008 §6 promise honored)
- Right-click "set status: done" on a droplist item persists across reloads (queued through `/api/lattice/correct`, written to the corrections JSONL, picked up by next viewmodel build)
- Browser console clean on the standard viewmodel-load path

## What this does NOT do

- Does not change `lattice-projection.ts` or any other backend file
- Does not modify droplist or the Signal.v1 schema
- Does not add new prefixes beyond `drop_*` and `sig_*` to the substrate allowlist
- Does not solve project routing (all droplist items still land under `project: 'atlas'` per PKT-008 first cut)
- Does not address the multi-signal dedup question — already closed in PKT-008 (dedup by `task_id`, newest `emitted_at` wins, `lattice-projection.ts:352-372`)

## Open before execution

1. Is `sig_*` actually a substrate-writable prefix, or only `drop_*`? PKT-008 today maps signals to `id = payload.task_id ?? sig.id`, so the prefix surfaced is whichever is present. Most signals have `task_id` (= `drop_*`), so `sig_*` is the fallback. Both should be writable.
2. Should the gate widening be a regex (proposed) or an enum allowlist `['canon_', 'drop_', 'sig_'].some(p => it.id.startsWith(p))`? Regex is shorter; startsWith allowlist is faster and clearer. Default: regex (matches existing style).
3. Should the ctx-menu label use the signal id (e.g. `'from droplist DAG (sig_abc123)'`) for traceability? The PKT-008 §6 contract names the signal id explicitly. Default: yes, if `prov.signal_id` is exposed in the viewmodel; else just the bare label.
