/**
 * Aegis Enterprise Fabric — Decision Cache
 *
 * TTL-based in-memory cache for policy decisions.
 * Key: tenant_id:agent_id:action:mode
 */

import { PolicyDecision, UUID, AgentActionName, Mode } from '../core/types.js';

interface CacheEntry {
  decision: PolicyDecision;
  expiresAt: number;
}

export class DecisionCache {
  private cache: Map<string, CacheEntry> = new Map();
  private defaultTtlMs: number;

  constructor(defaultTtlMs: number = 60_000) {
    this.defaultTtlMs = defaultTtlMs;
  }

  private key(tenantId: UUID, agentId: UUID, action: AgentActionName, mode: Mode): string {
    return `${tenantId}:${agentId}:${action}:${mode}`;
  }

  get(tenantId: UUID, agentId: UUID, action: AgentActionName, mode: Mode): PolicyDecision | null {
    const k = this.key(tenantId, agentId, action, mode);
    const entry = this.cache.get(k);
    if (!entry) return null;

    if (Date.now() > entry.expiresAt) {
      this.cache.delete(k);
      return null;
    }

    return { ...entry.decision, cached: true };
  }

  set(tenantId: UUID, agentId: UUID, action: AgentActionName, mode: Mode, decision: PolicyDecision, ttlMs?: number): void {
    const k = this.key(tenantId, agentId, action, mode);
    this.cache.set(k, {
      decision,
      expiresAt: Date.now() + (ttlMs || this.defaultTtlMs),
    });
  }

  invalidateTenant(tenantId: UUID): void {
    for (const [key] of this.cache) {
      if (key.startsWith(tenantId + ':')) {
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
