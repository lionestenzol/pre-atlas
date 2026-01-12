# MODULE 8 — UI SURFACE STREAMING (ULTRA-LOW DELTA MIRRORING)

**Status:** COMPLETE
**Version:** 1.0.0

---

## Mission

Mirror dashboards across nodes using **component state deltas**, not pixels.

> Send state changes, not screen data.

---

## Core Concepts

| Concept | Description |
|---------|-------------|
| UI Surface | A "screen" containing components |
| UI Component | GAUGE, CHART, LIST, INDICATOR, BUTTON |
| State Delta | JSON patch for component property changes |
| Stream Metrics | Bandwidth tracking for proof |

---

## Entity Types

```typescript
UISurfaceData {
  name: string;
  schema_version: '0.1.0';
  root_component_id: UUID;
  created_at: Timestamp;
}

UIComponentStateData {
  surface_id: UUID;
  kind: UIComponentKind;
  props: UIComponentProps;
  created_at: Timestamp;
}

UIComponentKind = 'TEXT' | 'GAUGE' | 'CHART' | 'LIST' | 'INDICATOR' | 'BUTTON';
```

---

## Component Props (Schema-Bounded)

### GAUGE
```typescript
{
  kind: 'GAUGE';
  label: string;
  value: number;
  min: number;
  max: number;
  unit: string;
  state: 'OK' | 'WARN' | 'ALERT';
}
```

### CHART
```typescript
{
  kind: 'CHART';
  title: string;
  series: { name: string; points: number[] };
  window: number;  // Max points to keep
}
```

### LIST
```typescript
{
  kind: 'LIST';
  title: string;
  items: Array<{ id: string; text: string; state: UIStateIndicator }>;
}
```

### INDICATOR
```typescript
{
  kind: 'INDICATOR';
  label: string;
  on: boolean;
  state: 'OK' | 'WARN' | 'ALERT';
}
```

---

## Allowed Delta Operations

| Operation | Description |
|-----------|-------------|
| REPLACE_SCALAR | Replace number/string/boolean/enum |
| APPEND_POINT | Add to chart points array |
| ADD_LIST_ITEM | Add keyed item to list |
| REPLACE_LIST_ITEM | Replace keyed item in list |
| REMOVE_LIST_ITEM | Remove keyed item from list |
| REPLACE_STATE | Replace state field (OK\|WARN\|ALERT) |
| REPLACE_ENABLED | Replace enabled flag |

---

## Streaming Architecture

```
Sender Node                    Receiver Node
┌─────────────────┐           ┌─────────────────┐
│ Component Store │           │ Component Store │
│ (source state)  │           │ (mirror state)  │
├─────────────────┤           ├─────────────────┤
│ UIStreamSender  │ ─deltas─► │ UIStreamReceiver│
│ - setProp()     │           │ - applyDelta()  │
│ - appendPoint() │           │ - replay()      │
└─────────────────┘           └─────────────────┘
```

---

## Files

| File | Purpose |
|------|---------|
| `ui-surface.ts` | Schemas, validators, component factories |
| `ui-stream.ts` | Sender/Receiver classes, metrics |
| `ui-stream-test.ts` | Ops Dashboard harness |

---

## Test Results

```
MODULE 8: UI SURFACE STREAMING — PROOF TESTS

Test 1: State Synchronization ✓
Test 2: Replay Reconstruction ✓
Test 3: Bandwidth Efficiency ✓ (128.7 bytes/delta < 150)

RESULTS: 3 passed, 0 failed
✓ MODULE 8 COMPLETE — State-based UI mirroring proven!
```

---

## Bandwidth Metrics

| Metric | Value |
|--------|-------|
| Full format avg | ~367 bytes/delta |
| Compact format avg | ~128 bytes/delta |
| Compression ratio | 2.85x |
| Target | <150 bytes/delta |

---

## Compact Wire Format

```typescript
interface CompactDelta {
  d: string;    // delta_id (8 char)
  e: string;    // entity_id (4 char short)
  t: number;    // timestamp
  p: JsonPatch[];
  ph: string;   // prev_hash (8 char)
  nh: string;   // new_hash (8 char)
}
```

---

## Sync Priority

UI entities are priority **6** in the sync order:
1. SystemState
2. PendingAction
3. ActuationIntent
4. ActuatorState/Receipt
5. Camera
6. **UI** ← UI Surface, Component, RenderTick, SurfaceLink

---

## What Module 8 Enables

- Remote dashboard mirroring over LoRa
- Deterministic UI reconstruction from deltas
- Bandwidth-efficient state sync
- Foundation for control surfaces (Module 10)
