/**
 * Delta-State Fabric — Module 1: Daily Cockpit
 *
 * Command center with:
 * - Mode display
 * - Prepared actions (mode-gated, max 7)
 * - Top tasks (mode-sorted)
 * - Drafts
 * - Leverage moves (LUT-derived only)
 * - Confirmation gate for all executions
 *
 * Delta-driven re-render. No polling.
 */

import {
  UUID,
  Timestamp,
  Mode,
  Priority,
  Entity,
  Delta,
  SystemStateData,
  InboxData,
  TaskData,
  ThreadData,
  DraftData,
  PendingActionData,
  ActionType,
  Author,
  JsonPatch,
} from './types';
import {
  Bucket,
  BucketedSignals,
  bucketSignals,
  RoutingConfig,
} from './routing';
import { createEntity, createDelta, now } from './delta';

// === CONSTANTS ===

const MAX_PREPARED_ACTIONS = 7;
const PENDING_ACTION_TIMEOUT_MS = 30000; // 30 seconds

// === DISPLAY TYPES ===

export interface SignalDisplay {
  raw: number;
  bucket: Bucket;
  label: string;
  is_critical: boolean;
}

export interface PreparedAction {
  slot: number;
  action_id: UUID;
  action_type: ActionType;
  label: string;
  entity_id: UUID;
  priority: Priority;
  is_overdue: boolean;
}

export interface TaskDisplay {
  task_id: UUID;
  title: string;
  priority: Priority;
  due_at: Timestamp | null;
  is_overdue: boolean;
  mode_relevance: number;
}

export interface DraftDisplay {
  draft_id: UUID;
  draft_type: 'MESSAGE' | 'ASSET' | 'PLAN' | 'SYSTEM';
  label: string;
  target_entity_id: UUID | null;
  status: 'READY' | 'QUEUED' | 'APPLIED' | 'DISMISSED' | 'PENDING';
}

export interface LeverageMove {
  move_id: string;
  description: string;
  impact: string;
  trigger_hint: string;
}

export interface CockpitState {
  timestamp: Timestamp;
  mode: Mode;
  mode_since: Timestamp;
  signals: {
    sleep_hours: SignalDisplay;
    open_loops: SignalDisplay;
    assets_shipped: SignalDisplay;
    deep_work_blocks: SignalDisplay;
    money_delta: SignalDisplay;
  };
  prepared_actions: PreparedAction[];
  top_tasks: TaskDisplay[];
  drafts: DraftDisplay[];
  leverage_moves: LeverageMove[];
  leverage_hint?: string | null;
  pending_action: {
    pending_id: UUID;
    action: PreparedAction;
    confirm_prompt: string;
    expires_at: Timestamp;
  } | null;
  last_delta_id: UUID | null;
  render_version: number;
}

// === ACTION → MODE MAPPING ===

const ACTION_MODE_MAP: Record<ActionType, Mode[]> = {
  reply_message: ['CLOSE_LOOPS'],
  complete_task: ['CLOSE_LOOPS', 'BUILD'],
  send_draft: ['CLOSE_LOOPS', 'BUILD', 'COMPOUND'],
  apply_automation: ['BUILD', 'COMPOUND', 'SCALE'],
  create_asset: ['BUILD'],
  delegate: ['SCALE'],
  rest_action: ['RECOVER'],
};

export function isActionAllowedInMode(actionType: ActionType, mode: Mode): boolean {
  return ACTION_MODE_MAP[actionType].includes(mode);
}

// === PRIORITY ORDER ===

const PRIORITY_ORDER: Record<Priority, number> = {
  CRITICAL: 0,
  HIGH: 1,
  NORMAL: 2,
  LOW: 3,
};

// === MODE RELEVANCE CALCULATION ===

