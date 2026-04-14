/**
 * Aegis Enterprise Fabric — Policy Store
 *
 * CRUD for policy rules per tenant. Policies stored via AegisStorage entity system.
 */

import {
  UUID, PolicyData, PolicyRule, Entity,
} from '../core/types.js';
import { createEntity, createDelta, generateUUID, now } from '../core/delta.js';
import { AegisStorage } from '../storage/aegis-storage.js';

export class PolicyStore {
  private storage: AegisStorage;

  constructor(storage: AegisStorage) {
    this.storage = storage;
  }

  async createPolicy(tenantId: UUID, rules: PolicyRule[]): Promise<{ policyId: UUID; entity: Entity }> {
    const policyData: PolicyData = {
      tenant_id: tenantId,
      rules: rules.map(r => ({
        ...r,
        rule_id: r.rule_id || generateUUID(),
        created_at: r.created_at || now(),
        updated_at: r.updated_at || now(),
      })),
      version: 1,
      created_at: now(),
      updated_at: now(),
    };

    const { entity, delta } = await createEntity('aegis_policy', policyData, tenantId);
    this.storage.saveEntity(tenantId, entity, policyData);
    this.storage.appendDelta(tenantId, delta);

    return { policyId: entity.entity_id, entity };
  }

  getPolicy(tenantId: UUID): { entity: Entity; data: PolicyData } | null {
    const policies = this.storage.loadEntitiesByType<PolicyData>(tenantId, 'aegis_policy');
    if (policies.length === 0) return null;
    // Return the most recent policy
    const latest = policies.sort((a, b) => b.state.updated_at - a.state.updated_at)[0];
    return { entity: latest.entity, data: latest.state };
  }

  getRules(tenantId: UUID): PolicyRule[] {
    const policy = this.getPolicy(tenantId);
    if (!policy) return [];
    return policy.data.rules.filter(r => r.enabled).sort((a, b) => a.priority - b.priority);
  }

  async addRule(tenantId: UUID, rule: Omit<PolicyRule, 'rule_id' | 'created_at' | 'updated_at'>): Promise<PolicyRule> {
    const policy = this.getPolicy(tenantId);
    const newRule: PolicyRule = {
      ...rule,
      rule_id: generateUUID(),
      created_at: now(),
      updated_at: now(),
    };

    if (!policy) {
      await this.createPolicy(tenantId, [newRule]);
    } else {
      policy.data.rules.push(newRule);
      policy.data.version += 1;
      policy.data.updated_at = now();
      this.storage.saveEntity(tenantId, policy.entity, policy.data);
    }

    return newRule;
  }

  async updateRule(tenantId: UUID, ruleId: UUID, updates: Partial<PolicyRule>): Promise<PolicyRule | null> {
    const policy = this.getPolicy(tenantId);
    if (!policy) return null;

    const ruleIndex = policy.data.rules.findIndex(r => r.rule_id === ruleId);
    if (ruleIndex === -1) return null;

    policy.data.rules[ruleIndex] = {
      ...policy.data.rules[ruleIndex],
      ...updates,
      rule_id: ruleId,  // preserve ID
      updated_at: now(),
    };
    policy.data.version += 1;
    policy.data.updated_at = now();
    this.storage.saveEntity(tenantId, policy.entity, policy.data);

    return policy.data.rules[ruleIndex];
  }

  async deleteRule(tenantId: UUID, ruleId: UUID): Promise<boolean> {
    const policy = this.getPolicy(tenantId);
    if (!policy) return false;

    const before = policy.data.rules.length;
    policy.data.rules = policy.data.rules.filter(r => r.rule_id !== ruleId);
    if (policy.data.rules.length === before) return false;

    policy.data.version += 1;
    policy.data.updated_at = now();
    this.storage.saveEntity(tenantId, policy.entity, policy.data);
    return true;
  }
}
