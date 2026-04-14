/**
 * Aegis Enterprise Fabric — Snapshot Manager
 *
 * Creates state snapshots every N deltas for faster rebuilds.
 * Supports point-in-time state reconstruction.
 */

import * as fs from 'fs';
import * as path from 'path';
import { UUID, Timestamp, Snapshot, Entity, Delta } from '../core/types.js';
import { generateUUID, now, hashState, reconstructState, applyPatch } from '../core/delta.js';
import { AegisStorage } from './aegis-storage.js';

const DEFAULT_SNAPSHOT_INTERVAL = 100;  // deltas between snapshots

export class SnapshotManager {
  private storage: AegisStorage;
  private snapshotInterval: number;

  constructor(storage: AegisStorage, snapshotInterval?: number) {
    this.storage = storage;
    this.snapshotInterval = snapshotInterval || DEFAULT_SNAPSHOT_INTERVAL;
  }

  /**
   * Check if a snapshot should be taken (delta count exceeds threshold since last snapshot).
   */
  shouldSnapshot(tenantId: UUID): boolean {
    const deltaCount = this.storage.getDeltaCount(tenantId);
    const snapshots = this.listSnapshots(tenantId);
    const lastSnapshotDeltaCount = snapshots.length > 0
      ? snapshots[snapshots.length - 1].delta_count
      : 0;

    return (deltaCount - lastSnapshotDeltaCount) >= this.snapshotInterval;
  }

  /**
   * Create a snapshot of the current state for a tenant.
   */
  async createSnapshot(tenantId: UUID): Promise<Snapshot> {
    const entities = this.storage.loadAllEntities(tenantId);
    const deltas = this.storage.loadDeltas(tenantId);
    const lastDelta = deltas.length > 0 ? deltas[deltas.length - 1] : null;

    const snapshot: Snapshot = {
      snapshot_id: generateUUID(),
      tenant_id: tenantId,
      delta_count: deltas.length,
      last_delta_id: lastDelta?.delta_id || 'none',
      last_delta_hash: lastDelta?.new_hash || '0'.repeat(64),
      entities: Array.from(entities.entries()).map(([, { entity, state }]) => ({ entity, state })),
      created_at: now(),
    };

    // Save snapshot
    const snapshotDir = path.join(this.storage.getTenantDir(tenantId), 'snapshots');
    if (!fs.existsSync(snapshotDir)) {
      fs.mkdirSync(snapshotDir, { recursive: true });
    }

    const snapshotFile = path.join(snapshotDir, `${snapshot.created_at}.json`);
    fs.writeFileSync(snapshotFile, JSON.stringify(snapshot, null, 2));

    return snapshot;
  }

  /**
   * List all snapshots for a tenant, sorted by creation time.
   */
  listSnapshots(tenantId: UUID): Snapshot[] {
    const snapshotDir = path.join(this.storage.getTenantDir(tenantId), 'snapshots');
    if (!fs.existsSync(snapshotDir)) return [];

    const files = fs.readdirSync(snapshotDir).filter(f => f.endsWith('.json')).sort();
    return files.map(f => {
      const content = fs.readFileSync(path.join(snapshotDir, f), 'utf-8');
      return JSON.parse(content) as Snapshot;
    });
  }

  /**
   * Rebuild state from the latest snapshot + subsequent deltas.
   * Optionally reconstruct state at a specific point in time.
   */
  rebuildState(tenantId: UUID, pointInTime?: Timestamp): Map<string, { entity: Entity; state: unknown }> {
    const snapshots = this.listSnapshots(tenantId);
    const allDeltas = this.storage.loadDeltas(tenantId);

    // Find the best snapshot to start from
    let baseSnapshot: Snapshot | null = null;
    if (pointInTime) {
      // Find the latest snapshot before the target time
      for (let i = snapshots.length - 1; i >= 0; i--) {
        if (snapshots[i].created_at <= pointInTime) {
          baseSnapshot = snapshots[i];
          break;
        }
      }
    } else {
      baseSnapshot = snapshots.length > 0 ? snapshots[snapshots.length - 1] : null;
    }

    // Start from snapshot or empty state
    const entityMap = new Map<string, { entity: Entity; state: unknown }>();
    if (baseSnapshot) {
      for (const { entity, state } of baseSnapshot.entities) {
        entityMap.set(entity.entity_id, { entity, state });
      }
    }

    // Determine which deltas to replay
    const startIndex = baseSnapshot ? baseSnapshot.delta_count : 0;
    const endIndex = pointInTime
      ? allDeltas.findIndex(d => d.timestamp > pointInTime)
      : allDeltas.length;
    const deltasToReplay = allDeltas.slice(startIndex, endIndex === -1 ? allDeltas.length : endIndex);

    // Replay deltas
    for (const delta of deltasToReplay) {
      const existing = entityMap.get(delta.entity_id);
      if (existing) {
        const newState = applyPatch(existing.state as Record<string, unknown>, delta.patch);
        entityMap.set(delta.entity_id, {
          entity: { ...existing.entity, current_version: existing.entity.current_version + 1, current_hash: delta.new_hash },
          state: newState,
        });
      }
    }

    return entityMap;
  }

  /**
   * Query a specific entity's state at a point in time.
   */
  queryEntityAtTime(tenantId: UUID, entityId: UUID, pointInTime: Timestamp): unknown | null {
    const state = this.rebuildState(tenantId, pointInTime);
    const result = state.get(entityId);
    return result ? result.state : null;
  }
}
