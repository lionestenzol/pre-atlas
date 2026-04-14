/**
 * Delta Kernel — Agent Store (PostgreSQL)
 */

import pg from 'pg';
import { generateUUID } from '@aegis/shared';
import type { AgentRecord, AgentProvider, AgentActionName } from '@aegis/shared';

const { Pool } = pg;
type PoolType = InstanceType<typeof Pool>;

export class AgentStore {
  async create(
    pool: PoolType,
    input: {
      name: string;
      provider: AgentProvider;
      version?: string;
      capabilities?: AgentActionName[];
      cost_center?: string;
      metadata?: Record<string, unknown>;
    }
  ): Promise<AgentRecord> {
    const id = generateUUID();
    const now = new Date().toISOString();
    const caps = input.capabilities || ['query_state'];

    await pool.query(
      `INSERT INTO agents (agent_id, name, provider, version, capabilities, cost_center, enabled, metadata, created_at, last_active_at)
       VALUES ($1, $2, $3, $4, $5, $6, true, $7, $8, $8)`,
      [id, input.name, input.provider, input.version || '1.0.0', caps, input.cost_center || 'default', JSON.stringify(input.metadata || {}), now]
    );

    return {
      agent_id: id,
      name: input.name,
      provider: input.provider,
      version: input.version || '1.0.0',
      capabilities: caps,
      cost_center: input.cost_center || 'default',
      enabled: true,
      metadata: input.metadata || {},
      created_at: now,
      last_active_at: now,
    };
  }

  async getById(pool: PoolType, agentId: string): Promise<AgentRecord | null> {
    const res = await pool.query('SELECT * FROM agents WHERE agent_id = $1', [agentId]);
    if (res.rows.length === 0) return null;
    return this.mapRow(res.rows[0]);
  }

  async getAll(pool: PoolType): Promise<AgentRecord[]> {
    const res = await pool.query('SELECT * FROM agents ORDER BY created_at DESC');
    return res.rows.map(row => this.mapRow(row));
  }

  async update(pool: PoolType, agentId: string, updates: Partial<AgentRecord>): Promise<AgentRecord | null> {
    const existing = await this.getById(pool, agentId);
    if (!existing) return null;

    const fields: string[] = [];
    const values: unknown[] = [];
    let idx = 1;

    if (updates.name !== undefined) { fields.push(`name = $${idx++}`); values.push(updates.name); }
    if (updates.provider !== undefined) { fields.push(`provider = $${idx++}`); values.push(updates.provider); }
    if (updates.version !== undefined) { fields.push(`version = $${idx++}`); values.push(updates.version); }
    if (updates.capabilities !== undefined) { fields.push(`capabilities = $${idx++}`); values.push(updates.capabilities); }
    if (updates.cost_center !== undefined) { fields.push(`cost_center = $${idx++}`); values.push(updates.cost_center); }
    if (updates.enabled !== undefined) { fields.push(`enabled = $${idx++}`); values.push(updates.enabled); }
    if (updates.metadata !== undefined) { fields.push(`metadata = $${idx++}`); values.push(JSON.stringify(updates.metadata)); }

    if (fields.length === 0) return existing;

    values.push(agentId);
    await pool.query(
      `UPDATE agents SET ${fields.join(', ')} WHERE agent_id = $${idx}`,
      values
    );

    return { ...existing, ...updates };
  }

  async updateActivity(pool: PoolType, agentId: string): Promise<void> {
    await pool.query(
      'UPDATE agents SET last_active_at = $1 WHERE agent_id = $2',
      [new Date().toISOString(), agentId]
    );
  }

  async getCount(pool: PoolType): Promise<number> {
    const res = await pool.query('SELECT COUNT(*) as count FROM agents');
    return parseInt(res.rows[0].count, 10);
  }

  private mapRow(row: Record<string, unknown>): AgentRecord {
    return {
      agent_id: row.agent_id as string,
      name: row.name as string,
      provider: row.provider as AgentProvider,
      version: row.version as string,
      capabilities: row.capabilities as AgentActionName[],
      cost_center: row.cost_center as string,
      enabled: row.enabled as boolean,
      metadata: (row.metadata || {}) as Record<string, unknown>,
      created_at: (row.created_at as Date).toISOString(),
      last_active_at: (row.last_active_at as Date).toISOString(),
    };
  }
}
