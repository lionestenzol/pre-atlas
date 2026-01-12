# ULTRA-LOW STREAMING SDK v0

**Status:** COMPLETE
**Version:** 1.0.0
**Modules:** 8, 9, 10

---

## Mission

Package UI mirroring, camera streaming, and remote control into a unified SDK.

> Everything is state. State changes are deltas. Deltas sync.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    DELTA-STATE FABRIC                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Module 8   │  │   Module 9   │  │  Module 10   │       │
│  │ UI Streaming │  │   Camera     │  │   Control    │       │
│  │              │  │  Streaming   │  │   Plane      │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                 │                 │               │
│         └────────────────┼────────────────┘               │
│                          │                                  │
│                    ┌─────▼─────┐                           │
│                    │   Delta   │                           │
│                    │   Sync    │                           │
│                    │ Protocol  │                           │
│                    └───────────┘                           │
│                          │                                  │
│              ┌───────────┴───────────┐                     │
│              ▼                       ▼                     │
│         ┌────────┐             ┌────────┐                  │
│         │  WiFi  │             │  LoRa  │                  │
│         └────────┘             └────────┘                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Module Summary

| Module | Purpose | Bandwidth | Tests |
|--------|---------|-----------|-------|
| 8 - UI Streaming | Dashboard mirroring | 128 bytes/delta | 3/3 ✓ |
| 9 - Camera | Scene delta streaming | 602 bytes/sec | 4/4 ✓ |
| 10 - Control | Bidirectional actuation | N/A (event-driven) | 4/4 ✓ |

---

## Entity Types Added

### Module 8 (UI)
- `ui_surface` — Screen definition
- `ui_component` — Widget state
- `ui_render_tick` — Frame grouping
- `ui_surface_link` — Mirroring relationship

### Module 9 (Camera)
- `camera_surface` — Camera definition
- `scene_tile` — Static/residual tile
- `scene_object` — Moving object
- `scene_light` — Lighting adjustment
- `camera_tick` — Frame grouping

### Module 10 (Control)
- `actuator` — Controllable device
- `actuator_state` — Device state
- `control_surface` — Control panel
- `control_widget` — Control element
- `actuation_intent` — Requested action
- `actuation_receipt` — Execution proof

---

## Sync Priority Order

| Priority | Entities |
|----------|----------|
| 1 | SystemState |
| 2 | PendingAction |
| 3 | ActuationIntent |
| 4 | ActuatorState, ActuationReceipt, Actuator |
| 5 | Camera (Surface, Tile, Object, Light, Tick) |
| 6 | UI (Surface, Component, RenderTick, SurfaceLink, ControlSurface, ControlWidget) |
| 7 | Messages, Threads |
| 8 | Tasks, Projects |
| 9 | Drafts, Notes, Inbox |
| 10 | Tokens, Patterns, Motifs, Proposals |

---

## Files

```
src/core/
├── types.ts              # All entity types
├── delta.ts              # Core delta operations
│
├── ui-surface.ts         # Module 8: UI schemas
├── ui-stream.ts          # Module 8: UI sender/receiver
├── ui-stream-test.ts     # Module 8: UI proof tests
│
├── camera-surface.ts     # Module 9: Camera schemas
├── camera-extractor.ts   # Module 9: Baseline + extraction
├── camera-renderer.ts    # Module 9: Scene compositor
├── camera-stream-test.ts # Module 9: Camera proof tests
│
├── control-surface.ts    # Module 10: Control schemas
├── actuation.ts          # Module 10: Policy + intent
├── device-agent.ts       # Module 10: Device execution
└── control-test.ts       # Module 10: Control proof tests
```

---

## Key Patterns

### 1. State-Based Streaming
Instead of pixels, send state changes as JSON patches.

```typescript
// Instead of: sendPixels(frame)
// Do this:
const delta = createDelta(entityId, prevHash, [
  { op: 'replace', path: '/value', value: 42 }
], newHash);
sendDelta(delta);
```

### 2. Hash Chain Verification
Every delta links to previous state via hash.

```typescript
if (currentData.hash !== delta.prev_hash) {
  return { success: false, reason: 'HASH_CHAIN_BROKEN' };
}
```

### 3. Idempotent Execution
Track what's been applied to prevent replay issues.

```typescript
if (actuatorState.last_applied_intent_id === intentId) {
  return { status: 'SKIPPED', reason: 'ALREADY_APPLIED' };
}
```

### 4. Deterministic Reconstruction
Same deltas → same state, always.

```typescript
// Replay 1000 deltas
const reconstructed = replay(deltas);
// Hash matches original
assert(computeHash(reconstructed) === expectedHash);
```

---

## Bandwidth Targets

| Stream Type | Target | Achieved |
|-------------|--------|----------|
| UI Deltas | <150 bytes/delta | 128 bytes/delta ✓ |
| Camera | <1024 bytes/sec | 602 bytes/sec ✓ |
| Residual Rate | <10% | 0% ✓ |

---

## Test Harnesses

### Run All Tests

```bash
# Module 8 - UI
npx tsx -e "import { runModule8Tests } from './src/core/ui-stream-test.ts'; runModule8Tests();"

# Module 9 - Camera
npx tsx -e "import { runModule9Tests } from './src/core/camera-stream-test.ts'; runModule9Tests();"

# Module 10 - Control
npx tsx -e "import { runModule10Tests } from './src/core/control-test.ts'; runModule10Tests();"
```

---

## Complete Control Loop

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Observe │ ──► │ Decide  │ ──► │Authorize│ ──► │ Actuate │
│ (Camera)│     │ (AI/UI) │     │ (Policy)│     │ (Device)│
└─────────┘     └─────────┘     └─────────┘     └─────────┘
     ▲                                               │
     │          ┌─────────┐     ┌─────────┐         │
     └───────── │ Record  │ ◄── │ Verify  │ ◄───────┘
                │ (Ledger)│     │(Receipt)│
                └─────────┘     └─────────┘
```

All steps are deltas. All deltas are replayable.

---

## What's Next

**Module 11: Swarm Scheduling**
- Decentralized task claiming for devices
- Work distribution without central coordinator
- Fault-tolerant execution

Command: **Start Module 11 — Swarm Work Claims.**
