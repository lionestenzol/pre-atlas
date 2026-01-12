/**
 * Delta-State Fabric v0 — Markov Routing Core
 *
 * LOCKED - This is the gravitational spine. Deterministic only.
 *
 * Runtime Law:
 *   (current_mode, bucketed_signals) → next_mode
 *
 * No AI. No heuristics. No drift.
 */

import { Mode, SystemStateData } from './types';

// === BUCKET TYPES ===

export type Bucket = 'LOW' | 'OK' | 'HIGH';

export interface BucketedSignals {
  sleep_hours: Bucket;
  open_loops: Bucket;
  assets_shipped: Bucket;
  deep_work_blocks: Bucket;
  money_delta: Bucket;
}

// === CONFIGURATION ===

export interface RoutingConfig {
  money_target: number; // threshold for money_delta HIGH
}

const DEFAULT_CONFIG: RoutingConfig = {
  money_target: 1000, // configurable per user
};

// === BUCKET FUNCTIONS ===

export function bucketSleepHours(hours: number): Bucket {
  if (hours < 6) return 'LOW';
  if (hours >= 7.5) return 'HIGH';
  return 'OK';
}

export function bucketOpenLoops(count: number): Bucket {
  // Note: For open_loops, LOW count is GOOD (HIGH bucket)
  if (count <= 1) return 'HIGH';
  if (count >= 4) return 'LOW';
  return 'OK';
}

export function bucketAssetsShipped(count: number): Bucket {
  if (count === 0) return 'LOW';
  if (count >= 2) return 'HIGH';
  return 'OK';
}

export function bucketDeepWorkBlocks(count: number): Bucket {
  if (count === 0) return 'LOW';
  if (count >= 2) return 'HIGH';
  return 'OK';
}

export function bucketMoneyDelta(delta: number, target: number): Bucket {
  if (delta <= 0) return 'LOW';
  if (delta >= target) return 'HIGH';
  return 'OK';
}

export function bucketSignals(
  signals: SystemStateData['signals'],
  config: RoutingConfig = DEFAULT_CONFIG
): BucketedSignals {
  return {
    sleep_hours: bucketSleepHours(signals.sleep_hours),
    open_loops: bucketOpenLoops(signals.open_loops),
    assets_shipped: bucketAssetsShipped(signals.assets_shipped),
    deep_work_blocks: bucketDeepWorkBlocks(signals.deep_work_blocks),
    money_delta: bucketMoneyDelta(signals.money_delta, config.money_target),
  };
}

// === ROUTING LUT ===

type RoutingRule = {
  condition: (b: BucketedSignals) => boolean;
  next: Mode;
};

// Global overrides — highest priority, apply from ANY state
const GLOBAL_OVERRIDES: RoutingRule[] = [
  {
    condition: (b) => b.sleep_hours === 'LOW',
    next: 'RECOVER',
  },
  {
    // open_loops LOW means ≥4 loops (bad) → need to close them
    condition: (b) => b.open_loops === 'LOW',
    next: 'CLOSE_LOOPS',
  },
];

// Primary routing table — mode-specific transitions
const MODE_TRANSITIONS: Record<Mode, RoutingRule[]> = {
  RECOVER: [
    {
      condition: (b) => b.sleep_hours === 'OK' || b.sleep_hours === 'HIGH',
      next: 'CLOSE_LOOPS',
    },
  ],

  CLOSE_LOOPS: [
    {
      condition: (b) => b.open_loops === 'OK' || b.open_loops === 'HIGH',
      next: 'BUILD',
    },
  ],

  BUILD: [
    {
      condition: (b) => b.assets_shipped === 'OK' || b.assets_shipped === 'HIGH',
      next: 'COMPOUND',
    },
  ],

  COMPOUND: [
    {
      condition: (b) =>
        (b.deep_work_blocks === 'OK' || b.deep_work_blocks === 'HIGH') &&
        (b.money_delta === 'OK' || b.money_delta === 'HIGH'),
      next: 'SCALE',
    },
  ],

  SCALE: [
    {
      condition: (b) => b.assets_shipped === 'LOW',
      next: 'BUILD',
    },
    {
      condition: (b) => b.money_delta === 'LOW',
      next: 'CLOSE_LOOPS',
    },
  ],
};

// === ROUTER ===

/**
 * Compute next mode from current mode and bucketed signals.
 * Pure function. Deterministic. No side effects.
 */
export function computeNextMode(
  currentMode: Mode,
  buckets: BucketedSignals
): Mode {
  // 1. Check global overrides first
  for (const rule of GLOBAL_OVERRIDES) {
    if (rule.condition(buckets)) {
      return rule.next;
    }
  }

  // 2. Check mode-specific transitions
  const modeRules = MODE_TRANSITIONS[currentMode];
  for (const rule of modeRules) {
    if (rule.condition(buckets)) {
      return rule.next;
    }
  }

  // 3. No rule fired → stay in current mode
  return currentMode;
}

/**
 * Full routing step: raw signals → next mode
 */
export function route(
  currentMode: Mode,
  signals: SystemStateData['signals'],
  config: RoutingConfig = DEFAULT_CONFIG
): Mode {
  const buckets = bucketSignals(signals, config);
  return computeNextMode(currentMode, buckets);
}

// === MODE BEHAVIOR CONTRACTS ===

export const MODE_ALLOWED_ACTIONS: Record<Mode, string[]> = {
  RECOVER: ['rest_tasks', 'health_actions', 'sleep', 'light_admin'],
  CLOSE_LOOPS: ['finish_tasks', 'reply_messages', 'clean_queues'],
  BUILD: ['draft_assets', 'plans', 'systems'],
  COMPOUND: ['extend_assets', 'marketing', 'leverage'],
  SCALE: ['hiring', 'delegation', 'infrastructure', 'funding'],
};

/**
 * Check if an action category is allowed in current mode.
 */
export function isActionAllowed(mode: Mode, action: string): boolean {
  return MODE_ALLOWED_ACTIONS[mode].includes(action);
}
