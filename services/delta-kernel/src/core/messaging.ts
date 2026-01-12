/**
 * Delta-State Fabric v0 — Messaging Flow
 *
 * Inbox, Thread, Message creation and delta operations.
 * All operations return deltas — no direct state mutation.
 */

import {
  UUID,
  Entity,
  Delta,
  JsonPatch,
  ThreadData,
  MessageData,
  TaskData,
  InboxData,
  Priority,
  Author,
} from './types';
import { createEntity, createDelta, now } from './delta';

// === TASK TRIGGER RULES ===

const TASK_TRIGGER_SET = new Set([
  'TEMPLATE_REQUEST_CALL',
  'TEMPLATE_REQUEST_MEETING',
  'TEMPLATE_REQUEST_REVIEW',
  'TEMPLATE_REQUEST_APPROVAL',
  'TEMPLATE_TODO',
  'TEMPLATE_ACTION_REQUIRED',
]);

const TEMPLATE_TO_TASK_TEMPLATE: Record<string, string> = {
  TEMPLATE_REQUEST_CALL: 'TEMPLATE_CALL',
  TEMPLATE_REQUEST_MEETING: 'TEMPLATE_MEETING',
  TEMPLATE_REQUEST_REVIEW: 'TEMPLATE_REVIEW',
  TEMPLATE_REQUEST_APPROVAL: 'TEMPLATE_APPROVAL',
  TEMPLATE_TODO: 'TEMPLATE_TASK',
  TEMPLATE_ACTION_REQUIRED: 'TEMPLATE_ACTION',
};

export function shouldTriggerTask(templateId: string): boolean {
  return TASK_TRIGGER_SET.has(templateId);
}

export function getTaskTemplate(messageTemplateId: string): string {
  return TEMPLATE_TO_TASK_TEMPLATE[messageTemplateId] || 'TEMPLATE_TASK';
}

// === INBOX OPERATIONS ===

export async function createInbox(): Promise<{
  entity: Entity;
  delta: Delta;
  state: InboxData;
}> {
  const initialState: InboxData = {
    unread_count: 0,
    priority_queue: [],
    task_queue: [],
    idea_queue: [],
    last_activity_at: now(),
  };

  return createEntity('inbox', initialState);
}

export function buildInboxUpdatePatches(
  threadId: UUID,
  currentUnread: number
): JsonPatch[] {
  return [
    { op: 'replace', path: '/last_activity_at', value: now() },
    { op: 'add', path: '/priority_queue/0', value: threadId },
    { op: 'replace', path: '/unread_count', value: currentUnread + 1 },
  ];
}

export function buildInboxReadPatches(newUnreadCount: number): JsonPatch[] {
  return [{ op: 'replace', path: '/unread_count', value: newUnreadCount }];
}

export function buildInboxTaskPatches(taskId: UUID): JsonPatch[] {
  return [{ op: 'add', path: '/task_queue/0', value: taskId }];
}

// === THREAD OPERATIONS ===

export async function createThread(
  title: string,
  participants: UUID[],
  priority: Priority = 'NORMAL'
): Promise<{ entity: Entity; delta: Delta; state: ThreadData }> {
  const initialState: ThreadData = {
    title,
    participants,
    last_message_id: null,
    unread_count: 0,
    priority,
    task_flag: false,
  };

  return createEntity('thread', initialState);
}

export function buildThreadMessagePatches(
  messageId: UUID,
  currentUnread: number
): JsonPatch[] {
  return [
    { op: 'replace', path: '/last_message_id', value: messageId },
    { op: 'replace', path: '/unread_count', value: currentUnread + 1 },
  ];
}

export function buildThreadReadPatches(): JsonPatch[] {
  return [{ op: 'replace', path: '/unread_count', value: 0 }];
}

export function buildThreadTaskFlagPatch(): JsonPatch[] {
  return [{ op: 'replace', path: '/task_flag', value: true }];
}

// === MESSAGE OPERATIONS ===

export async function createMessage(
  threadId: UUID,
  templateId: string,
  params: Record<string, string>,
  sender: UUID
): Promise<{ entity: Entity; delta: Delta; state: MessageData }> {
  const initialState: MessageData = {
    thread_id: threadId,
    template_id: templateId,
    params,
    sender,
    status: 'SENT',
  };

  return createEntity('message', initialState);
}

