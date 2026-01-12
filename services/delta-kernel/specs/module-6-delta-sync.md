# MODULE 6 — DELTA SYNC PROTOCOL

**Status:** COMPLETE
**Version:** 1.0.0

---

## Mission

Synchronize Entities + Deltas across devices using append-only deltas, hash-chained integrity, and LoRa-safe burst packets.

> No blobs. No full state transfers. Just deltas.

---

## Laws

1. **Append-only deltas** — Never modify history
2. **Hash-chained integrity** — Every delta links to prev_hash
3. **Idempotent exchange** — Same delta applied twice = no change
4. **LoRa-safe packets** — 220 bytes max default
5. **Deterministic conflict resolution** — Same inputs → same resolution

---

## Protocol Version

```typescript
PROTOCOL_VERSION = '0.1.0';
DEFAULT_MAX_PACKET_BYTES = 220;  // LoRa-safe
CHUNK_PAYLOAD_SIZE = 150;        // Leave room for headers
```

---

## Sync Node

```typescript
interface SyncNode {
  node_id: UUID;
  node_name: string;
  public_key: string;
  created_at: Timestamp;
}

interface NodeCapabilities {
  max_packet_bytes: number;
  supports_cbor: boolean;
  supports_encryption: boolean;
  protocol_version: string;
}
```

---

## Packet Types

| Type | Direction | Purpose |
|------|-----------|---------|
| HELLO | Bidirectional | Handshake, capabilities |
| HEADS | Bidirectional | Exchange entity heads |
| WANT | Request | Request missing deltas |
| DELTAS | Response | Send requested deltas |
| DELTAS_CHUNK | Response | Chunked large delta |
| ACK | Response | Confirm receipt |
| REJECT | Response | Report error |

### Packet Structures

```typescript
interface HelloPacket {
  type: 'HELLO';
  node_id: UUID;
  protocol_version: string;
  caps: NodeCapabilities;
  nonce: string;
}

interface HeadsPacket {
  type: 'HEADS';
  node_id: UUID;
  heads: EntityHead[];
}

interface WantPacket {
  type: 'WANT';
  node_id: UUID;
  wants: WantEntry[];
}

interface DeltasPacket {
  type: 'DELTAS';
  node_id: UUID;
  deltas: Delta[];
}

interface AckPacket {
  type: 'ACK';
  node_id: UUID;
  acked_delta_ids: UUID[];
}

interface RejectPacket {
  type: 'REJECT';
  node_id: UUID;
  reason: RejectReason;
  details: { delta_id?: UUID; message?: string };
}
```

---

## Sync Flow

```
Node A                         Node B
   │                              │
   │──────── HELLO ──────────────→│
   │←─────── HELLO ───────────────│
   │                              │
   │──────── HEADS ──────────────→│
   │←─────── HEADS ───────────────│
   │                              │
   │  (compute diff)              │  (compute diff)
   │                              │
   │──────── WANT ───────────────→│
   │←─────── WANT ────────────────│
   │                              │
   │←─────── DELTAS ──────────────│
   │──────── DELTAS ─────────────→│
   │                              │
   │──────── ACK ────────────────→│
   │←─────── ACK ─────────────────│
   │                              │
   ▼                              ▼
 SYNCED                        SYNCED
```

---

## Heads Diff

```typescript
interface HeadsDiff {
  localOnly: EntityHead[];     // We have, peer doesn't
  remoteOnly: EntityHead[];    // Peer has, we don't
  diverged: Array<{            // Both have, different hashes
    entity_id: UUID;
    local_hash: SHA256;
    local_version: number;
    remote_hash: SHA256;
    remote_version: number;
  }>;
  synced: EntityHead[];        // Identical
}

function computeHeadsDiff(localHeads, remoteHeads): HeadsDiff
function generateWantEntries(diff, localDeltas): WantEntry[]
```

---

## Delta Validation

```typescript
interface ValidationResult {
  valid: boolean;
  reason?: RejectReason;
  message?: string;
}

RejectReason =
  | 'HASH_CHAIN_BROKEN'
  | 'ENTITY_UNKNOWN'
  | 'SCHEMA_INVALID'
  | 'RATE_LIMITED'
  | 'UNAUTHORIZED';
```

**Validation Rules:**
1. Entity must exist OR delta must be genesis
2. prev_hash must match current entity hash
3. new_hash must match computed hash
4. Patch operations must be valid

---

## Conflict Detection & Resolution

```typescript
interface EntityConflict {
  entity_id: UUID;
  base_hash: SHA256;
  branch_a: { node_id: UUID; head_hash: SHA256; deltas: Delta[] };
  branch_b: { node_id: UUID; head_hash: SHA256; deltas: Delta[] };
  status: ConflictStatus;
  detected_at: Timestamp;
  resolved_at: Timestamp | null;
  resolution_delta_id: UUID | null;
}

ConflictStatus = 'DETECTED' | 'RESOLVING' | 'RESOLVED';
```

**Resolution Strategies:**
| Strategy | Description |
|----------|-------------|
| CHOOSE_A | Accept branch A's state |
| CHOOSE_B | Accept branch B's state |
| MERGE | Combine both with merged patch |

---

## LoRa Chunking

For deltas exceeding packet size:

