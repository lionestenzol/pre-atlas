/**
 * Delta-State Fabric — Module 6: Delta Sync Protocol
 *
 * Synchronizes Entities + Deltas across devices using:
 * - Append-only deltas
 * - Hash-chained integrity
 * - Idempotent exchange
 * - LoRa-safe burst packets
 * - Deterministic conflict resolution
 *
 * No blobs. No full state transfers unless bootstrapping.
 */

import {
  UUID,
  Timestamp,
  SHA256,
  Entity,
  Delta,
  EntityType,
  JsonPatch,
  SyncNode,
  NodeCapabilities,
  PeerWatermark,
  EntityHead,
  SyncPacket,
  HelloPacket,
  HeadsPacket,
  WantPacket,
  WantEntry,
  DeltasPacket,
  DeltasChunkPacket,
  AckPacket,
  RejectPacket,
  RejectReason,
  EntityConflict,
  ConflictStatus,
  SyncSession,
  SyncSessionState,
  SyncPriority,
  SYNC_PRIORITY_MAP,
} from './types';
import { generateUUID, now, hashState, applyPatch, verifyHashChain } from './delta';

// === CONSTANTS ===

const PROTOCOL_VERSION = '0.1.0';
const DEFAULT_MAX_PACKET_BYTES = 220; // LoRa-safe default
const CHUNK_PAYLOAD_SIZE = 150; // Leave room for headers in chunks

// === NODE MANAGEMENT ===

export function createNode(name: string, publicKey: string): SyncNode {
  return {
    node_id: generateUUID(),
    node_name: name,
    public_key: publicKey,
    created_at: now(),
  };
}

export function getDefaultCapabilities(): NodeCapabilities {
  return {
    max_packet_bytes: DEFAULT_MAX_PACKET_BYTES,
    supports_cbor: true,
    supports_encryption: false,
    protocol_version: PROTOCOL_VERSION,
  };
}

// === PACKET CREATION ===

export function createHelloPacket(node: SyncNode, caps?: Partial<NodeCapabilities>): HelloPacket {
  return {
    type: 'HELLO',
    node_id: node.node_id,
    protocol_version: PROTOCOL_VERSION,
    caps: { ...getDefaultCapabilities(), ...caps },
    nonce: generateUUID().slice(0, 16),
  };
}

export function createHeadsPacket(
  nodeId: UUID,
  entities: Array<{ entity: Entity; entityType: EntityType }>
): HeadsPacket {
  const heads: EntityHead[] = entities.map(({ entity, entityType }) => ({
    entity_id: entity.entity_id,
    entity_type: entityType,
    current_hash: entity.current_hash,
    current_version: entity.current_version,
  }));

  return {
    type: 'HEADS',
    node_id: nodeId,
    heads,
  };
}

export function createWantPacket(nodeId: UUID, wants: WantEntry[]): WantPacket {
  return {
    type: 'WANT',
    node_id: nodeId,
    wants,
  };
}

export function createDeltasPacket(nodeId: UUID, deltas: Delta[]): DeltasPacket {
  return {
    type: 'DELTAS',
    node_id: nodeId,
    deltas,
  };
}

export function createAckPacket(nodeId: UUID, deltaIds: UUID[]): AckPacket {
  return {
    type: 'ACK',
    node_id: nodeId,
    acked_delta_ids: deltaIds,
  };
}

export function createRejectPacket(
  nodeId: UUID,
  reason: RejectReason,
  details: RejectPacket['details']
): RejectPacket {
  return {
    type: 'REJECT',
    node_id: nodeId,
    reason,
    details,
  };
}

// === HEADS DIFF & WANT GENERATION ===

export interface HeadsDiff {
  // Entities we have that peer doesn't
  localOnly: EntityHead[];
  // Entities peer has that we don't
  remoteOnly: EntityHead[];
  // Entities both have but with different hashes (need sync)
  diverged: Array<{
    entity_id: UUID;
    local_hash: SHA256;
    local_version: number;
    remote_hash: SHA256;
    remote_version: number;
  }>;
  // Entities that are identical
  synced: EntityHead[];
}