function calculateModeRelevance(task: TaskData, mode: Mode): number {
  const titleTemplate = task.title_template || task.title || '';
  switch (mode) {
    case 'RECOVER':
      return task.priority === 'LOW' ? 100 : 20;
    case 'CLOSE_LOOPS':
      return task.linked_thread ? 100 : 80;
    case 'BUILD':
      return titleTemplate.includes('CREATE') ||
        titleTemplate.includes('BUILD')
        ? 100
        : 50;
    case 'COMPOUND':
      return titleTemplate.includes('EXTEND') ||
        titleTemplate.includes('IMPROVE')
        ? 100
        : 50;
    case 'SCALE':
      return titleTemplate.includes('DELEGATE') ||
        titleTemplate.includes('HIRE')
        ? 100
        : 30;
    default:
      return 50;
  }
}

// === LEVERAGE MOVE RULES (LUT) ===

interface LeverageMoveRule {
  rule_id: string;
  condition: (buckets: BucketedSignals, mode: Mode) => boolean;
  description: string;
  impact: string;
  trigger_hint: string;
}

const LEVERAGE_MOVE_RULES: LeverageMoveRule[] = [
  {
    rule_id: 'loops_to_build',
    condition: (b, m) => m === 'CLOSE_LOOPS' && (b.open_loops === 'LOW' || b.open_loops === 'OK'),
    description: 'Close loops to unlock BUILD mode',
    impact: 'Enables asset creation',
    trigger_hint: 'Complete or block pending tasks',
  },
  {
    rule_id: 'sleep_to_recover',
    condition: (b, m) => m !== 'RECOVER' && b.sleep_hours === 'LOW',
    description: 'Sleep deficit detected',
    impact: 'Will force RECOVER mode',
    trigger_hint: 'Rest to restore capacity',
  },
  {
    rule_id: 'assets_to_compound',
    condition: (b, m) => m === 'BUILD' && b.assets_shipped === 'LOW',
    description: 'Ship asset to unlock COMPOUND',
    impact: 'Enables leverage and extension',
    trigger_hint: 'Complete and ship one asset',
  },
  {
    rule_id: 'money_to_scale',
    condition: (b, m) =>
      (m === 'COMPOUND' || m === 'BUILD') && b.money_delta === 'OK',
    description: 'Revenue approaching target',
    impact: 'SCALE mode within reach',
    trigger_hint: 'Close pending deals or invoices',
  },
  {
    rule_id: 'scale_risk_assets',
    condition: (b, m) => m === 'SCALE' && b.assets_shipped === 'LOW',
    description: 'Asset pipeline empty',
    impact: 'Risk of dropping to BUILD',
    trigger_hint: 'Maintain shipping momentum',
  },
  {
    rule_id: 'scale_risk_money',
    condition: (b, m) => m === 'SCALE' && b.money_delta === 'LOW',
    description: 'Revenue dropped',
    impact: 'Risk of dropping to CLOSE_LOOPS',
    trigger_hint: 'Stabilize revenue stream',
  },
];

function computeLeverageMoves(buckets: BucketedSignals, mode: Mode): LeverageMove[] {
  return LEVERAGE_MOVE_RULES.filter((rule) => rule.condition(buckets, mode)).map(
    (rule) => ({
      move_id: rule.rule_id,
      description: rule.description,
      impact: rule.impact,
      trigger_hint: rule.trigger_hint,
    })
  );
}

// === TEMPLATE RENDERING (placeholder) ===

function renderTemplate(templateId: string, params: Record<string, string>): string {
  // In full implementation, this looks up template and fills slots
  // For now, return template ID with params appended
  const paramStr = Object.entries(params)
    .map(([k, v]) => `${k}=${v}`)
    .join(', ');
  return paramStr ? `${templateId} (${paramStr})` : templateId;
}

// === COCKPIT BUILDER ===

export interface CockpitBuildContext {
  systemState: { entity: Entity; state: SystemStateData };
  inbox: { entity: Entity; state: InboxData };
  tasks: Array<{ entity: Entity; state: TaskData }>;
  threads: Array<{ entity: Entity; state: ThreadData }>;
  drafts: Array<{ entity: Entity; state: DraftData }>;
  pendingAction: { entity: Entity; state: PendingActionData } | null;
  config?: RoutingConfig;
  lastDeltaId?: UUID;
  previousRenderVersion?: number;
}

