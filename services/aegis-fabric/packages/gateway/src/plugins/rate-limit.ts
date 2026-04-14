/**
 * Aegis Gateway — Redis Rate Limiter
 *
 * Sliding window rate limiting per tenant using Redis.
 * Spec 10.1: max_actions_per_hour per tenant.
 */

import type Redis from 'ioredis';

export interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  limit: number;
  resetAt: number;
  retryAfterMs?: number;
}

/**
 * Check and consume a rate limit token for a tenant.
 * Uses Redis sorted set with sliding window (1 hour).
 */
export async function checkRateLimit(
  redis: Redis,
  tenantId: string,
  maxPerHour: number
): Promise<RateLimitResult> {
  const key = `rl:${tenantId}`;
  const now = Date.now();
  const windowMs = 3_600_000; // 1 hour
  const windowStart = now - windowMs;

  // Atomic pipeline: remove expired, count, add new
  const pipeline = redis.pipeline();
  pipeline.zremrangebyscore(key, 0, windowStart);
  pipeline.zcard(key);
  pipeline.zadd(key, now.toString(), `${now}:${Math.random().toString(36).slice(2, 8)}`);
  pipeline.expire(key, 3600);

  const results = await pipeline.exec();
  if (!results) {
    return { allowed: true, remaining: maxPerHour, limit: maxPerHour, resetAt: now + windowMs };
  }

  const currentCount = (results[1]?.[1] as number) || 0;

  if (currentCount >= maxPerHour) {
    // Remove the token we just added (over limit)
    const pipeline2 = redis.pipeline();
    pipeline2.zremrangebyscore(key, now.toString(), now.toString());
    await pipeline2.exec();

    // Find the oldest entry to compute retry-after
    const oldest = await redis.zrange(key, 0, 0, 'WITHSCORES');
    const oldestTime = oldest.length >= 2 ? parseInt(oldest[1], 10) : now;
    const retryAfterMs = oldestTime + windowMs - now;

    return {
      allowed: false,
      remaining: 0,
      limit: maxPerHour,
      resetAt: oldestTime + windowMs,
      retryAfterMs: Math.max(retryAfterMs, 0),
    };
  }

  return {
    allowed: true,
    remaining: maxPerHour - currentCount - 1,
    limit: maxPerHour,
    resetAt: now + windowMs,
  };
}
