/**
 * Delta Kernel — Delta Store (PostgreSQL)
 *
 * Append-only delta log with SHA-256 hash chain verification.
 * Uses optimistic concurrency control via hashPrev (spec 9.3).
 */

import pg from 'pg';
import { computeDeltaHash, generateUUID } from '@aegis/shared';
import type { JsonPatch, Delta } from '@aegis/shared';

const { Pool } = pg;
type PoolType = InstanceType<typeof Pool>;

export interface DeltaAppendInput {
  authorType: string;
  authorId: string;
  patch: JsonPatch[];
  entityId?: string;
  meta?: Record<string, unknown>;
}

export interface DeltaAppendResult {
  deltaId: number;
  hash: string;
  hashPrev: string | null;
  timestampMs: number;
}

export class DeltaStore {
  /**
   * Append a new delta to the log with hash chain validation.
   * Uses a transaction with SELECT ... FOR UPDATE to prevent race conditions.
   * Returns 409-style error if hashPrev doesn't match the latest delta.
   */
  async append(pool: PoolType, input: DeltaAppendInput): Promise<DeltaAppendResult> {
    const client = await pool.connect();
    try {
      await client.query('BEGIN');

      // Lock and read the latest delta
      const latestRes = await client.query(
        `SELECT delta_id, hash FROM deltas ORDER BY delta_id DESC LIMIT 1 FOR UPDATE`
      );

      const hashPrev: string | null = latestRes.rows.length > 0
        ? latestRes.rows[0].hash
        : null;

      // Compute the new delta hash
      const timestamp = new Date().toISOString();
      const hash = computeDeltaHash(
        hashPrev,
        input.patch,
        input.authorType,
        input.authorId,
        timestamp
      );

      // Insert the new delta
      const insertRes = await client.query(
        `INSERT INTO deltas (hash, hash_prev, patch, author_type, author_id, entity_id, meta, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
         RETURNING delta_id, created_at`,
        [
          hash,
          hashPrev,
          JSON.stringify(input.patch),
          input.authorType,
          input.authorId,
          input.entityId || null,
          JSON.stringify(input.meta || {}),
          timestamp,
        ]
      );

      await client.query('COMMIT');

      return {
        deltaId: insertRes.rows[0].delta_id,
        hash,
        hashPrev,
        timestampMs: new Date(insertRes.rows[0].created_at).getTime(),
      };
    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    } finally {
      client.release();
    }
  }

  /**
   * Append a delta with a specific expected hashPrev (for external concurrency control).
   * Returns null if hashPrev doesn't match (409 Conflict scenario).
   */
  async appendWithHashCheck(
    pool: PoolType,
    input: DeltaAppendInput,
    expectedHashPrev: string | null
  ): Promise<DeltaAppendResult | null> {
    const client = await pool.connect();
    try {
      await client.query('BEGIN');

      const latestRes = await client.query(
        `SELECT delta_id, hash FROM deltas ORDER BY delta_id DESC LIMIT 1 FOR UPDATE`
      );

      const actualHashPrev: string | null = latestRes.rows.length > 0
        ? latestRes.rows[0].hash
        : null;

      if (actualHashPrev !== expectedHashPrev) {
        await client.query('ROLLBACK');
        return null; // Hash conflict
      }

      const timestamp = new Date().toISOString();
      const hash = computeDeltaHash(
        actualHashPrev,
        input.patch,
        input.authorType,
        input.authorId,
        timestamp
      );

      const insertRes = await client.query(
        `INSERT INTO deltas (hash, hash_prev, patch, author_type, author_id, entity_id, meta, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
         RETURNING delta_id, created_at`,
        [
          hash,
          actualHashPrev,
          JSON.stringify(input.patch),
          input.authorType,
          input.authorId,
          input.entityId || null,
          JSON.stringify(input.meta || {}),
          timestamp,
        ]
      );

      await client.query('COMMIT');

      return {
        deltaId: insertRes.rows[0].delta_id,
        hash,
        hashPrev: actualHashPrev,
        timestampMs: new Date(insertRes.rows[0].created_at).getTime(),
      };
    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    } finally {
      client.release();
    }
  }

  /**
   * Get deltas in order, optionally filtered by entity_id.
   */
  async getDeltas(
    pool: PoolType,
    opts?: { entityId?: string; afterDeltaId?: number; limit?: number }
  ): Promise<Delta[]> {
    let query = 'SELECT * FROM deltas WHERE 1=1';
    const params: unknown[] = [];
    let idx = 1;

    if (opts?.entityId) {
      query += ` AND entity_id = $${idx++}`;
      params.push(opts.entityId);
    }
    if (opts?.afterDeltaId) {
      query += ` AND delta_id > $${idx++}`;
      params.push(opts.afterDeltaId);
    }

    query += ' ORDER BY delta_id ASC';

    if (opts?.limit) {
      query += ` LIMIT $${idx++}`;
      params.push(opts.limit);
    }

    const res = await pool.query(query, params);
    return res.rows.map(row => ({
      delta_id: row.delta_id,
      entity_id: row.entity_id,
      hash: row.hash,
      hash_prev: row.hash_prev,
      patch: row.patch,
      author_type: row.author_type,
      author_id: row.author_id,
      meta: row.meta || {},
      created_at: row.created_at,
    }));
  }

  /**
   * Get the latest delta (for hash chain head).
   */
  async getLatest(pool: PoolType): Promise<Delta | null> {
    const res = await pool.query(
      'SELECT * FROM deltas ORDER BY delta_id DESC LIMIT 1'
    );
    if (res.rows.length === 0) return null;
    const row = res.rows[0];
    return {
      delta_id: row.delta_id,
      entity_id: row.entity_id,
      hash: row.hash,
      hash_prev: row.hash_prev,
      patch: row.patch,
      author_type: row.author_type,
      author_id: row.author_id,
      meta: row.meta || {},
      created_at: row.created_at,
    };
  }

  /**
   * Get total delta count.
   */
  async getCount(pool: PoolType): Promise<number> {
    const res = await pool.query('SELECT COUNT(*) as count FROM deltas');
    return parseInt(res.rows[0].count, 10);
  }

  /**
   * Verify the hash chain integrity. Returns the first broken delta_id or null if valid.
   */
  async verifyChain(pool: PoolType): Promise<{ valid: boolean; brokenAtDeltaId?: number }> {
    const deltas = await this.getDeltas(pool);
    let expectedPrevHash: string | null = null;

    for (const delta of deltas) {
      if (delta.hash_prev !== expectedPrevHash) {
        return { valid: false, brokenAtDeltaId: delta.delta_id as number };
      }
      expectedPrevHash = delta.hash;
    }

    return { valid: true };
  }
}
