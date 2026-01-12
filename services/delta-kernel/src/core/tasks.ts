/**
 * Delta-State Fabric v0 — Task Lifecycle
 *
 * Task state machine: OPEN → DONE/BLOCKED → ARCHIVED
 * All transitions return deltas. Signal hooks trigger routing.
 */

import {
  UUID,
  Timestamp,
  Entity,
  Delta,
  JsonPatch,
  TaskData,
  TaskStatus,
  InboxData,
  SystemStateData,
  Author,
} from './types';
import { createEntity, createDelta } from './delta';

// === VALID TRANSITIONS ===

type TaskTransition = {
  from: TaskStatus;
  to: TaskStatus;
};

const VALID_TRANSITIONS: TaskTransition[] = [
  { from: 'OPEN', to: 'DONE' },
  { from: 'OPEN', to: 'BLOCKED' },
  { from: 'BLOCKED', to: 'OPEN' },
  { from: 'BLOCKED', to: 'DONE' },
  { from: 'DONE', to: 'OPEN' }, // Reopen if needed
];

export function isValidTransition(from: TaskStatus, to: TaskStatus): boolean {
  return VALID_TRANSITIONS.some((t) => t.from === from && t.to === to);
}

// === TASK CREATION ===

export async function createTask(
  titleTemplate: string,
  titleParams: Record<string, string>,
  priority: 'LOW' | 'NORMAL' | 'HIGH' = 'NORMAL',
  dueAt: Timestamp | null = null,
  linkedThread: UUID | null = null
): Promise<{ entity: Entity; delta: Delta; state: TaskData }> {
  const initialState: TaskData = {
    title_template: titleTemplate,
    title_params: titleParams,
    status: 'OPEN',
    priority,
    due_at: dueAt,
    linked_thread: linkedThread,
  };

  return createEntity('task', initialState);
}

// === STATUS TRANSITIONS ===

export function buildStatusPatch(newStatus: TaskStatus): JsonPatch[] {
  return [{ op: 'replace', path: '/status', value: newStatus }];
}

export function buildPriorityPatch(
  priority: 'LOW' | 'NORMAL' | 'HIGH'
): JsonPatch[] {
  return [{ op: 'replace', path: '/priority', value: priority }];
}

export function buildDueDatePatch(dueAt: Timestamp | null): JsonPatch[] {
  return [{ op: 'replace', path: '/due_at', value: dueAt }];
}

// === INBOX PATCHES ===

function findTaskIndex(taskQueue: UUID[], taskId: UUID): number {
  return taskQueue.indexOf(taskId);
}

export function buildInboxAddTaskPatch(taskId: UUID): JsonPatch[] {
  return [{ op: 'add', path: '/task_queue/0', value: taskId }];
}

export function buildInboxRemoveTaskPatch(index: number): JsonPatch[] {
  return [{ op: 'remove', path: `/task_queue/${index}` }];
}

// === SIGNAL HOOKS ===

export function buildOpenLoopsDecrementPatch(
  currentOpenLoops: number
): JsonPatch[] {
  return [
    {
      op: 'replace',
      path: '/signals/open_loops',
      value: Math.max(0, currentOpenLoops - 1),
    },
  ];
}

export function buildOpenLoopsIncrementPatch(
  currentOpenLoops: number
): JsonPatch[] {
  return [
    { op: 'replace', path: '/signals/open_loops', value: currentOpenLoops + 1 },
  ];
}

// === COMPOSITE FLOWS ===

export interface BlockTaskResult {
  taskDelta: { entity: Entity; delta: Delta; state: TaskData };
  inboxDelta: { entity: Entity; delta: Delta; state: InboxData };
}

/**
 * Block a task — removes from inbox queue.
 */
export async function blockTask(
  taskEntity: Entity,
  taskState: TaskData,
  inboxEntity: Entity,
  inboxState: InboxData,
  author: Author = 'user'
): Promise<BlockTaskResult> {
  if (!isValidTransition(taskState.status, 'BLOCKED')) {
    throw new Error(
      `Invalid transition: ${taskState.status} → BLOCKED`
    );
  }

  // Update task status
  const taskPatches = buildStatusPatch('BLOCKED');
  const taskDelta = await createDelta(taskEntity, taskState, taskPatches, author);

  // Remove from inbox
  const taskIndex = findTaskIndex(inboxState.task_queue, taskEntity.entity_id);
  const inboxPatches =
    taskIndex >= 0 ? buildInboxRemoveTaskPatch(taskIndex) : [];
  const inboxDelta = await createDelta(
    inboxEntity,
    inboxState,
    inboxPatches,
    author
  );

  return { taskDelta, inboxDelta };
}

