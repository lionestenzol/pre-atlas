/**
 * Delta-State Fabric — Module 2: Preparation Engine
 *
 * Deterministic background workers that PREPARE (never execute) work.
 * Outputs: Draft entities, LeverageMove selections.
 * Execution requires PendingAction confirmation gate.
 *
 * Laws:
 * - No direct changes to operational entities
 * - Idempotent by design (fingerprints prevent duplicates)
 * - Delta-driven only (no polling)
 */

import {
  UUID,
  Timestamp,
  SHA256,
  Mode,
  Priority,
  Entity,
  Delta,
  DraftData,
  DraftType,
  SystemStateData,
  ThreadData,
  TaskData,
  ProjectData,
  Author,
} from './types';
import { createEntity, now, hashState } from './delta';
import { BucketedSignals, bucketSignals, RoutingConfig } from './routing';
import {
  TEMPLATE_IDS,
  TemplateId,
  isTemplateLegalForMode,
  getThreadTriageTemplates,
  getDraftTemplates,
} from './templates';

// === CONSTANTS ===

const MAX_DRAFTS_PER_RUN = 5;
const MAX_THREAD_TRIAGE = 5;
const MAX_TASK_TRIAGE = 10;
const MAX_LEVERAGE_MOVES = 3;

// TTL by mode (milliseconds)
const DRAFT_TTL: Record<Mode, number | null> = {
  RECOVER: 24 * 60 * 60 * 1000, // 24h
  CLOSE_LOOPS: 24 * 60 * 60 * 1000, // 24h
  BUILD: 72 * 60 * 60 * 1000, // 72h
  COMPOUND: 72 * 60 * 60 * 1000, // 72h
  SCALE: null, // No expiry
};

// === PREPARATION JOB (internal tracking) ===

export type JobType =
  | 'MODE_REFRESH'
  | 'THREAD_TRIAGE'
  | 'TASK_TRIAGE'
  | 'DRAFT_GEN'
  | 'LEVERAGE_GEN';

export type JobStatus = 'RUNNING' | 'DONE' | 'FAILED' | 'SKIPPED';

export interface PreparationJob {
  job_id: UUID;
  job_type: JobType;
  triggered_by_delta_id: UUID;
  started_at: Timestamp;
  completed_at?: Timestamp;
  status: JobStatus;
  notes?: string;
}

// === FINGERPRINT CALCULATION ===

export async function calculateDraftFingerprint(
  draftType: DraftType,
  templateId: string,
  targetEntityId: UUID | null,
  modeContext: Mode,
  keyParams: Record<string, string>
): Promise<SHA256> {
  const sortedParams = Object.keys(keyParams)
    .sort()
    .reduce(
      (acc, key) => {
        acc[key] = keyParams[key];
        return acc;
      },
      {} as Record<string, string>
    );

  return hashState({
    draft_type: draftType,
    template_id: templateId,
    target_entity_id: targetEntityId,
    mode_context: modeContext,
    key_params: sortedParams,
  });
}

// === LEVERAGE MOVE TYPES ===

export interface LeverageMove {
  move_id: string;
  mode: Mode;
  title: string;
  description: string;
  trigger_conditions: Record<string, string>;
  recommended_next_actions: string[];
  fingerprint: SHA256;
}

// === LEVERAGE MOVE LUT ===

interface LeverageMoveRule {
  move_id: string;
  modes: Mode[];
  condition: (buckets: BucketedSignals, mode: Mode) => boolean;
  title: string;
  description: string;
  trigger_conditions: Record<string, string>;
  recommended_next_actions: string[];
}