export function buildCockpit(ctx: CockpitBuildContext): CockpitState {
  const currentTime = now();
  const mode = ctx.systemState.state.mode;

  // Get signals from nested object or flat fields
  const rawSignals = ctx.systemState.state.signals || {
    sleep_hours: ctx.systemState.state.sleep_hours || 0,
    open_loops: ctx.systemState.state.open_loops || 0,
    assets_shipped: ctx.systemState.state.assets_shipped || 0,
    deep_work_blocks: ctx.systemState.state.deep_work_blocks || 0,
    money_delta: ctx.systemState.state.money_delta || 0,
  };
  const buckets = bucketSignals(rawSignals, ctx.config);

  // 1. Build signal displays
  const signals = {
    sleep_hours: {
      raw: rawSignals.sleep_hours,
      bucket: buckets.sleep_hours,
      label: `${rawSignals.sleep_hours}h`,
      is_critical: buckets.sleep_hours === 'LOW',
    },
    open_loops: {
      raw: rawSignals.open_loops,
      bucket: buckets.open_loops,
      label: `${rawSignals.open_loops} open`,
      is_critical: buckets.open_loops === 'LOW',
    },
    assets_shipped: {
      raw: rawSignals.assets_shipped,
      bucket: buckets.assets_shipped,
      label: `${rawSignals.assets_shipped} shipped`,
      is_critical: false,
    },
    deep_work_blocks: {
      raw: rawSignals.deep_work_blocks,
      bucket: buckets.deep_work_blocks,
      label: `${rawSignals.deep_work_blocks} blocks`,
      is_critical: false,
    },
    money_delta: {
      raw: rawSignals.money_delta,
      bucket: buckets.money_delta,
      label:
        rawSignals.money_delta >= 0
          ? `+$${rawSignals.money_delta}`
          : `-$${Math.abs(rawSignals.money_delta)}`,
      is_critical: buckets.money_delta === 'LOW',
    },
  };

  // 2. Build prepared actions (mode-filtered)
  const allActions: PreparedAction[] = [];

  // From tasks
  for (const task of ctx.tasks) {
    if (task.state.status === 'OPEN') {
      const actionType: ActionType = 'complete_task';
      if (isActionAllowedInMode(actionType, mode)) {
        const isOverdue =
          task.state.due_at != null && task.state.due_at < currentTime;
        allActions.push({
          slot: 0, // Will be assigned after sorting
          action_id: task.entity.entity_id,
          action_type: actionType,
          label: `Complete: ${task.state.title || renderTemplate(task.state.title_template || '', task.state.title_params || {})}`,
          entity_id: task.entity.entity_id,
          priority: task.state.priority === 'HIGH' ? 'HIGH' : 'NORMAL',
          is_overdue: isOverdue,
        });
      }
    }
  }

  // From threads (reply actions)
  for (const thread of ctx.threads) {
    if (!thread.entity.is_archived && thread.state.unread_count > 0) {
      const actionType: ActionType = 'reply_message';
      if (isActionAllowedInMode(actionType, mode)) {
        allActions.push({
          slot: 0,
          action_id: thread.entity.entity_id,
          action_type: actionType,
          label: `Reply: ${thread.state.title} (${thread.state.unread_count} unread)`,
          entity_id: thread.entity.entity_id,
          priority: thread.state.priority,
          is_overdue: false,
        });
      }
    }
  }

  // From drafts (send actions)
  for (const draft of ctx.drafts) {
    if (draft.state.status === 'READY') {
      const actionType: ActionType = 'send_draft';
      if (isActionAllowedInMode(actionType, mode)) {
        allActions.push({
          slot: 0,
          action_id: draft.entity.entity_id,
          action_type: actionType,
          label: `Send: ${renderTemplate(draft.state.template_id, draft.state.params)}`,
          entity_id: draft.entity.entity_id,
          priority: 'NORMAL',
          is_overdue: false,
        });
      }
    }
  }

  // Sort: overdue first, then priority, then age (older first by ID)
  allActions.sort((a, b) => {
    if (a.is_overdue !== b.is_overdue) return a.is_overdue ? -1 : 1;
    if (a.priority !== b.priority) {
      return PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
    }
    return a.action_id.localeCompare(b.action_id);
  });

  // Limit and assign slots
  const prepared_actions = allActions.slice(0, MAX_PREPARED_ACTIONS).map((a, i) => ({
    ...a,
    slot: i + 1,
  }));

  // 3. Build top tasks (mode-sorted)
  const top_tasks: TaskDisplay[] = ctx.tasks
    .filter((t) => t.state.status === 'OPEN')
    .map((t) => ({
      task_id: t.entity.entity_id,
      title: t.state.title || renderTemplate(t.state.title_template || '', t.state.title_params || {}),
      priority: (t.state.priority === 'HIGH' ? 'HIGH' : t.state.priority) as Priority,
      due_at: t.state.due_at ?? null,
      is_overdue: t.state.due_at != null && t.state.due_at < currentTime,
      mode_relevance: calculateModeRelevance(t.state, mode),
    }))
    .sort((a, b) => {
      // Mode relevance first
      if (a.mode_relevance !== b.mode_relevance) {
        return b.mode_relevance - a.mode_relevance;
      }
      // Then priority
      const aPrio = a.priority as Priority;
      const bPrio = b.priority as Priority;
      if (aPrio !== bPrio) {
        return PRIORITY_ORDER[aPrio] - PRIORITY_ORDER[bPrio];
      }
      // Then due date
      if (a.due_at !== b.due_at) {
        if (a.due_at == null) return 1;
        if (b.due_at == null) return -1;
        return a.due_at - b.due_at;
      }
      return 0;
    });

  // 4. Build drafts display
  const drafts: DraftDisplay[] = ctx.drafts
    .filter((d) => d.state.status !== 'APPLIED')
    .map((d) => ({
      draft_id: d.entity.entity_id,
      draft_type: d.state.draft_type,
      label: renderTemplate(d.state.template_id, d.state.params),
      target_entity_id: d.state.target_entity_id,
      status: d.state.status,
    }));

  // 5. Compute leverage moves (LUT only)
  const leverage_moves = computeLeverageMoves(buckets, mode);

  // 6. Build pending action display
  let pending_action: CockpitState['pending_action'] = null;
  if (
    ctx.pendingAction &&
    ctx.pendingAction.state.status === 'PENDING' &&
    ctx.pendingAction.state.expires_at > currentTime
  ) {
    const pa = ctx.pendingAction.state;
    const matchingAction = prepared_actions.find(
      (a) => a.entity_id === pa.target_entity_id
    );
    if (matchingAction) {
      pending_action = {
        pending_id: ctx.pendingAction.entity.entity_id,
        action: matchingAction,
        confirm_prompt: `Execute ${matchingAction.action_type}: ${matchingAction.label}?`,
        expires_at: pa.expires_at,
      };
    }
  }

  return {
    timestamp: currentTime,
    mode,
    mode_since: ctx.systemState.state.mode_since ?? ctx.systemState.entity.created_at,
    signals,
    prepared_actions,
    top_tasks,
    drafts,
    leverage_moves,
    pending_action,
    last_delta_id: ctx.lastDeltaId || null,
    render_version: (ctx.previousRenderVersion || 0) + 1,
  };
}

