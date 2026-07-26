# PKT-006 — Live Atlas signal emission

**Status:** done
**Owner:** claude_code (weapon-mode mission)
**Scope:** ~45 min
**Created:** 2026-06-08
**Closed:** 2026-06-08
**Resolves:** the "live wire pending" follow-up from PKT-005 / BIBLE §16
**Authoritative spec:** `.weapon/spec.md` (this packet was executed under WEAPON MODE)
**Bible refs:** §3 Principle, §16 Atlas Seam, §12 Acceptance Gates

---

## Doctrine

1. The graph has authority.
2. No tool action runs without a node — but the Atlas signal is *not* a tool action: it is a layer-3 emission about a settled graph, downstream of all node execution.
3. No completed core is reopened unless validation fails.

(See `DOCTRINE.md`.)

---

## Summary

`graph_engine.run_graph()` now emits one `Signal.v1` per settled DAG to `DROPLIST_ATLAS_SIGNALS_URL` when set. Drop -> packet -> DAG -> Atlas substrate is a closed loop.

## What landed

| Artifact | Change |
|---|---|
| `droplist/graph_engine.py` | New `_maybe_emit_atlas_signal()` helper + import of `os` and `atlas_signal`. One new line at the settle point: `_maybe_emit_atlas_signal(dag)`. |
| `test_atlas_emit.py` | New 6th acceptance gate. Stdlib `HTTPServer` fixture (no deps). Positive case: env set -> one Signal.v1 POST, structurally valid, audit event. Negative case: env unset -> no POST, no event. |
| `BIBLE.md §12` | Two new rows: PKT-005 + PKT-006 gates. |
| `BIBLE.md §16` | "Open follow-ups" replaced with "Live wire (shipped by PKT-006)" describing env gate, fail-isolation, audit trail. |

## Contract

Set the env var and emission starts:

```bash
export DROPLIST_ATLAS_SIGNALS_URL="http://127.0.0.1:3001/api/signals/ingest"
drop --graph "the doe is limping"
```

Each settle now POSTs one `Signal.v1` (mapped via `atlas_signal.dag_to_signal`). Failure is caught and recorded; the graph loop completes regardless. Audit trail in `data/dag_events.jsonl`:

```json
{"dag_id": "DAG-...", "event": "atlas_signal_emit", "url": "...",
 "signal_id": "sig_...", "ok": true, "error": null}
```

## Verification (all 6 gates green)

```
test_drops          ALL PASS
test_graph          5/5
test_tools          3/3
test_persist        7/7
test_atlas_signal   4/4   (PKT-005)
test_atlas_emit     2/2   (PKT-006)
```

No regressions from pre-PKT-006 baseline. Positive + negative case both verified.

## What this does NOT do

- **No retry buffer.** Failed emissions are logged once and forgotten. A re-emit on reconnection is deferred.
- **No back-channel.** Atlas can't reach into DropList. Still OQ-3 / OQ-4 territory.
- ~~**No source_layer enum change.** Still uses `"optogon"` placeholder. OQ-17 unchanged.~~ **PKT-006 itself did not change the enum; OQ-17 was resolved later by Stop 5 (2026-06-17). Current code emits `source_layer="droplist"`.**
- **No n8n flow JSON.** External config artifact; pattern documented in §16.