export function computeHeadsDiff(localHeads: EntityHead[], remoteHeads: EntityHead[]): HeadsDiff {
  const localMap = new Map(localHeads.map((h) => [h.entity_id, h]));
  const remoteMap = new Map(remoteHeads.map((h) => [h.entity_id, h]));

  const diff: HeadsDiff = {
    localOnly: [],
    remoteOnly: [],
    diverged: [],
    synced: [],
  };

  // Check local heads against remote
  for (const [entityId, localHead] of localMap) {
    const remoteHead = remoteMap.get(entityId);

    if (!remoteHead) {
      diff.localOnly.push(localHead);
    } else if (localHead.current_hash === remoteHead.current_hash) {
      diff.synced.push(localHead);
    } else {
      diff.diverged.push({
        entity_id: entityId,
        local_hash: localHead.current_hash,
        local_version: localHead.current_version,
        remote_hash: remoteHead.current_hash,
        remote_version: remoteHead.current_version,
      });
    }
  }

  // Check remote heads for entities we don't have
  for (const [entityId, remoteHead] of remoteMap) {
    if (!localMap.has(entityId)) {
      diff.remoteOnly.push(remoteHead);
    }
  }

  return diff;
}

export function generateWantEntries(
  diff: HeadsDiff,
  localDeltaStore: Map<UUID, Delta[]> // entity_id -> deltas
): WantEntry[] {
  const wants: WantEntry[] = [];

  // Want all remote-only entities from genesis
  for (const head of diff.remoteOnly) {
    wants.push({
      entity_id: head.entity_id,
      since_hash: '0'.repeat(64), // Genesis hash
    });
  }

  // Want diverged entities from our current head
  for (const diverged of diff.diverged) {
    // Request from our known hash forward
    wants.push({
      entity_id: diverged.entity_id,
      since_hash: diverged.local_hash,
    });
  }

  return wants;
}

// === DELTA VALIDATION ===

export interface ValidationResult {
  valid: boolean;
  reason?: RejectReason;
  message?: string;
}

export async function validateDelta(
  delta: Delta,
  knownEntities: Map<UUID, Entity>,
  entityDeltas: Map<UUID, Delta[]>
): Promise<ValidationResult> {
  const entity = knownEntities.get(delta.entity_id);
  const deltas = entityDeltas.get(delta.entity_id) || [];

  // Rule 1: Entity must exist OR this must be a creation delta
  const isGenesisDelta = delta.prev_hash === '0'.repeat(64);
  if (!entity && !isGenesisDelta) {
    return {
      valid: false,
      reason: 'ENTITY_UNKNOWN',
      message: `Entity ${delta.entity_id} not found and delta is not genesis`,
    };
  }

  // Rule 2: prev_hash must match current hash (or be genesis)
  if (entity && delta.prev_hash !== entity.current_hash) {
    // Check if this is a fork (same prev_hash as existing but different delta)
    const existingWithSamePrev = deltas.find(
      (d) => d.prev_hash === delta.prev_hash && d.delta_id !== delta.delta_id
    );
    if (existingWithSamePrev) {
      return {
        valid: false,
        reason: 'HASH_CHAIN_BROKEN',
        message: `Fork detected: delta ${delta.delta_id} has same prev_hash as ${existingWithSamePrev.delta_id}`,
      };
    }

    // Check if we're missing intermediate deltas
    const hasMatchingDelta = deltas.some((d) => d.new_hash === delta.prev_hash);
    if (!hasMatchingDelta && !isGenesisDelta) {
      return {
        valid: false,
        reason: 'HASH_CHAIN_BROKEN',
        message: `Missing parent delta with hash ${delta.prev_hash}`,
      };
    }
  }

  // Rule 3: Verify new_hash is correct
  const state = reconstructStateUpTo(deltas, delta.prev_hash);
  const newState = applyPatch(state, delta.patch);
  const computedHash = await hashState(newState);

  if (computedHash !== delta.new_hash) {
    return {
      valid: false,
      reason: 'HASH_CHAIN_BROKEN',
      message: `Hash mismatch: computed ${computedHash}, got ${delta.new_hash}`,
    };
  }

  // Rule 4: Validate patch structure (basic schema check)
  for (const op of delta.patch) {
    if (!isValidPatchOp(op)) {
      return {
        valid: false,
        reason: 'SCHEMA_INVALID',
        message: `Invalid patch operation: ${JSON.stringify(op)}`,
      };
    }
  }

  return { valid: true };
}

