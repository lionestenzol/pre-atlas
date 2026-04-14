/**
 * Delta Kernel — State Materializer
 *
 * Reconstructs entity state at a specific delta point by:
 * 1. Finding the nearest snapshot before the target delta
 * 2. Replaying deltas from that snapshot forward to the target
 */

import pg from 'pg';
import { applyPatch } from '@aegis/shared';
import type { JsonPatch } from '@aegis/shared';
import { SnapshotStore } from '../db/snapshot-store.js';
import { DeltaStore } from '../db/delta-store.js';

const { Pool } = pg;
type PoolType = InstanceType<typeof Pool>;

const snapshotStore = new SnapshotStore();
const deltaStore = new DeltaStore();

export class StateMaterializer {
  /**
   * Reconstruct the full state at a given delta_id.
   * Uses nearest snapshot + replay for efficiency.
   */
  async reconstructAtDelta(
    pool: PoolType,
    targetDeltaId: number
  ): Promise<Record<string, unknown>> {
    // Find nearest snapshot at or before the target
    const snapshot = await snapshotStore.getNearestBefore(pool, targetDeltaId);

    let state: Record<string, unknown> = {};
    let afterDeltaId = 0;

    if (snapshot) {
      state = { ...snapshot.state };
      afterDeltaId = snapshot.delta_id;
    }

    // Replay deltas from snapshot point to target
    const deltas = await deltaStore.getDeltas(pool, {
      afterDeltaId,
    });

    for (const delta of deltas) {
      if ((delta.delta_id as number) > targetDeltaId) break;

      const entityId = delta.entity_id || 'global';
      const currentEntityState = (state[entityId] || {}) as Record<string, unknown>;
      state[entityId] = applyPatch(currentEntityState, delta.patch as JsonPatch[]);
    }

    return state;
  }

  /**
   * Reconstruct a single entity's state at a given delta_id.
   */
  async reconstructEntityAtDelta(
    pool: PoolType,
    entityId: string,
    targetDeltaId: number
  ): Promise<Record<string, unknown>> {
    const deltas = await deltaStore.getDeltas(pool, { entityId });

    let state: Record<string, unknown> = {};

    for (const delta of deltas) {
      if ((delta.delta_id as number) > targetDeltaId) break;
      state = applyPatch(state, delta.patch as JsonPatch[]);
    }

    return state;
  }
}
