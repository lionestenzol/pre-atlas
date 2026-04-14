/**
 * Delta Kernel — Webhook Store (PostgreSQL)
 */

import pg from 'pg';
import { generateUUID, sha256 } from '@aegis/shared';
import type { WebhookEventType } from '@aegis/shared';

const { Pool } = pg;
type PoolType = InstanceType<typeof Pool>;

export interface WebhookRow {
  webhook_id: string;
  url: string;
  events: string[];
  secret_hash: string;
  enabled: boolean;
  retry_count: number;
  failure_count: number;
  last_triggered_at: string | null;
  created_at: string;
}

export class WebhookStore {
  async create(
    pool: PoolType,
    input: { url: string; events: WebhookEventType[]; secret: string }
  ): Promise<WebhookRow> {
    const id = generateUUID();
    const secretHash = sha256(input.secret);
    const now = new Date().toISOString();

    await pool.query(
      `INSERT INTO webhooks (webhook_id, url, events, secret_hash, enabled, retry_count, failure_count, created_at)
       VALUES ($1, $2, $3, $4, true, 3, 0, $5)`,
      [id, input.url, input.events, secretHash, now]
    );

    return {
      webhook_id: id, url: input.url, events: input.events, secret_hash: secretHash,
      enabled: true, retry_count: 3, failure_count: 0, last_triggered_at: null, created_at: now,
    };
  }

  async getAll(pool: PoolType): Promise<WebhookRow[]> {
    const res = await pool.query('SELECT * FROM webhooks WHERE enabled = true ORDER BY created_at DESC');
    return res.rows.map(row => this.mapRow(row));
  }

  async getById(pool: PoolType, webhookId: string): Promise<WebhookRow | null> {
    const res = await pool.query('SELECT * FROM webhooks WHERE webhook_id = $1', [webhookId]);
    if (res.rows.length === 0) return null;
    return this.mapRow(res.rows[0]);
  }

  async updateTrigger(pool: PoolType, webhookId: string, failed: boolean): Promise<void> {
    if (failed) {
      await pool.query(
        `UPDATE webhooks SET failure_count = failure_count + 1, last_triggered_at = $1 WHERE webhook_id = $2`,
        [new Date().toISOString(), webhookId]
      );
    } else {
      await pool.query(
        `UPDATE webhooks SET failure_count = 0, last_triggered_at = $1 WHERE webhook_id = $2`,
        [new Date().toISOString(), webhookId]
      );
    }
  }

  async delete(pool: PoolType, webhookId: string): Promise<boolean> {
    const res = await pool.query('DELETE FROM webhooks WHERE webhook_id = $1', [webhookId]);
    return (res.rowCount ?? 0) > 0;
  }

  private mapRow(row: Record<string, unknown>): WebhookRow {
    return {
      webhook_id: row.webhook_id as string,
      url: row.url as string,
      events: row.events as string[],
      secret_hash: row.secret_hash as string,
      enabled: row.enabled as boolean,
      retry_count: row.retry_count as number,
      failure_count: row.failure_count as number,
      last_triggered_at: row.last_triggered_at ? (row.last_triggered_at as Date).toISOString() : null,
      created_at: (row.created_at as Date).toISOString(),
    };
  }
}
