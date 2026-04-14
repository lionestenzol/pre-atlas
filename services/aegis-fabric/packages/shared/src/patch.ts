/**
 * Aegis Delta Fabric — JSON Patch (RFC 6902) Application
 *
 * Applies add/replace/remove patches to state objects.
 * Used by both Gateway (simulation) and Kernel (state materialization).
 */

import type { JsonPatch } from './types.js';

/**
 * Ensure intermediate path segments exist as objects.
 */
function ensurePathExists(obj: Record<string, unknown>, path: string): void {
  const parts = path.split('/').filter(Boolean).slice(0, -1);
  let current: Record<string, unknown> = obj;
  for (const part of parts) {
    if (!current[part] || typeof current[part] !== 'object') {
      current[part] = {};
    }
    current = current[part] as Record<string, unknown>;
  }
}

/**
 * Apply an array of JSON Patch operations to a state object.
 * Returns a deep copy with patches applied (original is not mutated).
 */
export function applyPatch<T extends Record<string, unknown>>(
  state: T,
  patch: JsonPatch[]
): T {
  const result = JSON.parse(JSON.stringify(state)) as T;

  for (const op of patch) {
    ensurePathExists(result, op.path);

    const pathParts = op.path.split('/').filter(Boolean);
    const key = pathParts[pathParts.length - 1];
    let target: Record<string, unknown> = result;

    for (let i = 0; i < pathParts.length - 1; i++) {
      target = target[pathParts[i]] as Record<string, unknown>;
    }

    switch (op.op) {
      case 'add':
        if (Array.isArray(target) && !isNaN(Number(key))) {
          target.splice(Number(key), 0, op.value);
        } else {
          target[key] = op.value;
        }
        break;
      case 'replace':
        target[key] = op.value;
        break;
      case 'remove':
        if (Array.isArray(target) && !isNaN(Number(key))) {
          target.splice(Number(key), 1);
        } else {
          delete target[key];
        }
        break;
    }
  }

  return result;
}

/**
 * Reconstruct state from an ordered array of deltas by replaying their patches.
 */
export function reconstructState<T>(deltas: Array<{ patch: JsonPatch[] }>): T {
  let state = {} as Record<string, unknown>;
  for (const delta of deltas) {
    state = applyPatch(state, delta.patch);
  }
  return state as T;
}
