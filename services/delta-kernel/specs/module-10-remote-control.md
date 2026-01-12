# MODULE 10 — REMOTE CONTROL + ACTUATION DELTAS

**Status:** COMPLETE
**Version:** 1.0.0

---

## Mission

Turn the delta fabric into a **bidirectional control plane**.

> observe → decide → authorize → actuate → verify → record

All as deltas. Replayable. Offline-safe. Radio-safe.

---

## Laws

1. **All control is state.** No "commands" outside the ledger.
2. **Actuation requires a gate.** Every actuation is authorized by policy + optional human confirmation.
3. **Idempotent execution.** Replays must not re-trigger unsafe actions.
4. **Deterministic device state.** Devices publish measured state back as deltas.
5. **Fail closed.** Unknown actions or invalid schema → REJECT.

---

## Entity Types

### Actuator (a controllable thing)
```typescript
ActuatorData {
  name: string;
  kind: ActuatorKind;
  owner_node_id: UUID;
  capabilities: {
    min?: number;
    max?: number;
    step?: number;
    allowed_values?: (number | string)[];
  };
  created_at: Timestamp;
}

ActuatorKind = 'RELAY' | 'SERVO' | 'MOTOR' | 'VALVE' | 'DIMMER' | 'SOFTWARE_TOGGLE' | 'SOFTWARE_PARAM';
```

### Actuator State (measured/confirmed)
```typescript
ActuatorStateData {
  actuator_id: UUID;
  owner_node_id: UUID;
  state: 'UNKNOWN' | 'OFF' | 'ON' | 'MOVING' | 'ERROR';
  value?: number | string;
  last_applied_intent_id?: UUID;  // Idempotency anchor
  updated_at: Timestamp;
}
```

### Control Surface (UI control panel)
```typescript
ControlSurfaceData {
  name: string;
  schema_version: '0.1.0';
  created_at: Timestamp;
}
```

### Control Widget (button/slider/toggle)
```typescript
ControlWidgetData {
  surface_id: UUID;
  kind: 'BUTTON' | 'TOGGLE' | 'SLIDER' | 'SELECT';
  label: string;
  target_actuator_id: UUID;
  props: {
    confirm: boolean;
    min?: number;
    max?: number;
    step?: number;
    options?: (number | string)[];
  };
  created_at: Timestamp;
}
```

### Actuation Intent (requested change)
```typescript
ActuationIntentData {
  actuator_id: UUID;
  requested_by_node_id: UUID;
  requested_by_actor: 'user' | 'system' | 'ai';
  request: {
    action: 'SET_ON' | 'SET_OFF' | 'SET_VALUE';
    value?: number | string;
  };
  policy: {
    requires_human_confirm: boolean;
    ttl_ms: number;
  };
  status: ActuationIntentStatus;
  reason?: string;
  created_at: Timestamp;
  expires_at: Timestamp;
}

ActuationIntentStatus = 'NEW' | 'AUTHORIZED' | 'DENIED' | 'EXPIRED' | 'DISPATCHED' | 'APPLIED' | 'FAILED';
```

### Actuation Receipt (proof of execution)
```typescript
ActuationReceiptData {
  intent_id: UUID;
  actuator_id: UUID;
  owner_node_id: UUID;
  outcome: 'APPLIED' | 'FAILED';
  observed_state: {
    state: ActuatorStateValue;
    value?: number | string;
  };
  created_at: Timestamp;
}
```

---

## Control Flow

```
Terminal → Intent(NEW) → Policy Gate → Intent(AUTHORIZED)
                              ↓
                    Device Pickup (DISPATCHED)
                              ↓
                    Physical Execution
                              ↓
                    Receipt + State Update
                              ↓
                    Intent(APPLIED/FAILED)
```

---

## Policy Engine (Deterministic)

All policies are LUT-driven. No runtime AI.

| Policy | Description |
|--------|-------------|
| Mode Legality | RECOVER mode restricts physical actuators |
| Bounds Check | Value must be within min/max or allowed_values |
| TTL Expiry | Deny if now > expires_at |
| Rate Limit | Max 3 intents/10s per actuator |
| Ownership | Only owner node can apply |

---

## Idempotency

Device MUST NOT re-execute an intent if:
- `ActuatorState.last_applied_intent_id == intent_id`
- A receipt exists for `intent_id`

This prevents:
- Replay loops
- Duplicate execution after resync
- LoRa retransmit duplication

---

## Files

| File | Purpose |
|------|---------|
| `control-surface.ts` | Schemas, validators, widget factories, ControlSurfaceStore |
| `actuation.ts` | Intent creation, policy engine, status transitions |
| `device-agent.ts` | VirtualActuator, DeviceAgent, idempotent apply |
| `control-test.ts` | Virtual Actuator harness |

---

## Test Results

```
MODULE 10: REMOTE CONTROL + ACTUATION DELTAS — PROOF TESTS

Test 1: Full Intent Flow ✓
  - Intent created → authorized → dispatched → applied → receipt

Test 2: Replay Idempotency ✓
  - Same intent replayed → SKIPPED (duplicate prevented)

Test 3: Out-of-Bounds Rejection ✓
  - SET_VALUE=999 for Dimmer (max=100) → DENIED (VALUE_ABOVE_MAX)
  - SET_VALUE=-10 for Dimmer (min=0) → DENIED (VALUE_BELOW_MIN)

Test 4: TTL Expiry Rejection ✓
  - Expired intent → DENIED (INTENT_EXPIRED)
  - Authorized intent expires → status=EXPIRED

RESULTS: 4 passed, 0 failed
✓ MODULE 10 COMPLETE — Bidirectional control plane proven!
```

---

## Metrics

```typescript
ControlMetrics {
  intents_created: number;
  intents_authorized: number;
  intents_denied: number;
  intents_applied: number;
  intents_failed: number;
  median_time_to_apply_ms: number;
  duplicates_prevented: number;
}
```

---

## Sync Priority (Updated)

| Priority | Entity Types |
|----------|--------------|
| 1 | SystemState |
| 2 | PendingAction |
| 3 | **ActuationIntent** |
| 4 | **ActuatorState, ActuationReceipt, Actuator** |
| 5 | Camera (Surface, Tile, Object, Light, Tick) |
| 6 | UI (Surface, Component, RenderTick, SurfaceLink, ControlSurface, ControlWidget) |
| 7 | Messages, Threads |
| 8 | Tasks, Projects |
| 9 | Drafts, Notes, Inbox |
| 10 | Tokens, Patterns, Motifs, Proposals |

---

## Allowed Delta Operations

| Operation | Description |
|-----------|-------------|
| REPLACE_STATUS | Replace intent status |
| REPLACE_STATE | Replace actuator state |
| REPLACE_VALUE | Replace actuator value |
| SET_REASON | Set denial/failure reason |

---

## What Module 10 Enables

- Full bidirectional control loop
- Safe remote actuation with policy gates
- Idempotent replay-safe execution
- Proof of execution via receipts
- Integration with PendingAction for human confirmation
- Foundation for swarm scheduling (Module 11)

---

## Next: Module 11 — Swarm Scheduling

Decentralized task claiming for devices.

Command: **Start Module 11 — Swarm Work Claims.**
