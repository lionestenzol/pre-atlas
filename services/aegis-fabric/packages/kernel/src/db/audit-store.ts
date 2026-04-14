/**
 * Delta Kernel — Audit Store (PostgreSQL)
 */

import pg from 'pg';
import { generateUUID } from '@aegis/shared';
import type { PolicyEffect, AgentActionName } from '@aegis/shared';

const { Pool } = pg;
type PoolType = InstanceType<typeof Pool>;

export interface AuditRow {
  audit_id: string;
  agent_id: string;
  action: string;
  effect: string;
  entity_ids: string[];
  delta_id: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export class AuditStore {
  async append(
    pool: PoolType,
    input: {
      agentId: string;
      action: AgentActionName;
      effect: PolicyEffect;
      entityIds?: string[];
      deltaId?: number;
      metadata?: Record<string, unknown>;
    }
  ): Promise<AuditRow> {
    const id = generateUUID();
    const now = new Date().toISOString();

    await pool.query(
      `INSERT INTO audit_log (audit_id, agent_id, action, effect, entity_ids, delta_id, metadata, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
      [id, input.agentId, input.action, input.effect, input.entityIds || [], input.deltaId || null, JSON.stringify(input.metadata || {}), now]
    );

    return {
      audit_id: id, agent_id: input.agentId, action: input.action, effect: input.effect,
      entity_ids: input.entityIds || [], delta_id: input.deltaId || null,
      metadata: input.metadata || {}, created_at: now,
    };
  }

  async getRecent(pool: PoolType, limit: number = 50): Promise<AuditRow[]> {
    const res = await pool.query(
      'SELECT * FROM audit_log ORDER BY created_at DESC LIMIT $1', [limit]
    );
    return res.rows.map(row => this.mapRow(row));
  }

  async getByAgent(pool: PoolType, agentId: string, limit: number = 50): Promise<AuditRow[]> {
    const res = await pool.query(
      'SELECT * FROM audit_log WHERE agent_id = $1 ORDER BY created_at DESC LIMIT $2',
      [agentId, limit]
    );
    return res.rows.map(row => this.mapRow(row));
  }

  async getByAction(pool: PoolType, action: string, limit: number = 50): Promise<AuditRow[]> {
    const res = await pool.query(
      'SELECT * FROM audit_log WHERE action = $1 ORDER BY created_at DESC LIMIT $2',
      [action, limit]
    );
    return res.rows.map(row => this.mapRow(row));
  }

  private mapRow(row: Record<string, unknown>): AuditRow {
    return {
      audit_id: row.audit_id as string,
      agent_id: row.agent_id as string,
      action: row.action as string,
      effect: row.effect as string,
      entity_ids: (row.entity_ids || []) as string[],
      delta_id: row.delta_id as number | null,
      metadata: (row.metadata || {}) as Record<string, unknown>,
      created_at: (row.created_at as Date).toISOString(),
    };
  }
}