const LEVERAGE_MOVE_RULES: LeverageMoveRule[] = [
  {
    move_id: 'close_to_build',
    modes: ['CLOSE_LOOPS'],
    condition: (b, m) => m === 'CLOSE_LOOPS' && b.open_loops !== 'HIGH',
    title: 'Close loops to unlock BUILD',
    description: 'Completing open tasks will transition you to BUILD mode',
    trigger_conditions: { open_loops: 'must reach HIGH (≤1)' },
    recommended_next_actions: ['Complete top 3 tasks', 'Block non-urgent tasks'],
  },
  {
    move_id: 'ship_to_compound',
    modes: ['BUILD'],
    condition: (b, m) => m === 'BUILD' && b.assets_shipped === 'LOW',
    title: 'Ship one asset to unlock COMPOUND',
    description: 'Shipping any asset will transition you to COMPOUND mode',
    trigger_conditions: { assets_shipped: 'must reach OK (≥1)' },
    recommended_next_actions: ['Finish current draft', 'Publish smallest viable asset'],
  },
  {
    move_id: 'deep_work_to_scale',
    modes: ['COMPOUND'],
    condition: (b, m) =>
      m === 'COMPOUND' &&
      (b.deep_work_blocks !== 'HIGH' || b.money_delta !== 'HIGH'),
    title: 'Deep work + revenue to unlock SCALE',
    description: 'Complete deep work blocks and hit revenue target for SCALE',
    trigger_conditions: {
      deep_work_blocks: 'must reach OK or HIGH',
      money_delta: 'must reach OK or HIGH',
    },
    recommended_next_actions: ['Schedule 2h deep work block', 'Close pending deals'],
  },
  {
    move_id: 'rest_to_close',
    modes: ['RECOVER'],
    condition: (b, m) => m === 'RECOVER' && b.sleep_hours === 'LOW',
    title: 'Rest to exit RECOVER',
    description: 'Sleep deficit is keeping you in RECOVER mode',
    trigger_conditions: { sleep_hours: 'must reach OK (≥6h)' },
    recommended_next_actions: ['Sleep 8 hours', 'No screens after 9pm'],
  },
  {
    move_id: 'maintain_scale',
    modes: ['SCALE'],
    condition: (b, m) =>
      m === 'SCALE' && (b.assets_shipped === 'LOW' || b.money_delta === 'LOW'),
    title: 'Maintain SCALE mode',
    description: 'Risk of dropping out of SCALE mode',
    trigger_conditions: {
      assets_shipped: 'keep at OK or HIGH',
      money_delta: 'keep at OK or HIGH',
    },
    recommended_next_actions: ['Delegate asset creation', 'Review revenue pipeline'],
  },
  {
    move_id: 'batch_close',
    modes: ['CLOSE_LOOPS'],
    condition: (b, m) => m === 'CLOSE_LOOPS' && b.open_loops === 'LOW',
    title: 'Batch close loops',
    description: 'You have many open loops — batch process them',
    trigger_conditions: { open_loops: 'currently LOW (≥4)' },
    recommended_next_actions: [
      'Set 25min timer',
      'Close/block/defer each loop',
      'No new intake',
    ],
  },
];

// === LEVERAGE MOVE SELECTOR (LUT only) ===

export async function selectLeverageMoves(
  mode: Mode,
  buckets: BucketedSignals
): Promise<LeverageMove[]> {
  const applicable = LEVERAGE_MOVE_RULES.filter(
    (rule) => rule.modes.includes(mode) && rule.condition(buckets, mode)
  );

  const moves: LeverageMove[] = [];

  for (const rule of applicable.slice(0, MAX_LEVERAGE_MOVES)) {
    const fingerprint = await hashState({
      move_id: rule.move_id,
      mode,
      trigger_conditions: rule.trigger_conditions,
    });

    moves.push({
      move_id: rule.move_id,
      mode,
      title: rule.title,
      description: rule.description,
      trigger_conditions: rule.trigger_conditions,
      recommended_next_actions: rule.recommended_next_actions,
      fingerprint,
    });
  }

  return moves;
}

// === MODE RELEVANCE LUT ===

interface ModeRelevanceRule {
  check: (task: TaskData, project?: ProjectData) => boolean;
  score: number;
}

