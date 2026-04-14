/**
 * Delta Kernel — Approval Store (PostgreSQL)
 */

import pg from 'pg';
import { generateUUID } from '@aegis/shared';
import type { AgentActionName, ApprovalWorkflowStatus } from '@aegis/shared';

const { Pool } = pg;
type PoolType = InstanceType<typeof Pool>;

export interface ApprovalRow {
  approval_id: string;
  action_id: string;
  agent_id: string;
  action: string;
  params: Record<string, unknown>;
  status: ApprovalWorkflowStatus;
  requested_at: string;
  decided_at: string | null;
  decided_by: string | null;
  reason: string | null;
  expires_at: string;
}

export class ApprovalStore {
  async create(
    pool: PoolType,
    input: {
      actionId: string;
      agentId: string;
      action: AgentActionName;
      params: Record<string, unknown>;
      expiresInMs?: number;
    }
  ): Promise<ApprovalRow> {
    const id = generateUUID();
    const now = new Date();
    const expiresAt = new Date(now.getTime() + (input.expiresInMs || 3_600_000));

    await pool.query(
      `INSERT INTO approvals (approval_id, action_id, agent_id, action, params, status, requested_at, expires_at)
       VALUES ($1, $2, $3, $4, $5, 'PENDING', $6, $7)`,
      [id, input.actionId, input.agentId, input.action, JSON.stringify(input.params), now.toISOString(), expiresAt.toISOString()]
    );

    return {
      approval_id: id,
      action_id: input.actionId,
      agent_id: input.agentId,
      action: input.action,
      params: input.params,
      status: 'PENDING',
      requested_at: now.toISOString(),
      decided_at: null,
      decided_by: null,
      reason: null,
      expires_at: expiresAt.toISOString(),
    };
  }

  async getById(pool: PoolType, approvalId: string): Promise<ApprovalRow | null> {
    const res = await pool.query('SELECT * FROM approvals WHERE approval_id = $1', [approvalId]);
    if (res.rows.length === 0) return null;
    return this.mapRow(res.rows[0]);
  }

  async getPending(pool: PoolType): Promise<ApprovalRow[]> {
    const res = await pool.query(
      `SELECT * FROM approvals WHERE status = 'PENDING' ORDER BY requested_at DESC`
    );
    return res.rows.map(row => this.mapRow(row));
  }

  async decide(
    pool: PoolType,
    approvalId: string,
    decision: 'APPROVED' | 'REJECTED',
    decidedBy: string,
    reason?: string
  ): Promise<ApprovalRow | null> {
    const existing = await this.getById(pool, approvalId);
    if (!existing || existing.status !== 'PENDING') return null;

    await pool.query(
      `UPDATE approvals SET status = $1, decided_at = $2, decided_by = $3, reason = $4
       WHERE approval_id = $5`,
      [decision, new Date().toISOString(), decidedBy, reason || null, approvalId]
    );

    return {
      ...existing,
      status: decision,
      decided_at: new Date().toISOString(),
      decided_by: decidedBy,
      reason: reason || null,
    };
  }

  async expirePending(pool: PoolType): Promise<number> {
    const res = await pool.query(
      `UPDATE approvals SET status = 'EXPIRED'
       WHERE status = 'PENDING' AND expires_at < NOW()`
    );
    return res.rowCount ?? 0;
  }

  private mapRow(row: Record<string, unknown>): ApprovalRow {
    return {
      approval_id: row.approval_id as string,
      action_id: row.action_id as string,
      agent_id: row.agent_id as string,
      action: row.action as string,
      params: row.params as Record<string, unknown>,
      status: row.status as ApprovalWorkflowStatus,
      requested_at: (row.requested_at as Date).toISOString(),
      decided_at: row.decided_at ? (row.decided_at as Date).toISOString() : null,
      decided_by: row.decided_by as string | null,
      reason: row.reason as string | null,
      expires_at: (row.expires_at as Date).toISOString(),
    };
  }
}