export function buildMessageStatusPatch(
  status: 'DELIVERED' | 'READ'
): JsonPatch[] {
  return [{ op: 'replace', path: '/status', value: status }];
}

// === TASK AUTO-CREATION ===

export async function createTaskFromMessage(
  messageTemplateId: string,
  messageParams: Record<string, string>,
  linkedThreadId: UUID
): Promise<{ entity: Entity; delta: Delta; state: TaskData }> {
  const taskTemplate = getTaskTemplate(messageTemplateId);

  const initialState: TaskData = {
    title_template: taskTemplate,
    title_params: messageParams,
    status: 'OPEN',
    priority: 'NORMAL',
    due_at: null,
    linked_thread: linkedThreadId,
  };

  return createEntity('task', initialState);
}

// === COMPOSITE FLOWS ===

export interface SendMessageResult {
  message: { entity: Entity; delta: Delta; state: MessageData };
  threadDelta: { entity: Entity; delta: Delta; state: ThreadData };
  inboxDelta: { entity: Entity; delta: Delta; state: InboxData };
  task?: { entity: Entity; delta: Delta; state: TaskData };
  taskThreadDelta?: { entity: Entity; delta: Delta; state: ThreadData };
  taskInboxDelta?: { entity: Entity; delta: Delta; state: InboxData };
}

/**
 * Full message send flow — returns all deltas needed.
 * Caller is responsible for persisting deltas.
 */
export async function sendMessage(
  threadEntity: Entity,
  threadState: ThreadData,
  inboxEntity: Entity,
  inboxState: InboxData,
  templateId: string,
  params: Record<string, string>,
  sender: UUID,
  author: Author = 'user'
): Promise<SendMessageResult> {
  // 1. Create message entity
  const message = await createMessage(
    threadEntity.entity_id,
    templateId,
    params,
    sender
  );

  // 2. Update thread
  const threadPatches = buildThreadMessagePatches(
    message.entity.entity_id,
    threadState.unread_count
  );
  const threadDelta = await createDelta(
    threadEntity,
    threadState,
    threadPatches,
    author
  );

  // 3. Update inbox
  const inboxPatches = buildInboxUpdatePatches(
    threadEntity.entity_id,
    inboxState.unread_count
  );
  const inboxDelta = await createDelta(
    inboxEntity,
    inboxState,
    inboxPatches,
    author
  );

  const result: SendMessageResult = {
    message,
    threadDelta,
    inboxDelta,
  };

  // 4. Check for task trigger
  if (shouldTriggerTask(templateId)) {
    const task = await createTaskFromMessage(
      templateId,
      params,
      threadEntity.entity_id
    );

    // Update thread with task flag
    const taskThreadPatches = buildThreadTaskFlagPatch();
    const taskThreadDelta = await createDelta(
      threadDelta.entity,
      threadDelta.state,
      taskThreadPatches,
      'system'
    );

    // Update inbox with task
    const taskInboxPatches = buildInboxTaskPatches(task.entity.entity_id);
    const taskInboxDelta = await createDelta(
      inboxDelta.entity,
      inboxDelta.state,
      taskInboxPatches,
      'system'
    );

    result.task = task;
    result.taskThreadDelta = taskThreadDelta;
    result.taskInboxDelta = taskInboxDelta;
  }

  return result;
}

/**
 * Mark thread as read — returns deltas for thread and inbox.
 */
export async function markThreadRead(
  threadEntity: Entity,
  threadState: ThreadData,
  inboxEntity: Entity,
  inboxState: InboxData,
  author: Author = 'user'
): Promise<{
  threadDelta: { entity: Entity; delta: Delta; state: ThreadData };
  inboxDelta: { entity: Entity; delta: Delta; state: InboxData };
}> {
  const readCount = threadState.unread_count;

  // Update thread
  const threadPatches = buildThreadReadPatches();
  const threadDelta = await createDelta(
    threadEntity,
    threadState,
    threadPatches,
    author
  );

  // Update inbox (subtract this thread's unread from total)
  const newInboxUnread = Math.max(0, inboxState.unread_count - readCount);
  const inboxPatches = buildInboxReadPatches(newInboxUnread);
  const inboxDelta = await createDelta(
    inboxEntity,
    inboxState,
    inboxPatches,
    author
  );

  return { threadDelta, inboxDelta };
}
