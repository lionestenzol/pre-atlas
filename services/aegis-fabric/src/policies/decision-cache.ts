/**
 * Aegis Enterprise Fabric — Decision Cache (lru-cache-backed).
 *
 * TTL-based in-memory cache for policy decisions.
 * Key: tenant_id:agent_id:action:mode.
 *
 * Public API preserved so policy-engine and tests do not move.
 * See ~/.claude/rules/common/assemble-first.md.
 */

import { LRUCache } from 'lru-cache';
import { PolicyDecision, UUID, AgentActionName, Mode } from '../core/types.js';

export class DecisionCache {
  private cache: LRUCache<string, PolicyDecision>;

  constructor(defaultTtlMs: number = 60_000) {
    this.cache = new LRUCache<string, PolicyDecision>({
      ttl: defaultTtlMs,
      ttlAutopurge: true,
    });
  }

  private key(tenantId: UUID, agentId: UUID, action: AgentActionName, mode: Mode): string {
    return `${tenantId}:${agentId}:${action}:${mode}`;
  }

  get(tenantId: UUID, agentId: UUID, action: AgentActionName, mode: Mode): PolicyDecision | null {
    const decision = this.cache.get(this.key(tenantId, agentId, action, mode));
    return decision ? { ...decision, cached: true } : null;
  }

  set(
    tenantId: UUID,
    agentId: UUID,
    action: AgentActionName,
    mode: Mode,
    decision: PolicyDecision,
    ttlMs?: number,
  ): void {
    const opts = ttlMs !== undefined ? { ttl: ttlMs } : undefined;
    this.cache.set(this.key(tenantId, agentId, action, mode), decision, opts);
  }

  invalidateTenant(tenantId: UUID): void {
    const prefix = tenantId + ':';
    for (const key of this.cache.keys()) {
      if (key.startsWith(prefix)) {
        this.cache.delete(key);
      }
    }
  }

  clear(): void {
    this.cache.clear();
  }

  size(): number {
    return this.cache.size;
  }
}