const MODE_RELEVANCE_LUT: Record<Mode, ModeRelevanceRule[]> = {
  RECOVER: [
    { check: (t) => t.priority === 'LOW', score: 100 },
    { check: (t) => (t.title_template ?? '').includes('health'), score: 90 },
    { check: (t) => (t.title_template ?? '').includes('admin'), score: 80 },
    { check: (t) => t.due_at != null && t.due_at < now() + 3600000, score: 70 },
  ],
  CLOSE_LOOPS: [
    { check: (t) => t.linked_thread !== null, score: 100 },
    { check: (t) => (t.title_template ?? '').includes('reply'), score: 95 },
    { check: (t) => (t.title_template ?? '').includes('finish'), score: 90 },
    { check: (t) => (t.title_template ?? '').includes('cleanup'), score: 85 },
    { check: (t) => t.priority === 'HIGH', score: 80 },
  ],
  BUILD: [
    { check: (t) => (t.title_template ?? '').includes('CREATE'), score: 100 },
    { check: (t) => (t.title_template ?? '').includes('BUILD'), score: 95 },
    { check: (t) => (t.title_template ?? '').includes('draft'), score: 90 },
    { check: (t) => (t.title_template ?? '').includes('outline'), score: 85 },
  ],
  COMPOUND: [
    { check: (t) => (t.title_template ?? '').includes('EXTEND'), score: 100 },
    { check: (t) => (t.title_template ?? '').includes('improve'), score: 95 },
    { check: (t) => (t.title_template ?? '').includes('expand'), score: 90 },
    { check: (t) => (t.title_template ?? '').includes('leverage'), score: 85 },
  ],
  SCALE: [
    { check: (t) => (t.title_template ?? '').includes('DELEGATE'), score: 100 },
    { check: (t) => (t.title_template ?? '').includes('hire'), score: 95 },
    { check: (t) => (t.title_template ?? '').includes('systemize'), score: 90 },
    { check: (t) => (t.title_template ?? '').includes('automate'), score: 85 },
  ],
};

export function calculateModeRelevance(
  task: TaskData,
  mode: Mode,
  project?: ProjectData
): number {
  const rules = MODE_RELEVANCE_LUT[mode];
  let maxScore = 30; // Base score

  for (const rule of rules) {
    if (rule.check(task, project)) {
      maxScore = Math.max(maxScore, rule.score);
    }
  }

  return maxScore;
}

// === THREAD TRIAGE WORKER ===

export interface ThreadTriageResult {
  thread: { entity: Entity; state: ThreadData };
  suggestedTemplateId: TemplateId;
  suggestedParams: Record<string, string>;
  priority: number;
}

export function triageThreads(
  threads: Array<{ entity: Entity; state: ThreadData }>,
  mode: Mode
): ThreadTriageResult[] {
  // Filter relevant threads
  const relevant = threads.filter(
    (t) =>
      !t.entity.is_archived &&
      (t.state.unread_count > 0 ||
        t.state.priority === 'HIGH' ||
        t.state.priority === 'CRITICAL' ||
        t.state.task_flag)
  );

  // Score and sort
  const scored = relevant.map((t) => {
    let priority = 0;

    // Priority scoring
    if (t.state.priority === 'CRITICAL') priority += 100;
    else if (t.state.priority === 'HIGH') priority += 75;
    else if (t.state.priority === 'NORMAL') priority += 50;

    // Unread scoring
    priority += Math.min(t.state.unread_count * 10, 50);

    // Task flag bonus
    if (t.state.task_flag) priority += 25;

    return { thread: t, priority };
  });

  scored.sort((a, b) => b.priority - a.priority);

  // Get templates for mode
  const templates = getThreadTriageTemplates(mode);
  const primaryTemplate = templates[0] || TEMPLATE_IDS.ACK;

  // Build results (top N)
  return scored.slice(0, MAX_THREAD_TRIAGE).map((item) => {
    const suggestedParams: Record<string, string> = {};

    // Fill in default params based on template
    if (primaryTemplate === TEMPLATE_IDS.DEFER) {
      suggestedParams.window = 'tomorrow';
    } else if (primaryTemplate === TEMPLATE_IDS.CLOSE_COMMIT) {
      suggestedParams.time = 'end of day';
    } else if (primaryTemplate === TEMPLATE_IDS.RECOVER_REST) {
      suggestedParams.time = 'tomorrow morning';
    } else if (primaryTemplate === TEMPLATE_IDS.FOLLOWUP) {
      suggestedParams.topic = item.thread.state.title;
    }

    return {
      thread: item.thread,
      suggestedTemplateId: primaryTemplate,
      suggestedParams,
      priority: item.priority,
    };
  });
}