// === CONFIRMATION GATE ===

export async function createPendingAction(
  action: PreparedAction,
  author: Author = 'user'
): Promise<{ entity: Entity; delta: Delta; state: PendingActionData }> {
  const currentTime = now();

  const initialState: PendingActionData = {
    action_type: action.action_type,
    target_entity_id: action.entity_id,
    payload: {
      label: action.label,
      priority: action.priority,
    },
    status: 'PENDING',
    created_at: currentTime,
    expires_at: currentTime + PENDING_ACTION_TIMEOUT_MS,
    confirmed_at: null,
  };

  return createEntity('pending_action', initialState);
}

export function buildConfirmPatch(confirmedAt: Timestamp): JsonPatch[] {
  return [
    { op: 'replace', path: '/status', value: 'CONFIRMED' },
    { op: 'replace', path: '/confirmed_at', value: confirmedAt },
  ];
}

export function buildCancelPatch(): JsonPatch[] {
  return [{ op: 'replace', path: '/status', value: 'CANCELLED' }];
}

export function buildExpirePatch(): JsonPatch[] {
  return [{ op: 'replace', path: '/status', value: 'EXPIRED' }];
}

export async function confirmPendingAction(
  pendingEntity: Entity,
  pendingState: PendingActionData,
  author: Author = 'user'
): Promise<{ entity: Entity; delta: Delta; state: PendingActionData }> {
  const patches = buildConfirmPatch(now());
  return createDelta(pendingEntity, pendingState, patches, author);
}

