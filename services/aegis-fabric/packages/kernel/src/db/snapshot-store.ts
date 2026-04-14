/**
 * Delta Kernel — Snapshot Store (PostgreSQL)
 *
 * Stores periodic full-state captures for fast replay and point-in-time queries.
 */

import pg from 'pg';

const { Pool } = pg;
type PoolType = InstanceType<typeof Pool>;

export interface SnapshotRow {
  snapshot_id: number;
  delta_id: number;
  state_hash: string;
  state: Record<string, unknown>;
  created_at: string;
}

export class SnapshotStore {
  /**
   * Create a new snapshot at the given delta point.
   */
  async create(
    pool: PoolType,
    deltaId: number,
    stateHash: string,
    state: Record<string, unknown>
  ): Promise<SnapshotRow> {
    const res = await pool.query(
      `INSERT INTO snapshots (delta_id, state_hash, state) VALUES ($1, $2, $3)
       RETURNING snapshot_id, created_at`,
      [deltaId, stateHash, JSON.stringify(state)]
    );

    return {
      snapshot_id: res.rows[0].snapshot_id,
      delta_id: deltaId,
      state_hash: stateHash,
      state,
      created_at: res.rows[0].created_at,
    };
  }

  /**
   * Get the latest snapshot (for fast state rebuild).
   */
  async getLatest(pool: PoolType): Promise<SnapshotRow | null> {
    const res = await pool.query(
      'SELECT * FROM snapshots ORDER BY delta_id DESC LIMIT 1'
    );
    if (res.rows.length === 0) return null;
    return this.mapRow(res.rows[0]);
  }

  /**
   * Get the nearest snapshot at or before a given delta_id (for point-in-time queries).
   */
  async getNearestBefore(pool: PoolType, deltaId: number): Promise<SnapshotRow | null> {
    const res = await pool.query(
      'SELECT * FROM snapshots WHERE delta_id <= $1 ORDER BY delta_id DESC LIMIT 1',
      [deltaId]
    );
    if (res.rows.length === 0) return null;
    return this.mapRow(res.rows[0]);
  }

  /**
   * Get snapshot count.
   */
  async getCount(pool: PoolType): Promise<number> {
    const res = await pool.query('SELECT COUNT(*) as count FROM snapshots');
    return parseInt(res.rows[0].count, 10);
  }

  /**
   * Prune old snapshots, keeping only the N most recent.
   */
  async prune(pool: PoolType, keepCount: number): Promise<number> {
    const res = await pool.query(
      `DELETE FROM snapshots WHERE snapshot_id NOT IN (
        SELECT snapshot_id FROM snapshots ORDER BY delta_id DESC LIMIT $1
      )`,
      [keepCount]
    );
    return res.rowCount ?? 0;
  }

  private mapRow(row: Record<string, unknown>): SnapshotRow {
    return {
      snapshot_id: row.snapshot_id as number,
      delta_id: row.delta_id as number,
      state_hash: row.state_hash as string,
      state: row.state as Record<string, unknown>,
      created_at: (row.created_at as Date).toISOString(),
    };
  }
}
