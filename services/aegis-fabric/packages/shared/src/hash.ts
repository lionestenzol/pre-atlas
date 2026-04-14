/**
 * Aegis Delta Fabric — SHA-256 Hashing Utilities
 *
 * Cryptographic hashing for delta chain integrity and state verification.
 * Uses Node.js built-in crypto.subtle (Web Crypto API).
 */

import { createHash, randomUUID } from 'node:crypto';
import type { SHA256 } from './types.js';

/**
 * Compute SHA-256 hash of a string. Synchronous (uses Node crypto).
 */
export function sha256(data: string): SHA256 {
  return createHash('sha256').update(data).digest('hex');
}

/**
 * Hash an arbitrary state object by JSON-serializing it first.
 * Keys are sorted for deterministic output.
 */
export function hashState(state: unknown): SHA256 {
  return sha256(canonicalJson(state));
}

/**
 * Compute the delta hash per the spec:
 * hash = SHA256(hashPrev + canonical_json(patch) + authorType + authorId + timestamp)
 */
export function computeDeltaHash(
  hashPrev: string | null,
  patch: unknown,
  authorType: string,
  authorId: string,
  timestamp: string
): SHA256 {
  const input = (hashPrev || '') + canonicalJson(patch) + authorType + authorId + timestamp;
  return sha256(input);
}

/**
 * Deterministic JSON serialization with sorted keys.
 * Ensures identical objects produce identical strings.
 */
export function canonicalJson(value: unknown): string {
  return JSON.stringify(value, (_key, val) => {
    if (val && typeof val === 'object' && !Array.isArray(val)) {
      return Object.keys(val).sort().reduce((sorted: Record<string, unknown>, key) => {
        sorted[key] = (val as Record<string, unknown>)[key];
        return sorted;
      }, {});
    }
    return val;
  });
}

/**
 * Generate a UUID v4 using Node.js built-in crypto.
 */
export function generateUUID(): string {
  return randomUUID();
}

/**
 * Current timestamp in Unix epoch milliseconds.
 */
export function now(): number {
  return Date.now();
}

/**
 * Genesis hash (all zeros) for the first delta in a chain.
 */
export const GENESIS_HASH = '0'.repeat(64);
