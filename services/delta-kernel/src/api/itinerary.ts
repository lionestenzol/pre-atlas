/**
 * Atlas Itinerary Compiler
 *
 * Composes pending_actions + open_loops + tasks + directive into an ordered
 * day-plan with a `close_via` verb per block. Deterministic over live state,
 * zero new persistence.
 *
 * See ATLAS_END_TO_END_DIAGNOSTIC.md — closes the MAPE-K plan/execute gap
 * where atomic pieces exist but nothing composes them into a march order.
 */

import type {
  Entity,
  Mode,
  Timestamp,
  UUID,
  Priority,
  TaskData,
  PendingActionData,
  SystemStateData,
  ActionType,
} from '../core/types-core';

// === PUBLIC TYPES ===

export type BlockKind = 'pending_action' | 'open_loop' | 'task' | 'directive';
export type BlockSize = 'small' | 'medium' | 'large';

export interface CloseVia {
  method: 'POST' | 'PUT' | 'GET';
  path: string;
  body?: unknown;
}

export interface ItineraryBlock {
  id: string;
  position: number;
  kind: BlockKind;
  title: string;
  why: string;
  size: BlockSize;
  priority: Priority | null;
  source: {
    pending_action_id?: UUID;
    loop_id?: string;
    task_id?: UUID;
    directive_id?: string;
  };
  close_via: CloseVia;
}

export interface OpenLoop {
  loop_id: string;
  loop_title?: string;
  opened_at?: Timestamp;
  priority?: Priority;
}

interface Loaded<T> {
  entity: Entity;
  state: T;
}

export interface ItineraryBuildContext {
  systemState: Loaded<SystemStateData>;
  pendingActions: Array<Loaded<PendingActionData>>;
  openLoops: OpenLoop[];
  tasks: Array<Loaded<TaskData>>;
  directive: { id?: string; text: string } | null;
  limit?: number;
}

export interface Itinerary {
  date: string;
  generated_at: number;
  mode: Mode;
  mode_since: Timestamp | null;
  blocks: ItineraryBlock[];
  counts: {
    pending_actions: number;
    open_loops: number;
    tasks: number;
    directive: number;
    total_composed: number;
  };
  next: { kind: BlockKind; id: string } | null;
}

// === INTERNAL CONSTANTS ===

const PRIORITY_RANK: Record<Priority, number> = {
  CRITICAL: 0,
  HIGH: 1,
  NORMAL: 2,
  LOW: 3,
};

const ACTION_LABELS: Record<ActionType, string> = {
  reply_message: 'Reply to message',
  complete_task: 'Complete task',
  send_draft: 'Send draft',
  apply_automation: 'Apply automation',
  create_asset: 'Create asset',
  delegate: 'Delegate',
  rest_action: 'Take a rest action',
};

// === BLOCK CONSTRUCTORS ===

function pendingActionBlock(
  pending: Loaded<PendingActionData>,
  position: number,
): ItineraryBlock {
  const actionType = pending.state.action_type;
  const label = ACTION_LABELS[actionType] || 'Confirm pending action';
  return {
    id: `block:pending:${pending.entity.entity_id}`,
    position,
    kind: 'pending_action',
    title: label,
    why: 'Prepared by the governance daemon and awaiting your confirmation.',
    size: 'small',
    priority: 'HIGH',
    source: { pending_action_id: pending.entity.entity_id },
    close_via: {
      method: 'POST',
      path: `/api/actions/confirm/${encodeURIComponent(pending.entity.entity_id)}`,
    },
  };
}

function openLoopBlock(loop: OpenLoop, position: number): ItineraryBlock {
  const title = loop.loop_title || `Close loop ${loop.loop_id}`;
  return {
    id: `block:loop:${loop.loop_id}`,
    position,
    kind: 'open_loop',
    title,
    why: 'Open loop tracked in governance state; closing it clears a slot.',
    size: 'medium',
    priority: loop.priority || 'NORMAL',
    source: { loop_id: loop.loop_id },
    close_via: {
      method: 'POST',
      path: '/api/law/close_loop',
      body: {
        loop_id: loop.loop_id,
        outcome: 'closed',
        title,
        status: 'RESOLVED',
        artifact_path: null,
        coverage_score: null,
      },
    },
  };
}

function taskBlock(task: Loaded<TaskData>, position: number): ItineraryBlock {
  const title = task.state.title_template || 'Untitled task';
  const hasThread = Boolean(task.state.linked_thread);
  return {
    id: `block:task:${task.entity.entity_id}`,
    position,
    kind: 'task',
    title,
    why: hasThread
      ? 'Task with linked conversation context.'
      : 'Open task in queue.',
    size: hasThread ? 'medium' : 'large',
    priority: task.state.priority as Priority,
    source: { task_id: task.entity.entity_id },
    close_via: {
      method: 'PUT',
      path: `/api/tasks/${encodeURIComponent(task.entity.entity_id)}`,
      body: [{ op: 'replace', path: '/status', value: 'DONE' }],
    },
  };
}