function reconstructStateUpTo(deltas: Delta[], targetHash: SHA256): Record<string, unknown> {
  if (targetHash === '0'.repeat(64)) {
    return {};
  }

  const sorted = [...deltas].sort((a, b) => a.timestamp - b.timestamp);
  let state: Record<string, unknown> = {};

  for (const delta of sorted) {
    state = applyPatch(state, delta.patch);
    if (delta.new_hash === targetHash) {
      break;
    }
  }

  return state;
}

function isValidPatchOp(op: JsonPatch): boolean {
  const validOps = ['add', 'remove', 'replace', 'move', 'copy', 'test'];
  if (!validOps.includes(op.op)) return false;
  if (typeof op.path !== 'string' || !op.path.startsWith('/')) return false;
  return true;
}

// === CONFLICT DETECTION & RESOLUTION ===

export interface ConflictStore {
  conflicts: Map<UUID, EntityConflict>; // entity_id -> conflict
}

export function createConflictStore(): ConflictStore {
  return { conflicts: new Map() };
}

export function detectConflict(
  entityId: UUID,
  localDeltas: Delta[],
  remoteDeltas: Delta[],
  localNodeId: UUID,
  remoteNodeId: UUID
): EntityConflict | null {
  // Find the common ancestor (last matching hash)
  const localHashes = new Set(localDeltas.map((d) => d.prev_hash));
  const remoteHashes = new Set(remoteDeltas.map((d) => d.prev_hash));

  let baseHash: SHA256 | null = null;

  // Find most recent common ancestor
  const localSorted = [...localDeltas].sort((a, b) => b.timestamp - a.timestamp);
  for (const delta of localSorted) {
    if (remoteHashes.has(delta.new_hash) || delta.prev_hash === '0'.repeat(64)) {
      baseHash = delta.prev_hash;
      break;
    }
  }

  if (!baseHash) {
    // No common ancestor found, use genesis
    baseHash = '0'.repeat(64);
  }

  // Get divergent deltas for each branch
  const localBranchDeltas = localDeltas.filter((d) => {
    const idx = localDeltas.findIndex((ld) => ld.new_hash === baseHash);
    return localDeltas.indexOf(d) > idx;
  });

  const remoteBranchDeltas = remoteDeltas.filter((d) => {
    const idx = remoteDeltas.findIndex((rd) => rd.new_hash === baseHash);
    return remoteDeltas.indexOf(d) > idx;
  });

  // No conflict if one branch is empty
  if (localBranchDeltas.length === 0 || remoteBranchDeltas.length === 0) {
    return null;
  }

  // Conflict exists
  const localHead = localBranchDeltas[localBranchDeltas.length - 1];
  const remoteHead = remoteBranchDeltas[remoteBranchDeltas.length - 1];

  return {
    entity_id: entityId,
    base_hash: baseHash,
    branch_a: {
      node_id: localNodeId,
      head_hash: localHead.new_hash,
      deltas: localBranchDeltas,
    },
    branch_b: {
      node_id: remoteNodeId,
      head_hash: remoteHead.new_hash,
      deltas: remoteBranchDeltas,
    },
    status: 'DETECTED',
    detected_at: now(),
    resolved_at: null,
    resolution_delta_id: null,
  };
}

export type ConflictResolution = 'CHOOSE_A' | 'CHOOSE_B' | 'MERGE';