// === TASK TRIAGE WORKER ===

export interface TaskTriageResult {
  task: { entity: Entity; state: TaskData };
  modeRelevance: number;
  isOverdue: boolean;
}

export function triageTasks(
  tasks: Array<{ entity: Entity; state: TaskData }>,
  mode: Mode
): TaskTriageResult[] {
  const currentTime = now();

  const openTasks = tasks.filter(
    (t) => t.state.status === 'OPEN' && !t.entity.is_archived
  );

  const scored = openTasks.map((t) => ({
    task: t,
    modeRelevance: calculateModeRelevance(t.state, mode),
    isOverdue: t.state.due_at != null && t.state.due_at < currentTime,
  }));

  // Sort by: overdue first, then mode relevance, then priority
  scored.sort((a, b) => {
    if (a.isOverdue !== b.isOverdue) return a.isOverdue ? -1 : 1;
    if (a.modeRelevance !== b.modeRelevance)
      return b.modeRelevance - a.modeRelevance;
    const priorityOrder: Record<string, number> = { CRITICAL: 0, HIGH: 1, NORMAL: 2, LOW: 3 };
    return (
      (priorityOrder[a.task.state.priority] || 2) -
      (priorityOrder[b.task.state.priority] || 2)
    );
  });

  return scored.slice(0, MAX_TASK_TRIAGE);
}

// === DRAFT GENERATOR WORKER ===

export interface DraftCandidate {
  draftType: DraftType;
  templateId: string;
  params: Record<string, string>;
  targetEntityId: UUID | null;
  sourceEntityId: UUID | null;
  fingerprint: SHA256;
}

