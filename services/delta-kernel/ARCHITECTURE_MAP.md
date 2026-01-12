# DELTA-STATE FABRIC — ARCHITECTURE MAP

## Delta Lifecycle

```
┌──────────────────────────────────────────────────────────────────┐
│                         DELTA LIFECYCLE                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  CREATE                  VALIDATE                   APPLY         │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐   │
│  │createEntity │───────►│verifyHash   │───────►│applyPatch   │   │
│  │createDelta  │        │Chain        │        │applyDelta   │   │
│  │delta.ts:50  │        │delta.ts:175 │        │delta.ts:89  │   │
│  │delta.ts:131 │        │             │        │delta.ts:216 │   │
│  └─────────────┘        └─────────────┘        └─────────────┘   │
│         │                      │                      │           │
│         ▼                      ▼                      ▼           │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐   │
│  │ prev_hash   │        │ REJECT if   │        │ new state   │   │
│  │ patch[]     │        │ broken      │        │ new hash    │   │
│  │ new_hash    │        │             │        │             │   │
│  └─────────────┘        └─────────────┘        └─────────────┘   │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Routing Lifecycle

```
┌──────────────────────────────────────────────────────────────────┐
│                        ROUTING LIFECYCLE                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  SIGNALS                 BUCKET                    ROUTE          │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐   │
│  │ sleep_hours │───────►│bucketSignals│───────►│computeNext  │   │
│  │ open_loops  │        │routing.ts:69│        │Mode         │   │
│  │ assets      │        │             │        │routing.ts:  │   │
│  │ deep_work   │        │LOW/OK/HIGH  │        │152          │   │
│  │ money_delta │        │             │        │             │   │
│  └─────────────┘        └─────────────┘        └─────────────┘   │
│                                │                      │           │
│                                ▼                      ▼           │
│                         ┌─────────────┐        ┌─────────────┐   │
│                         │ GLOBAL      │        │ next Mode   │   │
│                         │ OVERRIDES   │        │ RECOVER     │   │
│                         │ check first │        │ CLOSE_LOOPS │   │
│                         │             │        │ BUILD       │   │
│                         │             │        │ COMPOUND    │   │
│                         │             │        │ SCALE       │   │
│                         └─────────────┘        └─────────────┘   │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Sync Lifecycle

```
┌──────────────────────────────────────────────────────────────────┐
│                         SYNC LIFECYCLE                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Node A                                              Node B       │
│  ┌─────────┐    HELLO     ┌─────────┐    HELLO     ┌─────────┐   │
│  │         │─────────────►│         │◄─────────────│         │   │
│  │         │              │ delta-  │              │         │   │
│  │         │    HEADS     │ sync.ts │    HEADS     │         │   │
│  │         │─────────────►│         │◄─────────────│         │   │
│  │         │              │         │              │         │   │
│  │         │    WANT      │ :623    │    WANT      │         │   │
│  │         │◄─────────────│ handler │─────────────►│         │   │
│  │         │              │         │              │         │   │
│  │         │   DELTAS     │         │   DELTAS     │         │   │
│  │         │─────────────►│         │◄─────────────│         │   │
│  │         │              │         │              │         │   │
│  │         │    ACK       │         │    ACK       │         │   │
│  │         │◄─────────────│         │─────────────►│         │   │
│  └─────────┘              └─────────┘              └─────────┘   │
│                                                                   │
│  Validation:  validateDelta() → delta-sync.ts:231                │
│  Persistence: applyDeltaToContext() → delta-sync.ts:872          │
│  Conflict:    detectConflict() → delta-sync.ts:336               │
│  REJECT:      createRejectPacket() → delta-sync.ts:125           │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Payload Adapters (Streaming SDK)

```
┌──────────────────────────────────────────────────────────────────┐
│                        PAYLOAD ADAPTERS                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  MODULE 8: UI STREAMING                                          │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Sender: UIStreamSender (ui-stream.ts:97)                   │  │
│  │   setProp() → appendPoint() → upsertListItem() → flush()   │  │
│  │                                                             │  │
│  │ Receiver: UIStreamReceiver (ui-stream.ts:337)              │  │
│  │   registerComponent() → applyDelta() → replay()            │  │
│  │                                                             │  │
│  │ Validator: validateUIPatch() (ui-surface.ts:160)           │  │
│  │ Renderer: renderComponentToTerminal() (ui-stream.ts:453)   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  MODULE 9: CAMERA STREAMING                                      │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Extractor: CameraExtractor (camera-extractor.ts:151)       │  │
│  │   extractDeltas() = lights + objects + residuals           │  │
│  │                                                             │  │
│  │ Receiver: CameraStreamReceiver (camera-renderer.ts:28)     │  │
│  │   registerTile/Object/Light() → applyDelta() → replay()    │  │
│  │                                                             │  │
│  │ Compositor: composeScene() (camera-renderer.ts:236)        │  │
│  │   baseline + lights + objects → RenderedTile[][]           │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  MODULE 10: ACTUATION                                            │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Intent: createIntent() (actuation.ts:242)                  │  │
│  │   → processNewIntent() → evaluatePolicy()                  │  │
│  │                                                             │  │
│  │ Policy: evaluatePolicy() (actuation.ts:117)                │  │
│  │   mode + bounds + TTL + rate limit → AUTHORIZED/DENIED     │  │
│  │                                                             │  │
│  │ Agent: DeviceAgent (device-agent.ts:68)                    │  │
│  │   processAuthorizedIntents() → execute() → createReceipt() │  │
│  │                                                             │  │
│  │ Idempotency: last_applied_intent_id check                  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Sync Priority Order

```
┌──────────────────────────────────────────────────────────────────┐
│                      SYNC PRIORITY ORDER                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Priority 1:  SystemState (mode, signals)                        │
│  Priority 2:  PendingAction (user confirmations)                 │
│  Priority 3:  ActuationIntent (control commands)                 │
│  Priority 4:  ActuatorState, ActuationReceipt, Actuator          │
│  Priority 5:  Camera (Surface, Tile, Object, Light, Tick)        │
│  Priority 6:  UI (Surface, Component, ControlSurface, Widget)    │
│  Priority 7:  Messages, Threads                                  │
│  Priority 8:  Tasks, Projects                                    │
│  Priority 9:  Drafts, Notes, Inbox                               │
│  Priority 10: Tokens, Patterns, Motifs, Proposals                │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## File Map

```
src/core/
├── types.ts              # All entity types (1130+ lines)
├── delta.ts              # Core delta operations
├── routing.ts            # Mode computation (LUT)
├── delta-sync.ts         # Sync protocol
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

## Kill Switches (REJECT Paths)

| Component | Check | Result |
|-----------|-------|--------|
| delta-sync.ts:250 | prev_hash mismatch | HASH_CHAIN_BROKEN |
| delta-sync.ts:279 | computed hash mismatch | HASH_CHAIN_BROKEN |
| delta-sync.ts:289 | invalid patch op | SCHEMA_INVALID |
| ui-stream.ts:369 | prev_hash mismatch | HASH_CHAIN_BROKEN |
| ui-stream.ts:377 | invalid UI patch | SCHEMA_INVALID |
| camera-renderer.ts:125 | prev_hash mismatch | HASH_CHAIN_BROKEN |
| actuation.ts:124 | intent expired | INTENT_EXPIRED |
| actuation.ts:174 | value > max | VALUE_ABOVE_MAX |
| actuation.ts:206 | rate limited | RATE_LIMITED |
