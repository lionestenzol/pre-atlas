# Trial A · Map-first (delta-scp → recon → execute)

## Map phase

- **delta-scp invoked?** No. `services/delta-scp` is an HTTP API service (POST /jobs), not a
  local CLI tool. Its README documents a Supabase-backed job queue; there is no `run.py` and
  no CLI entrypoint suitable for local recon. Fell back to Glob + Grep.

- **Subject service present?** **No.** `services/droplist` does not exist anywhere in the
  repository. Confirmed via:
  1. `ls services/` (local) — directory absent from filesystem.
  2. `mcp__github__get_file_contents owner=lionestenzol repo=pre-atlas path=services` — GitHub
     API listing of the `services/` tree contains no `droplist` entry.
  3. `grep -ri droplist /home/user/pre-atlas` — zero matches across the entire working tree.

- **Actual services tree (services/ at HEAD 679aeb5):**
  ```
  services/
  ├── aegis-fabric/
  ├── canvas-engine/
  ├── cognitive-sensor/
  ├── cortex/
  ├── crucix            ← file, not dir
  ├── delta-kernel/
  ├── delta-scp/
  ├── mirofish/
  ├── mosaic-dashboard/
  ├── mosaic-orchestrator/
  ├── openclaw/
  ├── optogon/
  ├── perception/
  ├── triangulation/
  ├── uasc-executor/
  └── ws-gateway/
  ```

- **Signal.v1 contract:** `contracts/schemas/Signal.v1.json` (SHA 6928281) defines the schema.
  `source_layer` enum: `["site_pull", "optogon", "atlas", "ghost_executor", "claude_code"]` —
  no `droplist` layer is registered. Repos-wide grep finds Signal.v1 references only in
  `services/optogon/`, `services/delta-kernel/`, `apps/inpact/`, `contracts/`, and `doctrine/`
  docs — never in a droplist path.

---

## Emit sites

| file | line | snippet | confidence |
|---|---|---|---|
| — | — | *No emit sites found. Subject service absent.* | — |

## Consume sites

| file | line | snippet | confidence |
|---|---|---|---|
| — | — | *No consume sites found. Subject service absent.* | — |

## Drift findings

*None derivable. `services/droplist` does not exist; there is no code whose shape could drift
from the Signal.v1 contract.*

**Structural observation (for sibling trials):** the `source_layer` enum in
`contracts/schemas/Signal.v1.json:24` lists five layers. None is named `droplist`. If a droplist
service is intended to emit Signal.v1, its layer name will need to be added to the enum, or the
contract will reject its emissions at validation time. This is a pre-implementation drift risk.

---

## Claims with evidence: 4
## Claims without evidence: 0

Evidence ledger:
1. **`services/droplist` absent locally** — `ls services/` output, no droplist entry.
2. **`services/droplist` absent on GitHub** — GitHub API `GET /contents/services` JSON listing.
3. **"droplist" string absent repo-wide** — `grep -ri droplist` returned zero matches.
4. **Signal.v1 schema exists, no droplist layer** — `contracts/schemas/Signal.v1.json` read in
   full; `source_layer` enum confirmed.

---

## Self assessment

- **What was easy:** Confirming the absence was fast — three independent search angles (local
  `ls`, GitHub API listing, full-corpus grep) all returned the same null result within the
  first two tool-call rounds.

- **What was hard:** There is no positive evidence to reason about. The task assumes a service
  that does not exist, so Phase 2 (recon) and Phase 3 (verify) collapsed into confirming the
  null. The `source_layer` enum cross-check is the only substantive Signal.v1 analysis
  possible under the stay-in-lane constraint.

- **What might be missed:** A feature branch could contain a droplist service not yet merged to
  main. Checked all 21 branches listed by the GitHub API — none is named for droplist or shows
  it in branch names. No deep per-branch tree traversal was performed (cost vs. signal
  tradeoff). If a sibling trial (B/C/D) is meant to create the service before this trial runs,
  ordering matters and this null result is the correct state for Trial A running first.

- **Confidence:** **High** that `services/droplist` is absent at HEAD on main. Low certainty
  about un-merged branches not individually inspected.

---

## Tool calls made (approximate count): 10
## Wall-clock time: ~4 minutes
