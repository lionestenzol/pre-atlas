# PKT-010 — AtlasArtifact.v1 contract

**Status:** done
**Owner:** claude (drafted) → bruke (approve)
**Scope:** ~60–75 min · 2 new files + 2 edits (schema, schema-test, package.json script, BIBLE.md §13+§17)
**Created:** 2026-06-15
**Closed:** 2026-06-15 (`b7e02c8`)
**Resolves:** OQ-20 (NEW, see §13 row added by this packet)
**Bible refs:** §3 (Product Principle), §10 (Build Rules — settled-core fence), §13 (Open Questions), §14 steps 4 + 6 (pre-flight grep + Do-not-touch fence), §16 (Atlas Seam — sibling contract for behavioral signals), §17 (Artifact Seam — NEW, added by this packet)
**Follows:** PKT-005 (Atlas seam contract — codified §16 against the pre-existing Signal.v1 schema; PKT-010 is bigger because it ships both the new AtlasArtifact.v1 schema AND §17, since no artifact schema exists yet to codify)
**Follow-up:** PKT-011..015 (sketches, see "Follow-up packets" at end — not committed packets per §14 step 3)

---

## Doctrine

From `services/droplist/BIBLE.md`:

> **§3 Product Principle.** The graph has authority. Agents propose; the graph controls state. Local convenience never trumps the graph.

PKT-010 applies §3 to a new producer (claude). Claude has been *proposing* explanations into chat that the graph never sees. This packet lets the graph see them — but only by defining the contract first, never by letting claude write straight into lattice state.

> **§10 Build Rules.** Do not redesign working modules unless tests prove failure. Do not optimize interface before proving state.

Settled-core fence for PKT-010: `Signal.v1.json` is untouched. `signals-store.ts` is untouched. `lattice-projection.ts` is untouched. `apps/lattice/index.html` is untouched. The Atlas substrate stays exactly as PKT-005 / PKT-008 / PKT-009 left it. This packet only **adds** one JSON file (the schema) and one row to §13 (the OQ).

> **§14 step 4.** Pre-flight grep. Before any deletion or rename, `grep -rn` the symbols you plan to touch.

No deletions or renames in this packet. Pre-flight grep below proves the symbol space we want is empty.

> **§14 step 6.** Treat the `Do not touch` list as a hard fence.

See "What this does NOT do" at end.

> **§16 Atlas Seam.** The wire from DropList into the Atlas substrate. Resolves OQ-10. Defined by PKT-005.

§16 governs the *behavioral signal* seam (DropList → delta-kernel via `Signal.v1`). PKT-010 adds a parallel section §17 (Artifact Seam) for the *derived-knowledge* path. §16 stays untouched. The two seams stay separate so Signal.v1 (settled core) doesn't bend to carry payloads it wasn't designed for, and so each seam can evolve independently.

*Precedent note:* PKT-005 codified §16 against the pre-existing `Signal.v1.json` (the schema was committed 2026-04-19 in `065a4a6`, two months before PKT-005 landed §16 in `43866f5`). PKT-010 has a slightly bigger scope because it both **writes** the new `AtlasArtifact.v1` schema AND lands §17 — there is no pre-existing artifact schema to codify.

---

## Summary

Claude produces explanations and widgets (via `/show` and adjacent commands). They render inline in chat and vanish at session end. Lattice never sees them, so the substrate has no memory of them — no way for next-session-claude to read back "what I already explained about X," no way for the user to navigate to a past explanation from a lattice node.

`AtlasArtifact.v1` is the contract that closes that loop. Sibling shape to `Signal.v1`:

| | `Signal.v1` | `AtlasArtifact.v1` |
|---|---|---|
| **Carries** | Behavioral state ("droplist DAG settled to `done`") | Derived knowledge ("explanation of /show with embedded widget") |
| **Lifetime** | Ephemeral — in-memory ring (MAX_SIGNALS=500) | Durable — persisted via Storage class as `entity_type='artifact'` |
| **Discriminator** | `signal_type` enum (6 values) | `artifact_type` enum (4 values: `widget` `explanation` `recon` `anatomy_map`) |
| **Producer** | DropList, optogon, ghost-executor | claude_code primarily; recon scripts; anatomy-map |
| **Consumer** | Lattice (PKT-008 viewmodel wire) | Lattice (future PKT-012 viewmodel wire) |
| **Seam endpoint** | `POST /api/signals/ingest` | `POST /api/atlas/artifacts/ingest` (future PKT-011) |
| **Doctrine** | §16 | §17 (added by this packet) |

