# Contracts

JSON Schema contracts that define data formats exchanged between Pre Atlas services.

**Total schemas:** 47 as of 2026-04-26 (45 versioned `.v1.json` + 2 legacy unversioned: `CognitiveMetricsComputed.json` and `DirectiveProposed.json`)
**Python validator:** `contracts/validate.py` (jsonschema; walks `contracts/examples/` for example/schema pairs)
**TypeScript gate (AnatomyV1):** Zod twin at `services/canvas-engine/src/adapter/v1-schema.ts` — in-process validation inside the canvas-engine producer-consumer pipeline. ajv 8.x is in delta-kernel deps but no `npm run validate:anatomy` script is wired today.

---

## Overview

All data exports are validated against these schemas before writing. This ensures:

1. **Type safety** - Data conforms to expected structure
2. **Contract enforcement** - Services agree on data formats
3. **Validation** - Invalid writes are blocked

For canvas-engine specifically, the Zod twin in `services/canvas-engine/src/adapter/v1-schema.ts` uses `.passthrough()` on root/regions/chains/chainNodes/metadata as a mandatory two-way contract with `AnatomyV1.v1.json`. Adding a field to one without the other = silent drop.

---

## Schemas

### Cognitive / governance core (cognitive-sensor stack)

| Schema | Purpose | Used By |
|--------|---------|---------|
| `CognitiveMetricsComputed.json` | Cognitive state metrics | `export_cognitive_state.py` |
| `DailyPayload.v1.json` | CycleBoard UI payload | `export_daily_payload.py` |
| `DailyProjection.v1.json` | Combined daily artifact | `build_projection.py` |
| `DirectiveProposed.json` | CycleBoard mode routing directive (distinct from `Directive.v1.json` below) | `route_today.py` |
| `Closures.v1.json` | Closure registry + streaks | Phase 5B `/api/law/close_loop` |
| `CloseSignal.v1.json` | Closure event payload | Optogon → Atlas |
| `EnergyLog.v1.json` | Energy / sleep log entries | governance daemon |
| `LifeSignals.v1.json` | Aggregated life-signal payload | cognitive-sensor exports |
| `TimelineEvents.v1.json` | Timeline event stream | dashboard, atlas-cli |
| `WorkLedger.v1.json` | Work ledger entries | atlas-cli, daemon |
| `IdeaRegistry.v1.json` | Captured ideas registry | excavator, atlas-cli |
| `ExcavatedIdeas.v1.json` | Excavator output | `excavator.py` |
| `ModeContract.v1.json` | Python↔TS routing contract | `routing.ts` + `atlas_config.py` |

### Aegis Fabric (7 schemas)

Policy + approval engine. All Aegis schemas live in both `contracts/schemas/` and `services/aegis-fabric/contracts/schemas/`.

| Schema | Role |
|--------|------|
| `AegisAgent.v1.json` | Registered agent identity |
| `AegisAgentAction.v1.json` | Action attempt by an agent |
| `AegisApproval.v1.json` | Human/auto approval verdict |
| `AegisPolicy.v1.json` | Policy rule definition |
| `AegisPolicyDecision.v1.json` | Policy engine decision |
| `AegisTenant.v1.json` | Tenant scoping |
| `AegisWebhook.v1.json` | Outbound webhook notification |

### Cortex / governance extensions (added 2026-04-18)

| Schema | Role |
|--------|------|
| `CortexTask.v1.json` | Cortex execution task |
| `AnalystDecision.v1.json` | Analyst-layer decision |
| `RiskMitigation.v1.json` | Mitigation plan |
| `ProjectGoal.v1.json` | Project-level goal record |
| `WorkflowEvent.v1.json` | Workflow state event |
| `AutomationQueue.v1.json` | Automation backlog entry |
| `OrchestratorEvent.v1.json` | mosaic-orchestrator event |
| `TaskExecution.v1.json` | TaskPrompt → BuildOutput transcript |
| `ExecutionResult.v1.json` | Generic execution result envelope |
| `ExecutionSpec.v1.json` | Generic execution spec envelope |

### Mosaic Platform

| Schema | Role |
|--------|------|
| `CompoundState.v1.json` | Compound (rolled-up) system state |
| `FinancialLedger.v1.json` | Financial ledger entries |
| `MeteringUsage.v1.json` | Metering / usage records |
| `NetworkRegistry.v1.json` | Network registry |
| `SkillRegistry.v1.json` | Skill registry |
| `ValidationVerdict.v1.json` | Validator verdict |
| `SimulationReport.v1.json` | Simulation report |

### Anatomy / canvas-engine (added 2026-04-26)

| Schema | Role |
|--------|------|
| `AnatomyV1.v1.json` | Anatomy extension → canvas-engine producer-consumer contract. Validated 7/7 real captures (hn-v1, example-v1, ycombinator, linear, figma, apify, gmail). In-process gate: Zod twin at `services/canvas-engine/src/adapter/v1-schema.ts`. |

### Optogon Stack (added 2026-04-18)

Ten schemas defining the full Optogon stack contracts. Source of truth: `doctrine/02_ROSETTA_STONE.md` + `doctrine/03_OPTOGON_SPEC.md`. Validator: `contracts/validate.py`.

