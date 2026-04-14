/**
 * Aegis Enterprise Fabric — Delta Operations
 *
 * Core delta creation, application, and hash chain management.
 * Duplicated from delta-kernel for service independence.
 * All state changes flow through this module.
 */

import {
  UUID,
  Timestamp,
  SHA256,
  Author,
  Entity,
  Delta,
  JsonPatch,
  AegisEntityType,
  AegisEntityDataMap,
} from './types.js';

// === ID GENERATION ===

export function generateUUID(): UUID {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function now(): Timestamp {
  return Date.now();
}

// === HASHING ===

async function sha256(data: string): Promise<SHA256> {
  const encoder = new TextEncoder();
  const buffer = await crypto.subtle.digest('SHA-256', encoder.encode(data));
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

export async function hashState(state: unknown): Promise<SHA256> {
  return sha256(JSON.stringify(state));
}

// === ENTITY CREATION ===

export async function createEntity<T extends AegisEntityType>(
  entityType: T,
  initialState: AegisEntityDataMap[T],
  tenantId: UUID
): Promise<{ entity: Entity; delta: Delta; state: AegisEntityDataMap[T] }> {
  const entity_id = generateUUID();
  const timestamp = now();
  const initialHash = await hashState(initialState);

  const entity: Entity = {
    entity_id,
    entity_type: entityType,
    created_at: timestamp,
    current_version: 1,
    current_hash: initialHash,
    is_archived: false,
  };

  const patch: JsonPatch[] = Object.entries(initialState as unknown as Record<string, unknown>).map(([key, value]) => ({
    op: 'add' as const,
    path: `/${key}`,
    value,
  }));

  const delta: Delta = {
    delta_id: generateUUID(),
    entity_id,
    tenant_id: tenantId,
    timestamp,
    author: 'system',
    patch,
    prev_hash: '0'.repeat(64),
    new_hash: initialHash,
  };

  return { entity, delta, state: initialState };
}

// === JSON PATCH APPLICATION ===

function ensurePathExists(obj: Record<string, unknown>, path: string): void {
  const parts = path.split('/').filter(Boolean).slice(0, -1);
  let current: Record<string, unknown> = obj;
  for (const part of parts) {
    if (!current[part] || typeof current[part] !== 'object') {
      current[part] = {};
    }
    current = current[part] as Record<string, unknown>;
  }
}

export function applyPatch<T extends Record<string, unknown>>(
  state: T,
  patch: JsonPatch[]
): T {
  const result = JSON.parse(JSON.stringify(state)) as T;

  for (const op of patch) {
    ensurePathExists(result, op.path);

    const pathParts = op.path.split('/').filter(Boolean);
    const key = pathParts[pathParts.length - 1];
    let target: Record<string, unknown> = result;

    for (let i = 0; i < pathParts.length - 1; i++) {
      target = target[pathParts[i]] as Record<string, unknown>;
    }

    switch (op.op) {
      case 'add':
        if (Array.isArray(target) && !isNaN(Number(key))) {
          target.splice(Number(key), 0, op.value);
        } else {
          target[key] = op.value;
        }
        break;
      case 'replace':
        target[key] = op.value;
        break;
      case 'remove':
        if (Array.isArray(target) && !isNaN(Number(key))) {
          target.splice(Number(key), 1);
        } else {
          delete target[key];
        }
        break;
    }
  }

  return result;
}

// === DELTA CREATION ===

export async function createDelta<T extends Record<string, unknown>>(
  entity: Entity,
  currentState: T,
  patch: JsonPatch[],
  author: Author,
  tenantId: UUID
): Promise<{ entity: Entity; delta: Delta; state: T }> {
  const newState = applyPatch(currentState, patch);
  const newHash = await hashState(newState);
  const timestamp = now();

  const delta: Delta = {
    delta_id: generateUUID(),
    entity_id: entity.entity_id,
    tenant_id: tenantId,
    timestamp,
    author,
    patch,
    prev_hash: entity.current_hash,
    new_hash: newHash,
  };

  const updatedEntity: Entity = {
    ...entity,
    current_version: entity.current_version + 1,
    current_hash: newHash,
  };

  return { entity: updatedEntity, delta, state: newState };
}

// === STATE RECONSTRUCTION ===

export function reconstructState<T>(deltas: Delta[]): T {
  const sorted = [...deltas].sort((a, b) => a.timestamp - b.timestamp);
  let state = {} as Record<string, unknown>;

  for (const delta of sorted) {
    state = applyPatch(state, delta.patch);
  }

  return state as T;
}

// === HASH CHAIN VERIFICATION ===

export async function verifyHashChain(deltas: Delta[]): Promise<boolean> {
  const sorted = [...deltas].sort((a, b) => a.timestamp - b.timestamp);
  let state = {} as Record<string, unknown>;
  let expectedPrevHash = '0'.repeat(64);

  for (const delta of sorted) {
    if (delta.prev_hash !== expectedPrevHash) {
      return false;
    }

    state = applyPatch(state, delta.patch);
    const computedHash = await hashState(state);

    if (computedHash !== delta.new_hash) {
      return false;
    }

    expectedPrevHash = delta.new_hash;
  }

  return true;
}

// === APPLY DELTA TO STATE ===

export function applyDelta<T extends Record<string, unknown>>(
  state: T,
  delta: Delta
): T {
  return applyPatch(state, delta.patch);
}