This packet ships **the schema only** — one JSON file + one OQ row. Implementation packets (server, viewmodel, UI, claude wire) follow as PKT-011..015 in sequence.

---

## Pre-flight evidence

Confirming the symbol/file space PKT-010 wants to claim is empty:

```bash
# 1. Schema file does not exist
$ ls contracts/schemas/AtlasArtifact* contracts/schemas/Atlas.Artifact* 2>/dev/null
$ ls contracts/schemas/ | grep -i artifact
# (no output)

# 2. No source reference to AtlasArtifact / Atlas.Artifact anywhere
$ grep -rn "AtlasArtifact\|Atlas\\.Artifact" services/ apps/ contracts/ 2>/dev/null
# (no output)

# 3. No /api/atlas/artifacts route
$ grep -n "atlas/artifacts" services/delta-kernel/src/api/server.ts
# (no output)

# 4. No 'artifact' provenance source in lattice-projection
$ grep -n "'artifact'" services/delta-kernel/src/atlas/lattice-projection.ts
# (no output — current LatticeProvenanceSource union is 'cognitive-sensor.idea_registry' | 'optogon' | 'user' | 'ghost_executor' | 'droplist')

# 5. No 'artifact' string anywhere in apps/lattice/index.html
$ grep -in "artifact" apps/lattice/index.html
# (no output)

# 6. OQ-20 slot is free (OQ-19 is the most recent, resolved by PKT-008)
$ grep -E "^\| OQ-(19|20)" services/droplist/BIBLE.md
| OQ-19 | Consumer side of the DropList -> Lattice seam is not wired. ... | **RESOLVED by PKT-008** (2026-06-15). ...
# (OQ-20 absent — next free slot)

# 7. §17 slot is free (§15 and §16 exist; §17 absent — verified by section sweep)
$ grep -E '^## §1[567]' services/droplist/BIBLE.md
## §16. Atlas Seam
## §15. What is deliberately deferred
# (§17 absent — next free slot. §15 is appended after §16 in current file order; PKT-010 adds §17 at the bottom or in §-numeric order at bruke's preference.)

# 8. Schema convention confirmed: all 49 existing $id values are single-PascalCase + .v1 with no internal dots
$ grep -h '"\$id"' contracts/schemas/*.json | sort -u | head -5
"$id": "AegisAgent.v1"
"$id": "AnatomyV1.v1"
"$id": "AnalystDecision.v1"
"$id": "BuildOutput.v1"
"$id": "CloseSignal.v1"
# (zero schemas use Foo.Bar.v1 with internal dots — confirms AtlasArtifact.v1 is the correct shape, not Atlas.Artifact.v1)
```

Reference patterns we are matching:

```bash
# Schema convention sample (Signal.v1 — the structural sibling)
$ head -20 contracts/schemas/Signal.v1.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "Signal.v1",
  "title": "Signal",
  ...
}

# Storage class signature (the persistence path artifacts will use, NOT in this packet)
$ grep -n "loadEntitiesByType\|saveEntity" services/delta-kernel/src/cli/sqlite-storage.ts | head -5

# PKT-005 (the contract-only sibling)
$ ls services/droplist/PACKETS/005_atlas_seam_contract.md
services/droplist/PACKETS/005_atlas_seam_contract.md
```

---

## Spec

### Files touched (2 new + 2 edits)

