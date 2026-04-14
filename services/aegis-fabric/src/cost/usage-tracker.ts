/**
 * Aegis Enterprise Fabric — Usage Tracker
 *
 * Per-tenant, per-agent usage aggregation by time period.
 */

import { UUID, UsageRecord, AgentActionName } from '../core/types.js';
import { AegisStorage } from '../storage/aegis-storage.js';

export class UsageTracker {
  private storage: AegisStorage;
  private records: Map<string, UsageRecord> = new Map();

  constructor(storage: AegisStorage) {
    this.storage = storage;
    this.load();
  }

  private key(tenantId: UUID, agentId: UUID, period: string): string {
    return `${tenantId}:${agentId}:${period}`;
  }

  private todayPeriod(): string {
    return new Date().toISOString().slice(0, 10);  // YYYY-MM-DD
  }

  recordAction(
    tenantId: UUID,
    agentId: UUID,
    action: AgentActionName,
    tokensUsed?: number,
    costUsd?: number
  ): void {
    const period = this.todayPeriod();
    const k = this.key(tenantId, agentId, period);
    let record = this.records.get(k);

    if (!record) {
      record = {
        tenant_id: tenantId,
        agent_id: agentId,
        period,
        actions_count: 0,
        tokens_used: 0,
        cost_usd: 0,
        by_action: {},
        updated_at: Date.now(),
      };
    }

    record.actions_count += 1;
    record.tokens_used += tokensUsed || 0;
    record.cost_usd += costUsd || 0;
    record.by_action[action] = (record.by_action[action] || 0) + 1;
    record.updated_at = Date.now();

    this.records.set(k, record);
    this.save();
  }

  getUsage(tenantId: UUID, period?: string): UsageRecord[] {
    const results: UsageRecord[] = [];
    for (const record of this.records.values()) {
      if (record.tenant_id === tenantId) {
        if (!period || record.period === period) {
          results.push(record);
        }
      }
    }
    return results;
  }

  getUsageByAgent(tenantId: UUID, agentId: UUID, period?: string): UsageRecord[] {
    return this.getUsage(tenantId, period).filter(r => r.agent_id === agentId);
  }

  getTenantTotals(tenantId: UUID): { actions: number; tokens: number; cost: number } {
    const records = this.getUsage(tenantId);
    return records.reduce((acc, r) => ({
      actions: acc.actions + r.actions_count,
      tokens: acc.tokens + r.tokens_used,
      cost: acc.cost + r.cost_usd,
    }), { actions: 0, tokens: 0, cost: 0 });
  }

  private load(): void {
    const data = this.storage.readGlobalFile<{ records: Array<[string, UsageRecord]> }>('usage.json');
    if (data) {
      this.records = new Map(data.records);
    }
  }

  private save(): void {
    this.storage.writeGlobalFile('usage.json', {
      records: Array.from(this.records.entries()),
    });
  }
}
