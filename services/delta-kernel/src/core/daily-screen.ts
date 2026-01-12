/**
 * Delta-State Fabric v0 — Daily Mode Screen
 *
 * Builds the command center view from pure data transforms.
 * No AI at render time. LUT-driven.
 */

import {
  UUID,
  Timestamp,
  Mode,
  Priority,
  Entity,
  SystemStateData,
  InboxData,
  TaskData,
  ThreadData,
} from './types';
import {
  Bucket,
  BucketedSignals,
  bucketSignals,
  computeNextMode,
  RoutingConfig,
  MODE_ALLOWED_ACTIONS,
} from './routing';
import { now } from './delta';

// === SCREEN DATA TYPES ===

export interface SignalDisplay {
  raw: number;
  bucket: Bucket;
  label: string;
}

export interface PreparedAction {
  action_id: UUID;
  action_type:
    | 'reply_message'
    | 'complete_task'
    | 'review_thread'
    | 'create_asset'
    | 'extend_asset'
    | 'delegate'
    | 'rest'
    | 'light_admin';
  label: string;
  entity_id: UUID;
  priority: Priority;
  is_overdue: boolean;
}

export interface TransitionHint {
  target_mode: Mode;
  condition: string;
  distance: string;
}

export interface DailyScreenData {
  mode: Mode;
  signals: {
    sleep_hours: SignalDisplay;
    open_loops: SignalDisplay;
    assets_shipped: SignalDisplay;
    deep_work_blocks: SignalDisplay;
    money_delta: SignalDisplay;
  };
  mode_reason: string[];
  allowed_actions: PreparedAction[];
  transition_hints: TransitionHint[];
  generated_at: Timestamp;
}

// === ACTION TYPE → MODE MAPPING ===

const ACTION_MODE_MAP: Record<PreparedAction['action_type'], Mode[]> = {
  reply_message: ['CLOSE_LOOPS'],
  complete_task: ['CLOSE_LOOPS', 'BUILD'],
  review_thread: ['CLOSE_LOOPS'],
  create_asset: ['BUILD'],
  extend_asset: ['COMPOUND'],
  delegate: ['SCALE'],
  rest: ['RECOVER'],
  light_admin: ['RECOVER'],
};

export function isActionAllowedInMode(
  actionType: PreparedAction['action_type'],
  mode: Mode
): boolean {
  return ACTION_MODE_MAP[actionType].includes(mode);
}

// === MODE REASON BUILDER ===

function buildModeReason(
  mode: Mode,
  buckets: BucketedSignals,
  previousMode: Mode | null
): string[] {
  const reasons: string[] = [];

  // Check global overrides first
  if (buckets.sleep_hours === 'LOW') {
    reasons.push('sleep_hours is LOW (<6h) — Global override to RECOVER');
  }

  if (buckets.open_loops === 'LOW') {
    reasons.push('open_loops is LOW (≥4 open) — Global override to CLOSE_LOOPS');
  }

  // Mode-specific reasons
  if (reasons.length === 0) {
    switch (mode) {
      case 'RECOVER':
        reasons.push('Recovering — rest and light admin only');
        break;
      case 'CLOSE_LOOPS':
        reasons.push('Closing loops — finish tasks, reply messages');
        if (buckets.open_loops === 'OK') {
          reasons.push('open_loops is OK (2-3 open)');
        }
        break;
      case 'BUILD':
        reasons.push('Building — create new assets and systems');
        if (buckets.assets_shipped === 'LOW') {
          reasons.push('assets_shipped is LOW (0) — need to ship');
        }
        break;
      case 'COMPOUND':
        reasons.push('Compounding — extend existing assets');
        break;
      case 'SCALE':
        reasons.push('Scaling — delegation and infrastructure');
        break;
    }
  }

  return reasons;
}

// === TRANSITION HINTS BUILDER ===

function buildTransitionHints(
  mode: Mode,
  buckets: BucketedSignals,
  rawSignals: SystemStateData['signals']
): TransitionHint[] {
  const hints: TransitionHint[] = [];

  switch (mode) {
    case 'RECOVER':
      if (buckets.sleep_hours === 'LOW') {
        const needed = 6 - rawSignals.sleep_hours;
        hints.push({
          target_mode: 'CLOSE_LOOPS',
          condition: 'sleep_hours reaches OK (≥6h)',
          distance: `Sleep ${needed.toFixed(1)}h more`,
        });
      }
      break;

    case 'CLOSE_LOOPS':
      if (buckets.open_loops === 'LOW' || buckets.open_loops === 'OK') {
        const needed = rawSignals.open_loops - 1;
        hints.push({
          target_mode: 'BUILD',
          condition: 'open_loops reaches HIGH (≤1)',
          distance: `Close ${needed} more loop${needed !== 1 ? 's' : ''}`,
        });
      }
      break;

    case 'BUILD':
      if (buckets.assets_shipped === 'LOW') {
        hints.push({
          target_mode: 'COMPOUND',
          condition: 'assets_shipped reaches OK (≥1)',
          distance: 'Ship 1 asset',
        });
      }
      break;

    case 'COMPOUND':
      hints.push({
        target_mode: 'SCALE',
        condition: 'deep_work_blocks OK+ AND money_delta OK+',
        distance: 'Complete deep work and hit money target',
      });
      break;

    case 'SCALE':
      if (buckets.assets_shipped === 'LOW') {
        hints.push({
          target_mode: 'BUILD',
          condition: 'assets_shipped drops to LOW',
          distance: 'Currently at risk — ship to maintain',
        });
      }
      if (buckets.money_delta === 'LOW') {
        hints.push({
          target_mode: 'CLOSE_LOOPS',
          condition: 'money_delta is LOW',
          distance: 'Revenue dropped — need to stabilize',
        });
      }
      break;
  }

  // Always show RECOVER risk if sleep is borderline
  if (mode !== 'RECOVER' && rawSignals.sleep_hours < 6.5) {
    hints.push({
      target_mode: 'RECOVER',
      condition: 'sleep_hours drops to LOW (<6h)',
      distance: `${(rawSignals.sleep_hours - 6).toFixed(1)}h buffer remaining`,
    });
  }

  return hints;
}