1. **NEW** — `contracts/schemas/AtlasArtifact.v1.json` (full schema, ~85 lines)
2. **NEW** — `services/delta-kernel/src/tests/atlas-artifact-schema-tests.ts` (~120 LOC — ajv-compile + 11 fixtures; mirrors `lattice-projection-droplist-tests.ts` shape but uses `ajv` + `ajv-formats` like `signals-store.ts:14,54-55`)
3. **EDIT** — `services/delta-kernel/package.json` scripts block — add `"test:artifact-schema": "tsx src/tests/atlas-artifact-schema-tests.ts"` next to existing `test:lattice-droplist` (else the test file is dead — `run-tests.ts` does not glob `src/tests/*.ts`)
4. **EDIT** — `services/droplist/BIBLE.md` — append OQ-20 row to §13 (~1 line) AND add new §17 Artifact Seam section (~40 lines, mirrors §16 shape, points at this packet)

No source-code changes to delta-kernel runtime, no `apps/lattice/` changes, no Signal.v1 changes. The contract-only ships with the contract-only test; downstream wiring lands in PKT-011+.

### Changes

**Change 1 — Create `contracts/schemas/AtlasArtifact.v1.json`:**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "AtlasArtifact.v1",
  "title": "Atlas Artifact",
  "description": "Durable knowledge artifact produced by an agent. Sibling to Signal.v1: signals are behavioral state (ephemeral, ring-buffered); artifacts are derived knowledge (persistent, addressable, re-renderable by lattice). See Bible §17 for the seam doctrine and §16 for the parallel Signal seam.",
  "type": "object",
  "required": ["schema_version", "id", "created_at", "source_layer", "artifact_type", "payload"],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0" },
    "id": { "type": "string", "minLength": 1 },
    "created_at": { "type": "string", "format": "date-time" },
    "source_layer": {
      "type": "string",
      "enum": ["site_pull", "optogon", "atlas", "ghost_executor", "claude_code", "droplist"]
    },
    "artifact_type": {
      "type": "string",
      "enum": ["widget", "explanation", "recon", "anatomy_map"]
    },
    "topic": {
      "type": "object",
      "required": ["text"],
      "properties": {
        "text": { "type": "string", "minLength": 1 },
        "origin": { "type": "string", "enum": ["explicit_arg", "inferred_from_prior_turn"] },
        "raw_command": { "type": ["string", "null"] }
      }
    },
    "session": {
      "type": "object",
      "properties": {
        "session_id": { "type": "string" },
        "turn_index": { "type": "integer", "minimum": 0 },
        "model": { "type": "string" }
      }
    },
    "payload": {
      "type": "object",
      "required": ["title"],
      "properties": {
        "title": { "type": "string", "minLength": 1 },
        "prose": { "type": "string" },
        "widgets": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["mode", "source"],
            "properties": {
              "title": { "type": "string" },
              "mode": { "type": "string", "enum": ["svg", "html"] },
              "source": { "type": "string", "minLength": 1 },
              "loading_messages": { "type": "array", "items": { "type": "string" } }
            }
          }
        },
        "paired_turn": {
          "type": "object",
          "description": "When /show is invoked bare (no argument), it discards the prior assistant turn and re-answers. This captures both sides of that pair so lattice can show the back-reference. prior_assistant_message is the producer's discretion to send verbatim or summarized.",
          "properties": {
            "prior_user_message": { "type": ["string", "null"] },
            "prior_assistant_message": { "type": ["string", "null"] },
            "prior_turn_index": { "type": ["integer", "null"] }
          }
        },
        "data": { "type": "object", "additionalProperties": true }
      }
    },
    "lattice_binding": {
      "type": "object",
      "required": ["node_id"],
      "properties": {
        "node_id": { "type": "string", "minLength": 1 },
        "domain": { "type": ["string", "null"] }
      }
    }
  }
}
```

Field-by-field rationale:

| Field | Why this shape |
|---|---|
| `schema_version: "1.0"` | Rosetta canon (Signal, Directive, ContextPackage all `"1.0"`, not `"1.0.0"`). |
| `id` | `string, minLength 1`. No format constraint — caller picks `art_<uuid12>` to match the `sig_<uuid12>` convention. Not enforced at schema-level (Signal.v1 doesn't either). |
| `created_at` | ISO date-time. Diverges from Signal.v1's `emitted_at` because artifacts are *created* once and re-referenced; signals are *emitted* on a moment. Different verbs, different semantics. Convention is per-schema custom verbs (Signal `emitted_at`, Directive `issued_at`, ContextPackage `captured_at`, BuildOutput `completed_at`, SimulationReport `created_at` — `created_at` matches the durability semantic). |
| `source_layer` | Same 6 values as `Signal.v1.source_layer` enum verbatim — including `claude_code` and `droplist`. At PKT-010 ship this was 5 values; OQ-17 was later resolved by Stop 5 (2026-06-17) which extended BOTH `Signal.v1` and `AtlasArtifact.v1` in a single doctrine move. |
| `artifact_type` | New discriminator enum, 4 values. `widget` = a `/show` SVG/HTML rendering. `explanation` = prose-only output. `recon` = a `code-recon` skill output. `anatomy_map` = an `anatomy-map` skill HTML. Free to extend; lattice renderers branch on this. |
| `topic` | The "what this is about" handle. `origin` distinguishes user-typed args (`/show foo`) from inferred-from-prior-turn (bare `/show`). Lets future readers know how reliable the topic string is. |
| `session` | Conversation provenance — session id, turn index, model. Optional so non-conversational producers (recon scripts) can omit it. |
| `payload.widgets[]` | Array because one /show call can emit multiple widgets. `mode` is the auto-detection result (`<svg` → `svg`, else `html`) — stored explicitly so lattice doesn't re-detect. `source` is the raw widget code; lattice re-renders from this. |
| `payload.paired_turn` | For bare `/show` invocations, captures the prior assistant turn that got "thrown out and re-answered." `prior_assistant_message` is the producer's discretion to send verbatim or summarized; no size constraint enforced. Schema's `description` field calls this out explicitly so future readers don't assume the message is always full or always summarized. |
| `payload.data` | Free-object escape hatch following the §16 convention (`Signal.payload.data` is also `type: object, additionalProperties: true`). For per-artifact-type extras that don't deserve schema keys yet. |
| `lattice_binding` | Optional. When present, `node_id` is REQUIRED and non-empty (a `lattice_binding` object means "this is bound to a real node"; "no binding" is expressed by omitting the field, not by `node_id: null`). Three states: absent (floating), `{node_id: "n42"}` (bound, no domain), `{node_id: "n42", domain: "atlas"}` (fully bound). |

No `oneOf` / `anyOf` per repo convention (zero schemas in the existing 49 use them). Discriminator enum + free payload is the doctrine.

**Change 2 — Append OQ-20 row to `services/droplist/BIBLE.md` §13:**

Insert one row at the bottom of the §13 table, after OQ-19:

```markdown
| OQ-20 | Should claude's chat-side outputs (explanations, widgets, recon snapshots) become substrate, and if so, what's the contract? | Defined by PKT-010 — `AtlasArtifact.v1` is the sibling contract to `Signal.v1`. Sits alongside §16's Signal seam under new §17. PKT-011+ wire the runtime path. |
```

(Wording is intentionally a neutral *should* / *if so* question, not a thesis statement. The contract this packet ships is one resolution; future packets are free to revisit if the schema-based answer proves wrong.)

**Change 3 — Add new section `§17. Artifact Seam` to `services/droplist/BIBLE.md`:**

Insert immediately after the closing of §16 (before §15 "What is deliberately deferred," which currently sits below §16 in section-numeric order). Body mirrors §16 shape:

```markdown
## §17. Artifact Seam