```typescript
interface DeltasChunkPacket {
  type: 'DELTAS_CHUNK';
  node_id: UUID;
  delta_id: UUID;
  chunk_index: number;
  chunk_total: number;
  chunk_payload: string;  // Base64 encoded
}

function shouldChunk(delta, maxBytes): boolean
function chunkDelta(nodeId, delta, chunkSize): DeltasChunkPacket[]
function reassembleChunks(chunks): Delta | null
```

---

## Priority Queue

Sync order based on entity type priority:

```typescript
type SyncPriority = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10;

SYNC_PRIORITY_MAP: Record<EntityType, SyncPriority> = {
  system_state: 1,
  pending_action: 2,
  actuation_intent: 3,
  actuator: 4, actuator_state: 4, actuation_receipt: 4,
  camera_surface: 5, scene_tile: 5, scene_object: 5, scene_light: 5, camera_tick: 5,
  ui_surface: 6, ui_component: 6, ui_render_tick: 6, ui_surface_link: 6,
  control_surface: 6, control_widget: 6,
  message: 7, thread: 7,
  task: 8, project: 8,
  draft: 9, note: 9, inbox_item: 9,
  token: 10, pattern: 10, motif: 10, discovery_proposal: 10, design_proposal: 10,
};
```

---

## Session Management

```typescript
interface SyncSession {
  session_id: UUID;
  local_node_id: UUID;
  remote_node_id: UUID;
  state: SyncSessionState;
  started_at: Timestamp;
  completed_at: Timestamp | null;
  deltas_sent: number;
  deltas_received: number;
  conflicts_detected: number;
}

SyncSessionState =
  | 'HELLO_SENT'
  | 'HELLO_RECEIVED'
  | 'HEADS_EXCHANGED'
  | 'SYNCING'
  | 'COMPLETE'
  | 'ERROR';
```

---

## Watermark Tracking

```typescript
interface PeerWatermark {
  peer_node_id: UUID;
  last_sync_at: Timestamp;
  entity_heads: Record<UUID, SHA256>;  // entity_id → last known hash
}

function updateWatermark(watermark, heads): PeerWatermark
function createWatermark(peerId): PeerWatermark
```

---

## Sync Context

```typescript
interface SyncContext {
  localNode: SyncNode;
  localEntities: Map<UUID, Entity>;
  localDeltas: Map<UUID, Delta[]>;  // entity_id → deltas
  entityTypes: Map<UUID, EntityType>;
  peerWatermarks: Map<UUID, PeerWatermark>;
  conflictStore: ConflictStore;
}

interface SyncResult {
  session: SyncSession;
  deltasReceived: Delta[];
  deltasSent: Delta[];
  conflictsDetected: EntityConflict[];
  errors: Array<{ packet: SyncPacket; error: string }>;
}
```

---

## Packet Handling

```typescript
async function handleIncomingPacket(
  ctx: SyncContext,
  session: SyncSession,
  packet: SyncPacket
): Promise<{ response: SyncPacket | null; session: SyncSession }>
```

| Packet | Handler | Response |
|--------|---------|----------|
| HELLO | handleHello | HELLO |
| HEADS | handleHeads | WANT or HEADS |
| WANT | handleWant | DELTAS |
| DELTAS | handleDeltas | ACK or REJECT |
| DELTAS_CHUNK | handleDeltasChunk | (buffered) |
| ACK | handleAck | none |
| REJECT | handleReject | none (log error) |

---

## Signature Verification

```typescript
// Canonical JSON for signing (sorted keys, no sig field)
function canonicalizePacket(packet: SyncPacket): string

async function signPacket(packet, privateKey): SyncPacket
async function verifyPacketSignature(packet, publicKey): boolean
```

---

## Bootstrap (New Node)

```typescript
async function bootstrapFromPeer(
  ctx: SyncContext,
  peerHeads: EntityHead[]
): Promise<WantEntry[]> {
  // Want everything from genesis
  return peerHeads.map(head => ({
    entity_id: head.entity_id,
    since_hash: '0'.repeat(64),
  }));
}
```

---

## Files

| File | Purpose |
|------|---------|
| `delta-sync.ts` | Full implementation (~965 lines) |

---

## Key Functions

| Function | Purpose |
|----------|---------|
| `createNode()` | Create new sync node |
| `createHelloPacket()` | Build HELLO packet |
| `createHeadsPacket()` | Build HEADS packet |
| `createWantPacket()` | Build WANT packet |
| `createDeltasPacket()` | Build DELTAS packet |
| `computeHeadsDiff()` | Compare head lists |
| `generateWantEntries()` | Determine what to request |
| `validateDelta()` | Check delta validity |
| `detectConflict()` | Find divergent branches |
| `resolveConflict()` | Create resolution delta |
| `chunkDelta()` | Split large delta |
| `reassembleChunks()` | Reconstruct delta |
| `prioritizeDeltas()` | Order by entity priority |
| `handleIncomingPacket()` | Process received packet |

---

## Error Handling

| Error | Reason | Recovery |
|-------|--------|----------|
| HASH_CHAIN_BROKEN | prev_hash mismatch | Request missing deltas |
| ENTITY_UNKNOWN | Entity not found | Request from genesis |
| SCHEMA_INVALID | Bad patch structure | Reject, log |
| RATE_LIMITED | Too many requests | Backoff |
| UNAUTHORIZED | Signature invalid | Reject |

---

## Next: Module 7 — Off-Grid Nodes

Physical deployment on radios, batteries, and mesh networks.

Command: **Continue to Module 7 — Off-Grid Nodes.**