export interface MergeResolution {
  type: 'MERGE';
  mergedPatch: JsonPatch[];
}

export async function resolveConflict(
  conflict: EntityConflict,
  resolution: ConflictResolution,
  mergeData?: MergeResolution
): Promise<Delta | null> {
  if (conflict.status === 'RESOLVED') {
    return null;
  }

  let newPatch: JsonPatch[];
  let prevHash: SHA256;

  switch (resolution) {
    case 'CHOOSE_A':
      // Accept branch A's head as the new state
      // Create a delta that "acknowledges" branch B and moves to A
      prevHash = conflict.branch_b.head_hash;
      newPatch = conflict.branch_a.deltas.flatMap((d) => d.patch);
      break;

    case 'CHOOSE_B':
      // Accept branch B's head as the new state
      prevHash = conflict.branch_a.head_hash;
      newPatch = conflict.branch_b.deltas.flatMap((d) => d.patch);
      break;

    case 'MERGE':
      if (!mergeData) {
        throw new Error('Merge resolution requires mergeData');
      }
      // Use the later head as prev, apply merge patch
      const aTime = Math.max(...conflict.branch_a.deltas.map((d) => d.timestamp));
      const bTime = Math.max(...conflict.branch_b.deltas.map((d) => d.timestamp));
      prevHash = aTime > bTime ? conflict.branch_a.head_hash : conflict.branch_b.head_hash;
      newPatch = mergeData.mergedPatch;
      break;

    default:
      return null;
  }

  // Reconstruct state and compute new hash
  const baseState = {}; // Would need full state reconstruction
  const newState = applyPatch(baseState, newPatch);
  const newHash = await hashState(newState);

  const resolutionDelta: Delta = {
    delta_id: generateUUID(),
    entity_id: conflict.entity_id,
    timestamp: now(),
    author: 'user',
    patch: [
      {
        op: 'add',
        path: '/_conflict_resolution',
        value: {
          resolved_conflict: conflict.base_hash,
          resolution_type: resolution,
          branch_a_head: conflict.branch_a.head_hash,
          branch_b_head: conflict.branch_b.head_hash,
        },
      },
      ...newPatch,
    ],
    prev_hash: prevHash,
    new_hash: newHash,
  };

  return resolutionDelta;
}

// === LORA CHUNKING ===

export function shouldChunk(delta: Delta, maxBytes: number = DEFAULT_MAX_PACKET_BYTES): boolean {
  const serialized = JSON.stringify(delta);
  return serialized.length > maxBytes - 50; // Leave room for packet wrapper
}

export function chunkDelta(
  nodeId: UUID,
  delta: Delta,
  chunkSize: number = CHUNK_PAYLOAD_SIZE
): DeltasChunkPacket[] {
  const serialized = JSON.stringify(delta);
  const encoded = btoa(serialized); // Base64 encode

  const chunks: DeltasChunkPacket[] = [];
  const totalChunks = Math.ceil(encoded.length / chunkSize);

  for (let i = 0; i < totalChunks; i++) {
    const start = i * chunkSize;
    const end = Math.min(start + chunkSize, encoded.length);
    const payload = encoded.slice(start, end);

    chunks.push({
      type: 'DELTAS_CHUNK',
      node_id: nodeId,
      delta_id: delta.delta_id,
      chunk_index: i,
      chunk_total: totalChunks,
      chunk_payload: payload,
    });
  }

  return chunks;
}

export function reassembleChunks(chunks: DeltasChunkPacket[]): Delta | null {
  if (chunks.length === 0) return null;

  // Verify all chunks are for same delta
  const deltaId = chunks[0].delta_id;
  if (!chunks.every((c) => c.delta_id === deltaId)) {
    return null;
  }

  // Sort by index
  const sorted = [...chunks].sort((a, b) => a.chunk_index - b.chunk_index);

  // Verify completeness
  const total = sorted[0].chunk_total;
  if (sorted.length !== total) {
    return null;
  }

  // Reassemble
  const encoded = sorted.map((c) => c.chunk_payload).join('');

  try {
    const serialized = atob(encoded);
    return JSON.parse(serialized) as Delta;
  } catch {
    return null;
  }
}