The wire from agents (claude, recon, anatomy-map) into the Atlas substrate. Resolves OQ-20. Defined by PKT-010.

### Endpoint

```
POST  http://<delta-kernel>/api/atlas/artifacts/ingest
  Content-Type: application/json
  Body:        AtlasArtifact.v1 (see contracts/schemas/AtlasArtifact.v1.json)
  Response:    202 { ok: true, artifact_id }   on success
               400 { ok: false, error, details }   on schema validation failure
```

Endpoint is defined by this Bible section; the route is wired in PKT-011.

### How artifacts differ from signals

| | Signal (§16) | Artifact (§17) |
|---|---|---|
| Carries | Behavioral state | Derived knowledge |
| Lifetime | Ephemeral (ring) | Durable (persisted via Storage class as `entity_type='artifact'`) |
| Producer | DropList, optogon, ghost-executor | claude_code primarily; recon scripts; anatomy-map |
| Re-renderable | No | Yes — `payload.widgets[].source` is the source of truth |

The two seams stay separate so Signal.v1 (settled core) doesn't bend to carry payloads it wasn't designed for, and so each seam can evolve independently.

### Three layers, decoupled (same shape as §16)

```
                       AtlasArtifact.v1
claude / /show hook ----------------------> delta-kernel
show_capture.js          POST /api/atlas/artifacts/ingest      (PKT-015 wires the producer; PKT-011 wires the route)
```

