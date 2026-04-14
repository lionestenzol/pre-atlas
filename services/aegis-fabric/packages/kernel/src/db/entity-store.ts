/**
 * Delta Kernel — Entity Store (PostgreSQL)
 *
 * CRUD for the current materialized entity state.
 * Updated atomically alongside delta appends.
 */

import pg from 'pg';
import { generateUUID, hashState } from '@aegis/shared';
import type { JsonPatch } from '@aegis/shared';
import { applyPatch } from '@aegis/shared';

const { Pool } = pg;
type PoolType = InstanceType<typeof Pool>;

export interface EntityRow {
  entity_id: string;
  entity_type: string;
  version: number;
  current_hash: string;
  state: Record<string, unknown>;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export class EntityStore {
  /**
   * Create a new entity with initial state.
   */
  async create(
    pool: PoolType,
    entityType: string,
    state: Record<string, unknown>,
    entityId?: string
  ): Promise<EntityRow> {
    const id = entityId || generateUUID();
    const hash = hashState(state);
    const now = new Date().toISOString();

    await pool.query(
      `INSERT INTO entities (entity_id, entity_type, version, current_hash, state, is_archived, created_at, updated_at)
       VALUES ($1, $2, 1, $3, $4, false, $5, $5)`,
      [id, entityType, hash, JSON.stringify(state), now]
    );

    return {
      entity_id: id,
      entity_type: entityType,
      version: 1,
      current_hash: hash,
      state,
      is_archived: false,
      created_at: now,
      updated_at: now,
    };
  }

  /**
   * Update an entity by applying a JSON Patch.
   */
  async update(
    pool: PoolType,
    entityId: string,
    patch: JsonPatch[]
  ): Promise<EntityRow | null> {
    const existing = await this.getById(pool, entityId);
    if (!existing) return null;

    const newState = applyPatch(existing.state as Record<string, unknown>, patch);
    const newHash = hashState(newState);
    const now = new Date().toISOString();

    await pool.query(
      `UPDATE entities SET state = $1, current_hash = $2, version = version + 1, updated_at = $3
       WHERE entity_id = $4`,
      [JSON.stringify(newState), newHash, now, entityId]
    );

    return {
      ...existing,
      state: newState,
      current_hash: newHash,
      version: existing.version + 1,
      updated_at: now,
    };
  }

  /**
   * Get entity by ID.
   */
  async getById(pool: PoolType, entityId: string): Promise<EntityRow | null> {
    const res = await pool.query(
      'SELECT * FROM entities WHERE entity_id = $1',
      [entityId]
    );
    if (res.rows.length === 0) return null;
    return this.mapRow(res.rows[0]);
  }

  /**
   * Get entities by type (with optional archive filter).
   */
  async getByType(
    pool: PoolType,
    entityType: string,
    opts?: { includeArchived?: boolean; limit?: number }
  ): Promise<EntityRow[]> {
    let query = 'SELECT * FROM entities WHERE entity_type = $1';
    const params: unknown[] = [entityType];

    if (!opts?.includeArchived) {
      query += ' AND is_archived = false';
    }

    query += ' ORDER BY created_at DESC';

    if (opts?.limit) {
      query += ` LIMIT $2`;
      params.push(opts.limit);
    }

    const res = await pool.query(query, params);
    return res.rows.map(row => this.mapRow(row));
  }

  /**
   * Get all entities.
   */
  async getAll(pool: PoolType, opts?: { includeArchived?: boolean }): Promise<EntityRow[]> {
    let query = 'SELECT * FROM entities';
    if (!opts?.includeArchived) {
      query += ' WHERE is_archived = false';
    }
    query += ' ORDER BY created_at DESC';

    const res = await pool.query(query);
    return res.rows.map(row => this.mapRow(row));
  }

  /**
   * Soft-delete (archive) an entity.
   */
  async archive(pool: PoolType, entityId: string): Promise<boolean> {
    const res = await pool.query(
      `UPDATE entities SET is_archived = true, updated_at = $1 WHERE entity_id = $2`,
      [new Date().toISOString(), entityId]
    );
    return (res.rowCount ?? 0) > 0;
  }

  /**
   * Get entity count by type.
   */
  async countByType(pool: PoolType, entityType?: string): Promise<number> {
    let query = 'SELECT COUNT(*) as count FROM entities WHERE is_archived = false';
    const params: unknown[] = [];

    if (entityType) {
      query += ' AND entity_type = $1';
      params.push(entityType);
    }

    const res = await pool.query(query, params);
    return parseInt(res.rows[0].count, 10);
  }

  private mapRow(row: Record<string, unknown>): EntityRow {
    return {
      entity_id: row.entity_id as string,
      entity_type: row.entity_type as string,
      version: row.version as number,
      current_hash: row.current_hash as string,
      state: row.state as Record<string, unknown>,
      is_archived: row.is_archived as boolean,
      created_at: (row.created_at as Date).toISOString(),
      updated_at: (row.updated_at as Date).toISOString(),
    };
  }
}