| Schema | Contract / Spec | Producer | Consumer |
|--------|-----------------|----------|----------|
| `OptogonNode.v1.json` | Spec §6 | Path author | Optogon runtime |
| `OptogonPath.v1.json` | Spec §7 | Path author | Optogon runtime |
| `OptogonSessionState.v1.json` | Spec §8 | Optogon runtime | Optogon runtime / InPACT debug |
| `ContextPackage.v1.json` | Rosetta Contract 1 | Site Pull | Optogon |
| `CloseSignal.v1.json` | Rosetta Contract 2 | Optogon | Atlas |
| `Directive.v1.json` | Rosetta Contract 3 | Atlas | Ghost Executor (Cortex) |
| `TaskPrompt.v1.json` | Rosetta Contract 4 (request) | Ghost Executor | Claude Code |
| `BuildOutput.v1.json` | Rosetta Contract 4 (response) | Claude Code | Ghost Executor |
| `Signal.v1.json` | Rosetta Contract 5 | Any layer | InPACT |
| `UserPreferenceStore.v1.json` | Rosetta Cross-Session Memory | Atlas (write) | All layers (read) |

Run validator:
```bash
# All schemas with examples (Python validator)
python contracts/validate.py           # terse
python contracts/validate.py --verbose # list each schema/example pair
```

Exit 0 = success. Exit 1 = at least one schema/example pair failed; details printed. Currently 10 of 47 schemas have example payloads in `contracts/examples/`; the rest validate at runtime when consumers write data. AnatomyV1 is gated in-process by the Zod twin (`services/canvas-engine/src/adapter/v1-schema.ts`) rather than a CLI validator — adding a no-network npm script for it is open work.

---

## Schema Details

### CognitiveMetricsComputed.json

Cognitive state snapshot exported by `export_cognitive_state.py`.

```json
{
  "closure": { "open": 14, "closed": 1, "archived": 1 },
  "drift": { "rising": [...], "fading": [...] },
  "anchors": [...]
}
```

### DailyPayload.v1.json

Payload consumed by CycleBoard UI.

```json
{
  "mode": "CLOSURE",
  "build_allowed": false,
  "primary_action": "Close or archive 'Project X'",
  "open_loops": ["Project X", "Project Y"],
  "open_loop_count": 14,
  "closure_ratio": 6.67,
  "risk": "HIGH",
  "generated_at": "2026-01-09"
}
```

**Mode values:** `CLOSURE`, `MAINTENANCE`, `BUILD`
**Risk values:** `LOW`, `MEDIUM`, `HIGH`

### DailyProjection.v1.json

Combined artifact merging cognitive state and directive.

```json
{
  "date": "2026-01-09",
  "cognitive": { ... },
  "directive": { ... }
}
```

### DirectiveProposed.json

Daily routing directive format.

```json
{
  "mode": "CLOSURE",
  "primary_action": "Close 'Project X'",
  "rationale": "..."
}
```

### Closures.v1.json (Phase 5B)

Persistent registry of closed loops with streak tracking.

```json
{
  "closures": [
    { "ts": 1736400000000, "loop_id": "abc", "title": "Project X", "outcome": "closed" }
  ],
  "stats": {
    "total_closures": 15,
    "closures_today": 3,
    "last_closure_at": 1736400000000,
    "streak_days": 5,
    "last_streak_date": "2026-01-09",
    "best_streak": 7
  }
}
```

**Outcome values:** `closed`, `archived`

---

## Validation

### Python (cognitive-sensor)

```python
from validate import validate_payload, require_valid

# Soft validation (returns bool, error)
valid, error = validate_payload(data, "DailyPayload.v1.json")

# Hard validation (raises on failure)
require_valid(data, "DailyPayload.v1.json", "export context")
```

### TypeScript (delta-kernel)

Schemas are loaded and validated using JSON Schema draft-07.

---

## Adding New Schemas

1. Create `schemas/YourSchema.v1.json` with JSON Schema draft-07 format
2. Add validation function in `services/cognitive-sensor/validate.py`
3. Document schema in this README
4. Update `PRE_ATLAS_MAP.md` schemas tree
5. If consumers need TypeScript zod validation (canvas-engine pattern), add a Zod twin **in lockstep** with the JSON Schema — adding a field to one without the other = silent drop

---

## Examples

See `examples/` for sample payloads. As of 2026-04-26, 10 of 47 schemas have example payloads:

- `BuildOutput.v1.example.json`
- `CloseSignal.v1.example.json`
- `ContextPackage.v1.example.json`
- `Directive.v1.example.json`
- `OptogonNode.v1.example.json`
- `OptogonPath.v1.example.json`
- `OptogonSessionState.v1.example.json`
- `Signal.v1.example.json`
- `TaskPrompt.v1.example.json`
- `UserPreferenceStore.v1.example.json`

All Optogon stack examples are threaded through `ship_inpact_lesson` as the running scenario (per `doctrine/04_BUILD_PLAN.md` Section 5). AnatomyV1 has no example payload under `contracts/examples/` yet — its 7 real captures live under `~/web-audit/.canvas/<host>/anatomy.json` (hn-v1, example-v1, ycombinator, linear, figma, apify, gmail) and are validated in-process by the canvas-engine Zod twin during `/clone` calls.

---

## Schema Versioning

Schemas use `.v1.json` suffix for versioning. When making breaking changes:

1. Create new version (e.g., `DailyPayload.v2.json`)
2. Keep old version for backwards compatibility
3. Update consumers to use new version

---

*Part of the Pre Atlas personal operating system.*