export interface ResumeTaskResult {
  taskDelta: { entity: Entity; delta: Delta; state: TaskData };
  inboxDelta: { entity: Entity; delta: Delta; state: InboxData };
}

/**
 * Resume a blocked task — adds back to inbox queue.
 */
export async function resumeTask(
  taskEntity: Entity,
  taskState: TaskData,
  inboxEntity: Entity,
  inboxState: InboxData,
  author: Author = 'user'
): Promise<ResumeTaskResult> {
  if (!isValidTransition(taskState.status, 'OPEN')) {
    throw new Error(`Invalid transition: ${taskState.status} → OPEN`);
  }

  // Update task status
  const taskPatches = buildStatusPatch('OPEN');
  const taskDelta = await createDelta(taskEntity, taskState, taskPatches, author);

  // Add back to inbox
  const inboxPatches = buildInboxAddTaskPatch(taskEntity.entity_id);
  const inboxDelta = await createDelta(
    inboxEntity,
    inboxState,
    inboxPatches,
    author
  );

  return { taskDelta, inboxDelta };
}

export interface CompleteTaskResult {
  taskDelta: { entity: Entity; delta: Delta; state: TaskData };
  inboxDelta: { entity: Entity; delta: Delta; state: InboxData };
  systemStateDelta: { entity: Entity; delta: Delta; state: SystemStateData };
}

/**
 * Complete a task — removes from inbox, decrements open_loops signal.
 * This may trigger Markov routing change.
 */
export async function completeTask(
  taskEntity: Entity,
  taskState: TaskData,
  inboxEntity: Entity,
  inboxState: InboxData,
  systemStateEntity: Entity,
  systemState: SystemStateData,
  author: Author = 'user'
): Promise<CompleteTaskResult> {
  if (!isValidTransition(taskState.status, 'DONE')) {
    throw new Error(`Invalid transition: ${taskState.status} → DONE`);
  }

  // Update task status
  const taskPatches = buildStatusPatch('DONE');
  const taskDelta = await createDelta(taskEntity, taskState, taskPatches, author);

  // Remove from inbox
  const taskIndex = findTaskIndex(inboxState.task_queue, taskEntity.entity_id);
  const inboxPatches =
    taskIndex >= 0 ? buildInboxRemoveTaskPatch(taskIndex) : [];
  const inboxDelta = await createDelta(
    inboxEntity,
    inboxState,
    inboxPatches,
    author
  );

  // Decrement open_loops signal
  const signalPatches = buildOpenLoopsDecrementPatch(
    systemState.signals.open_loops
  );
  const systemStateDelta = await createDelta(
    systemStateEntity,
    systemState,
    signalPatches,
    'system'
  );

  return { taskDelta, inboxDelta, systemStateDelta };
}

export interface ArchiveTaskResult {
  entityDelta: { entity: Entity; delta: Delta; state: TaskData };
}

/**
 * Archive a task — sets is_archived on entity.
 * Only DONE tasks should be archived.
 */
export async function archiveTask(
  taskEntity: Entity,
  taskState: TaskData,
  author: Author = 'system'
): Promise<ArchiveTaskResult> {
  if (taskState.status !== 'DONE') {
    throw new Error('Can only archive DONE tasks');
  }

  // Archive is on the entity itself, but we track via delta
  const patches: JsonPatch[] = [
    { op: 'add', path: '/is_archived', value: true },
  ];
  const entityDelta = await createDelta(taskEntity, taskState, patches, author);

  return { entityDelta };
}

// === QUERY HELPERS ===

export function getOverdueTasks(
  tasks: Array<{ entity: Entity; state: TaskData }>,
  currentTime: Timestamp
): Array<{ entity: Entity; state: TaskData }> {
  return tasks.filter(
    (t) =>
      t.state.status === 'OPEN' &&
      t.state.due_at !== null &&
      t.state.due_at < currentTime
  );
}

export function getTasksByPriority(
  tasks: Array<{ entity: Entity; state: TaskData }>,
  priority: 'LOW' | 'NORMAL' | 'HIGH'
): Array<{ entity: Entity; state: TaskData }> {
  return tasks.filter(
    (t) => t.state.status === 'OPEN' && t.state.priority === priority
  );
}

export function getBlockedTasks(
  tasks: Array<{ entity: Entity; state: TaskData }>
): Array<{ entity: Entity; state: TaskData }> {
  return tasks.filter((t) => t.state.status === 'BLOCKED');
}
