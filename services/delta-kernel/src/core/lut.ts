/**
 * Delta-State Fabric — LUT (Lookup Table) Router
 *
 * Deterministic Markov routing based on current mode and signal buckets.
 * No ML, no probabilities — pure lookup.
 */

import { Mode, Timestamp } from './types';

// === SIGNAL TYPES ===

export interface Signals {
  sleep_hours: number;
  open_loops: number;
  leverage_balance: number;
  streak_days: number;
  pending_actions: number;
}

// === BUCKET TYPES ===

export type SleepBucket = 'CRITICAL' | 'LOW' | 'OK';
export type LoopsBucket = 'MANY' | 'SOME' | 'CLEAR';
export type LeverageBucket = 'DEFICIT' | 'NEUTRAL' | 'HIGH';
export type StreakBucket = 'NONE' | 'BUILDING' | 'STRONG';

export interface Buckets {
  sleep: SleepBucket;
  loops: LoopsBucket;
  leverage: LeverageBucket;
  streak: StreakBucket;
}

// === SYSTEM STATE INPUT ===

export interface SystemStateInput {
  current_mode: Mode;
  mode_locked_until: Timestamp | null;
}

// === BUCKET CALCULATION ===

export function calculateBuckets(signals: Signals): Buckets {
  return {
    sleep: signals.sleep_hours >= 7 ? 'OK' : signals.sleep_hours >= 5 ? 'LOW' : 'CRITICAL',
    loops: signals.open_loops <= 3 ? 'CLEAR' : signals.open_loops <= 7 ? 'SOME' : 'MANY',
    leverage: signals.leverage_balance > 10 ? 'HIGH' : signals.leverage_balance > 0 ? 'NEUTRAL' : 'DEFICIT',
    streak: signals.streak_days >= 7 ? 'STRONG' : signals.streak_days >= 3 ? 'BUILDING' : 'NONE',
  };
}

// === ROUTING RULES ===

/**
 * The Markov spine routing table.
 *
 * Mode transitions follow strict rules:
 * - RECOVER is always accessible (can always retreat)
 * - Each mode has prerequisites to enter
 * - Mode lock prevents transitions until unlocked
 */
export function route(state: SystemStateInput, buckets: Buckets): Mode {
  const { current_mode, mode_locked_until } = state;
  const now = Date.now();

  // Check if mode is locked
  if (mode_locked_until && now < mode_locked_until) {
    return current_mode;
  }

  // RULE 1: Critical sleep forces RECOVER
  if (buckets.sleep === 'CRITICAL') {
    return 'RECOVER';
  }

  // RULE 2: Low sleep forces RECOVER or CLOSE_LOOPS
  if (buckets.sleep === 'LOW') {
    if (current_mode === 'BUILD' || current_mode === 'COMPOUND' || current_mode === 'SCALE') {
      return 'RECOVER';
    }
    // Can stay in RECOVER or CLOSE_LOOPS
    return current_mode === 'CLOSE_LOOPS' ? 'CLOSE_LOOPS' : 'RECOVER';
  }

  // Sleep is OK — check other conditions

  // RULE 3: Many open loops forces CLOSE_LOOPS (unless already there or RECOVER)
  if (buckets.loops === 'MANY') {
    if (current_mode === 'BUILD' || current_mode === 'COMPOUND' || current_mode === 'SCALE') {
      return 'CLOSE_LOOPS';
    }
  }

  // RULE 4: Can progress forward if conditions met
  switch (current_mode) {
    case 'RECOVER':
      // Can exit RECOVER if sleep is OK
      if (buckets.sleep === 'OK') {
        return 'CLOSE_LOOPS';
      }
      return 'RECOVER';

    case 'CLOSE_LOOPS':
      // Can enter BUILD if loops are clear or just some
      if (buckets.loops === 'CLEAR' || buckets.loops === 'SOME') {
        return 'BUILD';
      }
      return 'CLOSE_LOOPS';

    case 'BUILD':
      // Can enter COMPOUND if leverage is not deficit
      if (buckets.leverage !== 'DEFICIT' && buckets.loops !== 'MANY') {
        return 'COMPOUND';
      }
      return 'BUILD';

    case 'COMPOUND':
      // Can enter SCALE if leverage is high and streak is building
      if (buckets.leverage === 'HIGH' && buckets.streak !== 'NONE') {
        return 'SCALE';
      }
      return 'COMPOUND';

    case 'SCALE':
      // Stay in SCALE if conditions remain good
      if (buckets.leverage === 'HIGH' && buckets.streak !== 'NONE' && buckets.sleep === 'OK') {
        return 'SCALE';
      }
      // Fall back to COMPOUND
      return 'COMPOUND';
  }

  return current_mode;
}

// === MODE PROGRESSION CHECK ===

export function canEnterMode(targetMode: Mode, buckets: Buckets): boolean {
  switch (targetMode) {
    case 'RECOVER':
      return true; // Always accessible

    case 'CLOSE_LOOPS':
      return buckets.sleep !== 'CRITICAL';

    case 'BUILD':
      return buckets.sleep === 'OK' && buckets.loops !== 'MANY';

    case 'COMPOUND':
      return buckets.sleep === 'OK' && buckets.loops !== 'MANY' && buckets.leverage !== 'DEFICIT';

    case 'SCALE':
      return (
        buckets.sleep === 'OK' &&
        buckets.loops !== 'MANY' &&
        buckets.leverage === 'HIGH' &&
        buckets.streak !== 'NONE'
      );
  }
}

// === MODE INFO ===

export const MODE_DESCRIPTIONS: Record<Mode, string> = {
  RECOVER: 'Rest and restore energy. Only recovery actions available.',
  CLOSE_LOOPS: 'Clear pending items and reduce mental load.',
  BUILD: 'Create new work. Full capabilities enabled.',
  COMPOUND: 'Extend and improve existing work.',
  SCALE: 'Delegate, automate, and multiply impact.',
};

export const MODE_ORDER: Mode[] = ['RECOVER', 'CLOSE_LOOPS', 'BUILD', 'COMPOUND', 'SCALE'];

export function getModeIndex(mode: Mode): number {
  return MODE_ORDER.indexOf(mode);
}

export function isHigherMode(a: Mode, b: Mode): boolean {
  return getModeIndex(a) > getModeIndex(b);
}