export async function generateDraftCandidates(
  mode: Mode,
  threadTriage: ThreadTriageResult[],
  taskTriage: TaskTriageResult[],
  existingFingerprints: Set<string>
): Promise<DraftCandidate[]> {
  const candidates: DraftCandidate[] = [];

  // A) MESSAGE drafts from thread triage
  for (const item of threadTriage) {
    if (candidates.length >= MAX_DRAFTS_PER_RUN) break;

    const fingerprint = await calculateDraftFingerprint(
      'MESSAGE',
      item.suggestedTemplateId,
      item.thread.entity.entity_id,
      mode,
      item.suggestedParams
    );

    // Skip if duplicate
    if (existingFingerprints.has(fingerprint)) continue;

    candidates.push({
      draftType: 'MESSAGE',
      templateId: item.suggestedTemplateId,
      params: item.suggestedParams,
      targetEntityId: item.thread.entity.entity_id,
      sourceEntityId: null,
      fingerprint,
    });
  }

  // B) PLAN drafts from task triage (batch close plan)
  if (mode === 'CLOSE_LOOPS' && taskTriage.length >= 3) {
    const topTasks = taskTriage.slice(0, 3);
    const planParams = {
      count: String(topTasks.length),
      tasks: topTasks.map((t) => t.task.state.title_template).join(', '),
    };

    const fingerprint = await calculateDraftFingerprint(
      'PLAN',
      'BATCH_CLOSE_PLAN',
      null,
      mode,
      planParams
    );

    if (!existingFingerprints.has(fingerprint) && candidates.length < MAX_DRAFTS_PER_RUN) {
      candidates.push({
        draftType: 'PLAN',
        templateId: 'BATCH_CLOSE_PLAN',
        params: planParams,
        targetEntityId: null,
        sourceEntityId: topTasks[0].task.entity.entity_id,
        fingerprint,
      });
    }
  }

  // C) ASSET drafts (BUILD/COMPOUND only)
  if (mode === 'BUILD' || mode === 'COMPOUND') {
    const assetTemplates = getDraftTemplates(mode, 'ASSET');

    if (assetTemplates.length > 0 && candidates.length < MAX_DRAFTS_PER_RUN) {
      const templateId = assetTemplates[0];
      const params: Record<string, string> = {};

      if (templateId === TEMPLATE_IDS.BUILD_OUTLINE) {
        params.asset = 'New Asset';
      } else if (templateId === TEMPLATE_IDS.COMPOUND_EXTEND) {
        params.asset = 'Existing Asset';
        params.addition = 'enhancement';
      }

      const fingerprint = await calculateDraftFingerprint(
        'ASSET',
        templateId,
        null,
        mode,
        params
      );

      if (!existingFingerprints.has(fingerprint)) {
        candidates.push({
          draftType: 'ASSET',
          templateId,
          params,
          targetEntityId: null,
          sourceEntityId: null,
          fingerprint,
        });
      }
    }
  }

  // D) SYSTEM drafts (SCALE only)
  if (mode === 'SCALE') {
    const systemTemplates = getDraftTemplates(mode, 'SYSTEM');

    if (systemTemplates.length > 0 && candidates.length < MAX_DRAFTS_PER_RUN) {
      const templateId = systemTemplates[0];
      const params: Record<string, string> = {};

      if (templateId === TEMPLATE_IDS.SCALE_SYSTEMIZE) {
        params.process = 'workflow';
      } else if (templateId === TEMPLATE_IDS.SCALE_DELEGATE) {
        params.task = 'task';
      }

      const fingerprint = await calculateDraftFingerprint(
        'SYSTEM',
        templateId,
        null,
        mode,
        params
      );

      if (!existingFingerprints.has(fingerprint)) {
        candidates.push({
          draftType: 'SYSTEM',
          templateId,
          params,
          targetEntityId: null,
          sourceEntityId: null,
          fingerprint,
        });
      }
    }
  }

  return candidates;
}

// === DRAFT CREATION ===

export async function createDraftFromCandidate(
  candidate: DraftCandidate,
  mode: Mode,
  createdBy: Author = 'system'
): Promise<{ entity: Entity; delta: Delta; state: DraftData }> {
  const currentTime = now();
  const ttl = DRAFT_TTL[mode];

  const initialState: DraftData = {
    draft_type: candidate.draftType,
    template_id: candidate.templateId,
    params: candidate.params,
    target_entity_id: candidate.targetEntityId,
    source_entity_id: candidate.sourceEntityId,
    fingerprint: candidate.fingerprint,
    status: 'READY',
    created_by: createdBy,
    mode_context: mode,
    created_at: currentTime,
    expires_at: ttl ? currentTime + ttl : null,
  };

  return createEntity('draft', initialState);
}

// === PREPARATION ENGINE ORCHESTRATOR ===

export interface PreparationContext {
  systemState: { entity: Entity; state: SystemStateData };
  threads: Array<{ entity: Entity; state: ThreadData }>;
  tasks: Array<{ entity: Entity; state: TaskData }>;
  existingDrafts: Array<{ entity: Entity; state: DraftData }>;
  triggeredByDeltaId: UUID;
  config?: RoutingConfig;
}

export interface PreparationResult {
  newDrafts: Array<{ entity: Entity; delta: Delta; state: DraftData }>;
  leverageMoves: LeverageMove[];
  threadTriage: ThreadTriageResult[];
  taskTriage: TaskTriageResult[];
  jobs: PreparationJob[];
}

let jobCounter = 0;

function createJobId(): UUID {
  return `job-${++jobCounter}-${now()}`;
}

