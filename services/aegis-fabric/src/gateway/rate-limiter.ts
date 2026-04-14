/**
 * Aegis Enterprise Fabric — Rate Limiter
 *
 * Token bucket algorithm per tenant+agent. In-memory.
 * Refills tokens based on max_actions_per_hour quota.
 */

import { UUID } from '../core/types.js';

interface Bucket {
  tokens: number;
  max: number;
  refillRate: number;  // tokens per ms
  lastRefill: number;  // timestamp ms
}

export class RateLimiter {
  private buckets: Map<string, Bucket> = new Map();

  private key(tenantId: UUID, agentId?: UUID): string {
    return agentId ? `${tenantId}:${agentId}` : tenantId;
  }

  /**
   * Try to consume a token. Returns true if allowed.
   */
  consume(tenantId: UUID, maxPerHour: number, agentId?: UUID): boolean {
    const k = this.key(tenantId, agentId);
    let bucket = this.buckets.get(k);

    if (!bucket) {
      bucket = {
        tokens: maxPerHour,
        max: maxPerHour,
        refillRate: maxPerHour / 3_600_000,  // per ms
        lastRefill: Date.now(),
      };
      this.buckets.set(k, bucket);
    }

    // Refill tokens based on elapsed time
    const elapsed = Date.now() - bucket.lastRefill;
    bucket.tokens = Math.min(bucket.max, bucket.tokens + elapsed * bucket.refillRate);
    bucket.lastRefill = Date.now();

    if (bucket.tokens < 1) {
      return false;
    }

    bucket.tokens -= 1;
    return true;
  }

  getRemaining(tenantId: UUID, agentId?: UUID): number {
    const k = this.key(tenantId, agentId);
    const bucket = this.buckets.get(k);
    if (!bucket) return -1;  // no bucket = unlimited
    return Math.floor(bucket.tokens);
  }

  reset(tenantId: UUID, agentId?: UUID): void {
    const k = this.key(tenantId, agentId);
    this.buckets.delete(k);
  }
}
