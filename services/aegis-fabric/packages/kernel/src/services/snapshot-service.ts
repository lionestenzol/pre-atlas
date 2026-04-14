/**
 * Delta Kernel — Snapshot Service
 *
 * Automatically creates snapshots every N deltas for fast state reconstruction.
 * Runs as a background interval in the Kernel process.
 */

import pg from 'pg';
import { hashState } from '@aegis/shared';
import { DeltaStore } from '../db/delta-store.js';
import { SnapshotStore } from '../db/snapshot-store.js';
import { StateMaterializer } from './state-materializer.js';

const { Pool } = pg;
type PoolType = InstanceType<typeof Pool>;

const deltaStore = new DeltaStore();
const snapshotStore = new SnapshotStore();
const materializer = new StateMaterializer();

const DEFAULT_SNAPSHOT_INTERVAL = 1000; // Every 1000 deltas
const DEFAULT_MAX_SNAPSHOTS = 50;       // Keep last 50 snapshots

export class SnapshotService {
  private intervalMs: number;
  private snapshotEvery: number;
  private maxSnapshots: number;
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor(opts?: { intervalMs?: number; snapshotEvery?: number; maxSnapshots?: number }) {
    this.intervalMs = opts?.intervalMs || 60_000;       // Check every 60s
    this.snapshotEvery = opts?.snapshotEvery || DEFAULT_SNAPSHOT_INTERVAL;
    this.maxSnapshots = opts?.maxSnapshots || DEFAULT_MAX_SNAPSHOTS;
  }

  /**
   * Check if a snapshot is needed for a tenant and create one if so.
   */
  async maybeSnapshot(pool: PoolType): Promise<boolean> {
    const deltaCount = await deltaStore.getCount(pool);
    const latestSnapshot = await snapshotStore.getLatest(pool);

    const deltasSinceSnapshot = latestSnapshot
      ? deltaCount - latestSnapshot.delta_id
      : deltaCount;

    if (deltasSinceSnapshot < this.snapshotEvery) return false;

    // Get the latest delta to snapshot at
    const latest = await deltaStore.getLatest(pool);
    if (!latest) return false;

    // Reconstruct full state at this delta
    const state = await materializer.reconstructAtDelta(pool, latest.delta_id as number);
    const stateHash = hashState(state);

    await snapshotStore.create(pool, latest.delta_id as number, stateHash, state);

    // Prune old snapshots
    await snapshotStore.prune(pool, this.maxSnapshots);

    return true;
  }

  /**
   * Start periodic snapshot checking for a set of tenant pools.
   */
  start(getTenantPools: () => Map<string, PoolType>): void {
    this.timer = setInterval(async () => {
      const pools = getTenantPools();
      for (const [, pool] of pools) {
        try {
          await this.maybeSnapshot(pool);
        } catch {
          // Log but don't crash — snapshot is non-critical
        }
      }
    }, this.intervalMs);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}