// === PRIORITY QUEUE ===

export interface PrioritizedDelta {
  delta: Delta;
  entityType: EntityType;
  priority: SyncPriority;
}

export function prioritizeDeltas(
  deltas: Delta[],
  entityTypes: Map<UUID, EntityType>
): PrioritizedDelta[] {
  return deltas
    .map((delta) => {
      const entityType = entityTypes.get(delta.entity_id) || 'note';
      return {
        delta,
        entityType,
        priority: SYNC_PRIORITY_MAP[entityType],
      };
    })
    .sort((a, b) => {
      // Sort by priority (lower = higher priority)
      if (a.priority !== b.priority) {
        return a.priority - b.priority;
      }
      // Then by timestamp (older first)
      return a.delta.timestamp - b.delta.timestamp;
    });
}

// === SYNC SESSION MANAGEMENT ===

export function createSyncSession(localNodeId: UUID, remoteNodeId: UUID): SyncSession {
  return {
    session_id: generateUUID(),
    local_node_id: localNodeId,
    remote_node_id: remoteNodeId,
    state: 'HELLO_SENT',
    started_at: now(),
    completed_at: null,
    deltas_sent: 0,
    deltas_received: 0,
    conflicts_detected: 0,
  };
}

export function updateSessionState(
  session: SyncSession,
  newState: SyncSessionState
): SyncSession {
  return {
    ...session,
    state: newState,
    completed_at: newState === 'COMPLETE' || newState === 'ERROR' ? now() : null,
  };
}

// === SYNC ORCHESTRATOR ===

export interface SyncContext {
  localNode: SyncNode;
  localEntities: Map<UUID, Entity>;
  localDeltas: Map<UUID, Delta[]>; // entity_id -> deltas
  entityTypes: Map<UUID, EntityType>;
  peerWatermarks: Map<UUID, PeerWatermark>; // peer_node_id -> watermark
  conflictStore: ConflictStore;
}

export interface SyncResult {
  session: SyncSession;
  deltasReceived: Delta[];
  deltasSent: Delta[];
  conflictsDetected: EntityConflict[];
  errors: Array<{ packet: SyncPacket; error: string }>;
}

export async function handleIncomingPacket(
  ctx: SyncContext,
  session: SyncSession,
  packet: SyncPacket
): Promise<{ response: SyncPacket | null; session: SyncSession }> {
  switch (packet.type) {
    case 'HELLO':
      return handleHello(ctx, session, packet);

    case 'HEADS':
      return handleHeads(ctx, session, packet);

    case 'WANT':
      return handleWant(ctx, session, packet);

    case 'DELTAS':
      return handleDeltas(ctx, session, packet);

    case 'DELTAS_CHUNK':
      return handleDeltasChunk(ctx, session, packet);

    case 'ACK':
      return handleAck(ctx, session, packet);

    case 'REJECT':
      return handleReject(ctx, session, packet);

    default:
      return { response: null, session };
  }
}

function handleHello(
  ctx: SyncContext,
  session: SyncSession,
  packet: HelloPacket
): { response: SyncPacket | null; session: SyncSession } {
  // Respond with our HELLO
  const response = createHelloPacket(ctx.localNode);
  const updatedSession = updateSessionState(session, 'HELLO_RECEIVED');

  return { response, session: updatedSession };
}