// === ACTION BUILDERS ===

export function buildTaskAction(
  task: { entity: Entity; state: TaskData },
  currentTime: Timestamp
): PreparedAction {
  const isOverdue =
    task.state.due_at !== null && task.state.due_at < currentTime;

  return {
    action_id: task.entity.entity_id,
    action_type: 'complete_task',
    label: `Complete: ${task.state.title_template}`, // Template rendering happens at display layer
    entity_id: task.entity.entity_id,
    priority: task.state.priority === 'HIGH' ? 'HIGH' : 'NORMAL',
    is_overdue: isOverdue,
  };
}

export function buildThreadAction(
  thread: { entity: Entity; state: ThreadData }
): PreparedAction {
  const hasUnread = thread.state.unread_count > 0;

  return {
    action_id: thread.entity.entity_id,
    action_type: hasUnread ? 'reply_message' : 'review_thread',
    label: hasUnread
      ? `Reply: ${thread.state.title} (${thread.state.unread_count} unread)`
      : `Review: ${thread.state.title}`,
    entity_id: thread.entity.entity_id,
    priority: thread.state.priority,
    is_overdue: false,
  };
}

// === MAIN SCREEN BUILDER ===

export interface ScreenBuildContext {
  systemState: { entity: Entity; state: SystemStateData };
  inbox: { entity: Entity; state: InboxData };
  tasks: Array<{ entity: Entity; state: TaskData }>;
  threads: Array<{ entity: Entity; state: ThreadData }>;
  config?: RoutingConfig;
}

export function buildDailyScreen(ctx: ScreenBuildContext): DailyScreenData {
  const { systemState, inbox, tasks, threads, config } = ctx;
  const currentTime = now();

  // 1. Bucket signals
  const buckets = bucketSignals(systemState.state.signals, config);

  // 2. Build signal display
  const signals = {
    sleep_hours: {
      raw: systemState.state.signals.sleep_hours,
      bucket: buckets.sleep_hours,
      label: `${systemState.state.signals.sleep_hours}h`,
    },
    open_loops: {
      raw: systemState.state.signals.open_loops,
      bucket: buckets.open_loops,
      label: `${systemState.state.signals.open_loops} open`,
    },
    assets_shipped: {
      raw: systemState.state.signals.assets_shipped,
      bucket: buckets.assets_shipped,
      label: `${systemState.state.signals.assets_shipped} shipped`,
    },
    deep_work_blocks: {
      raw: systemState.state.signals.deep_work_blocks,
      bucket: buckets.deep_work_blocks,
      label: `${systemState.state.signals.deep_work_blocks} blocks`,
    },
    money_delta: {
      raw: systemState.state.signals.money_delta,
      bucket: buckets.money_delta,
      label:
        systemState.state.signals.money_delta >= 0
          ? `+$${systemState.state.signals.money_delta}`
          : `-$${Math.abs(systemState.state.signals.money_delta)}`,
    },
  };

  // 3. Build mode reason
  const mode_reason = buildModeReason(systemState.state.mode, buckets, null);

  // 4. Build allowed actions (filtered by mode)
  const mode = systemState.state.mode;
  const allActions: PreparedAction[] = [];

  // Add task actions
  for (const task of tasks) {
    if (task.state.status === 'OPEN') {
      const action = buildTaskAction(task, currentTime);
      if (isActionAllowedInMode(action.action_type, mode)) {
        allActions.push(action);
      }
    }
  }

  // Add thread actions
  for (const thread of threads) {
    if (!thread.entity.is_archived) {
      const action = buildThreadAction(thread);
      if (isActionAllowedInMode(action.action_type, mode)) {
        allActions.push(action);
      }
    }
  }

  // Sort: overdue first, then by priority
  const priorityOrder: Record<Priority, number> = {
    CRITICAL: 0,
    HIGH: 1,
    NORMAL: 2,
    LOW: 3,
  };

  allActions.sort((a, b) => {
    if (a.is_overdue !== b.is_overdue) {
      return a.is_overdue ? -1 : 1;
    }
    return priorityOrder[a.priority] - priorityOrder[b.priority];
  });

  // 5. Build transition hints
  const transition_hints = buildTransitionHints(
    mode,
    buckets,
    systemState.state.signals
  );

  return {
    mode,
    signals,
    mode_reason,
    allowed_actions: allActions,
    transition_hints,
    generated_at: currentTime,
  };
}

// === SCREEN DELTA (for sync) ===

/**
 * The screen itself is NOT an entity — it's a computed view.
 * But we can serialize it for LoRa transmission as a compressed payload.
 */
export function serializeScreenForSync(screen: DailyScreenData): string {
  // Minimal payload: mode + action count + first 3 action IDs
  const actionIds = screen.allowed_actions.slice(0, 3).map((a) => a.action_id);

  return JSON.stringify({
    m: screen.mode,
    ac: screen.allowed_actions.length,
    top: actionIds,
    t: screen.generated_at,
  });
}