export async function runPreparationEngine(
  ctx: PreparationContext
): Promise<PreparationResult> {
  const jobs: PreparationJob[] = [];
  const mode = ctx.systemState.state.mode;
  const buckets = bucketSignals(ctx.systemState.state.signals, ctx.config);

  // Job 1: Thread Triage
  const threadTriageJob: PreparationJob = {
    job_id: createJobId(),
    job_type: 'THREAD_TRIAGE',
    triggered_by_delta_id: ctx.triggeredByDeltaId,
    started_at: now(),
    status: 'RUNNING',
  };
  jobs.push(threadTriageJob);

  const threadTriage = triageThreads(ctx.threads, mode);
  threadTriageJob.completed_at = now();
  threadTriageJob.status = 'DONE';
  threadTriageJob.notes = `Triaged ${threadTriage.length} threads`;

  // Job 2: Task Triage
  const taskTriageJob: PreparationJob = {
    job_id: createJobId(),
    job_type: 'TASK_TRIAGE',
    triggered_by_delta_id: ctx.triggeredByDeltaId,
    started_at: now(),
    status: 'RUNNING',
  };
  jobs.push(taskTriageJob);

  const taskTriage = triageTasks(ctx.tasks, mode);
  taskTriageJob.completed_at = now();
  taskTriageJob.status = 'DONE';
  taskTriageJob.notes = `Triaged ${taskTriage.length} tasks`;

  // Job 3: Draft Generation
  const draftGenJob: PreparationJob = {
    job_id: createJobId(),
    job_type: 'DRAFT_GEN',
    triggered_by_delta_id: ctx.triggeredByDeltaId,
    started_at: now(),
    status: 'RUNNING',
  };
  jobs.push(draftGenJob);

  // Get existing fingerprints to prevent duplicates
  const existingFingerprints: Set<string> = new Set(
    ctx.existingDrafts
      .filter((d) => d.state.status === 'READY' || d.state.status === 'QUEUED')
      .map((d) => d.state.fingerprint)
      .filter((f): f is string => f !== undefined)
  );

  const candidates = await generateDraftCandidates(
    mode,
    threadTriage,
    taskTriage,
    existingFingerprints
  );

  const newDrafts: Array<{ entity: Entity; delta: Delta; state: DraftData }> = [];

  for (const candidate of candidates) {
    const draft = await createDraftFromCandidate(candidate, mode, 'system');
    newDrafts.push(draft);
  }

  draftGenJob.completed_at = now();
  draftGenJob.status = 'DONE';
  draftGenJob.notes = `Generated ${newDrafts.length} drafts`;

  // Job 4: Leverage Move Selection
  const leverageJob: PreparationJob = {
    job_id: createJobId(),
    job_type: 'LEVERAGE_GEN',
    triggered_by_delta_id: ctx.triggeredByDeltaId,
    started_at: now(),
    status: 'RUNNING',
  };
  jobs.push(leverageJob);

  const leverageMoves = await selectLeverageMoves(mode, buckets);
  leverageJob.completed_at = now();
  leverageJob.status = 'DONE';
  leverageJob.notes = `Selected ${leverageMoves.length} moves`;

  return {
    newDrafts,
    leverageMoves,
    threadTriage,
    taskTriage,
    jobs,
  };
}

// === DELTA-DRIVEN TRIGGER ===

export function shouldTriggerPreparation(delta: Delta): boolean {
  // Trigger on system state changes
  for (const patch of delta.patch) {
    if (patch.path.includes('mode') || patch.path.includes('signals')) {
      return true;
    }
  }

  // Trigger on new messages/tasks/threads
  for (const patch of delta.patch) {
    if (
      patch.path.includes('unread') ||
      patch.path.includes('status') ||
      patch.path.includes('priority')
    ) {
      return true;
    }
  }

  return false;
}

// === DRAFT CLEANUP (expired drafts) ===

export function getExpiredDrafts(
  drafts: Array<{ entity: Entity; state: DraftData }>,
  currentTime: Timestamp
): Array<{ entity: Entity; state: DraftData }> {
  return drafts.filter(
    (d) =>
      d.state.status === 'READY' &&
      d.state.expires_at != null &&
      d.state.expires_at < currentTime
  );
}