function handleHeads(
  ctx: SyncContext,
  session: SyncSession,
  packet: HeadsPacket
): { response: SyncPacket | null; session: SyncSession } {
  // Build our heads
  const localHeads: EntityHead[] = Array.from(ctx.localEntities.entries()).map(
    ([entityId, entity]) => ({
      entity_id: entityId,
      entity_type: ctx.entityTypes.get(entityId) || 'note',
      current_hash: entity.current_hash,
      current_version: entity.current_version,
    })
  );

  // Compute diff
  const diff = computeHeadsDiff(localHeads, packet.heads);

  // Generate wants for what we're missing
  const wants = generateWantEntries(diff, ctx.localDeltas);

  const updatedSession = updateSessionState(session, 'HEADS_EXCHANGED');

  if (wants.length > 0) {
    return {
      response: createWantPacket(ctx.localNode.node_id, wants),
      session: updatedSession,
    };
  }

  // If no wants, send our heads
  return {
    response: createHeadsPacket(
      ctx.localNode.node_id,
      Array.from(ctx.localEntities.entries()).map(([id, entity]) => ({
        entity,
        entityType: ctx.entityTypes.get(id) || 'note',
      }))
    ),
    session: updatedSession,
  };
}

function handleWant(
  ctx: SyncContext,
  session: SyncSession,
  packet: WantPacket
): { response: SyncPacket | null; session: SyncSession } {
  const deltasToSend: Delta[] = [];

  for (const want of packet.wants) {
    const entityDeltas = ctx.localDeltas.get(want.entity_id) || [];

    // Find deltas after since_hash
    let foundSinceHash = want.since_hash === '0'.repeat(64);

    for (const delta of entityDeltas) {
      if (foundSinceHash) {
        deltasToSend.push(delta);
      } else if (delta.new_hash === want.since_hash) {
        foundSinceHash = true;
      }
    }
  }

  // Prioritize deltas
  const prioritized = prioritizeDeltas(deltasToSend, ctx.entityTypes);
  const orderedDeltas = prioritized.map((p) => p.delta);

  const updatedSession: SyncSession = {
    ...session,
    state: 'SYNCING',
    deltas_sent: session.deltas_sent + orderedDeltas.length,
  };

  return {
    response: createDeltasPacket(ctx.localNode.node_id, orderedDeltas),
    session: updatedSession,
  };
}

async function handleDeltas(
  ctx: SyncContext,
  session: SyncSession,
  packet: DeltasPacket
): Promise<{ response: SyncPacket | null; session: SyncSession }> {
  const ackedIds: UUID[] = [];
  const errors: Array<{ deltaId: UUID; reason: RejectReason; message: string }> = [];

  for (const delta of packet.deltas) {
    const validation = await validateDelta(delta, ctx.localEntities, ctx.localDeltas);

    if (validation.valid) {
      // Apply delta
      applyDeltaToContext(ctx, delta);
      ackedIds.push(delta.delta_id);
    } else {
      errors.push({
        deltaId: delta.delta_id,
        reason: validation.reason!,
        message: validation.message || '',
      });

      // Check for conflict
      if (validation.reason === 'HASH_CHAIN_BROKEN') {
        const localDeltas = ctx.localDeltas.get(delta.entity_id) || [];
        const conflict = detectConflict(
          delta.entity_id,
          localDeltas,
          [delta],
          ctx.localNode.node_id,
          packet.node_id
        );

        if (conflict) {
          ctx.conflictStore.conflicts.set(delta.entity_id, conflict);
        }
      }
    }
  }

  const conflictsDetected = Array.from(ctx.conflictStore.conflicts.values()).filter(
    (c) => c.status === 'DETECTED'
  ).length;

  const updatedSession: SyncSession = {
    ...session,
    deltas_received: session.deltas_received + ackedIds.length,
    conflicts_detected: conflictsDetected,
  };

  if (errors.length > 0) {
    return {
      response: createRejectPacket(ctx.localNode.node_id, errors[0].reason, {
        delta_id: errors[0].deltaId,
        message: errors[0].message,
      }),
      session: updatedSession,
    };
  }

  return {
    response: createAckPacket(ctx.localNode.node_id, ackedIds),
    session: updatedSession,
  };
}

// Chunk reassembly buffer
const chunkBuffers = new Map<UUID, DeltasChunkPacket[]>();

