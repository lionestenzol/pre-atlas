# Trial B · Hunt-first (recon → scp → execute)

## Hunt phase

- Search angles used:
  1. `Signal\.v1|signal_v1|SignalV1` — regex across `services/droplist` (path)
  2. `emit_signal|publish|send_signal` — regex across `services/droplist` (path)
  3. `Signal\.v1|signal_v1|SignalV1|emit_signal|send_signal|consume_signal|receive_signal` — regex across `services/` root
  4. `Signal|signal` — broad file-match across `services/`
  5. `droplist` — literal search across entire repo (all files)
  6. `find /home/user/pre-atlas -name "*droplist*"` — filesystem name search
  7. `emit|publish|consume|receive` with glob `**/droplist*` — pattern-scoped search

- Total hits: 0 within `services/droplist` (directory does not exist)

**Critical finding:** `services/droplist` does not exist in this repository. The full list of service directories under `services/` is:

```
aegis-fabric   canvas-engine  cognitive-sensor  cortex
crucix         delta-kernel   delta-scp         mirofish
mosaic-dashboard  mosaic-orchestrator  openclaw  optogon
perception     triangulation  uasc-executor     ws-gateway
```

No file or directory anywhere in the repo matches the string "droplist" by any search angle.

Signal.v1 patterns DO exist in the repo, but exclusively in services outside the mission scope:
- `services/optogon/src/optogon/signals.py:1` — EMIT (builds Signal.v1 payloads)
- `services/optogon/src/optogon/preferences_client.py:80` — EMIT (POST CloseSignal.v1)
- `services/delta-kernel/src/atlas/signals-store.ts:2,7,10,90` — CONSUME/STORE
- `services/delta-kernel/src/api/server.ts:1988,2070` — CONSUME (ingest endpoint)
- `services/cognitive-sensor/SYSTEM_MAP.md:117` — doc reference only

All of these are out-of-scope for this trial (optogon and delta-kernel are not droplist).

## Local map phase

- delta-scp invoked? **No** — `tsx` runtime is not installed in this environment.
  Command attempted: `cd services/delta-scp && npm run compress -- /home/user/pre-atlas/services`
  Result: `sh: 1: tsx: not found` — uninvocable within the 2-minute budget.
- Fell back to: Glob + Grep for all symbol and file-pattern searches.

- Localized skeleton: **N/A** — no hit files exist within `services/droplist`.

Out-of-scope Signal.v1 topology (for orientation only, not the deliverable):
```
services/optogon/
  src/optogon/signals.py          ← builds Signal.v1 payloads → posts to delta-kernel
  src/optogon/preferences_client.py ← posts CloseSignal.v1 → delta-kernel

services/delta-kernel/
  src/atlas/signals-store.ts      ← SQLite-backed Signal.v1 storage, validates schema
  src/api/server.ts               ← POST /api/atlas/signals (ingest) + /api/atlas/close-signal
```

## Emit sites

| file | line | snippet | confidence |
|---|---|---|---|
| *(none)* | — | `services/droplist` does not exist | N/A |

## Consume sites

| file | line | snippet | confidence |
|---|---|---|---|
| *(none)* | — | `services/droplist` does not exist | N/A |

## Drift findings

1. **Scope target absent** — The mission requests analysis of `services/droplist`, but no such service directory or file exists in the repository at HEAD (branch `main`, date 2026-06-15). No emit, consume, or drift analysis is possible.
   Evidence: `find /home/user/pre-atlas -name "*droplist*"` → empty; `ls /home/user/pre-atlas/services/` → 16 directories, none named droplist.

## Claims with evidence: 1
## Claims without evidence: 0

---

**Evidence-backed claims:**
1. `services/droplist` does not exist — verified by 7 independent search angles (directory listing, `find` name search, repo-wide `grep` for "droplist", Glob with `**/droplist*`, and three Signal-pattern grepping runs all targeting that path and producing zero results).

## Self assessment

- **What was easy:** Confirming the absence of the target; the directory listing and "droplist" literal search both returned immediately with zero hits. Multiple angles converged on the same null result with high confidence.
- **What was hard:** Distinguishing "target does not exist" from "search technique is wrong" — required running 7 distinct angles including filesystem `find`, repo-wide literal grep, and path-scoped pattern greps before concluding with confidence.
- **What might be missed:** A service under a different name that serves the same functional role as a "droplist" (e.g., a queue or drain service). Brief scan of existing service names and their SYSTEM_MAP docs found no strong candidate. The `crucix`, `openclaw`, and `perception` services were not deeply explored but have no Signal.v1 hits via the broad pattern search.
- **Confidence:** **High** — null result confirmed by 7 independent angles.

## Tool calls made (approximate count): 12
## Wall-clock time: ~4 minutes
