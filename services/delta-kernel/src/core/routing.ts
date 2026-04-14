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

import { Mode, SystemStateData, Bucket, LifeSignals } from './types';

// Re-export Bucket from types-core (canonical definition)
export type { Bucket };

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
  const s = signals || { sleep_hours: 0, open_loops: 0, assets_shipped: 0, deep_work_blocks: 0, money_delta: 0 };
  return {
    sleep_hours: bucketSleepHours(s.sleep_hours),
    open_loops: bucketOpenLoops(s.open_loops),
    assets_shipped: bucketAssetsShipped(s.assets_shipped),
    deep_work_blocks: bucketDeepWorkBlocks(s.deep_work_blocks),
    money_delta: bucketMoneyDelta(s.money_delta, config.money_target),
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
    next: 'CLOSURE',
  },
];

// Primary routing table — mode-specific transitions
const MODE_TRANSITIONS: Record<Mode, RoutingRule[]> = {
  RECOVER: [
    {
      condition: (b) => b.sleep_hours === 'OK' || b.sleep_hours === 'HIGH',
      next: 'CLOSURE',
    },
  ],

  CLOSURE: [
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

  MAINTENANCE: [],

  SCALE: [
    {
      condition: (b) => b.assets_shipped === 'LOW',
      next: 'BUILD',
    },
    {
      condition: (b) => b.money_delta === 'LOW',
      next: 'CLOSURE',
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
  CLOSURE: ['finish_tasks', 'reply_messages', 'clean_queues'],
  MAINTENANCE: ['light_admin', 'health_actions', 'finish_tasks'],
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

// === MODE UTILITIES ===

export const MODE_DESCRIPTIONS: Record<Mode, string> = {
  RECOVER: 'Rest and restore energy. Only recovery actions available.',
  CLOSURE: 'Clear pending items and reduce mental load.',
  MAINTENANCE: 'System maintenance mode. Light admin and health actions.',
  BUILD: 'Create new work. Full capabilities enabled.',
  COMPOUND: 'Extend and improve existing work.',
  SCALE: 'Delegate, automate, and multiply impact.',
};

export const MODE_ORDER: Mode[] = ['RECOVER', 'CLOSURE', 'MAINTENANCE', 'BUILD', 'COMPOUND', 'SCALE'];

export function getModeIndex(mode: Mode): number {
  return MODE_ORDER.indexOf(mode);
}

export function isHigherMode(a: Mode, b: Mode): boolean {
  return getModeIndex(a) > getModeIndex(b);
}

// === LIFE SIGNAL BUCKET FUNCTIONS ===

export function bucketEnergyLevel(level: number): Bucket {
  if (level < 30) return 'LOW';   // Depleted — block high-effort modes
  if (level >= 70) return 'HIGH'; // Peak — all modes available
  return 'OK';
}

export function bucketFinancialPosition(runway_months: number): Bucket {
  if (runway_months < 2) return 'LOW';   // Critical — force closure
  if (runway_months >= 6) return 'HIGH'; // Secure — growth unlocked
  return 'OK';
}

export function bucketSkillsUtilization(pct: number): Bucket {
  if (pct < 40) return 'LOW';   // Working in weakness areas
  if (pct >= 70) return 'HIGH'; // Leveraging strengths
  return 'OK';
}

export function bucketNetworkActive(score: number): Bucket {
  if (score < 20) return 'LOW';   // Isolated
  if (score >= 60) return 'HIGH'; // Well-connected
  return 'OK';
}

// === CONSTRAINT ENGINE ===
// Runs AFTER core Markov routing. Keeps the routing kernel pure.
// Constraints can only downgrade mode, never upgrade.

interface RoutingConstraint {
  id: string;
  applies: (mode: Mode, life: LifeSignals) => boolean;
  enforces: Mode;
  reason: string;
}

const LIFE_CONSTRAINTS: RoutingConstraint[] = [
  {
    id: 'energy_gate',
    applies: (mode, life) =>
      bucketEnergyLevel(life.energy.energy_level) === 'LOW' &&
      getModeIndex(mode) > getModeIndex('MAINTENANCE'),
    enforces: 'MAINTENANCE',
    reason: 'Energy depleted — high-effort modes blocked until recovery',
  },
  {
    id: 'burnout_gate',
    applies: (mode, life) =>
      life.energy.burnout_risk && mode !== 'RECOVER',
    enforces: 'RECOVER',
    reason: 'Burnout risk detected — forced recovery',
  },
  {
    id: 'financial_crisis',
    applies: (mode, life) =>
      bucketFinancialPosition(life.finance.runway_months) === 'LOW' &&
      mode !== 'CLOSURE' && mode !== 'RECOVER',
    enforces: 'CLOSURE',
    reason: 'Financial runway <2 months — focus on shipping revenue-generating work',
  },
  {
    id: 'scale_requires_network',
    applies: (mode, life) =>
      mode === 'SCALE' &&
      bucketNetworkActive(life.network.collaboration_score) === 'LOW',
    enforces: 'BUILD',
    reason: 'Cannot scale without collaboration infrastructure — build first',
  },
  {
    id: 'red_alert_zone',
    applies: (mode, life) =>
      life.energy.red_alert_active &&
      getModeIndex(mode) > getModeIndex('MAINTENANCE'),
    enforces: 'MAINTENANCE',
    reason: 'In predicted interference window — limit to maintenance only',
  },
];

/**
 * Apply life-signal constraints after core routing.
 * Constraints can only downgrade mode, never upgrade.
 * Returns the constrained mode and list of active constraints.
 */
export function applyLifeConstraints(
  mode: Mode,
  lifeSignals: LifeSignals | undefined
): { mode: Mode; activeConstraints: Array<{ id: string; reason: string }> } {
  if (!lifeSignals) {
    return { mode, activeConstraints: [] };
  }

  const activeConstraints: Array<{ id: string; reason: string }> = [];
  let constrainedMode = mode;

  for (const constraint of LIFE_CONSTRAINTS) {
    if (constraint.applies(constrainedMode, lifeSignals)) {
      // Only downgrade, never upgrade
      if (getModeIndex(constraint.enforces) < getModeIndex(constrainedMode)) {
        constrainedMode = constraint.enforces;
        activeConstraints.push({ id: constraint.id, reason: constraint.reason });
      }
    }
  }

  return { mode: constrainedMode, activeConstraints };
}

/**
 * Full routing step with life-signal constraints.
 * Core routing → constraint engine → final mode.
 */
export function routeWithConstraints(
  currentMode: Mode,
  signals: SystemStateData['signals'],
  lifeSignals?: LifeSignals,
  config: RoutingConfig = DEFAULT_CONFIG
): { mode: Mode; activeConstraints: Array<{ id: string; reason: string }> } {
  const coreMode = route(currentMode, signals, config);
  return applyLifeConstraints(coreMode, lifeSignals);
}
