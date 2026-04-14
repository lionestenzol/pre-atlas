/**
 * Delta Kernel — Usage Store (PostgreSQL)
 */

import pg from 'pg';
import type { AgentActionName } from '@aegis/shared';

const { Pool } = pg;
type PoolType = InstanceType<typeof Pool>;

export interface UsageRow {
  agent_id: string;
  period: string;
  actions_count: number;
  tokens_used: number;
  cost_usd: number;
  by_action: Record<string, number>;
  updated_at: string;
}

export class UsageStore {
  /**
   * Record an action for usage tracking (upsert).
   */
  async recordAction(
    pool: PoolType,
    agentId: string,
    action: AgentActionName,
    tokens?: number,
    costUsd?: number
  ): Promise<void> {
    const period = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
    const now = new Date().toISOString();

    // Try upsert
    const existing = await pool.query(
      'SELECT * FROM usage_records WHERE agent_id = $1 AND period = $2',
      [agentId, period]
    );

    if (existing.rows.length > 0) {
      const row = existing.rows[0];
      const byAction = (row.by_action || {}) as Record<string, number>;
      byAction[action] = (byAction[action] || 0) + 1;

      await pool.query(
        `UPDATE usage_records SET
          actions_count = actions_count + 1,
          tokens_used = tokens_used + $1,
          cost_usd = cost_usd + $2,
          by_action = $3,
          updated_at = $4
         WHERE agent_id = $5 AND period = $6`,
        [tokens || 0, costUsd || 0, JSON.stringify(byAction), now, agentId, period]
      );
    } else {
      const byAction: Record<string, number> = { [action]: 1 };
      await pool.query(
        `INSERT INTO usage_records (agent_id, period, actions_count, tokens_used, cost_usd, by_action, updated_at)
         VALUES ($1, $2, 1, $3, $4, $5, $6)`,
        [agentId, period, tokens || 0, costUsd || 0, JSON.stringify(byAction), now]
      );
    }
  }

  async getByAgent(pool: PoolType, agentId: string, period?: string): Promise<UsageRow[]> {
    let query = 'SELECT * FROM usage_records WHERE agent_id = $1';
    const params: unknown[] = [agentId];

    if (period) {
      query += ' AND period = $2';
      params.push(period);
    }

    query += ' ORDER BY period DESC';

    const res = await pool.query(query, params);
    return res.rows.map(row => this.mapRow(row));
  }

  async getAll(pool: PoolType, period?: string): Promise<UsageRow[]> {
    let query = 'SELECT * FROM usage_records';
    const params: unknown[] = [];

    if (period) {
      query += ' WHERE period = $1';
      params.push(period);
    }

    query += ' ORDER BY period DESC, actions_count DESC';

    const res = await pool.query(query, params);
    return res.rows.map(row => this.mapRow(row));
  }

  async getTotals(pool: PoolType): Promise<{ actions: number; tokens: number; cost: number }> {
    const res = await pool.query(
      'SELECT COALESCE(SUM(actions_count), 0) as actions, COALESCE(SUM(tokens_used), 0) as tokens, COALESCE(SUM(cost_usd), 0) as cost FROM usage_records'
    );
    return {
      actions: parseInt(res.rows[0].actions, 10),
      tokens: parseInt(res.rows[0].tokens, 10),
      cost: parseFloat(res.rows[0].cost),
    };
  }

  private mapRow(row: Record<string, unknown>): UsageRow {
    return {
      agent_id: row.agent_id as string,
      period: row.period as string,
      actions_count: row.actions_count as number,
      tokens_used: row.tokens_used as number,
      cost_usd: parseFloat(row.cost_usd as string),
      by_action: (row.by_action || {}) as Record<string, number>,
      updated_at: (row.updated_at as Date).toISOString(),
    };
  }
}
