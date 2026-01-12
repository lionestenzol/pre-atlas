# MODULE 9 — CAMERA TILE DELTA STREAMING

**Status:** COMPLETE
**Version:** 1.0.0

---

## Mission

Stream "video" as **scene state deltas**, not pixels.

> Objects move. Lights change. Baseline tiles persist.

---

## Core Concepts

| Concept | Description |
|---------|-------------|
| Baseline | First frame captures static tile hashes |
| Object | Moving shape (tracked blob) |
| Light | Global or regional brightness/color adjustment |
| Residual | Tile changed from baseline (fallback) |
| Scene | Composite of baseline + lights + objects + residuals |

---

## Entity Types

```typescript
CameraSurfaceData {
  name: string;
  grid_w: number;           // Grid width in tiles
  grid_h: number;           // Grid height in tiles
  tile_size: number;        // Tile size in pixels
  created_at: Timestamp;
}

SceneTileData {
  surface_id: UUID;
  x: number;                // Grid position
  y: number;
  hash: SHA256;             // Content hash
  brightness: number;       // -8..+8 adjustment
  chroma: number;           // -8..+8 adjustment
  is_residual: boolean;
  created_at: Timestamp;
}

SceneObjectData {
  surface_id: UUID;
  shape_tiles: UUID[];      // References to tiles
  x: number;                // Current position
  y: number;
  vx: number;               // Velocity
  vy: number;
  brightness: number;
  visible: boolean;
  created_at: Timestamp;
}

SceneLightData {
  surface_id: UUID;
  region: 'GLOBAL' | { x, y, w, h };
  brightness: number;       // -16..+16
  color_temp: number;       // Kelvin (2700-6500)
  created_at: Timestamp;
}
```

---

## Extraction Pipeline

```
Frame N → Extract → Deltas
          │
          ├── 1. Lighting Pass (global/regional brightness)
          │
          ├── 2. Object Pass (tracked blobs → position deltas)
          │
          └── 3. Residual Pass (unexplained changes → tile deltas)
```

### Priority Order

1. **Lights** — Cheapest (1-2 deltas/frame)
2. **Objects** — Preferred (position + velocity)
3. **Residuals** — Fallback (tile-level changes)

---

## Deterministic Rendering

```
composeScene(store) → RenderedTile[][]

1. Initialize grid with zeros
2. Apply baseline tiles
3. Apply light adjustments (global then regional)
4. Draw objects (mark tiles, add brightness)
5. Clamp brightness to [-16, +16]
```

---

## Files

| File | Purpose |
|------|---------|
| `camera-surface.ts` | Schemas, validators, CameraSceneStore |
| `camera-extractor.ts` | Baseline builder, extraction pipeline |
| `camera-renderer.ts` | CameraStreamReceiver, composeScene |
| `camera-stream-test.ts` | Static room + moving object harness |

---

## Test Results

```
MODULE 9: CAMERA TILE DELTA STREAMING — PROOF TESTS

Test 1: State Synchronization ✓
Test 2: Bandwidth Efficiency ✓ (602.1 bytes/sec < 1024)
Test 3: Replay Reconstruction ✓
Test 4: Residual Tile Rate ✓ (0.00% < 10%)

RESULTS: 4 passed, 0 failed
✓ MODULE 9 COMPLETE — State-based video proven!
```

---

## Bandwidth Metrics

| Metric | Value |
|--------|-------|
| Bytes/second | 602.1 |
| Target | <1024 bytes/sec |
| Residual rate | 0% |
| Target residual | <10% |

---

## Allowed Delta Operations

| Operation | Description |
|-----------|-------------|
| REPLACE_POSITION | Replace x, y, vx, vy |
| REPLACE_BRIGHTNESS | Replace brightness |
| REPLACE_CHROMA | Replace chroma |
| REPLACE_COLOR_TEMP | Replace color_temp |
| REPLACE_HASH | Replace tile hash (residual) |
| ADD_SHAPE_TILE | Add to shape_tiles |
| REMOVE_SHAPE_TILE | Remove from shape_tiles |
| REPLACE_VISIBLE | Replace visibility |

---

## Sync Priority

Camera entities are priority **5** in the sync order:
1. SystemState
2. PendingAction
3. ActuationIntent
4. ActuatorState/Receipt
5. **Camera** ← Surface, Tile, Object, Light, Tick

---

## Compact Wire Format

```typescript
interface CompactCameraDelta {
  d: string;    // delta_id (8 char)
  e: string;    // entity_id (4 char short)
  t: number;    // timestamp
  type: 'T' | 'O' | 'L';  // Tile, Object, Light
  p: Array<{ o: string; k: string; v: unknown }>;
  ph: string;   // prev_hash (8 char)
  nh: string;   // new_hash (8 char)
}
```

---

## What Module 9 Enables

- Remote camera monitoring over LoRa
- Bandwidth-efficient "video" streaming
- Deterministic scene reconstruction
- Foundation for computer vision pipelines