function handleDeltasChunk(
  ctx: SyncContext,
  session: SyncSession,
  packet: DeltasChunkPacket
): { response: SyncPacket | null; session: SyncSession } {
  // Add to buffer
  const existing = chunkBuffers.get(packet.delta_id) || [];
  existing.push(packet);
  chunkBuffers.set(packet.delta_id, existing);

  // Check if complete
  if (existing.length === packet.chunk_total) {
    const delta = reassembleChunks(existing);
    chunkBuffers.delete(packet.delta_id);

    if (delta) {
      // Process as regular delta
      const deltasPacket: DeltasPacket = {
        type: 'DELTAS',
        node_id: packet.node_id,
        deltas: [delta],
      };
      return handleDeltas(ctx, session, deltasPacket) as unknown as {
        response: SyncPacket | null;
        session: SyncSession;
      };
    }
  }

  // Not complete yet, no response needed
  return { response: null, session };
}

function handleAck(
  ctx: SyncContext,
  session: SyncSession,
  packet: AckPacket
): { response: SyncPacket | null; session: SyncSession } {
  // ACKs are noted, no response needed
  // In production, would update retry/resend tracking
  return { response: null, session };
}

function handleReject(
  ctx: SyncContext,
  session: SyncSession,
  packet: RejectPacket
): { response: SyncPacket | null; session: SyncSession } {
  // Log rejection, potentially trigger conflict resolution
  console.error(`Sync rejected: ${packet.reason}`, packet.details);

  const updatedSession = updateSessionState(session, 'ERROR');
  return { response: null, session: updatedSession };
}

function applyDeltaToContext(ctx: SyncContext, delta: Delta): void {
  // Add to delta store
  const existing = ctx.localDeltas.get(delta.entity_id) || [];
  existing.push(delta);
  ctx.localDeltas.set(delta.entity_id, existing);

  // Update entity
  const entity = ctx.localEntities.get(delta.entity_id);
  if (entity) {
    entity.current_hash = delta.new_hash;
    entity.current_version += 1;
  } else {
    // Genesis delta, create entity
    // Would need entity_type from packet context
  }
}

// === CANONICAL JSON FOR SIGNATURES ===

export function canonicalizePacket(packet: SyncPacket): string {
  // Remove sig field for signing
  const { sig, ...payload } = packet as SyncPacket & { sig?: string };

  // Sort keys recursively
  return JSON.stringify(payload, Object.keys(payload).sort());
}

// === SIGNATURE VERIFICATION (placeholder) ===

export async function signPacket(
  packet: SyncPacket,
  privateKey: string
): Promise<SyncPacket> {
  const canonical = canonicalizePacket(packet);
  // In production: Ed25519 sign
  const sig = await hashState(canonical + privateKey);

  return { ...packet, sig };
}

export async function verifyPacketSignature(
  packet: SyncPacket,
  publicKey: string
): Promise<boolean> {
  if (!packet.sig) return false;

  const canonical = canonicalizePacket(packet);
  // In production: Ed25519 verify
  // Placeholder: just check hash matches
  const expectedSig = await hashState(canonical + publicKey);

  return packet.sig === expectedSig;
}

// === WATERMARK MANAGEMENT ===

export function updateWatermark(
  watermark: PeerWatermark,
  heads: EntityHead[]
): PeerWatermark {
  const newHeads = { ...watermark.entity_heads };

  for (const head of heads) {
    newHeads[head.entity_id] = head.current_hash;
  }

  return {
    ...watermark,
    entity_heads: newHeads,
    last_sync_at: now(),
  };
}

export function createWatermark(peerId: UUID): PeerWatermark {
  return {
    peer_node_id: peerId,
    last_sync_at: now(),
    entity_heads: {},
  };
}

// === BOOTSTRAP (new node joining) ===

export async function bootstrapFromPeer(
  ctx: SyncContext,
  peerHeads: EntityHead[]
): Promise<WantEntry[]> {
  // New node wants everything
  return peerHeads.map((head) => ({
    entity_id: head.entity_id,
    since_hash: '0'.repeat(64),
  }));
}
