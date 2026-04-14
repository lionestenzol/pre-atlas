/**
 * Aegis Gateway — Redis Idempotency Plugin
 *
 * Stores action responses keyed by idempotency key.
 * SET NX with 24h TTL. If key exists, returns cached response.
 */

import type Redis from 'ioredis';

const TTL_SECONDS = 86_400; // 24 hours

export interface IdempotencyResult {
  cached: boolean;
  response?: unknown;
}

/**
 * Check if an idempotency key already has a stored response.
 */
export async function checkIdempotency(
  redis: Redis,
  tenantId: string,
  key: string
): Promise<IdempotencyResult> {
  const redisKey = `idem:${tenantId}:${key}`;
  const existing = await redis.get(redisKey);

  if (existing) {
    return { cached: true, response: JSON.parse(existing) };
  }

  return { cached: false };
}

/**
 * Store a response for an idempotency key.
 */
export async function storeIdempotencyResponse(
  redis: Redis,
  tenantId: string,
  key: string,
  response: unknown
): Promise<void> {
  const redisKey = `idem:${tenantId}:${key}`;
  await redis.set(redisKey, JSON.stringify(response), 'EX', TTL_SECONDS);
}