function directiveBlock(
  directive: { id?: string; text: string },
  position: number,
): ItineraryBlock {
  return {
    id: `block:directive:${directive.id || 'current'}`,
    position,
    kind: 'directive',
    title: directive.text,
    why: 'Latest directive emitted by Atlas.',
    size: 'medium',
    priority: null,
    source: { directive_id: directive.id || 'current' },
    close_via: {
      method: 'GET',
      path: '/api/atlas/next-directive',
    },
  };
}

// === COMPOSER ===

/**
 * Compose the itinerary. Pure function over live state.
 *
 * Ordering:
 *   1. Pending actions first (daemon already prepared these)
 *   2. In CLOSURE or RECOVER mode, open loops promoted above tasks
 *   3. HIGH-priority tasks
 *   4. Directive (if any)
 *   5. Remaining open loops
 *   6. Remaining tasks by priority
 */
export function buildItinerary(ctx: ItineraryBuildContext): Itinerary {
  const limit = ctx.limit ?? 8;
  const mode = ctx.systemState.state.mode;
  const modeSince = ctx.systemState.state.last_mode_transition_at ?? null;

  const blocks: ItineraryBlock[] = [];
  let pos = 1;

  // Only actionable pending — filter out CONFIRMED/CANCELLED/EXPIRED
  const activePending = ctx.pendingActions.filter(
    (p) => p.state.status === 'PENDING',
  );
  for (const pending of activePending) {
    if (blocks.length >= limit) break;
    blocks.push(pendingActionBlock(pending, pos++));
  }

  const openTasks = ctx.tasks.filter(
    (t) => t.state.status === 'OPEN' || t.state.status === 'IN_PROGRESS',
  );
  const highPriorityTasks = openTasks.filter((t) => t.state.priority === 'HIGH');
  const otherTasks = openTasks
    .filter((t) => t.state.priority !== 'HIGH')
    .sort((a, b) => PRIORITY_RANK[a.state.priority] - PRIORITY_RANK[b.state.priority]);

  const closureFirst = mode === 'CLOSURE' || mode === 'RECOVER';
  const remainingLoops: OpenLoop[] = [...ctx.openLoops];

  if (closureFirst) {
    while (remainingLoops.length > 0 && blocks.length < limit) {
      const loop = remainingLoops.shift();
      if (loop) blocks.push(openLoopBlock(loop, pos++));
    }
  }

  for (const task of highPriorityTasks) {
    if (blocks.length >= limit) break;
    blocks.push(taskBlock(task, pos++));
  }

  if (ctx.directive && blocks.length < limit) {
    blocks.push(directiveBlock(ctx.directive, pos++));
  }

  if (!closureFirst) {
    for (const loop of remainingLoops) {
      if (blocks.length >= limit) break;
      blocks.push(openLoopBlock(loop, pos++));
    }
  }

  for (const task of otherTasks) {
    if (blocks.length >= limit) break;
    blocks.push(taskBlock(task, pos++));
  }

  const date = new Date().toISOString().slice(0, 10);
  const next = blocks.length > 0 ? { kind: blocks[0].kind, id: blocks[0].id } : null;

  return {
    date,
    generated_at: Date.now(),
    mode,
    mode_since: modeSince,
    blocks,
    counts: {
      pending_actions: activePending.length,
      open_loops: ctx.openLoops.length,
      tasks: openTasks.length,
      directive: ctx.directive ? 1 : 0,
      total_composed: blocks.length,
    },
    next,
  };
}

/**
 * Parse open loops from governance_state.json shape.
 * Tolerant of missing/varied keys — governance_state.json has been observed
 * to use `loop_id | id | convo_id` for the id and `title | loop_title` for
 * the title. Any string id passes; malformed entries are dropped.
 */
export function parseOpenLoops(governanceState: unknown): OpenLoop[] {
  if (!governanceState || typeof governanceState !== 'object') return [];
  const raw = (governanceState as Record<string, unknown>).open_loops;
  if (!Array.isArray(raw)) return [];
  const loops: OpenLoop[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;
    const rec = item as Record<string, unknown>;
    const loopId = rec.loop_id ?? rec.id ?? rec.convo_id;
    if (typeof loopId !== 'string' || !loopId) continue;
    const title = typeof rec.title === 'string'
      ? rec.title
      : (typeof rec.loop_title === 'string' ? rec.loop_title : undefined);
    const opened = typeof rec.opened_at === 'number' ? rec.opened_at as Timestamp : undefined;
    const priority = (rec.priority === 'LOW' || rec.priority === 'NORMAL' || rec.priority === 'HIGH' || rec.priority === 'CRITICAL')
      ? rec.priority as Priority
      : undefined;
    loops.push({ loop_id: loopId, loop_title: title, opened_at: opened, priority });
  }
  return loops;
}
