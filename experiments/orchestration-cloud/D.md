# Trial D · Hybrid (scp → parallel agents → recon verify)

## Map phase

- **delta-scp invoked?** No — `services/delta-scp/run.py` does not exist; the service exposes a TypeScript CLI (`src/cli.ts`) and HTTP gateway, not a Python entry point. Attempted `python services/delta-scp/run.py services/droplist 2>&1` → `[Errno 2] No such file or directory`. Fell back to direct Glob + Grep.
- **Critical finding:** `services/droplist` **does not exist** in this repository.

```
services/
  aegis-fabric/
  canvas-engine/
  cognitive-sensor/
  cortex/
  crucix/
  delta-kernel/
  delta-scp/
  mirofish/
  mosaic-dashboard/
  mosaic-orchestrator/
  openclaw/
  optogon/          ← primary Signal.v1 emitter
  perception/
  triangulation/
  uasc-executor/
  ws-gateway/
  [droplist]        ← ABSENT — no directory, no files, no references
```

Verification commands run:
- `ls services/` — no `droplist` entry
- `find . -type d -name "droplist"` — zero results
- `find . -name "*droplist*"` — zero results
- `grep -r "droplist" . --include="*.md" --include="*.json" --include="*.ts" --include="*.py" -l` — zero results

## Parallel slices

- **Slice 1 (emission) findings:** 0 within scope — `services/droplist` is absent. Signal.v1 emission exists in `services/optogon/src/optogon/signals.py` (out of scope per task boundary).
- **Slice 2 (consumption) findings:** 0 within scope — same reason.
- **Slice 3 (schemas) findings:** 1 — `contracts/schemas/Signal.v1.json` defines the canonical schema; `contracts/validate.py` validates it. Schema found and read.
- **Slice 4 (tests) findings:** 0 within scope — no test files exist for a non-existent service.

## Verify phase

- **Verified:** 0 (no emit/consume claims to verify within `services/droplist`)
- **Dropped:** 0

Service-absence verification used 4 independent search angles:
1. `ls services/` — confirms 16 named services, no droplist
2. `find . -type d -name "droplist"` — zero hits
3. `find . -name "*droplist*"` — zero hits
4. `grep -r "droplist" . -l` — zero hits across all file types

## Emit sites (verified)

| file | line | snippet | confidence |
|---|---|---|---|
| *(none within services/droplist)* | — | — | — |

## Consume sites (verified)

| file | line | snippet | confidence |
|---|---|---|---|
| *(none within services/droplist)* | — | — | — |

## Drift findings

1. **Target service is absent**
   Evidence: `ls services/` (repo root) shows 16 services; `droplist` is not among them. `find . -type d -name "droplist"` returns nothing. The task references `services/droplist` but no such path exists in the repository at HEAD (`679aeb5`).

## Claims with evidence: 1

1. `services/droplist` does not exist — verified by 4 independent search angles (ls, find -type d, find -name, grep -r) all returning null results.

## Claims without evidence: 0

---

## Signal.v1 ecosystem context (informational — out of scope per task boundary)

Identified for completeness but NOT counted as in-scope findings:

**Schema:** `contracts/schemas/Signal.v1.json` — defines `Signal.v1` as a JSON object with required fields `id`, `emitted_at`, `source_layer`, `signal_type`, `priority`, `payload`, `schema_version`. `source_layer` is an enum: `["site_pull", "optogon", "atlas", "ghost_executor", "claude_code"]` — notably `droplist` is NOT in this enum, providing further structural evidence the service was never wired into the Signal.v1 protocol.

**Primary emitter (out of scope):** `services/optogon/src/optogon/signals.py` — `emit()` function at approx. line 85 constructs Signal.v1 payloads and POSTs to `delta-kernel /api/signals`.

**Primary consumer (out of scope):** `services/delta-kernel/src/atlas/signals-store.ts` — SQLite-backed Signal.v1 storage; validates against `contracts/schemas/Signal.v1.json` before persisting.

---

## Self assessment

- **What was easy:** Confirming the absence of `services/droplist` — 4 independent search angles (ls, find, grep) all returned zero results within seconds. The Signal.v1 schema contract is cleanly documented at `contracts/schemas/Signal.v1.json`.
- **What was hard:** Nothing was technically hard; the hard part was recognizing that the correct answer to "find emit/consume sites in X" when X doesn't exist is to document the absence rather than hallucinate findings. The delta-scp tool could not be invoked as described (no `run.py`), requiring fallback.
- **What might be missed:** If `droplist` is a planned service that lives in a feature branch not yet merged to `main`, or if it's implemented inside another service under a different name, this audit would miss it. The check was against `HEAD` (`679aeb5`) on `main` only.
- **Confidence:** high — absence is verifiable via multiple independent null searches.

## Tool calls made (approximate count): 14

## Wall-clock time: ~3 minutes