### Guarantees and non-guarantees

- **One render = one artifact.** Re-runs produce new `id`s.
- **Pure storage is idempotent** for a given input — same input → same artifact body (modulo `id` and `created_at`).
- **Persistence Atlas-side.** Unlike signals, artifacts are kept indefinitely via the Storage class. Deletion is a future packet.
- **No back-channel today.** Atlas doesn't reach into the producer. (Mirror of §16 same-named constraint.)
```

### Change 4 — Add npm script to `services/delta-kernel/package.json`

Insert one line in the `scripts` block, next to the existing `test:lattice-droplist` entry (added by PKT-008):

```json
"test:artifact-schema": "tsx src/tests/atlas-artifact-schema-tests.ts",
```

Without this, the new test file is dead code from CI/local-loop perspective — `npm test` resolves to `tsx src/core/run-tests.ts` which only imports `./fabric-tests` and does NOT glob `src/tests/*.ts`. The `test:lattice-droplist` script is the precedent pattern.

### What about §16 (Atlas Seam)?

§16 stays untouched. PKT-010 adds the parallel §17 (Artifact Seam) instead of extending §16:

1. §10 settled-core says don't redesign §16 unless tests prove failure. Signal seam is working (PKT-008 closed OQ-19).
2. Artifacts have a different shape, different producer, different lifetime. Extending §16 would force §16 to become a generalized "Atlas seam" rather than the focused Signal seam it is today.
3. PKT-005 precedent (correctly stated): PKT-005 codified §16 against the pre-existing `Signal.v1.json` schema. PKT-010 mirrors the *doctrine-section* half of that pattern (adding §17), while also doing the *schema-creation* half PKT-005 didn't need (since no `AtlasArtifact.v1` exists yet).

So PKT-010 lands §17 NEW alongside the new schema, and leaves §16 untouched.

### What about Signal.v1?

Untouched. Specifically:

- `Signal.v1.source_layer` enum is **not** extended. PKT-010's `AtlasArtifact.v1.source_layer` reuses the existing 5 values verbatim.
- `Signal.v1.signal_type` enum is **not** extended. Artifacts have their own `artifact_type` discriminator.
- No `Signal.v1.payload.data` schema is added or changed.

~~OQ-17 (extending `source_layer` to include `droplist`) is untouched by PKT-010 — it remains pending.~~ **PKT-010 itself did not extend the enums; OQ-17 was resolved later by Stop 5 (2026-06-17), which extended both `Signal.v1.source_layer` and `AtlasArtifact.v1.source_layer` together as the single doctrine move predicted here.**

---

## Contract

The full schema text above IS the contract. Reproduced once more in the canonical location (`contracts/schemas/AtlasArtifact.v1.json`) so reviewers can compare.

A worked example (happy-path `widget` artifact, no lattice binding):

```json
{
  "schema_version": "1.0",
  "id": "art_8a4f9b6e68f3",
  "created_at": "2026-06-15T14:43:21.108Z",
  "source_layer": "claude_code",
  "artifact_type": "widget",
  "topic": {
    "text": "delta-kernel autoheal explainer",
    "origin": "inferred_from_prior_turn",
    "raw_command": "/show"
  },
  "session": {
    "session_id": "0631e005-bb73-4e67-ab25-579cf1e0a4e5",
    "turn_index": 14,
    "model": "claude-opus-4-7[1m]"
  },
  "payload": {
    "title": "Delta-kernel dies and self-heals within 15 minutes",
    "prose": "Tool availability. There's an MCP server called visualize connected to this session that exposes show_widget...",
    "widgets": [
      {
        "title": "delta_kernel_autoheal_explainer",
        "mode": "svg",
        "source": "<svg width=\"100%\" viewBox=\"0 0 680 460\" role=\"img\">...</svg>",
        "loading_messages": ["Drawing the heartbeat", "Sketching the bounce-back", "Laying out the before and after"]
      }
    ],
    "paired_turn": {
      "prior_user_message": "the widgets ae new though bc it used t obe ascii",
      "prior_assistant_message": "Explained that the visualize MCP server is what enabled SVG widgets vs the prior ASCII art.",
      "prior_turn_index": 13
    }
  }
}
```

(Note: `lattice_binding` is omitted to mean "floating artifact, no binding to a specific lattice node." If a future producer wants to bind, the field present with non-empty `node_id` is the signal.)

---

## Verification

### NEW UNIT TEST

`services/delta-kernel/src/tests/atlas-artifact-schema-tests.ts` (NEW, ~120 LOC) — load `AtlasArtifact.v1.json` with ajv-compile, run 11 labeled fixtures. **MUST** mirror `signals-store.ts:14,54-55` ajv setup exactly:

```typescript
import Ajv, { type ValidateFunction } from 'ajv';
import addFormats from 'ajv-formats';
const ajv = new Ajv({ strict: false, allErrors: true });
addFormats(ajv);  // load-bearing — without this, format: date-time is silently a no-op
const validate = ajv.compile(schema);
```

Omitting `addFormats(ajv)` makes the `format: date-time` constraint invisible to the test (ajv strict:false downgrades unknown-format to a warning, not an error). This is the production validator's exact wiring — the test must match or the schema's date-time guarantee is fictional in CI.

| # | Fixture | Asserts |
|---|---|---|
| 1 | Happy `widget` (worked example) | `validate === true`; zero errors |
| 2 | Happy `explanation` (no widgets, prose + topic only) | valid; tolerates absent `widgets` and absent `paired_turn` |
| 3 | Happy `recon` (payload.data = free nested object) | valid; `payload.data` accepts arbitrary nested shape |
| 4 | Happy `anatomy_map` (source_layer = `site_pull`) | valid; exercises both the 4th artifact_type AND a non-`claude_code` source_layer |
| 5 | Happy `widget` with `mode: "html"` (not svg) | valid; covers the html branch of the mode enum |
| 6 | Happy artifact with `lattice_binding: {node_id: "n42"}` present | valid; covers the bound state |
| 7 | Missing `schema_version` (required field) | `false`; error message includes `schema_version` |
| 8 | Missing `payload.title` (required nested field) | `false`; error mentions `title` |
| 9 | Bad `artifact_type` (e.g. `"poem"`) | `false`; error mentions enum violation |
| 10 | Bad `source_layer` (e.g. `"drilbit"`) | `false`; error mentions enum violation |
| 11 | Malformed `created_at` (e.g. `"yesterday"`) | `false`; error mentions `format` / `date-time` — proves `addFormats` is wired correctly |

Gate: **11/11 PASS.** Fixture 11 is the canary: if `addFormats(ajv)` is forgotten in the test setup, fixture 11 will spuriously pass `validate === true` and the gate must catch that (i.e. the assertion is `validate === false`, not `validate === true || true`).

Test file is self-contained — no runtime dependency on a future artifacts-store. Schema-loading test only.

### REGRESSION GATE — existing acceptance gates must still pass

PKT-010 touches no source code. The following gates from Bible §12 must hold their existing counts unchanged:

| Suite | Expected |
|---|---|
| `test_drops` | PASS |
| `test_graph` | 5/5 |
| `test_tools` | 3/3 |
| `test_persist` | 7/7 |
| `test_atlas_signal` | 4/4 |
| `test_atlas_emit` | 2/2 |
| `test_server` | 7/7 |
| `services/delta-kernel/src/tests/lattice-projection-droplist-tests.ts` | All PASS (PKT-008's added tests, exact count to be re-verified at execution) |

If any gate count drops, the packet does not ship. There is no rebalancing.

### E2E smoke

**None.** PKT-010 adds a schema file + doctrine section. There is no runtime path to exercise. E2E enters at PKT-011 when the first `POST /api/atlas/artifacts/ingest` route exists, and the full producer → consumer chain enters at the end of PKT-014/PKT-015.

### Manual UI test plan

**None.** No UI changes in this packet.

### Operational gate (run before declaring done)

```bash
cd services/delta-kernel
npm run test:artifact-schema  # MUST report 11/11 PASS
npm run test:lattice-droplist # MUST report unchanged count (PKT-008 baseline)
npm test                      # the original fabric-tests — MUST stay green
```

---

## What this does NOT do

- Does **NOT** modify `contracts/schemas/Signal.v1.json` (settled core per §10).
- Does **NOT** modify `services/delta-kernel/src/atlas/signals-store.ts` (settled core).
- Does **NOT** modify `services/delta-kernel/src/atlas/lattice-projection.ts` — PKT-008 territory, untouched.
- Does **NOT** modify `apps/lattice/index.html` — PKT-009 territory, untouched.
- Does **NOT** add a server route. `POST /api/atlas/artifacts/ingest` is PKT-011.
- Does **NOT** create `services/delta-kernel/src/atlas/artifacts-store.ts`. PKT-011.
- Does **NOT** extend `LatticeProvenanceSource` to include `'atlas.artifact'`. PKT-012.
- Does **NOT** render artifacts in lattice. PKT-013.
- Does **NOT** ship a claude-side MCP server or skill. PKT-014.
- Does **NOT** hook `/show` to emit artifacts. PKT-015.
- Does **NOT** define `GET /api/atlas/context` (the "current lattice focus + recent artifacts" aggregate). Out of scope until PKT-011's follow-up sketch resolves how focus is tracked.
- ~~Does **NOT** extend `Signal.v1.source_layer` enum (OQ-17 untouched).~~ **PKT-010 didn't; Stop 5 (2026-06-17) did — both enums extended together as the single doctrine move predicted above.**
- ~~Does **NOT** add `"droplist"` to `AtlasArtifact.v1.source_layer` — when droplist becomes an artifact producer, both enums extend together (one doctrine move).~~ **Done by Stop 5 (2026-06-17), independent of droplist becoming an artifact producer — shipped on Bruke override for honesty (`Signal.v1` already had a real droplist producer via PKT-006).**
- Does **NOT** define a `oneOf`-discriminated payload variant. Repo convention is enum-on-envelope + free payload. If a future packet proves the four artifact_types need separate shapes, that's a doctrine move with its own packet.

---

## Open before execution

1. **OQ-20 wording.** Current draft is a neutral *should / if so* question, not a thesis. Bruke confirms the wording or edits before commit.
2. **`artifact_type` enum scope.** Current: `widget` `explanation` `recon` `anatomy_map`. If bruke wants to leave one off (e.g. drop `recon` — `code-recon` outputs are markdown, not visual artifacts) or add (e.g. `manuscript_page` for the PaperMe pipeline), decide before commit. Enums are easy to extend later but enum values cannot be removed without a schema migration.
3. **§17 placement in BIBLE.md.** Current file order is: §13, §14, §16, §15 (numerically out of order). PKT-010 inserts §17 — bruke picks placement: (a) immediately after §16 to keep "seam" sections grouped, (b) after §15, (c) renumber to fix the existing §15/§16 ordering issue as part of this packet. Default: option (a).
4. **`paired_turn.prior_assistant_message` size policy.** Schema doesn't constrain length. Producer (PKT-015 capture hook) decides verbatim vs summary. Confirm bruke is fine with that flexibility, or add a soft `maxLength` (e.g. 4000) to nudge toward summarization.

---

## Follow-up packets (sketches, not committed)

> **These are roadmap sketches. Each requires its own packet per §14 step 3 before work begins. Scope estimates are best-effort and will be re-calibrated when each packet is written.**

The /show ↔ lattice ↔ claude vision is a 6-packet sequence. PKT-010 ships the contract; the rest implement against it:

| # | Title | Sketched scope | Touches | Hard deps |
|---|---|---|---|---|
| **PKT-010** | **AtlasArtifact.v1 contract** *(this packet)* | ~60–75 min | `contracts/schemas/AtlasArtifact.v1.json` (NEW), `services/delta-kernel/src/tests/atlas-artifact-schema-tests.ts` (NEW), `services/delta-kernel/package.json` (+1 script), BIBLE §13 OQ-20 + §17 (NEW) | — |
| PKT-011 | Artifacts-store + ingest route + (optional) /api/atlas/context | ~60 min | `services/delta-kernel/src/atlas/artifacts-store.ts` (NEW, mirrors signals-store), `server.ts` (+POST `/ingest`, +GET `/artifacts`, optionally +GET `/api/atlas/context` aggregate) | PKT-010 |
| PKT-012 | Lattice viewmodel consumes artifacts | ~30 min | `lattice-projection.ts` (mirrors PKT-008's signals consumer block; adds `loadArtifacts?` to `StorageLike`; `artifactToItem()` helper; extends `LatticeProvenanceSource`) | PKT-011 |
| PKT-013 | Lattice UI renders artifacts | ~30 min | `apps/lattice/index.html` (mirrors PKT-009; adds `'artifact'` branch to ctx menu + correction gate; zod schema for `artifacts`) | PKT-012 |
| PKT-014 | claude-side MCP server `atlas-context` | ~45–60 min | NEW MCP server in `~/mcp-servers/atlas-context/` with two tools: `atlas_artifact_write` (POSTs to `/api/atlas/artifacts/ingest`), `atlas_artifact_recent` (GETs `/api/atlas/artifacts?since=`). Adds entry to `~/.claude.json` MCP config. **NOTE:** original PKT-010 sketch claimed `atlas_context_read` would fetch "lattice focus + recent artifacts" — but no `lattice_focus` exists server-side. Either descope to `atlas_artifact_recent` (this row) OR add a follow-up packet PKT-014b to ship client→server focus tracking. | PKT-011 |
| PKT-015 | `/show` capture hook | ~50–75 min | `~/.claude/scripts/hooks/show-capture.js` (NEW), `~/.claude/settings.json` (+PostToolUse matcher `mcp__visualize__show_widget`). Reads session JSONL at `~/.claude/projects/<slug>/<session_id>.jsonl` to find paired turn. POSTs `AtlasArtifact.v1` to delta-kernel via the MCP tool from PKT-014. **NOTE:** original PKT-010 sketched this as 15 min in `~/.claude/commands/show.md` — that was wrong twice (commands aren't a hook surface; hooks live in `scripts/hooks/`). Real work is the session-JSONL parse for `paired_turn` capture. | PKT-014 (hard) |

**Hard dependency note:** PKT-015 calls `atlas_artifact_write` (an MCP tool defined by PKT-014). If PKT-014 is reverted while PKT-015 is live, every `/show` invocation errors. PKT-015 must ship after PKT-014, and a revert of PKT-014 must roll PKT-015 with it.

**Pragmatic ship order:** PKT-011 → PKT-012 → PKT-014 → PKT-015 (now `/show` writes are persisting) → PKT-013 (now lattice can render what's been written). PKT-013 can land earlier in the chain but its UI is dormant until artifacts exist.

**Missing-packet candidates (not committed, just flagged):**
- *PKT-014b* (focus tracking): if bruke wants "claude reads what user is currently looking at," needs a `POST /api/lattice/focus` from `apps/lattice/index.html` and a `GET /api/atlas/context` aggregate. ~45 min, optional.
- *PKT-016* (E2E integration): tiny packet asserting `claude → MCP → kernel → lattice viewmodel → DOM` as a single transaction. Either land as its own packet or fold into PKT-013's verification.

Total realistic budget across PKT-010..015: **~4.5–5.5 hours**, not 3.5.
