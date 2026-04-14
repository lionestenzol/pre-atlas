/**
 * Delta Kernel — Policy Store (PostgreSQL)
 */

import pg from 'pg';
import { generateUUID, now } from '@aegis/shared';
import type { PolicyRule, UUID } from '@aegis/shared';

const { Pool } = pg;
type PoolType = InstanceType<typeof Pool>;

export interface PolicyRow {
  policy_id: string;
  version: number;
  rules: PolicyRule[];
  created_at: string;
  updated_at: string;
}

export class PolicyStore {
  /**
   * Get the tenant's policy (there is typically one policy document per tenant).
   */
  async getPolicy(pool: PoolType): Promise<PolicyRow | null> {
    const res = await pool.query('SELECT * FROM policies ORDER BY version DESC LIMIT 1');
    if (res.rows.length === 0) return null;
    return this.mapRow(res.rows[0]);
  }

  /**
   * Get all enabled rules sorted by priority.
   */
  async getRules(pool: PoolType): Promise<PolicyRule[]> {
    const policy = await this.getPolicy(pool);
    if (!policy) return [];
    return policy.rules
      .filter(r => r.enabled)
      .sort((a, b) => a.priority - b.priority);
  }

  /**
   * Create or replace the tenant policy with a set of rules.
   */
  async createPolicy(pool: PoolType, rules: Partial<PolicyRule>[]): Promise<PolicyRow> {
    const policyId = generateUUID();
    const timestamp = now();
    const fullRules: PolicyRule[] = rules.map(r => ({
      rule_id: r.rule_id || generateUUID(),
      name: r.name || 'Unnamed Rule',
      description: r.description || '',
      priority: r.priority ?? 100,
      conditions: r.conditions || [],
      effect: r.effect || 'ALLOW',
      reason: r.reason || '',
      enabled: r.enabled !== false,
      created_at: timestamp,
      updated_at: timestamp,
    }));

    const existing = await this.getPolicy(pool);
    const newVersion = existing ? existing.version + 1 : 1;

    await pool.query(
      `INSERT INTO policies (policy_id, version, rules, created_at, updated_at) VALUES ($1, $2, $3, $4, $4)`,
      [policyId, newVersion, JSON.stringify(fullRules), new Date().toISOString()]
    );

    return {
      policy_id: policyId,
      version: newVersion,
      rules: fullRules,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
  }

  /**
   * Add a single rule to the current policy.
   */
  async addRule(pool: PoolType, rule: Partial<PolicyRule>): Promise<PolicyRule> {
    const existing = await this.getPolicy(pool);
    const timestamp = now();
    const newRule: PolicyRule = {
      rule_id: generateUUID(),
      name: rule.name || 'Unnamed Rule',
      description: rule.description || '',
      priority: rule.priority ?? 100,
      conditions: rule.conditions || [],
      effect: rule.effect || 'ALLOW',
      reason: rule.reason || '',
      enabled: rule.enabled !== false,
      created_at: timestamp,
      updated_at: timestamp,
    };

    if (existing) {
      const updatedRules = [...existing.rules, newRule];
      await pool.query(
        `UPDATE policies SET rules = $1, version = version + 1, updated_at = $2 WHERE policy_id = $3`,
        [JSON.stringify(updatedRules), new Date().toISOString(), existing.policy_id]
      );
    } else {
      await this.createPolicy(pool, [newRule]);
    }

    return newRule;
  }

  private mapRow(row: Record<string, unknown>): PolicyRow {
    return {
      policy_id: row.policy_id as string,
      version: row.version as number,
      rules: row.rules as PolicyRule[],
      created_at: (row.created_at as Date).toISOString(),
      updated_at: (row.updated_at as Date).toISOString(),
    };
  }
}
