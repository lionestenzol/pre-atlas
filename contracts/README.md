# Contracts

JSON Schema contracts that define data formats exchanged between Pre Atlas services.

---

## Overview

All data exports are validated against these schemas before writing. This ensures:

1. **Type safety** - Data conforms to expected structure
2. **Contract enforcement** - Services agree on data formats
3. **Validation** - Invalid writes are blocked

---

## Schemas

### Pre-existing (cognitive-sensor stack)

| Schema | Purpose | Used By |
|--------|---------|---------|
| `CognitiveMetricsComputed.json` | Cognitive state metrics | `export_cognitive_state.py` |
| `DailyPayload.v1.json` | CycleBoard UI payload | `export_daily_payload.py` |
| `DailyProjection.v1.json` | Combined daily artifact | `build_projection.py` |
| `DirectiveProposed.json` | CycleBoard mode routing directive (distinct from `Directive.v1.json` below) | `route_today.py` |
| `Closures.v1.json` | Closure registry + streaks | Phase 5B `/api/law/close_loop` |

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
python contracts/validate.py           # terse
python contracts/validate.py --verbose # list each schema/example pair
```

Exit 0 = all 10 schemas validate their matching examples. Exit 1 = one or more failed; details printed.

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
4. Update FILE_MAP.md

---

## Examples

See `examples/` for sample payloads:

- `daily_payload_example.json` — Sample CycleBoard payload (pre-existing)
- `OptogonNode.v1.example.json` through `UserPreferenceStore.v1.example.json` — One example per Optogon stack schema. All threaded through `ship_inpact_lesson` as the running scenario (per `doctrine/04_BUILD_PLAN.md` Section 5).

---

## Schema Versioning

Schemas use `.v1.json` suffix for versioning. When making breaking changes:

1. Create new version (e.g., `DailyPayload.v2.json`)
2. Keep old version for backwards compatibility
3. Update consumers to use new version

---

*Part of the Pre Atlas personal operating system.*