export async function cancelPendingAction(
  pendingEntity: Entity,
  pendingState: PendingActionData,
  author: Author = 'user'
): Promise<{ entity: Entity; delta: Delta; state: PendingActionData }> {
  const patches = buildCancelPatch();
  return createDelta(pendingEntity, pendingState, patches, author);
}

export async function expirePendingAction(
  pendingEntity: Entity,
  pendingState: PendingActionData
): Promise<{ entity: Entity; delta: Delta; state: PendingActionData }> {
  const patches = buildExpirePatch();
  return createDelta(pendingEntity, pendingState, patches, 'system');
}

// === DRAFT OPERATIONS ===

export async function createDraft(
  draftType: 'MESSAGE' | 'ASSET' | 'PLAN' | 'SYSTEM',
  templateId: string,
  params: Record<string, string>,
  targetEntityId: UUID | null,
  modeContext: Mode,
  createdBy: Author = 'system'
): Promise<{ entity: Entity; delta: Delta; state: DraftData }> {
  const initialState: DraftData = {
    draft_type: draftType,
    template_id: templateId,
    params,
    target_entity_id: targetEntityId,
    status: 'READY',
    created_by: createdBy,
    mode_context: modeContext,
  };

  return createEntity('draft', initialState);
}

export function buildDraftAppliedPatch(): JsonPatch[] {
  return [{ op: 'replace', path: '/status', value: 'APPLIED' }];
}

export async function applyDraft(
  draftEntity: Entity,
  draftState: DraftData,
  author: Author = 'user'
): Promise<{ entity: Entity; delta: Delta; state: DraftData }> {
  const patches = buildDraftAppliedPatch();
  return createDelta(draftEntity, draftState, patches, author);
}

// === DELTA-DRIVEN RE-RENDER ===

export type AffectedSection =
  | 'mode'
  | 'signals'
  | 'prepared_actions'
  | 'top_tasks'
  | 'drafts'
  | 'leverage_moves'
  | 'pending_action';

export function getAffectedSections(delta: Delta): AffectedSection[] {
  const sections: AffectedSection[] = [];

  // Determine by entity type (would need entity lookup in real impl)
  // For now, check patch paths for hints

  for (const patch of delta.patch) {
    if (patch.path.includes('mode') || patch.path.includes('signals')) {
      sections.push('mode', 'signals', 'prepared_actions', 'top_tasks', 'leverage_moves');
    }
    if (patch.path.includes('status')) {
      sections.push('prepared_actions', 'top_tasks', 'drafts', 'pending_action');
    }
    if (patch.path.includes('unread')) {
      sections.push('prepared_actions');
    }
    if (patch.path.includes('draft') || patch.path.includes('template')) {
      sections.push('drafts', 'prepared_actions');
    }
  }

  // Dedupe
  return [...new Set(sections)];
}

/**
 * Check if cockpit needs re-render based on delta.
 * Returns true if any relevant section is affected.
 */
export function shouldRerender(delta: Delta): boolean {
  return getAffectedSections(delta).length > 0;
}
