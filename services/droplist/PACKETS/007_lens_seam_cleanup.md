# PKT-007 — Lens-seam cleanup (remove duplicate Lattice route)

**Status:** done
**Owner:** claude_code (recon-corrected cleanup)
**Scope:** ~20 min
**Created:** 2026-06-14
**Closed:** 2026-06-14
**Resolves:** OQ-18 (duplicate Lattice surface across droplist + delta-kernel)
**Bible refs:** §3 Principle ("no node done without evidence"), §10 (settled core), §13 OQ-18

---

## Doctrine

1. The graph has authority.
2. No completed core is reopened unless validation fails. delta-kernel's `lattice-projection.ts` is settled core; droplist must not duplicate it.
3. No interface before state. The :3071 lattice route was an interface without a real consumer.

(See `DOCTRINE.md`.)

---

## Summary

A prior `/weapon` workflow (wf_8ee048e7-eb9) shipped a parallel `/api/lattice/viewmodel` route in `droplist/server.py` on port 3071. Code-recon verify mode caught the mismatch before commit:

- `apps/lattice/index.html:2368` hardcodes `ATLAS_BASE = 'http://127.0.0.1:3001'`
- `apps/lattice/index.html:2407` fetches `ATLAS_BASE + '/api/lattice/viewmodel'`
- `services/delta-kernel/src/api/server.ts:2003` already serves that route via `atlas/lattice-projection.ts`

Lattice will never call :3071. The droplist route was dead on arrival.

This packet removes the duplicate. DropList keeps its read-only API for `line.html` + `chain.html`. The droplist -> Lattice feed already exists via PKT-006's `Signal.v1` emission to delta-kernel.

## Pre-flight evidence

```
grep -rn "lattice_viewmodel|lattice/viewmodel" services/droplist/

services/droplist/droplist/server.py:118  @app.get("/api/lattice/viewmodel")
services/droplist/droplist/server.py:119  def get_lattice_viewmodel() -> dict:
services/droplist/droplist/server.py:120      from . import lattice_viewmodel
services/droplist/droplist/server.py:121      return lattice_viewmodel.build_viewmodel()
services/droplist/test_server.py:112     # comment ref only
services/droplist/test_server.py:122-123 # checks list entry
services/droplist/droplist/lattice_viewmodel.py  # the orphan mapper

grep -rn "lattice_viewmodel" services/delta-kernel/ apps/
# zero hits — no consumer outside droplist itself
```

Confirms: removing the route makes `lattice_viewmodel.py` an orphan with zero callers anywhere in the tree.

## What landed

| Artifact | Change |
|---|---|
| `droplist/server.py` | Removed `/api/lattice/viewmodel` route (4 lines). Added 6-line comment block at imports explaining where Lattice lives. |
| `droplist/lattice_viewmodel.py` | Deleted. 130-line mapper had a single caller (the removed route). |
| `test_server.py` | Removed `/api/lattice/viewmodel` row from `_checks()` contract gate. Updated header comment. PKT-007 acceptance gate is now 7 endpoints, not 8. |
| `BIBLE.md §13` | Added OQ-18 entry, marked RESOLVED. |

## Contract — DropList HTTP surface after cleanup

`droplist/server.py` exposes 7 read-only endpoints on `127.0.0.1:3071`:

```
GET /api/now              -> {job, after}            (line.html)
GET /api/dag/{dag_id}     -> dag object               (chain.html)
GET /api/dags             -> {dags}                   (listing)
GET /api/packets          -> {packets, total}         (packet list)
GET /api/state            -> {recurring, due_today, locked_refs}
GET /api/brief            -> {ready, blocked, waiting}
GET /api/entities         -> {entities}
```

Lattice integration path:

```
DropList settle -> Signal.v1 -> delta-kernel /api/signals/ingest
                                        |
                                        v
                              lattice-projection.ts
                                        |
                                        v
                       GET /api/lattice/viewmodel  (delta-kernel:3001)
                                        |
                                        v
                       apps/lattice/index.html  (replicache pull)
```

DropList does not own a Lattice surface. delta-kernel does. PKT-006's `_maybe_emit_atlas_signal` is the wire.

## Verification

```
test_drops          ALL PASS
test_graph          5/5
test_tools          3/3
test_persist        7/7
test_atlas_signal   4/4   (PKT-005)
test_atlas_emit     2/2   (PKT-006)
test_server         7/7   (PKT-007, was 8/8 with the duplicate)
```

No regressions. The contract gate now reflects droplist's actual responsibility surface.

## What this does NOT do

- **Does not modify delta-kernel.** Its `/api/lattice/viewmodel` + `/api/lattice/correct` routes are unchanged. Settled core stays settled.
- **Does not extend Signal.v1 mapping.** Whether `lattice-projection.ts` should pull anything additional from droplist-emitted signals (vs. just reading delta-kernel's existing state) is a delta-kernel-side decision, not a droplist one.
- **Does not delete the `ui/` HTMLs.** `line.html` (`/api/now`) and `chain.html` (`/api/dag/{id}`) both depend on droplist's surviving endpoints.

## Why this was a near-miss

Recon agents in the prior workflow read `Downloads/lattice.html` (a standalone prototype with in-memory state and no hardcoded base URL) and inferred the contract from it. They never opened `apps/lattice/index.html` — the production Replicache-backed version that points at delta-kernel. The /weapon workflow shipped the route to a port the real Lattice can't reach.

Caught by `code-recon` verify mode (two-angle citation required per load-bearing claim). The "apps/lattice fetches `/api/lattice/viewmodel`" claim resolved via Grep + Read against the production file, not the prototype. The hardcoded base URL surfaced immediately.

This is exactly the failure mode the verifier discipline (memory: `feedback_agent_report_distrust.md`, `reference_verified_audit_default.md`) exists to catch. The packet workflow caught it before commit, as designed.
